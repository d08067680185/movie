"""
全网搜代理：转发 PanSou 聚合搜索（TG频道+插件源），带内存TTL缓存与结果清洗。
PanSou 部署为 docker-compose 中的 pansou 服务（ghcr.io/fish2018/pansou）。
"""
import re
import time
import asyncio
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import SearchLog
from utils import send_telegram
from textnorm import normalize_keyword
from dedup import clean_key
from ratelimit import SlidingWindowLimiter, get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["livesearch"])

# 展示顺序即优先级；不在此表的类型（magnet/ed2k等）不返回
CLOUD_TYPES = ["quark", "baidu", "aliyun", "uc", "xunlei", "115", "123", "tianyi", "mobile", "pikpak"]

# PanSou 本身没有内容分类概念(搜的是TG分享群/插件源的原始文本)，只能靠给查询词
# 追加板块相关的限定词来做粗略加权，不是精确过滤——video 板块沿用原有行为不加限定词，
# 避免搜索结果因为新逻辑而变化
SECTION_KEYWORD_HINTS = {
    "software": "软件",
    "ebook": "电子书",
    "music": "音乐",
    "game": "游戏",
}

_URL_RE = re.compile(r"https?://\S+")

_cache: dict = {}          # keyword -> (ts, payload)
_CACHE_TTL = 300.0
_CACHE_MAX = 200
# 2026-08-16: 此前硬编码100，是本项目自己加的保护性截断（PanSou /api/search本身不
# 分页也没有条数上限说明）。前端 LiveSearchResults.tsx 早就有客户端"加载更多"分页
# (visibleCount/PAGE_SIZE)，服务端多给的数据会自然分批展示，不需要跟着改前端。
# 300是"明显比100宽松"和"单进程内存缓存不被极端关键词打爆"之间的折中值。
_MAX_ITEMS_PER_TYPE = 300
_lock = asyncio.Lock()

# 进程内调用统计（单worker部署；多worker需换Redis，缓存同理）
_stats = {"requests": 0, "cache_hits": 0, "upstream_errors": 0, "coalesced": 0}

# 同一 cache_key 缓存未命中时的并发请求合并：多个用户同时搜同一个新关键词，
# 只有第一个("leader")真正打 PanSou 上游，其余请求等待并复用同一个结果，
# 避免每个并发请求都各自触发一次慢上游调用（雪崩）。用完即删，不会常驻增长。
_inflight: dict = {}       # cache_key -> asyncio.Future

# pansou sidecar 只有 1.0 cpu（docker-compose.yml），单次搜索内部本身要并发查
# 上百个TG频道/插件源，已经比较吃资源；这里限制"不同关键词"同时打到上游的
# 并发数（相同关键词已被 _fetch_coalesced 收敛成一次调用，不受此信号量影响），
# 避免多人同时搜不同新词把 sidecar 拖到假死。4 是保守起始值，后续可结合
# /api/livesearch/health 的 inflight_requests/requests 观察调优
_PANSOU_CONCURRENCY = asyncio.Semaphore(4)

# /api/livesearch 缓存未命中时单次调用成本远高于 /api/search（10秒级上游调用+
# 给下游 pansou 施压），阈值比 /api/search 的 60/60s 更紧
_livesearch_limiter = SlidingWindowLimiter(
    max_attempts=30, window_seconds=60, message="全网搜请求过于频繁，请稍后再试"
)


def rate_limit_livesearch(request: Request):
    ip = get_client_ip(request)
    _livesearch_limiter.check(ip)
    _livesearch_limiter.record(ip)


async def _fetch_coalesced(cache_key: str, upstream_keyword: str, refresh: bool) -> dict:
    async with _lock:
        fut = _inflight.get(cache_key)
        is_leader = fut is None
        if is_leader:
            fut = asyncio.get_event_loop().create_future()
            _inflight[cache_key] = fut

    if not is_leader:
        _stats["coalesced"] += 1
        return await fut

    try:
        payload = await _fetch_pansou(upstream_keyword, refresh)
    except BaseException as e:  # noqa: BLE001 - propagate to all waiters, then re-raise here
        fut.set_exception(e)
        fut.exception()  # mark retrieved so asyncio doesn't log "exception never retrieved" if no one else awaited
        async with _lock:
            _inflight.pop(cache_key, None)
        raise
    fut.set_result(payload)
    async with _lock:
        _inflight.pop(cache_key, None)
    return payload

