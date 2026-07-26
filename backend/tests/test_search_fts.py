import pytest
import httpx
from httpx import ASGITransport
from sqlalchemy import text

from api.search import build_fts_query, build_prefix_glob
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


def test_build_prefix_glob_appends_wildcard_and_casefolds():
    assert build_prefix_glob("Iron") == "iron*"


def test_build_prefix_glob_escapes_special_chars():
    # * ? [ ] 是 GLOB 元字符，用户输入里如果真包含要转义成字符类，
    # 不然会被当成通配符而不是字面量搜索
    assert build_prefix_glob("a*b") == "a[*]b*"
    assert build_prefix_glob("a?b") == "a[?]b*"
    assert build_prefix_glob("a[b") == "a[[]b*"
    assert build_prefix_glob("a]b") == "a[]]b*"


@pytest.mark.asyncio
async def test_short_keyword_matches_title_prefix_only(db_session):
    """短关键词(<3字符)前缀匹配的行为验证：搜"安"命中"安家"(开头)，
    不再命中"长安"(中间/结尾) —— 这是已跟用户确认过的取舍。"""
    from main import app

    db_session.add_all([
        Resource(title="安家", category="电视剧", year=2020),
        Resource(title="长安十二时辰", category="电视剧", year=2019),
    ])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/search", params={"q": "安"})
    assert resp.status_code == 200
    data = resp.json()
    titles = [item["title"] for item in data["items"]]
    assert "安家" in titles
    assert "长安十二时辰" not in titles


@pytest.mark.asyncio
async def test_short_keyword_matches_title_en_and_original_title_prefix(db_session):
    from main import app

    db_session.add_all([
        Resource(title="钢铁侠", title_en="Iron Man", category="电影", year=2008),
    ])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/search", params={"q": "ir"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_fts_search_ranks_title_match_above_popular_synopsis_only_match(db_session):
    """bm25 相关度验证：关键词出现在标题(短字段)里的资源，即使热度低，
    也应该排在关键词只是淹没在长简介里、但热度很高的资源前面。"""
    from main import app

    keyword = "谜之钥匙"
    db_session.add_all([
        Resource(
            title=f"{keyword}的秘密", category="电影", year=2023,
            view_count=0, synopsis="",
        ),
        Resource(
            title="毫不相关的另一部电影", category="电影", year=2023,
            view_count=999999,
            synopsis="这是一段很长的简介文字，中间某处不起眼地提到了" + keyword + "但只是背景细节，" * 5,
        ),
    ])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/search", params={"q": keyword})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["items"][0]["title"] == f"{keyword}的秘密"
