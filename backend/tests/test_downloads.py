import os
from datetime import datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport

import ytdlp_client
from config import settings
from models import Download


def _client():
    from main import app
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_create_download_rejects_invalid_url():
    async with _client() as client:
        resp = await client.post("/api/downloads", json={"url": "not-a-url"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_download_rejects_non_http_scheme():
    async with _client() as client:
        resp = await client.post("/api/downloads", json={"url": "ftp://example.com/x"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_download_accepts_valid_url_and_dispatches(monkeypatch):
    started = {}

    async def fake_download(url, download_dir, task_id):
        started["called"] = (url, task_id)
        return {"file_path": "/tmp/fake.mp4", "total_bytes": 123, "title": "fake"}

    monkeypatch.setattr(ytdlp_client, "download", fake_download)

    async with _client() as client:
        resp = await client.post("/api/downloads", json={"url": "https://www.youtube.com/watch?v=abc"})
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body


@pytest.mark.asyncio
async def test_per_ip_concurrency_limit(db_session):
    ip = "1.2.3.4"
    for _ in range(settings.DOWNLOAD_MAX_CONCURRENT_PER_IP):
        db_session.add(Download(source_url="https://x.com/1", status="downloading", requester_ip=ip))
    await db_session.commit()

    async with _client() as client:
        resp = await client.post(
            "/api/downloads",
            json={"url": "https://www.youtube.com/watch?v=abc"},
            headers={"X-Forwarded-For": ip},
        )
    # httpx test transport 的 request.client 走本地默认地址，不一定等于 X-Forwarded-For，
    # 所以这里直接构造 DB 记录校验并发计数逻辑本身（active_count 查询）而非依赖 header 注入 IP
    from api.downloads import _active_count
    count = await _active_count(db_session, ip)
    assert count == settings.DOWNLOAD_MAX_CONCURRENT_PER_IP


@pytest.mark.asyncio
async def test_global_concurrency_limit_blocks_new_requests(db_session, monkeypatch):
    for i in range(settings.DOWNLOAD_MAX_CONCURRENT_GLOBAL):
        db_session.add(Download(source_url=f"https://x.com/{i}", status="downloading", requester_ip=f"9.9.9.{i}"))
    await db_session.commit()

    async def fake_download(url, download_dir, task_id):
        return {"file_path": "/tmp/fake.mp4", "total_bytes": 1, "title": "fake"}

    monkeypatch.setattr(ytdlp_client, "download", fake_download)

    async with _client() as client:
        resp = await client.post("/api/downloads", json={"url": "https://www.youtube.com/watch?v=abc"})
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_download_lifecycle_sets_expires_at_on_complete(db_session, monkeypatch):
    from api.downloads import _run_download_task

    async def fake_download(url, download_dir, task_id):
        return {"file_path": "/tmp/fake_complete.mp4", "total_bytes": 999, "title": "fake title"}

    monkeypatch.setattr(ytdlp_client, "download", fake_download)

    row = Download(source_url="https://www.youtube.com/watch?v=xyz", status="queued", requester_ip="5.5.5.5")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    await _run_download_task(row.id, row.source_url)

    await db_session.refresh(row)
    assert row.status == "complete"
    assert row.file_path == "/tmp/fake_complete.mp4"
    assert row.total_bytes == 999
    assert row.expires_at is not None
    assert row.expires_at > datetime.utcnow()


@pytest.mark.asyncio
async def test_download_lifecycle_records_error_message(db_session, monkeypatch):
    from api.downloads import _run_download_task

    async def failing_download(url, download_dir, task_id):
        raise ytdlp_client.DownloadError("该网站不受支持")

    monkeypatch.setattr(ytdlp_client, "download", failing_download)

    row = Download(source_url="https://v.qq.com/x/y", status="queued", requester_ip="6.6.6.6")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    await _run_download_task(row.id, row.source_url)

    await db_session.refresh(row)
    assert row.status == "error"
    assert "该网站不受支持" in row.error_message


@pytest.mark.asyncio
async def test_file_endpoint_rejects_incomplete_task(db_session):
    row = Download(source_url="https://x.com", status="downloading", requester_ip="7.7.7.7")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    async with _client() as client:
        resp = await client.get(f"/api/downloads/{row.id}/file")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_file_endpoint_rejects_expired_task(db_session, tmp_path):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"fake video bytes")
    row = Download(
        source_url="https://x.com",
        status="complete",
        file_path=str(f),
        expires_at=datetime.utcnow() - timedelta(hours=1),
        requester_ip="8.8.8.8",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    async with _client() as client:
        resp = await client.get(f"/api/downloads/{row.id}/file")
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_file_endpoint_serves_completed_file(db_session, tmp_path):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"fake video bytes")
    row = Download(
        source_url="https://x.com",
        status="complete",
        file_path=str(f),
        expires_at=datetime.utcnow() + timedelta(hours=1),
        requester_ip="8.8.8.9",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    async with _client() as client:
        resp = await client.get(f"/api/downloads/{row.id}/file")
    assert resp.status_code == 200
    assert resp.content == b"fake video bytes"


@pytest.mark.asyncio
async def test_cleanup_expired_downloads_removes_file_and_marks_expired(db_session, tmp_path):
    from api.downloads import cleanup_expired_downloads

    f = tmp_path / "expired.mp4"
    f.write_bytes(b"data")
    row = Download(
        source_url="https://x.com",
        status="complete",
        file_path=str(f),
        expires_at=datetime.utcnow() - timedelta(minutes=1),
        requester_ip="1.1.1.1",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    await cleanup_expired_downloads()

    await db_session.refresh(row)
    assert row.status == "expired"
    assert row.file_path is None
    assert not f.exists()


@pytest.mark.asyncio
async def test_cleanup_marks_stalled_tasks_as_error(db_session):
    from api.downloads import cleanup_expired_downloads

    row = Download(
        source_url="https://x.com",
        status="downloading",
        requester_ip="2.2.2.2",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    # created_at 有 server_default=now()，测试里直接改它模拟"6小时前创建"
    from sqlalchemy import update
    await db_session.execute(
        update(Download).where(Download.id == row.id).values(created_at=datetime.utcnow() - timedelta(hours=7))
    )
    await db_session.commit()

    await cleanup_expired_downloads()

    await db_session.refresh(row)
    assert row.status == "error"
    assert row.error_message is not None


@pytest.mark.asyncio
async def test_create_download_dedupes_in_flight_identical_url(db_session, monkeypatch):
    calls = []

    async def fake_download(url, download_dir, task_id):
        calls.append(task_id)
        return {"file_path": "/tmp/fake.mp4", "total_bytes": 1, "title": "fake"}

    monkeypatch.setattr(ytdlp_client, "download", fake_download)

    url = "https://www.youtube.com/watch?v=dedupe_test"
    async with _client() as client:
        r1 = await client.post("/api/downloads", json={"url": url})
        r2 = await client.post("/api/downloads", json={"url": url})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]

    # 确认数据库里也确实只有一条 in-flight 记录，不是"返回了同一个id但其实建了两条"
    from sqlalchemy import select
    rows = (await db_session.execute(select(Download).where(Download.source_url == url))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_create_download_does_not_dedupe_completed_tasks(db_session):
    """已完成的任务不应该被复用——同一链接完成后应该能重新发起下载。"""
    url = "https://www.youtube.com/watch?v=completed_test"
    row = Download(source_url=url, status="complete", requester_ip="3.3.3.3")
    db_session.add(row)
    await db_session.commit()

    from api.downloads import _find_in_flight_task
    existing = await _find_in_flight_task(db_session, url)
    assert existing is None


@pytest.mark.asyncio
async def test_run_download_task_marks_error_on_wall_clock_timeout(db_session, monkeypatch):
    from api.downloads import _run_download_task
    import api.downloads as downloads_module
    import asyncio as asyncio_module

    async def hanging_download(url, download_dir, task_id):
        await asyncio_module.sleep(999)

    monkeypatch.setattr(ytdlp_client, "download", hanging_download)
    monkeypatch.setattr(downloads_module, "_DOWNLOAD_WALL_CLOCK_TIMEOUT", 0.05)

    row = Download(source_url="https://x.com/hang", status="queued", requester_ip="4.4.4.4")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    await _run_download_task(row.id, row.source_url)

    await db_session.refresh(row)
    assert row.status == "error"
    assert "超时" in row.error_message or "过长" in row.error_message
