import os

import httpx
import pytest
from httpx import ASGITransport

from models import Download, DiskUsageSnapshot, Resource, ResourceLink


def _client():
    from main import app
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _admin_headers(monkeypatch) -> dict:
    from config import settings
    from auth import hash_password
    token = "test-admin-token-for-operations-tests"
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", hash_password(token))
    return {"X-Admin-Token": token}


@pytest.mark.asyncio
async def test_delete_download_removes_row_and_file(db_session, monkeypatch, tmp_path):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"data")
    row = Download(source_url="https://x.com", status="complete", file_path=str(f), requester_ip="1.1.1.1")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    async with _client() as client:
        resp = await client.delete(f"/api/admin/downloads/{row.id}", headers=_admin_headers(monkeypatch))
    assert resp.status_code == 200
    assert not f.exists()

    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        assert await db.get(Download, row.id) is None


@pytest.mark.asyncio
async def test_delete_download_404_for_missing_id(monkeypatch):
    async with _client() as client:
        resp = await client.delete("/api/admin/downloads/999999", headers=_admin_headers(monkeypatch))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_download_handles_already_missing_file(db_session, monkeypatch):
    row = Download(source_url="https://x.com", status="complete", file_path="/nonexistent/path.mp4", requester_ip="1.1.1.1")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    async with _client() as client:
        resp = await client.delete(f"/api/admin/downloads/{row.id}", headers=_admin_headers(monkeypatch))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_disk_usage_history_returns_snapshots_oldest_first(db_session, monkeypatch):
    from sqlalchemy import update
    from datetime import datetime, timedelta

    s1 = DiskUsageSnapshot(download_dir_gb=1.0, backups_dir_gb=2.0)
    s2 = DiskUsageSnapshot(download_dir_gb=1.5, backups_dir_gb=2.5)
    db_session.add_all([s1, s2])
    await db_session.commit()
    await db_session.refresh(s1)
    await db_session.refresh(s2)
    await db_session.execute(update(DiskUsageSnapshot).where(DiskUsageSnapshot.id == s1.id).values(recorded_at=datetime.utcnow() - timedelta(days=1)))
    await db_session.commit()

    async with _client() as client:
        resp = await client.get("/api/admin/disk-usage-history", headers=_admin_headers(monkeypatch))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["download_dir_gb"] == 1.0  # 较早的排前面
    assert data[1]["download_dir_gb"] == 1.5


@pytest.mark.asyncio
async def test_record_disk_usage_snapshot_writes_a_row(monkeypatch, tmp_path):
    from api.admin import record_disk_usage_snapshot
    from config import settings

    monkeypatch.setattr(settings, "DOWNLOAD_DIR", str(tmp_path))
    (tmp_path / "fake.mp4").write_bytes(b"x" * 1024)

    await record_disk_usage_snapshot()

    from database import AsyncSessionLocal
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(DiskUsageSnapshot))).scalars().all()
        assert len(rows) >= 1


@pytest.mark.asyncio
async def test_bulk_delete_resources_removes_multiple(db_session, monkeypatch):
    r1 = Resource(title="批量删除测试1", category="电影")
    r2 = Resource(title="批量删除测试2", category="电影")
    db_session.add_all([r1, r2])
    await db_session.commit()
    await db_session.refresh(r1)
    await db_session.refresh(r2)

    async with _client() as client:
        resp = await client.post(
            "/api/admin/resources/bulk-delete",
            json={"ids": [r1.id, r2.id]},
            headers=_admin_headers(monkeypatch),
        )
    assert resp.status_code == 200

    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        assert await db.get(Resource, r1.id) is None
        assert await db.get(Resource, r2.id) is None


@pytest.mark.asyncio
async def test_bulk_delete_resources_rejects_empty_ids(monkeypatch):
    async with _client() as client:
        resp = await client.post(
            "/api/admin/resources/bulk-delete",
            json={"ids": []},
            headers=_admin_headers(monkeypatch),
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_merge_duplicate_group_merges_all_into_keep(db_session, monkeypatch):
    keep = Resource(title="保留的资源", category="电影")
    dup1 = Resource(title="重复1", category="电影")
    dup2 = Resource(title="重复2", category="电影")
    db_session.add_all([keep, dup1, dup2])
    await db_session.commit()
    await db_session.refresh(keep)
    await db_session.refresh(dup1)
    await db_session.refresh(dup2)

    db_session.add_all([
        ResourceLink(resource_id=dup1.id, source_id=1, url="https://x.com/1", link_type="direct"),
        ResourceLink(resource_id=dup2.id, source_id=1, url="https://x.com/2", link_type="direct"),
    ])
    await db_session.commit()

    async with _client() as client:
        resp = await client.post(
            "/api/admin/duplicates/merge-group",
            json={"keep_id": keep.id, "dup_ids": [dup1.id, dup2.id]},
            headers=_admin_headers(monkeypatch),
        )
    assert resp.status_code == 200

    from database import AsyncSessionLocal
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        assert await db.get(Resource, dup1.id) is None
        assert await db.get(Resource, dup2.id) is None
        links = (await db.execute(select(ResourceLink).where(ResourceLink.resource_id == keep.id))).scalars().all()
        assert len(links) == 2


@pytest.mark.asyncio
async def test_merge_duplicate_group_skips_keep_id_in_dup_list(db_session, monkeypatch):
    keep = Resource(title="保留的资源2", category="电影")
    db_session.add(keep)
    await db_session.commit()
    await db_session.refresh(keep)

    async with _client() as client:
        resp = await client.post(
            "/api/admin/duplicates/merge-group",
            json={"keep_id": keep.id, "dup_ids": [keep.id]},
            headers=_admin_headers(monkeypatch),
        )
    assert resp.status_code == 200
    assert "0 条" in resp.json()["message"] or "移动 0 条" in resp.json()["message"]


@pytest.mark.asyncio
async def test_live_link_reports_sorted_by_count_desc(db_session, monkeypatch):
    from models import LiveLinkReport

    db_session.add_all([
        LiveLinkReport(url_hash="h1", url="https://pan.quark.cn/s/low", report_count=1),
        LiveLinkReport(url_hash="h2", url="https://pan.quark.cn/s/high", report_count=5),
    ])
    await db_session.commit()

    async with _client() as client:
        resp = await client.get("/api/admin/live-link-reports", headers=_admin_headers(monkeypatch))
    assert resp.status_code == 200
    data = resp.json()
    assert [d["url"] for d in data] == ["https://pan.quark.cn/s/high", "https://pan.quark.cn/s/low"]
    assert data[0]["report_count"] == 5


@pytest.mark.asyncio
async def test_live_link_reports_requires_admin_token():
    async with _client() as client:
        resp = await client.get("/api/admin/live-link-reports")
    assert resp.status_code in (401, 403)
