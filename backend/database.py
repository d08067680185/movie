from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from models import Resource, Source, Tag, ResourceTag, SpiderLog, SearchLog  # noqa
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_rl_resource_id ON resource_links (resource_id)",
            "CREATE INDEX IF NOT EXISTS idx_rl_source_id ON resource_links (source_id)",
            "CREATE INDEX IF NOT EXISTS idx_rl_is_valid ON resource_links (is_valid)",
            "CREATE INDEX IF NOT EXISTS idx_r_category_rating ON resources (category, rating DESC)",
            "CREATE INDEX IF NOT EXISTS idx_r_year ON resources (year DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sl_count ON search_logs (count DESC)",
        ]:
            await conn.execute(text(sql))
        # 统一历史分类值
        await conn.execute(text(
            "UPDATE resources SET category = '经典资源' WHERE category IN ('综艺', '资源')"
        ))
