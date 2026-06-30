from pydantic_settings import BaseSettings
from typing import Optional


CATEGORY_MAP: dict[str, str] = {
    "movie": "电影",
    "tv": "电视剧",
    "anime": "动漫",
    "variety": "经典资源",
}


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./movie_search.db"
    TMDB_API_KEY: Optional[str] = None
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE: str = "https://image.tmdb.org/t/p"
    SECRET_KEY: str = "your-secret-key-change-in-prod"
    ADMIN_PASSWORD: str = "admin123"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    SPIDER_INTERVAL_HOURS: int = 6
    MAX_PAGES_PER_SOURCE: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
