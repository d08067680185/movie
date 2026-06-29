"""
网盘链接搜索爬虫
对数据库中无下载链接的影视资源，通过 Bing 搜索寻找夸克/百度网盘公开分享链接。

原理: Bing 搜索 "{片名} {年份} 夸克网盘" / "{片名} 百度网盘" → 从结果页提取链接

配置示例:
{
  "delay": 3.0,          // 请求间隔秒数（建议 ≥ 2，避免被封）
  "max_per_run": 20,     // 每次运行处理的资源数上限
  "min_links": 0,        // 跳过已有 N 条以上链接的资源（0=只处理无链接的）
  "pan_types": ["quark", "baidu"],  // 目标网盘类型
  "search_lang": "zh-CN"
}

注意:
- Bing 搜索结果依赖公开网页内容，不保证命中率
- 网盘链接时效性有限，过期链接需要手动标记无效
- 建议 delay ≥ 3，避免触发 Bing 的反爬
"""
import re
import asyncio
import logging
from typing import List, Dict
from bs4 import BeautifulSoup
from spiders.base import BaseSpider, ResourceItem

logger = logging.getLogger(__name__)

# 各网盘的 URL 模式和元数据
PAN_PATTERNS: Dict[str, Dict] = {
    "quark": {
        "pattern": r"https?://pan\.quark\.cn/s/[A-Za-z0-9]+",
        "link_type": "pan_quark",
        "name": "夸克网盘",
    },
    "baidu": {
        "pattern": r"https?://pan\.baidu\.com/s/[A-Za-z0-9_\-]+",
        "link_type": "pan_baidu",
        "name": "百度网盘",
    },
    "aliyun": {
        "pattern": r"https?://(?:www\.aliyundrive\.com|www\.alipan\.com)/s/[A-Za-z0-9]+",
        "link_type": "pan_aliyun",
        "name": "阿里云盘",
    },
}

# Bing 提取码模式 (百度常见: 提取码: xxxx 或 密码: xxxx)
PASSWORD_PATTERN = re.compile(
    r"(?:提取码|密码|访问码|password)[：:]\s*([A-Za-z0-9]{4})",
    re.IGNORECASE,
)

QUALITY_PATTERNS = [
    (re.compile(r'4[Kk]|2160[Pp]'), '4K'),
    (re.compile(r'1080[Pp]'),        '1080P'),
    (re.compile(r'720[Pp]'),         '720P'),
    (re.compile(r'480[Pp]'),         '480P'),
]

def detect_quality(text: str) -> str:
    for pat, q in QUALITY_PATTERNS:
        if pat.search(text):
            return q
    return None


