"""
Bangumi (bgm.tv) 动漫信息补全爬虫
免费、无需 API Key，专门收录动漫，国漫覆盖率高。

用途：对数据库中缺少封面/评分/简介的动漫资源，通过 Bangumi 搜索补全元数据。
"""
import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

BGM_API = "https://api.bgm.tv"
BGM_IMG = "https://lain.bgm.tv"

HEADERS = {
    "User-Agent": "movie-search/1.0 (https://github.com/local)",
    "Accept": "application/json",
}

# 清理标题：去掉季数、括号年份、集数说明、合集标签等
CLEAN_PATTERNS = [
    (re.compile(r'\s*[\(（]\d{4}[\)）]'), ''),            # (2023)
    (re.compile(r'\s*（[^）]*）'), ''),                    # 全角括号内容
    (re.compile(r'\s*第[一二三四五六七八九十百\d]+季'), ''), # 第X季
    (re.compile(r'\s*Season\s*\d+', re.I), ''),           # Season 2
    (re.compile(r'\s+S\d+$', re.I), ''),                  # S2
    (re.compile(r'\s*[\(（][^)）]*[\)）]'), ''),           # 剩余括号
    # 合集/多季/集数范围 —— 从尾部清理
    (re.compile(r'\s*\d+[-~]\d+季全?$'), ''),             # 1-3季
    (re.compile(r'\s*\d+[-~]\d+合集$'), ''),              # 1-2合集
    (re.compile(r'\s*\d+部合集$'), ''),                   # 3部合集
    (re.compile(r'\s*全\d+集.*$'), ''),                   # 全104集(1986)
    (re.compile(r'\s*(合集|全集|年番|特别篇|剧场版|全系列|剧场)\s*$'), ''),
    (re.compile(r'\s*(含第一季|含.{1,4}季)\s*$'), ''),   # 含第一季
    (re.compile(r'\s*\d+集.*$'), ''),                     # 82部
    (re.compile(r'\s*BLACK\s*.*$'), ''),                  # 工作细胞 BLACK...
    (re.compile(r'\s*·.*$'), ''),                         # 凹凸世界·新生
    (re.compile(r'\s+[A-Z][a-zA-Z\s\-:!]+$'), ''),       # 尾部英文副标题
]

def clean_title(title: str) -> str:
    t = title.strip()
    # 若标题含日文假名，优先提取日文部分作为搜索词
    jp_match = re.search(r'[぀-ヿ][^a-zA-Z\(\（]{3,}', t)
    if jp_match:
        jp_part = jp_match.group(0).strip()
        # 去掉日文部分前后的标点
        jp_part = re.sub(r'[!！\-–—～\s]+$', '', jp_part)
        if len(jp_part) >= 3:
            return jp_part
    # 否则逐步清理中文标题
    for pat, repl in CLEAN_PATTERNS:
        t = pat.sub(repl, t)
        t = t.strip()
    # 去掉结尾标点
    t = re.sub(r'[\s\.\-·。，、…]+$', '', t).strip()
    return t or title.strip()


def _extra_queries(title: str) -> list:
    """从合集/多季标题提取更多候选搜索词"""
    extras = []
    # "我独自升级 1-2季" → "我独自升级"
    m = re.match(r'^(.+?)\s+\d+[-~]\d+季', title)
    if m:
        extras.append(m.group(1).strip())
    # "魔法科高校的劣等生（1-3季+剧场版+特别篇）" → "魔法科高校的劣等生"
    m = re.match(r'^(.+?)[\(（]', title)
    if m:
        extras.append(m.group(1).strip())
    # 空格分割取前半（去掉英/日副标题）
    parts = title.split()
    if len(parts) > 1:
        # 取直到第一个全英文或全假名词前的部分
        cn_parts = []
        for p in parts:
            if re.search(r'[a-zA-Z]{4,}', p) or re.search(r'[぀-ヿ]{3,}', p):
                break
            cn_parts.append(p)
        if cn_parts and len(' '.join(cn_parts)) >= 2:
            extras.append(' '.join(cn_parts))
    return extras


