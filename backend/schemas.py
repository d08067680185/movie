from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class ResourceLinkOut(BaseModel):
    id: int
    link_type: str
    url: str
    quality: Optional[str]
    size: Optional[str]
    format: Optional[str]
    subtitle: Optional[str]
    episode_info: Optional[str]
    password: Optional[str]
    source_name: Optional[str] = None

    class Config:
        from_attributes = True


class ResourceCardOut(BaseModel):
    id: int
    title: str
    title_en: Optional[str]
    year: Optional[int]
    category: Optional[str]
    genre: Optional[str]
    rating: Optional[float]
    poster_url: Optional[str]
    link_count: int = 0
    view_count: int = 0

    class Config:
        from_attributes = True


class ResourceDetailOut(BaseModel):
    id: int
    title: str
    title_en: Optional[str]
    original_title: Optional[str]
    year: Optional[int]
    category: Optional[str]
    genre: Optional[str]
    country: Optional[str]
    language: Optional[str]
    duration: Optional[int]
    rating: Optional[float]
    rating_count: Optional[int]
    synopsis: Optional[str]
    poster_url: Optional[str]
    backdrop_url: Optional[str]
    directors: Optional[List[str]]
    actors: Optional[List[str]]
    view_count: int
    links: List[ResourceLinkOut] = []
    tags: List[str] = []

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ResourceCardOut]


class SourceOut(BaseModel):
    id: int
    name: str
    base_url: Optional[str]
    is_active: bool
    last_crawled: Optional[datetime]
    total_resources: int

    class Config:
        from_attributes = True


class SpiderLogOut(BaseModel):
    id: int
    source_id: Optional[int]
    status: str
    new_resources: int
    updated_resources: int
    error_msg: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class ResourceCreate(BaseModel):
    title: str
    title_en: Optional[str] = None
    year: Optional[int] = None
    category: Optional[str] = None
    genre: Optional[str] = None
    country: Optional[str] = None
    synopsis: Optional[str] = None
    poster_url: Optional[str] = None
    rating: Optional[float] = None
    directors: Optional[List[str]] = None
    actors: Optional[List[str]] = None


class LinkCreate(BaseModel):
    resource_id: int
    source_id: int
    url: str
    link_type: str
    quality: Optional[str] = None
    size: Optional[str] = None
    format: Optional[str] = None
    subtitle: Optional[str] = None
    episode_info: Optional[str] = None
    password: Optional[str] = None


class HotSearch(BaseModel):
    keyword: str
    count: int


class StatsOut(BaseModel):
    total_resources: int
    total_links: int
    total_sources: int
    categories: dict


class BatchLinkIn(BaseModel):
    url: str
    link_type: str          # pan_quark / pan_baidu / pan_aliyun / magnet / direct
    quality: Optional[str] = None
    episode_info: Optional[str] = None
    password: Optional[str] = None


class BatchResourceIn(BaseModel):
    title: str
    year: Optional[int] = None
    category: str = "动漫"
    genre: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None   # 更新中 / 已完结 / 停更
    synopsis: Optional[str] = None
    poster_url: Optional[str] = None
    rating: Optional[float] = None
    links: List[BatchLinkIn] = []


class BatchImportResult(BaseModel):
    created: int
    updated: int
    links_added: int
    skipped: int
    errors: List[str] = []
