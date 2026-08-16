"""
全网搜代理：转发 PanSou 聚合搜索（TG频道+插件源），带内存TTL缓存与结果清洗。
PanSou 部署为 docker-compose 中的 pansou 服务（ghcr.io/fish2018/pansou）。
"""
import re
import time
import asyncio
import logging
from collections import Counter
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from opencc import OpenCC
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db, AsyncSessionLocal
from models import SearchLog, PansouSourceStat
from utils import send_telegram
from textnorm import normalize_keyword
from dedup import clean_key
from ratelimit import SlidingWindowLimiter, get_client_ip

# TG频道/插件源内容以简体为主，繁体输入统一转成简体再发给PanSou查询/算缓存key，
# 这样"斗羅大陸"和"斗罗大陆"能命中同一批结果+同一个缓存槽，不用维护简繁两套
_T2S = OpenCC("t2s")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["livesearch"])

# 展示顺序即优先级；magnet(磁力/BT种子)放最后——PanSou本身就有这个类型(此前
# 一直被过滤掉)，2026-08-16 起还会额外并发查 bitsearch.to(见 _fetch_bitsearch)
# 补充英文磁力资源，PanSou现有147个频道+90个插件清一色中文资源分享向，磁力这条
# 线是目前唯一覆盖到英文内容的渠道
CLOUD_TYPES = ["quark", "baidu", "aliyun", "uc", "xunlei", "115", "123", "tianyi", "mobile", "pikpak", "magnet"]

# PanSou 本身没有内容分类概念(搜的是TG分享群/插件源的原始文本)，只能靠给查询词
# 追加板块相关的限定词来做粗略加权，不是精确过滤——video 板块沿用原有行为不加限定词，
# 避免搜索结果因为新逻辑而变化
SECTION_KEYWORD_HINTS = {
    "software": "软件",
    "ebook": "电子书",
    "music": "音乐",
    "game": "游戏",
}

_URL_RE = re.compile(r"(?:https?://|magnet:\?)\S+")


def _parse_query(q: str) -> tuple[str, list[str]]:
    """解析 `-排除词` 语法。按空白切分，`-`开头(长度>1)的词归入排除词，
    其余拼回正向关键词。排除词不参与PanSou上游查询/缓存key，只在拿到结果后
    做后处理过滤——这样同一组正向词、不同排除词组合能共享同一次上游调用。"""
    include, exclude = [], []
    for tok in q.split():
        if tok.startswith("-") and len(tok) > 1:
            exclude.append(tok[1:])
        else:
            include.append(tok)
    return " ".join(include).strip(), exclude


def _apply_exclude_filter(by_type: dict, exclude_terms: list[str]) -> dict:
    norm_excludes = [normalize_keyword(t) for t in exclude_terms if t]
    if not norm_excludes:
        return by_type
    filtered = {}
    for ctype, items in by_type.items():
        kept = [it for it in items if not any(ex in normalize_keyword(it["title"]) for ex in norm_excludes)]
        if kept:
            filtered[ctype] = kept
    return filtered

_cache: dict = {}          # keyword -> (ts, payload)
_CACHE_TTL = 300.0
_CACHE_MAX = 200
# 2026-08-16: 此前硬编码100，是本项目自己加的保护性截断（PanSou /api/search本身不
# 分页也没有条数上限说明）。前端 LiveSearchResults.tsx 早就有客户端"加载更多"分页
# (visibleCount/PAGE_SIZE)，服务端多给的数据会自然分批展示，不需要跟着改前端。
# 300是"明显比100宽松"和"单进程内存缓存不被极端关键词打爆"之间的折中值。
_MAX_ITEMS_PER_TYPE = 300
_lock = asyncio.Lock()

# 来源命中率展示给终端用户（此前 pansou_source_stats 只是后台admin监控用的死频道
# 排查工具，见改动一）：内存缓存 source_key->hit_count，5分钟刷新一次，避免每次
# 搜索响应都查一遍DB（一次搜索的by_type里可能有几百条item，每条都要查命中数）
_source_hits_cache: dict[str, int] = {}
_source_hits_cache_ts = 0.0
_SOURCE_HITS_TTL = 300.0
_source_hits_lock = asyncio.Lock()


