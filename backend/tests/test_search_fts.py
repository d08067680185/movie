import pytest
import httpx
from httpx import ASGITransport
from sqlalchemy import text

from api.search import build_fts_query
from models import Resource


def test_build_fts_query_wraps_as_phrase():
    assert build_fts_query("流浪地球") == '"流浪地球"'


def test_build_fts_query_escapes_embedded_quotes():
    # 双引号需要转义为两个双引号，且整体仍被包裹在短语引号内，
    # 防止拼出 FTS5 布尔操作符（如 OR/NOT）逃逸出短语匹配
    result = build_fts_query('标题"带引号')
    assert result == '"标题""带引号"'
    # 结果里的引号数量应为偶数对（每个原始引号变两个）+ 首尾各一个
    assert result.startswith('"') and result.endswith('"')


def test_build_fts_query_does_not_let_or_operator_escape():
    malicious = 'x" OR 1=1 OR "y'
    result = build_fts_query(malicious)
    # 转义后原始输入中的引号全部变成 ""，不会在两侧产生"裸露"的短语边界
    assert result == '"x"" OR 1=1 OR ""y"'


@pytest.mark.asyncio
async def test_search_fts_matches_seeded_resource(db_session):
    r = Resource(title="流浪地球2", category="电影", year=2023)
    db_session.add(r)
    await db_session.commit()
    await db_session.refresh(r)

    from database import engine
    async with engine.begin() as conn:
        rows = (await conn.execute(
            text("SELECT rowid FROM resources_fts WHERE resources_fts MATCH :kw"),
            {"kw": build_fts_query("流浪地球")},
        )).all()
    assert any(row[0] == r.id for row in rows)


@pytest.mark.asyncio
async def test_search_endpoint_category_filter(db_session):
    from main import app

    db_session.add_all([
        Resource(title="示例电影", category="电影", year=2024),
        Resource(title="示例剧集", category="电视剧", year=2024),
    ])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/search", params={"category": "movie"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "示例电影"
