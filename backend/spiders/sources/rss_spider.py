"""
RSS 爬虫 — 从 RSS/Atom feed 聚合影视资源
配置示例: {"feed_url": "https://example.com/feed.xml"}
"""
import re
import logging
from typing import List
from xml.etree import ElementTree as ET
from spiders.base import BaseSpider, ResourceItem

logger = logging.getLogger(__name__)

QUALITY_PATTERNS = [
    (r'4K|2160[Pp]', '4K'),
    (r'1080[Pp]', '1080P'),
    (r'720[Pp]', '720P'),
    (r'480[Pp]', '480P'),
]

LINK_TYPE_PATTERNS = [
    (r'^magnet:', 'magnet'),
    (r'pan\.baidu\.com', 'pan_baidu'),
    (r'aliyundrive\.com|alipan\.com', 'pan_aliyun'),
    (r'pan\.quark\.cn', 'pan_quark'),
    (r'^https?://', 'page'),
]


def detect_quality(text: str) -> str:
    for pattern, quality in QUALITY_PATTERNS:
        if re.search(pattern, text, re.I):
            return quality
    return None


def detect_link_type(url: str) -> str:
    for pattern, ltype in LINK_TYPE_PATTERNS:
        if re.search(pattern, url, re.I):
            return ltype
    return 'page'


class RSSSpider(BaseSpider):
    name = "rss"

    async def crawl(self, page: int = 1) -> List[ResourceItem]:
        feed_url = self.config.get("feed_url")
        if not feed_url or page > 1:
            return []

        try:
            resp = await self.get(feed_url)
            root = ET.fromstring(resp.text)
        except Exception as e:
            logger.error(f"RSS parse error: {e}")
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = []

        # 支持 RSS 2.0 和 Atom
        entries = root.findall(".//item") or root.findall(".//atom:entry", ns)

        for entry in entries:
            title = (
                entry.findtext("title") or
                entry.findtext("atom:title", namespaces=ns) or ""
            ).strip()

            description = (
                entry.findtext("description") or
                entry.findtext("atom:summary", namespaces=ns) or ""
            ).strip()

            link = (
                entry.findtext("link") or
                entry.findtext("atom:link", namespaces=ns) or ""
            ).strip()

            if not title:
                continue

            # 尝试从标题提取年份
            year_match = re.search(r'\b(19|20)\d{2}\b', title)
            year = int(year_match.group()) if year_match else None

            item = ResourceItem(title=title, year=year, synopsis=description[:500] if description else None)

            if link:
                item.add_link(
                    url=link,
                    link_type=detect_link_type(link),
                    quality=detect_quality(title + " " + description),
                )

            # 从描述中提取额外链接
            for url in re.findall(r'(magnet:\?[^\s<>"]+|https?://[^\s<>"]+)', description):
                if url != link:
                    item.add_link(
                        url=url,
                        link_type=detect_link_type(url),
                        quality=detect_quality(description),
                    )

            items.append(item)

        return items