async def _get_source_hit_map() -> dict[str, int]:
    global _source_hits_cache_ts
    now = time.time()
    if _source_hits_cache and (now - _source_hits_cache_ts) < _SOURCE_HITS_TTL:
        return _source_hits_cache
    async with _source_hits_lock:
        # 双重检查：拿到锁后可能已经被另一个并发请求刷新过了
        if _source_hits_cache and (time.time() - _source_hits_cache_ts) < _SOURCE_HITS_TTL:
            return _source_hits_cache
        try:
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    select(PansouSourceStat.source_key, PansouSourceStat.hit_count)
                )).all()
            _source_hits_cache.clear()
            _source_hits_cache.update({key: count for key, count in rows})
            _source_hits_cache_ts = time.time()
        except Exception as e:
            logger.warning("加载来源命中率缓存失败: %s", e)
    return _source_hits_cache

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


# 链接有效性检测：直接代理 PanSou 自带的 POST /api/check/links（对同一批已自托管的
# PanSou 实例复用，服务端有分级缓存），覆盖 baidu/aliyun/quark/tianyi/uc/mobile/
# 115/xunlei/123 共9种网盘——比这个项目之前手写的"只测夸克+百度"覆盖广得多，
# 也不需要自己维护各家分享页私有接口的解析逻辑。每次结果列表可见量级(<=30)
_check_links_limiter = SlidingWindowLimiter(
    max_attempts=90, window_seconds=60, message="链接检测请求过于频繁，请稍后再试"
)


def rate_limit_check_links(request: Request):
    ip = get_client_ip(request)
    _check_links_limiter.check(ip)
    _check_links_limiter.record(ip)


@router.post("/livesearch/check-links")
async def check_links(
    items: list[dict] = Body(..., embed=True, description='[{"url": str, "cloud_type": str}]'),
    _rl=Depends(rate_limit_check_links),
):
    """代理 PanSou 的 /api/check/links。只保留 state 是 ok/bad 的结果映射成
    True/False——locked(需要提取码)/uncertain(检测失败)/unsupported(该网盘类型
    暂不支持检测) 都不在返回结果里出现，前端据此区分"确认有效/失效"和"不确定"。"""
    items = items[:30]
    payload_items = [
        {"disk_type": it.get("cloud_type"), "url": it.get("url")}
        for it in items
        if it.get("url") and it.get("cloud_type")
    ]
    if not payload_items:
        return {"results": {}}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.PANSOU_URL}/api/check/links",
                json={"items": payload_items},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("链接检测代理PanSou失败: %s", e)
        return {"results": {}}
    results: dict[str, bool] = {}
    for r in data.get("results") or []:
        state = r.get("state")
        if state in ("ok", "bad"):
            results[r.get("url")] = state == "ok"
    return {"results": results}


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


def _relevance_tier(title: str, norm_keyword: str, tokens: list[str]) -> int:
    """结果按与关键词的相关性分档，越小越相关。用在草筛300条硬截断*之前*的排序，
    避免真正相关的结果因为在 PanSou 原始返回顺序里靠后而被截断挡在外面。
    不引入分词/相似度库，只做子串包含判断——足够覆盖"标题里到底有没有关键词"
    这个最基本的相关性信号，比完全不排序(纯用上游原始顺序)已经是明显改善。"""
    t = normalize_keyword(title)
    if t == norm_keyword:
        return 0
    if norm_keyword in t:
        return 1
    if tokens and all(tok in t for tok in tokens):
        return 2
    return 3


def _normalize(data: dict, keyword: str) -> dict:
    merged = data.get("merged_by_type") or {}
    norm_keyword = normalize_keyword(keyword)
    tokens = [tok for tok in norm_keyword.split(" ") if tok]
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
        # 先按相关性稳定排序（同档内保持 PanSou 原始相对顺序），再截断——
        # 截断在排序之后，保留的300条才是"最相关的300条"而不是"最先返回的300条"
        items.sort(key=lambda it: _relevance_tier(it["title"], norm_keyword, tokens))
        items = items[:_MAX_ITEMS_PER_TYPE]
        if items:
            by_type[ctype] = items
            total += len(items)
    return {"total": total, "by_type": by_type}


