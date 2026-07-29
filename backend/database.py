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
    from models import (  # noqa
        Resource, Source, Tag, ResourceTag, SpiderLog, SearchLog, Download, DiskUsageSnapshot,
        PanAccount, TransferTask, PanTransferSettings, Section, Category,
    )
    from sqlalchemy import text
    async with engine.begin() as conn:
        # WAL 模式：读写可并发进行，大幅降低多写入者场景下的锁冲突/损坏概率
        # （默认的 rollback journal 模式下，写入时会阻塞所有读，并发写更容易冲突）
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))

        await conn.run_sync(Base.metadata.create_all)

        # 旧库补字段：resource_links.last_checked_at（链接检测追踪用）
        cols = (await conn.execute(text("PRAGMA table_info(resource_links)"))).all()
        col_names = {c[1] for c in cols}
        if "last_checked_at" not in col_names:
            await conn.execute(text("ALTER TABLE resource_links ADD COLUMN last_checked_at DATETIME"))
        if "episode_number" not in col_names:
            await conn.execute(text("ALTER TABLE resource_links ADD COLUMN episode_number INTEGER"))
            # 回填：从已有 episode_info 里解析集数/序号(如"第3集"/"资源2"->3/2)
            await conn.execute(text(
                "UPDATE resource_links SET episode_number = "
                "CAST(substr(episode_info, 2, length(episode_info) - 2) AS INTEGER) "
                "WHERE episode_info GLOB '第[0-9]*集'"
            ))
            await conn.execute(text(
                "UPDATE resource_links SET episode_number = "
                "CAST(substr(episode_info, 3) AS INTEGER) "
                "WHERE episode_info GLOB '资源[0-9]*' AND episode_number IS NULL"
            ))

        # 旧库补字段：resources.poster_checked_at（海报链接有效性检测追踪用）
        res_cols = (await conn.execute(text("PRAGMA table_info(resources)"))).all()
        res_col_names = {c[1] for c in res_cols}
        if "poster_checked_at" not in res_col_names:
            await conn.execute(text("ALTER TABLE resources ADD COLUMN poster_checked_at DATETIME"))

        # 旧库补字段：板块化改造(资源分享平台升级) —— section_id/extra_data/submitted_by/status
        if "section_id" not in res_col_names:
            await conn.execute(text("ALTER TABLE resources ADD COLUMN section_id INTEGER"))
        if "extra_data" not in res_col_names:
            await conn.execute(text("ALTER TABLE resources ADD COLUMN extra_data JSON"))
        if "submitted_by" not in res_col_names:
            await conn.execute(text("ALTER TABLE resources ADD COLUMN submitted_by INTEGER"))
        if "status" not in res_col_names:
            await conn.execute(text("ALTER TABLE resources ADD COLUMN status VARCHAR(20) DEFAULT 'published'"))
            await conn.execute(text("UPDATE resources SET status = 'published' WHERE status IS NULL"))

        # 板块种子数据：首次建表时插入5个板块 + 影视动画下沿用原有4个分类值
        section_seed = [
            ("video", "影视动画", "🎬", 0),
            ("software", "软件工具", "💻", 1),
            ("ebook", "电子书", "📚", 2),
            ("music", "音乐音频", "🎵", 3),
            ("game", "游戏", "🎮", 4),
        ]
        for key, name, icon, order in section_seed:
            await conn.execute(text(
                "INSERT INTO sections (key, name, icon, sort_order) "
                "SELECT :key, :name, :icon, :order WHERE NOT EXISTS "
                "(SELECT 1 FROM sections WHERE key = :key)"
            ), {"key": key, "name": name, "icon": icon, "order": order})

        video_section_id = (await conn.execute(
            text("SELECT id FROM sections WHERE key = 'video'")
        )).scalar()
        for name, order in [("电影", 0), ("电视剧", 1), ("动漫", 2), ("经典资源", 3)]:
            await conn.execute(text(
                "INSERT INTO categories (section_id, name, sort_order) "
                "SELECT :sid, :name, :order WHERE NOT EXISTS "
                "(SELECT 1 FROM categories WHERE section_id = :sid AND name = :name)"
            ), {"sid": video_section_id, "name": name, "order": order})

        # 存量资源全部属于影视动画板块（升级前系统只做影视，section_id 尚未回填的都归到 video）
        await conn.execute(text(
            "UPDATE resources SET section_id = :sid WHERE section_id IS NULL"
        ), {"sid": video_section_id})

        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_rl_last_checked ON resource_links (last_checked_at)",
            "CREATE INDEX IF NOT EXISTS idx_rl_resource_id ON resource_links (resource_id)",
            "CREATE INDEX IF NOT EXISTS idx_rl_source_id ON resource_links (source_id)",
            "CREATE INDEX IF NOT EXISTS idx_rl_is_valid ON resource_links (is_valid)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_rl_resource_url ON resource_links (resource_id, url)",
            "CREATE INDEX IF NOT EXISTS idx_r_category_rating ON resources (category, rating DESC)",
            "CREATE INDEX IF NOT EXISTS idx_r_year ON resources (year DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sl_count ON search_logs (count DESC)",
            # 短关键词兜底走前缀匹配(ILIKE 编译成 lower(col) LIKE lower(pattern)，
            # 普通列索引对此不生效，必须是表达式索引)
            "CREATE INDEX IF NOT EXISTS idx_r_title_lower ON resources (LOWER(title))",
            "CREATE INDEX IF NOT EXISTS idx_r_title_en_lower ON resources (LOWER(title_en))",
            "CREATE INDEX IF NOT EXISTS idx_r_original_title_lower ON resources (LOWER(original_title))",
            "CREATE INDEX IF NOT EXISTS idx_r_section_id ON resources (section_id)",
            "CREATE INDEX IF NOT EXISTS idx_categories_section ON categories (section_id)",
            "CREATE INDEX IF NOT EXISTS idx_pa_netdisk_type ON pan_accounts (netdisk_type)",
            "CREATE INDEX IF NOT EXISTS idx_tt_status ON transfer_tasks (status)",
            "CREATE INDEX IF NOT EXISTS idx_tt_pan_account ON transfer_tasks (pan_account_id)",
        ]:
            await conn.execute(text(sql))
        # 统一历史分类值
        await conn.execute(text(
            "UPDATE resources SET category = '经典资源' WHERE category IN ('综艺', '资源')"
        ))

        # 网盘转存总开关：固定单行(id=1)，默认开启保持现有行为不变
        await conn.execute(text(
            "INSERT INTO pan_transfer_settings (id, enabled) "
            "SELECT 1, 1 WHERE NOT EXISTS (SELECT 1 FROM pan_transfer_settings WHERE id = 1)"
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
