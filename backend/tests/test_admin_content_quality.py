import httpx
import pytest
from httpx import ASGITransport

from models import Resource


def _client():
    from main import app
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _admin_headers(monkeypatch) -> dict:
    """ASGITransport 不会触发 main.py 的 lifespan(那里才会把明文密码迁移成
    ADMIN_PASSWORD_HASH)，测试里直接把哈希设进 settings，跟真实迁移流程解耦。"""
    from config import settings
    from auth import hash_password
    token = "test-admin-token-for-content-quality-tests"
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", hash_password(token))
    return {"X-Admin-Token": token}


@pytest.mark.asyncio
async def test_duplicates_fuzzy_endpoint_finds_punctuation_variants(db_session, monkeypatch):
    db_session.add_all([
        Resource(title="三体.4K.蓝光", year=2023, category="电影"),
        Resource(title="三体 高清完整版", year=2023, category="电影"),
    ])
    await db_session.commit()

    async with _client() as client:
        resp = await client.get("/api/admin/duplicates", params={"fuzzy": "true"}, headers=_admin_headers(monkeypatch))
    assert resp.status_code == 200
    groups = resp.json()
    assert len(groups) == 1
    assert groups[0]["count"] == 2


@pytest.mark.asyncio
async def test_duplicates_exact_endpoint_unaffected_by_fuzzy_param_default(db_session, monkeypatch):
    db_session.add_all([
        Resource(title="精确同名", year=2024, category="电影"),
        Resource(title="精确同名", year=2024, category="电影"),
    ])
    await db_session.commit()

    async with _client() as client:
        resp = await client.get("/api/admin/duplicates", headers=_admin_headers(monkeypatch))
    assert resp.status_code == 200
    groups = resp.json()
    assert any(g["count"] == 2 for g in groups)


@pytest.mark.asyncio
async def test_run_poster_check_clears_broken_poster_url(db_session, monkeypatch):
    from api.admin import run_poster_check

    resource = Resource(title="坏海报测试", year=2024, category="电影", poster_url="https://example.com/dead.jpg")
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)

    class FakeResp:
        status = 404
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakeSession:
        def head(self, *a, **kw): return FakeResp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    import aiohttp
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **kw: FakeSession())

    await run_poster_check(max_per_run=10)

    await db_session.refresh(resource)
    assert resource.poster_url is None
    assert resource.poster_checked_at is not None


@pytest.mark.asyncio
async def test_run_poster_check_keeps_working_poster_url(db_session, monkeypatch):
    from api.admin import run_poster_check

    resource = Resource(title="好海报测试", year=2024, category="电影", poster_url="https://example.com/ok.jpg")
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)

    class FakeResp:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakeSession:
        def head(self, *a, **kw): return FakeResp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    import aiohttp
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **kw: FakeSession())

    await run_poster_check(max_per_run=10)

    await db_session.refresh(resource)
    assert resource.poster_url == "https://example.com/ok.jpg"


@pytest.mark.asyncio
async def test_bulk_enrich_tmdb_skips_when_no_api_key(db_session, monkeypatch):
    from api.admin import run_bulk_enrich_tmdb
    from config import settings

    monkeypatch.setattr(settings, "TMDB_API_KEY", None)
    result = await run_bulk_enrich_tmdb(max_per_run=5)
    assert result == {"processed": 0, "enriched": 0}


@pytest.mark.asyncio
async def test_bulk_enrich_tmdb_applies_matched_candidate(db_session, monkeypatch):
    from api.admin import run_bulk_enrich_tmdb
    from config import settings
    import api.tmdb as tmdb_module

    monkeypatch.setattr(settings, "TMDB_API_KEY", "fake-key")

    resource = Resource(title="缺元数据的电影", year=2023, category="电影")
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)

    async def fake_search(query):
        return [{"tmdb_id": 999, "media_type": "movie", "title": query, "year": "2023"}]

    async def fake_apply(resource_obj, tmdb_id, media_type):
        resource_obj.synopsis = "已补全"
        resource_obj.poster_url = "https://image.tmdb.org/t/p/w500/fake.jpg"

    monkeypatch.setattr(tmdb_module, "search_tmdb_multi", fake_search)
    monkeypatch.setattr(tmdb_module, "apply_tmdb_data", fake_apply)

    result = await run_bulk_enrich_tmdb(max_per_run=5)
    assert result["enriched"] == 1

    await db_session.refresh(resource)
    assert resource.synopsis == "已补全"