async def _record_source_stats(by_type: dict) -> None:
    """PanSou 每条结果自带 source 字段(tg:<频道>/plugin:<插件>)，聚合计数写进
    pansou_source_stats，用于识别长期零命中的死来源。只在真正打了上游时调用
    (见 _fetch_pansou)，不在缓存命中路径重复计数，避免热门关键词把统计刷虚高。
    用独立 session（不复用请求注入的 db）——本函数可能被并发合并(_fetch_coalesced)
    的 leader 调用，此时原始请求的 db session 生命周期不可控。"""
    counts = Counter()
    for items in by_type.values():
        for it in items:
            src = it.get("source")
            if src:
                counts[src] += 1
    if not counts:
        return
    try:
        async with AsyncSessionLocal() as db:
            for source_key, n in counts.items():
                ins = sqlite_insert(PansouSourceStat).values(source_key=source_key, hit_count=n)
                ins = ins.on_conflict_do_update(
                    index_elements=["source_key"],
                    set_={"hit_count": PansouSourceStat.hit_count + n, "last_hit_at": func.now()},
                )
                await db.execute(ins)
            await db.commit()
    except Exception as e:
        # 统计失败不应该影响搜索结果返回，但静默会让"来源榜单为什么不更新"排查不出来
        logger.warning("PanSou来源统计写入失败: %s", e)


_BITSEARCH_URL = "https://bitsearch.to/api/v1/search"


async def _fetch_bitsearch(keyword: str) -> list[dict]:
    """bitsearch.to（solidtorrents.to改版后重定向到的新域名）有公开、不需要鉴权
    的JSON搜索API，是目前全网搜里唯一覆盖英文磁力/BT资源的渠道——PanSou自己的
    147个频道+90个插件清一色中文资源分享向。失败(超时/网络错误/接口变更)静默
    返回空列表，不影响主搜索流程，也不接入PanSou那套熔断/限流机制(独立小接口，
    没必要共用)。"""
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(
                _BITSEARCH_URL,
                params={"q": keyword, "category": "all", "sort": "seeders", "limit": 20},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("bitsearch.to 请求失败: %s", e)
        return []
    items = []
    for r in data.get("results") or []:
        infohash = r.get("infohash")
        title = r.get("title")
        if not infohash or not title:
            continue
        seeders = r.get("seeders", 0)
        items.append({
            "url": f"magnet:?xt=urn:btih:{infohash}&dn={quote(title)}",
            "password": "",
            "note": f"{title} (做种{seeders})",
            "datetime": r.get("updatedAt"),
            "source": "api:bitsearch",
        })
    return items


async def _fetch_pansou(keyword: str, refresh: bool) -> dict:
    async def _call_pansou():
        async with _PANSOU_CONCURRENCY:
            params = {"kw": keyword, "res": "merge"}
            if refresh:
                params["refresh"] = "true"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{settings.PANSOU_URL}/api/search", params=params)
                resp.raise_for_status()
                return resp.json()

    body, bitsearch_items = await asyncio.gather(_call_pansou(), _fetch_bitsearch(keyword))
    if body.get("code") not in (0, None):
        raise HTTPException(status_code=502, detail=f"pansou error: {body.get('message')}")
    data = body.get("data") or body
    if bitsearch_items:
        merged = dict(data.get("merged_by_type") or {})
        merged["magnet"] = (merged.get("magnet") or []) + bitsearch_items
        data = {**data, "merged_by_type": merged}
    payload = _normalize(data, keyword)
    asyncio.create_task(_record_source_stats(payload["by_type"]))
    return payload


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
    raw_q = q.strip()
    if not raw_q:
        raise HTTPException(status_code=400, detail="关键词不能为空")
    # `-排除词` 语法：排除词不参与上游查询/缓存key，只在拿到结果后做后处理过滤
    # （见 _apply_exclude_filter），这样同一组正向词、不同排除词能共享同一次上游调用
    keyword, exclude_terms = _parse_query(raw_q)
    if not keyword:
        raise HTTPException(status_code=400, detail="不能只有排除词，至少需要一个正向关键词")
    # 繁体输入统一转简体再往下走（缓存key/上游查询/热词统计全部用转换后的值），
    # 让繁体输入和对应的简体输入命中同一批结果、同一个缓存槽
    keyword = _T2S.convert(keyword)
    exclude_terms = [_T2S.convert(t) for t in exclude_terms]
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

    by_type = _apply_exclude_filter(payload["by_type"], exclude_terms)
    types = [{"type": t, "count": len(items)} for t, items in by_type.items()]
    if cloud_type:
        by_type = {cloud_type: by_type.get(cloud_type, [])}
    total = sum(len(v) for v in by_type.values())

    # 来源命中率：新建 item 字典而不是原地改，因为 by_type 在没有排除词时跟
    # _cache 里存的是同一个对象引用，原地 mutate 会污染后续请求复用的缓存数据
    hit_map = await _get_source_hit_map()
    by_type = {
        ctype: [{**it, "source_hits": hit_map.get(it["source"], 0)} for it in items]
        for ctype, items in by_type.items()
    }
    return {"total": total, "types": types, "by_type": by_type}