# 简单熔断：连续失败达到阈值后，短时间内直接快速失败，避免请求堆积等 PanSou 卡死
_CIRCUIT_FAIL_THRESHOLD = 3
_CIRCUIT_COOLDOWN = 30.0
_circuit_failures = 0
_circuit_open_until = 0.0


def _clean_url(raw: str) -> Optional[str]:
    """pansou 的 url 字段偶尔混入换行+标签文字，只保留第一个 URL 本体；
    末尾 # 是已知的 pansou 噪音（跟 password 字段同源），rstrip 只删字符串
    真正末尾的字符，quark/aliyun 链接里 .../s/x#/list/share 这种中间片段
    路由不受影响，不存在误伤风险"""
    m = _URL_RE.search(raw or "")
    if not m:
        return None
    return m.group(0).rstrip(").,;\"'>】」）#")


def _normalize(data: dict) -> dict:
    merged = data.get("merged_by_type") or {}
    by_type: dict = {}
    total = 0
    for ctype in CLOUD_TYPES:
        seen = set()
        seen_titles = set()
        items = []
        for it in merged.get(ctype) or []:
            url = _clean_url(it.get("url", ""))
            if not url or url in seen:
                continue
            # 插件源的 note 可能带 <span> 高亮标签，先去 HTML 再压空白
            note = re.sub(r"<[^>]+>", "", it.get("note") or "")
            note = re.sub(r"\s+", " ", note).strip()
            title = note or url
            # 同一资源被不同 TG 频道转发会产生不同 URL 但标题几乎一样，
            # 用查重脚本同款的标题归一化逻辑在同一网盘类型内额外去重
            # （不做跨类型去重：不同类型的URL域名本身就不同，不会重复）
            title_key = clean_key(title)
            if title_key and title_key in seen_titles:
                continue
            seen.add(url)
            if title_key:
                seen_titles.add(title_key)
            password = (it.get("password") or "").strip().rstrip("#")
            items.append({
                "title": title,
                "url": url,
                "password": password,
                "datetime": it.get("datetime"),
                "source": it.get("source") or "",
            })
            if len(items) >= _MAX_ITEMS_PER_TYPE:
                break
        if items:
            by_type[ctype] = items
            total += len(items)
    return {"total": total, "by_type": by_type}


async def _fetch_pansou(keyword: str, refresh: bool) -> dict:
    async with _PANSOU_CONCURRENCY:
        params = {"kw": keyword, "res": "merge"}
        if refresh:
            params["refresh"] = "true"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.PANSOU_URL}/api/search", params=params)
            resp.raise_for_status()
            body = resp.json()
    if body.get("code") not in (0, None):
        raise HTTPException(status_code=502, detail=f"pansou error: {body.get('message')}")
    return _normalize(body.get("data") or body)


def _circuit_is_open() -> bool:
    return time.time() < _circuit_open_until


def _circuit_record_failure():
    global _circuit_failures, _circuit_open_until
    _circuit_failures += 1
    if _circuit_failures >= _CIRCUIT_FAIL_THRESHOLD:
        _circuit_open_until = time.time() + _CIRCUIT_COOLDOWN
        logger.warning("pansou 连续失败 %d 次，熔断 %.0f 秒", _circuit_failures, _CIRCUIT_COOLDOWN)
        # 熔断打开时(而非每次失败)发一次告警；被熔断跳过的请求不会再次调用到这里，天然不会刷屏
        try:
            asyncio.create_task(send_telegram(
                f"⚠️ <b>全网搜(PanSou)熔断触发</b>\n连续失败 {_circuit_failures} 次，{_CIRCUIT_COOLDOWN:.0f} 秒内将快速失败"
            ))
        except RuntimeError:
            # 没有运行中的事件循环(理论上生产环境这里总在异步请求处理内被调用，不应发生)
            logger.warning("熔断告警未发送：无运行中的事件循环")


