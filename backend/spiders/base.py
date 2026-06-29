import httpx
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)
ua = UserAgent()


class ResourceItem:
    """标准化爬取结果"""
    def __init__(
        self,
        title: str,
        year: Optional[int] = None,
        category: str = "movie",
        genre: Optional[str] = None,
        country: Optional[str] = None,
        rating: Optional[float] = None,
        synopsis: Optional[str] = None,
        poster_url: Optional[str] = None,
        directors: Optional[List[str]] = None,
        actors: Optional[List[str]] = None,
        links: Optional[List[Dict]] = None,
    ):
        self.title = title
        self.year = year
        self.category = category
        self.genre = genre
        self.country = country
        self.rating = rating
        self.synopsis = synopsis
        self.poster_url = poster_url
        self.directors = directors or []
        self.actors = actors or []
        self.links = links or []

    def add_link(
        self,
        url: str,
        link_type: str = "page",
        quality: str = None,
        size: str = None,
        format: str = None,
        subtitle: str = None,
        episode_info: str = None,
        password: str = None,
    ):
        self.links.append({
            "url": url,
            "link_type": link_type,
            "quality": quality,
            "size": size,
            "format": format,
            "subtitle": subtitle,
            "episode_info": episode_info,
            "password": password,
        })


class BaseSpider(ABC):
    name: str = "base"
    base_url: str = ""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.client = httpx.AsyncClient(
            headers={"User-Agent": ua.random},
            timeout=30.0,
            follow_redirects=True,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        try:
            resp = await self.client.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            logger.error(f"[{self.name}] GET {url} failed: {e}")
            raise

    @abstractmethod
    async def crawl(self, page: int = 1) -> List[ResourceItem]:
        """爬取第 page 页，返回 ResourceItem 列表"""
        pass

    async def search(self, keyword: str) -> List[ResourceItem]:
        """在源站搜索关键词（可选实现）"""
        return []