class PanSearchSpider(BaseSpider):
    """
    此爬虫不走 crawl(page) 接口，由 run_pan_search 单独调度，
    crawl() 返回空列表保持接口兼容。
    """
    name = "pan_search"
    base_url = "https://www.bing.com"

    async def crawl(self, page: int = 1) -> List[ResourceItem]:
        # 不支持标准 crawl 模式
        return []

    async def _bing_search(self, query: str) -> List[Dict]:
        """搜索 Bing 并返回提取到的网盘链接列表"""
        pan_types = self.config.get("pan_types", ["quark", "baidu"])
        patterns  = {k: v for k, v in PAN_PATTERNS.items() if k in pan_types}

        url = "https://www.bing.com/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": self.config.get("search_lang", "zh-CN,zh;q=0.9"),
            "Accept": "text/html,application/xhtml+xml",
        }
        try:
            resp = await self.client.get(url, params={"q": query, "setlang": "zh-CN"}, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Bing search failed for '{query}': {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        full_text = resp.text

        found = []
        seen_urls = set()

        for pan_key, meta in patterns.items():
            for m in re.finditer(meta["pattern"], full_text):
                url_match = m.group()
                if url_match in seen_urls:
                    continue
                seen_urls.add(url_match)

                # 在匹配位置前后100字符内寻找提取码
                start = max(0, m.start() - 200)
                ctx   = full_text[start: m.end() + 200]
                pw_m  = PASSWORD_PATTERN.search(ctx)
                quality = detect_quality(ctx)

                found.append({
                    "url": url_match,
                    "link_type": meta["link_type"],
                    "quality": quality,
                    "password": pw_m.group(1) if pw_m else None,
                    "source": "bing_search",
                })

        return found

    async def search_for_resource(self, title: str, year: int = None) -> List[Dict]:
        """为单部影片搜索夸克/百度网盘链接"""
        pan_types = self.config.get("pan_types", ["quark", "baidu"])
        delay     = float(self.config.get("delay", 3.0))

        year_str  = str(year) if year else ""
        pan_keywords = {
            "quark": "夸克网盘",
            "baidu": "百度网盘",
            "aliyun": "阿里云盘",
        }
        queries = [
            f"{title} {year_str} {pan_keywords[t]}".strip()
            for t in pan_types if t in pan_keywords
        ]

        all_links = []
        seen = set()
        for q in queries:
            links = await self._bing_search(q)
            for lk in links:
                if lk["url"] not in seen:
                    seen.add(lk["url"])
                    all_links.append(lk)
            await asyncio.sleep(delay)

        return all_links


async def run_pan_search(source_id: int, config: dict):
    """
    独立调度函数：对数据库中无下载链接的影视资源批量搜索网盘链接并写入。
    由 api/admin.py 的触发接口调用。
    """
    from database import AsyncSessionLocal
    from models import Resource, ResourceLink, Source, SpiderLog
    from sqlalchemy import select, func, update
    from datetime import datetime

    max_per_run = int(config.get("max_per_run", 20))
    min_links   = int(config.get("min_links", 0))

    async with AsyncSessionLocal() as db:
        # 找出链接数 <= min_links 的资源
        subq = (
            select(ResourceLink.resource_id, func.count(ResourceLink.id).label("cnt"))
            .group_by(ResourceLink.resource_id)
            .subquery()
        )
        stmt = (
            select(Resource)
            .outerjoin(subq, Resource.id == subq.c.resource_id)
            .where(
                (subq.c.cnt == None) | (subq.c.cnt <= min_links)
            )
            .order_by(Resource.rating.desc().nulls_last())
            .limit(max_per_run)
        )
        resources = (await db.execute(stmt)).scalars().all()

        source = await db.get(Source, source_id)
        if not source:
            return

        log = SpiderLog(source_id=source_id, status="running")
        db.add(log)
        await db.commit()
        await db.refresh(log)

    new_link_count = 0

    async with PanSearchSpider(config) as spider:
        for res in resources:
            logger.info(f"[PanSearch] 搜索: {res.title} ({res.year})")
            links = await spider.search_for_resource(res.title, res.year)

            if not links:
                continue

            async with AsyncSessionLocal() as db:
                for lk in links:
                    existing = (await db.execute(
                        select(ResourceLink).where(
                            ResourceLink.resource_id == res.id,
                            ResourceLink.url == lk["url"],
                        )
                    )).scalar_one_or_none()
                    if existing is None:
                        db.add(ResourceLink(
                            resource_id=res.id,
                            source_id=source_id,
                            url=lk["url"],
                            link_type=lk["link_type"],
                            quality=lk.get("quality"),
                            password=lk.get("password"),
                            is_valid=True,
                        ))
                        new_link_count += 1
                await db.commit()

            logger.info(f"[PanSearch] {res.title}: +{len(links)} 条链接")

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(SpiderLog).where(SpiderLog.id == log.id).values(
                status="success",
                new_resources=new_link_count,
                finished_at=datetime.utcnow(),
            )
        )
        await db.commit()

    logger.info(f"[PanSearch] 完成，共写入 {new_link_count} 条网盘链接")