async def search_bangumi(client, title: str) -> Optional[dict]:
    """搜索 Bangumi，返回最匹配的动漫条目"""
    clean = clean_title(title)
    queries = list(dict.fromkeys([clean] + _extra_queries(title) + [title]))

    for q in queries:
        if not q or len(q) < 2:
            continue
        try:
            resp = await client.get(
                f"{BGM_API}/search/subject/{q}",
                params={"type": 2, "responseGroup": "small", "max_results": 8},
                headers=HEADERS,
                timeout=8,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            results = data.get("list") or []
            if not results:
                continue

            # 优先精确匹配中文名
            for item in results:
                name_cn = item.get("name_cn") or ""
                name = item.get("name") or ""
                if (clean and (clean in name_cn or name_cn in clean)) or \
                   (clean and (clean in name or name in clean)):
                    return item

            # 返回第一个结果
            return results[0]
        except Exception as e:
            logger.debug(f"Bangumi search '{q}': {e}")
            await asyncio.sleep(0.5)

    return None


async def get_bangumi_detail(client, subject_id: int) -> Optional[dict]:
    """获取动漫详情（含完整图片、评分、简介）"""
    try:
        resp = await client.get(
            f"{BGM_API}/subject/{subject_id}",
            params={"responseGroup": "large"},
            headers=HEADERS,
            timeout=8,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"Bangumi detail {subject_id}: {e}")
    return None


def extract_meta(detail: dict) -> dict:
    """从 Bangumi 详情提取有用字段"""
    images = detail.get("images") or {}
    poster = (
        images.get("large") or images.get("common") or
        images.get("medium") or images.get("small") or ""
    )
    # bgm.tv 图片需要加协议头
    if poster and poster.startswith("//"):
        poster = "https:" + poster
    elif poster and poster.startswith("http://"):
        poster = "https:" + poster[5:]

    rating = detail.get("rating") or {}
    score = rating.get("score")

    # 年份从 air_date 取
    year = None
    air_date = detail.get("air_date") or ""
    m = re.match(r"(\d{4})", air_date)
    if m:
        year = int(m.group(1))

    synopsis = (detail.get("summary") or "").strip()
    if len(synopsis) > 500:
        synopsis = synopsis[:500] + "..."

    return {
        "poster_url": poster or None,
        "rating": float(score) if score else None,
        "year": year,
        "synopsis": synopsis or None,
        "bgm_id": detail.get("id"),
    }


async def run_bangumi_enrich(config: dict):
    """
    批量补全：对缺少封面的动漫资源通过 Bangumi 搜索并写入元数据。
    config:
      max_per_run: int  每次处理数量 (default 50)
      delay: float      请求间隔秒 (default 1.0)
      overwrite: bool   是否覆盖已有封面 (default False)
    """
    import httpx
    from database import AsyncSessionLocal
    from models import Resource, SpiderLog, Source
    from sqlalchemy import select, update
    from datetime import datetime
    from tasks import start_task, update_task, finish_task

    max_per_run = int(config.get("max_per_run", 50))
    delay = float(config.get("delay", 1.0))
    overwrite = bool(config.get("overwrite", False))
    source_id = config.get("source_id")

    async with AsyncSessionLocal() as db:
        stmt = select(Resource).where(Resource.category == "动漫")
        if not overwrite:
            stmt = stmt.where(
                (Resource.poster_url == None) | (Resource.poster_url == "")
            )
        stmt = stmt.order_by(Resource.id).limit(max_per_run)
        resources = (await db.execute(stmt)).scalars().all()

        log = SpiderLog(source_id=source_id, status="running")
        db.add(log)
        await db.commit()
        await db.refresh(log)

    start_task("bangumi_enrich", "Bangumi 动漫补全", total=len(resources))
    enriched = 0
    failed = 0

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for idx, res in enumerate(resources):
            logger.info(f"[Bangumi] 搜索: {res.title}")
            try:
                item = await search_bangumi(client, res.title)
                if not item:
                    logger.info(f"[Bangumi] 未找到: {res.title}")
                    failed += 1
                    await asyncio.sleep(delay)
                    update_task("bangumi_enrich", done=idx+1, message=f"已处理 {idx+1}/{len(resources)}")
                    continue

                detail = await get_bangumi_detail(client, item["id"])
                if not detail:
                    failed += 1
                    await asyncio.sleep(delay)
                    update_task("bangumi_enrich", done=idx+1, message=f"已处理 {idx+1}/{len(resources)}")
                    continue

                meta = extract_meta(detail)

                async with AsyncSessionLocal() as db:
                    r = await db.get(Resource, res.id)
                    if r:
                        if meta["poster_url"] and (not r.poster_url or overwrite):
                            r.poster_url = meta["poster_url"]
                        if meta["rating"] and not r.rating:
                            r.rating = meta["rating"]
                        if meta["year"] and not r.year:
                            r.year = meta["year"]
                        if meta["synopsis"] and not r.synopsis:
                            r.synopsis = meta["synopsis"]
                        await db.commit()
                        enriched += 1
                        logger.info(f"[Bangumi] ✓ {res.title} → 封面:{bool(meta['poster_url'])} 评分:{meta['rating']}")

            except Exception as e:
                logger.warning(f"[Bangumi] 处理 {res.title} 出错: {e}")
                failed += 1

            update_task("bangumi_enrich", done=idx+1, message=f"已处理 {idx+1}/{len(resources)}")
            await asyncio.sleep(delay)

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(SpiderLog).where(SpiderLog.id == log.id).values(
                status="success",
                new_resources=enriched,
                error_msg=f"failed:{failed}" if failed else None,
                finished_at=datetime.utcnow(),
            )
        )
        await db.commit()

    finish_task("bangumi_enrich", status="success", message=f"补全 {enriched} 条，未找到 {failed} 条")
    logger.info(f"[Bangumi] 完成：补全 {enriched} 条，未找到 {failed} 条")
