"""
测试用临时 SQLite 文件数据库。必须在导入 database/main 之前设置
DATABASE_URL，因为 database.py 在模块加载时就用 settings.DATABASE_URL 创建了引擎。
用文件而非 :memory: ，因为异步连接池可能开多个连接，:memory: 每个连接各自一个空库。
"""
import os
import tempfile
import asyncio
import pytest
import pytest_asyncio

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"
os.environ["ADMIN_PASSWORD"] = "test_admin_password"
os.environ.pop("ADMIN_PASSWORD_HASH", None)
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

from database import init_db, AsyncSessionLocal, engine  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _init_test_db():
    await init_db()
    yield
    await engine.dispose()
    os.unlink(_db_path)


@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """每个测试后清空业务表，保持用例互相独立"""
    yield
    async with AsyncSessionLocal() as session:
        from sqlalchemy import text
        for table in ["resource_links", "resources", "sources", "spider_logs", "search_logs"]:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.execute(text("DELETE FROM resources_fts"))
        await session.commit()