def _circuit_record_success():
    global _circuit_failures
    _circuit_failures = 0


@router.get("/livesearch/health")
async def livesearch_health():
    """全网搜依赖探活 + 调用统计（admin 监控面板用，无敏感信息）"""
    pansou = "down"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.PANSOU_URL}/api/health")
            if resp.status_code == 200:
                pansou = "up"
    except httpx.HTTPError:
        pass
    return {
        "pansou": pansou,
        "cache_entries": len(_cache),
        "inflight_requests": len(_inflight),
        "circuit_open": _circuit_is_open(),
        **_stats,
    }


@router.get("/livesearch")
async def livesearch(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词"),
    cloud_type: Optional[str] = Query(None, max_length=20, description="按网盘类型过滤"),
    section: Optional[str] = Query(None, max_length=20, description="板块 key，非video时会给查询词追加板块限定词做粗略加权"),
    refresh: bool = Query(False, description="绕过缓存强制刷新"),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit_livesearch),
):
    keyword = q.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")
    # 缓存key/热词统计用归一化后的关键词(大小写不敏感+空白折叠)，避免"三体"和
    # "三体 "(尾部空格)/大小写不同的英文标题各占一个缓存槽、热词各算一条；实际
    # 发给 PanSou 的查询串仍用用户原始输入，不影响上游搜索语义
    hint = SECTION_KEYWORD_HINTS.get(section or "")
    upstream_keyword = f"{keyword} {hint}" if hint else keyword
    # 板块不同时哪怕关键词一样，发给PanSou的查询串也不同，缓存槽必须区分，否则
    # 软件板块搜"三体"会命中影视板块缓存的结果
    cache_key = f"{section or ''}:{normalize_keyword(keyword)}"

    _stats["requests"] += 1
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and not refresh and (now - cached[0]) < _CACHE_TTL:
        _stats["cache_hits"] += 1
        payload = cached[1]
    else:
        if _circuit_is_open():
            _stats["upstream_errors"] += 1
            raise HTTPException(status_code=503, detail="全网搜服务暂时不可用，请稍后重试")
        try:
            payload = await _fetch_coalesced(cache_key, upstream_keyword, refresh)
            _circuit_record_success()
        except httpx.HTTPError as e:
            _stats["upstream_errors"] += 1
            _circuit_record_failure()
            logger.warning("pansou 请求失败: %s", e)
            raise HTTPException(status_code=502, detail="全网搜服务暂时不可用，请稍后重试")
        async with _lock:
            if len(_cache) >= _CACHE_MAX:
                oldest = min(_cache, key=lambda k: _cache[k][0])
                _cache.pop(oldest, None)
            _cache[cache_key] = (now, payload)

        # 记入搜索热词（与本地搜共用 SearchLog）——用原始大小写的 keyword 而不是
        # 归一化后的 cache_key，因为这张表的值会直接展示成热词chip文字，
        # casefold 后会让"Iron Man"变成"iron man"这种可见的展示回归
        try:
            ins = sqlite_insert(SearchLog).values(keyword=keyword, count=1)
            ins = ins.on_conflict_do_update(
                index_elements=["keyword"],
                set_={"count": SearchLog.count + 1, "last_searched": func.now()},
            )
            await db.execute(ins)
            await db.commit()
        except Exception as e:
            # 热词统计失败不应该影响本次搜索结果返回，但完全静默会让"热词为什么
            # 一直不更新"这种问题排查不出来，至少留个痕迹
            logger.warning("全网搜热词写入失败 keyword=%s: %s", keyword, e)

    by_type = payload["by_type"]
    types = [{"type": t, "count": len(items)} for t, items in by_type.items()]
    if cloud_type:
        by_type = {cloud_type: by_type.get(cloud_type, [])}
    total = sum(len(v) for v in by_type.values())
    return {"total": total, "types": types, "by_type": by_type}
