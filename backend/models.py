from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, Table, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


ResourceTag = Table(
    "resource_tags",
    Base.metadata,
    Column("resource_id", Integer, ForeignKey("resources.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    title_en = Column(String(500))
    original_title = Column(String(500))
    year = Column(Integer, index=True)
    category = Column(String(50), index=True)  # movie, tv, anime, variety
    genre = Column(String(200))
    country = Column(String(100))
    language = Column(String(100))
    duration = Column(Integer)  # minutes
    rating = Column(Float)
    rating_count = Column(Integer, default=0)
    synopsis = Column(Text)
    poster_url = Column(String(1000))
    backdrop_url = Column(String(1000))
    tmdb_id = Column(Integer, unique=True, index=True)
    douban_id = Column(String(50))
    imdb_id = Column(String(50))
    directors = Column(JSON, default=list)
    actors = Column(JSON, default=list)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    links = relationship("ResourceLink", back_populates="resource", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=ResourceTag, back_populates="resources")


class ResourceLink(Base):
    __tablename__ = "resource_links"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    url = Column(String(2000), nullable=False)
    link_type = Column(String(50))  # magnet, pan_baidu, pan_aliyun, pan_quark, direct, page
    quality = Column(String(50))    # 4K, 1080P, 720P, 480P, HD, SD
    size = Column(String(50))
    format = Column(String(50))     # MKV, MP4, AVI
    subtitle = Column(String(100))  # 中字, 外挂字幕
    episode_info = Column(String(200))
    password = Column(String(100))
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    resource = relationship("Resource", back_populates="links")
    source = relationship("Source")


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    base_url = Column(String(500))
    spider_class = Column(String(100))
    is_active = Column(Boolean, default=True)
    last_crawled = Column(DateTime(timezone=True))
    total_resources = Column(Integer, default=0)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    tag_type = Column(String(50))  # genre, area, decade

    resources = relationship("Resource", secondary=ResourceTag, back_populates="tags")


class SpiderLog(Base):
    __tablename__ = "spider_logs"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    status = Column(String(50))  # running, success, failed
    new_resources = Column(Integer, default=0)
    updated_resources = Column(Integer, default=0)
    error_msg = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(200), nullable=False, index=True, unique=True)
    count = Column(Integer, default=1)
    last_searched = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
