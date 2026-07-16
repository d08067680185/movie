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
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import SearchLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["livesearch"])

# 展示顺序即优先级；不在此表的类型（magnet/ed2k等）不返回
CLOUD_TYPES = ["quark", "baidu", "aliyun", "uc", "xunlei", "115", "123", "tianyi", "mobile", "pikpak"]

_URL_RE = re.compile(r"https?://\S+")

_cache: dict = {}          # keyword -> (ts, payload)
_CACHE_TTL = 300.0
_CACHE_MAX = 200
_lock = asyncio.Lock()

# 进程内调用统计（单worker部署；多worker需换Redis，缓存同理）
_stats = {"requests": 0, "cache_hits": 0, "upstream_errors": 0}


def _clean_url(raw: str) -> Optional[str]:
    """pansou 的 url 字段偶尔混入换行+标签文字，只保留第一个 URL 本体"""
    m = _URL_RE.search(raw or "")
    if not m:
        return None
    return m.group(0).rstrip(").,;\"'>】」）")


def _normalize(data: dict) -> dict:
    merged = data.get("merged_by_type") or {}
    by_type: dict = {}
    total = 0
    for ctype in CLOUD_TYPES:
        seen = set()
        items = []
        for it in merged.get(ctype) or []:
            url = _clean_url(it.get("url", ""))
            if not url or url in seen:
                continue
            seen.add(url)
            # 插件源的 note 可能带 <span> 高亮标签，先去 HTML 再压空白
            note = re.sub(r"<[^>]+>", "", it.get("note") or "")
            note = re.sub(r"\s+", " ", note).strip()
            password = (it.get("password") or "").strip().rstrip("#")
            items.append({
                "title": note or url,
                "url": url,
                "password": password,
                "datetime": it.get("datetime"),
                "source": it.get("source") or "",
            })
            if len(items) >= 100:
                break
        if items:
            by_type[ctype] = items
            total += len(items)
    return {"total": total, "by_type": by_type}


async def _fetch_pansou(keyword: str, refresh: bool) -> dict:
    params = {"kw": keyword, "res": "merge"}
    if refresh:
        params["refresh"] = "true"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{settings.PANSOU_URL}/api/search", params=params)
        resp.raise_for_status()
        body = resp.json()
    if body.get("code") not in (0, None):
        raise HTTPException(status_code=502, detail=f"pansou error: {body.get('message')}")
    return _normalize(body.get("data") or body)


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
    return {"pansou": pansou, "cache_entries": len(_cache), **_stats}


@router.get("/livesearch")
async def livesearch(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词"),
    cloud_type: Optional[str] = Query(None, max_length=20, description="按网盘类型过滤"),
    refresh: bool = Query(False, description="绕过缓存强制刷新"),
    db: AsyncSession = Depends(get_db),
):
    keyword = q.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    _stats["requests"] += 1
    now = time.time()
    cached = _cache.get(keyword)
    if cached and not refresh and (now - cached[0]) < _CACHE_TTL:
        _stats["cache_hits"] += 1
        payload = cached[1]
    else:
        try:
            payload = await _fetch_pansou(keyword, refresh)
        except httpx.HTTPError as e:
            _stats["upstream_errors"] += 1
            logger.warning("pansou 请求失败: %s", e)
            raise HTTPException(status_code=502, detail="全网搜服务暂时不可用，请稍后重试")
        async with _lock:
            if len(_cache) >= _CACHE_MAX:
                oldest = min(_cache, key=lambda k: _cache[k][0])
                _cache.pop(oldest, None)
            _cache[keyword] = (now, payload)

        # 记入搜索热词（与本地搜共用 SearchLog）
        try:
            ins = sqlite_insert(SearchLog).values(keyword=keyword, count=1)
            ins = ins.on_conflict_do_update(
                index_elements=["keyword"],
                set_={"count": SearchLog.count + 1, "last_searched": func.now()},
            )
            await db.execute(ins)
            await db.commit()
        except Exception:
            pass

    by_type = payload["by_type"]
    types = [{"type": t, "count": len(items)} for t, items in by_type.items()]
    if cloud_type:
        by_type = {cloud_type: by_type.get(cloud_type, [])}
    total = sum(len(v) for v in by_type.values())
    return {"total": total, "types": types, "by_type": by_type}
