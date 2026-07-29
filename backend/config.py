from pydantic_settings import BaseSettings
from typing import Optional


CATEGORY_MAP: dict[str, str] = {
    "movie": "电影",
    "tv": "电视剧",
    "anime": "动漫",
    "variety": "经典资源",
}

# 板块种子数据的唯一权威定义（database.py 建表时据此写入 sections 表，
# api/sections.py 直接查表返回，此处仅供其它模块引用 key 时保持一致，不再重复硬编码）
SECTION_KEYS = ["video", "software", "ebook", "music", "game"]


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./movie_search.db"
    TMDB_API_KEY: Optional[str] = None
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE: str = "https://image.tmdb.org/t/p"
    SECRET_KEY: str = "your-secret-key-change-in-prod"
    ADMIN_PASSWORD: Optional[str] = "admin123"  # 明文兜底，仅在无 ADMIN_PASSWORD_HASH 时使用，首次启动会自动迁移为哈希
    ADMIN_PASSWORD_HASH: Optional[str] = None
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    SPIDER_INTERVAL_HOURS: int = 6
    MAX_PAGES_PER_SOURCE: int = 10
    LINK_CHECK_INTERVAL_HOURS: int = 2
    LINK_CHECK_BATCH_SIZE: int = 300
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    PANSOU_URL: str = "http://localhost:8888"

    # 视频下载(yt-dlp)
    DOWNLOAD_DIR: str = "./downloads"
    DOWNLOAD_MAX_CONCURRENT_GLOBAL: int = 5
    DOWNLOAD_MAX_CONCURRENT_PER_IP: int = 2
    DOWNLOAD_MAX_SIZE_GB: float = 8.0
    DOWNLOAD_RETENTION_HOURS: int = 12
    DOWNLOAD_QUOTA_GB: float = 30.0

    # 网盘转存(pan_transfer)
    PAN_CREDENTIAL_ENC_KEY: Optional[str] = None  # Fernet key，加密存储网盘账号cookie/token；未配置时启动报错
    PAN_TRANSFER_INTERVAL_SECONDS: int = 30  # 同一网盘账号两次转存操作的最小间隔，人为限速规避风控
    PAN_TRANSFER_MAX_RETRY: int = 2
    PAN_TRANSFER_POLL_SECONDS: int = 60  # APScheduler 拉取 pending 任务的轮询间隔

    class Config:
        env_file = ".env"


settings = Settings()
