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


class Section(Base):
    """板块：影视动画/软件工具/电子书文档/音乐音频/游戏 等顶层内容类型分组。"""
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False, unique=True, index=True)  # 英文slug: video/software/ebook/music/game
    name = Column(String(100), nullable=False)  # 中文展示名
    icon = Column(String(20))
    sort_order = Column(Integer, default=0)


class Category(Base):
    """板块下的分类，替代原来写死在 Resource.category 里的固定枚举。"""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)  # 中文分类值，与 Resource.category 一致
    sort_order = Column(Integer, default=0)

    section = relationship("Section")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    title_en = Column(String(500))
    original_title = Column(String(500))
    year = Column(Integer, index=True)
    category = Column(String(50), index=True)  # movie, tv, anime, variety
    section_id = Column(Integer, ForeignKey("sections.id"), index=True)
    genre = Column(String(200))
    country = Column(String(100))
    language = Column(String(100))
    duration = Column(Integer)  # minutes
    rating = Column(Float)
    rating_count = Column(Integer, default=0)
    synopsis = Column(Text)
    poster_url = Column(String(1000))
    backdrop_url = Column(String(1000))
    poster_checked_at = Column(DateTime(timezone=True))
    tmdb_id = Column(Integer, unique=True, index=True)
    douban_id = Column(String(50))
    imdb_id = Column(String(50))
    directors = Column(JSON, default=list)
    actors = Column(JSON, default=list)
    extra_data = Column(JSON, default=dict)  # 板块专属元数据(电子书作者/出版社，音乐艺术家/专辑，游戏平台/版本，软件开发商/系统要求 等)
    submitted_by = Column(Integer, nullable=True)  # 预留：未来用户提交功能接入，指向 users.id，本轮不启用
    status = Column(String(20), default="published", index=True)  # 预留：未来审核流程接入(published/pending/rejected)，本轮全部默认 published
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    links = relationship("ResourceLink", back_populates="resource", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=ResourceTag, back_populates="resources")
    section = relationship("Section")


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
    episode_number = Column(Integer)  # 结构化集数，从 episode_info 解析(如"第3集"->3)，无法解析则为空
    password = Column(String(100))
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_checked_at = Column(DateTime(timezone=True))

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


class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String(2000), nullable=False)
    title = Column(String(500))
    status = Column(String(20), nullable=False, default="queued", index=True)  # queued, downloading, complete, error, expired
    total_bytes = Column(Integer)
    downloaded_bytes = Column(Integer, default=0)
    file_path = Column(String(1000))
    error_message = Column(Text)
    requester_ip = Column(String(64), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), index=True)


class PanAccount(Base):
    """用户自有的网盘账号，凭证(cookie/token)以加密形式存储，转存时解密使用。"""
    __tablename__ = "pan_accounts"

    id = Column(Integer, primary_key=True, index=True)
    netdisk_type = Column(String(20), nullable=False, index=True)  # quark, baidu, aliyun, xunlei
    alias = Column(String(100), nullable=False)
    credential = Column(Text, nullable=False)  # Fernet 加密后的 cookie/token blob
    capacity_total_gb = Column(Float)
    capacity_used_gb = Column(Float)
    status = Column(String(20), nullable=False, default="active")  # active, risk_limited, disabled
    last_used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TransferTask(Base):
    """一条"把第三方分享链接转存到自己网盘"的任务记录。"""
    __tablename__ = "transfer_tasks"

    id = Column(Integer, primary_key=True, index=True)
    resource_link_id = Column(Integer, ForeignKey("resource_links.id"), nullable=True, index=True)
    pan_account_id = Column(Integer, ForeignKey("pan_accounts.id"), nullable=False, index=True)
    netdisk_type = Column(String(20), nullable=False)
    source_url = Column(String(2000), nullable=False)
    source_password = Column(String(100))
    source_title = Column(String(500))
    status = Column(String(20), nullable=False, default="pending", index=True)
    # pending, running, success, failed, quota_exceeded, risk_blocked
    saved_share_url = Column(String(2000))
    saved_share_password = Column(String(100))
    error_msg = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    resource_link = relationship("ResourceLink")
    pan_account = relationship("PanAccount")


class PanTransferSettings(Base):
    """网盘转存功能总开关，固定单行(id=1)。DB字段而非.env——参照 Source.is_active
    的模式，是运行时业务开关不是密钥，调度端每轮直接查库判断即可，不用管理内存缓存/重启。"""
    __tablename__ = "pan_transfer_settings"

    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PansouSourceStat(Base):
    """全网搜(PanSou)来源命中统计——source_key 格式 tg:<频道名> / plugin:<插件名>，
    与 docker-compose.yml 里 CHANNELS/ENABLED_PLUGINS 配置的条目一一对应，用于识别
    长期零命中的死来源。只在 PanSou 上游真正被调用时(缓存未命中)累加，避免热门
    关键词的缓存命中把统计刷成虚高。"""
    __tablename__ = "pansou_source_stats"

    source_key = Column(String(150), primary_key=True)
    hit_count = Column(Integer, nullable=False, default=0)
    last_hit_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DiskUsageSnapshot(Base):
    """每日一次的磁盘占用快照，供管理后台画简单的历史趋势图(容量规划用)。"""
    __tablename__ = "disk_usage_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    download_dir_gb = Column(Float)
    backups_dir_gb = Column(Float)
