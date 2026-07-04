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

        # 旧库补字段：resource_links.last_checked_at（链接检测追踪用）
        cols = (await conn.execute(text("PRAGMA table_info(resource_links)"))).all()
        if not any(c[1] == "last_checked_at" for c in cols):
            await conn.execute(text("ALTER TABLE resource_links ADD COLUMN last_checked_at DATETIME"))

        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_rl_last_checked ON resource_links (last_checked_at)",
            "CREATE INDEX IF NOT EXISTS idx_rl_resource_id ON resource_links (resource_id)",
            "CREATE INDEX IF NOT EXISTS idx_rl_source_id ON resource_links (source_id)",
            "CREATE INDEX IF NOT EXISTS idx_rl_is_valid ON resource_links (is_valid)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_rl_resource_url ON resource_links (resource_id, url)",
            "CREATE INDEX IF NOT EXISTS idx_r_category_rating ON resources (category, rating DESC)",
            "CREATE INDEX IF NOT EXISTS idx_r_year ON resources (year DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sl_count ON search_logs (count DESC)",
        ]:
            await conn.execute(text(sql))
        # 统一历史分类值
        await conn.execute(text(
            "UPDATE resources SET category = '经典资源' WHERE category IN ('综艺', '资源')"
        ))

        # FTS5(trigram) 全文索引：加速标题/演职员/简介关键词搜索，避免全表 ilike 扫描
        # 注意：不用 content='resources' 外部内容表 —— aiosqlite 异步执行 FTS5 的
        # rebuild/delete 特殊管理命令时行数看似正常但索引不会真正生效（已验证），
        # 改为独立存储的 FTS5 表，全部用普通 INSERT/DELETE 维护，规避该问题。
        await conn.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS resources_fts USING fts5("
            "title, title_en, original_title, directors, actors, synopsis, "
            "tokenize='trigram')"
        ))
        await conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS resources_ai AFTER INSERT ON resources BEGIN "
            "INSERT INTO resources_fts(rowid, title, title_en, original_title, directors, actors, synopsis) "
            "VALUES (new.id, new.title, new.title_en, new.original_title, new.directors, new.actors, new.synopsis); "
            "END"
        ))
        await conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS resources_ad AFTER DELETE ON resources BEGIN "
            "DELETE FROM resources_fts WHERE rowid = old.id; "
            "END"
        ))
        await conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS resources_au AFTER UPDATE ON resources BEGIN "
            "DELETE FROM resources_fts WHERE rowid = old.id; "
            "INSERT INTO resources_fts(rowid, title, title_en, original_title, directors, actors, synopsis) "
            "VALUES (new.id, new.title, new.title_en, new.original_title, new.directors, new.actors, new.synopsis); "
            "END"
        ))
        # 索引行数与主表不一致时（首次启用/历史数据未回填，或曾用旧方案写坏）重建一次
        fts_count = (await conn.execute(text("SELECT COUNT(*) FROM resources_fts"))).scalar()
        res_count = (await conn.execute(text("SELECT COUNT(*) FROM resources"))).scalar()
        if fts_count != res_count:
            await conn.execute(text("DELETE FROM resources_fts"))
            await conn.execute(text(
                "INSERT INTO resources_fts(rowid, title, title_en, original_title, directors, actors, synopsis) "
                "SELECT id, title, title_en, original_title, directors, actors, synopsis FROM resources"
            ))
