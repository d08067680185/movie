import httpx
import pytest
from httpx import ASGITransport

from models import PanAccount, PanTransferSettings, ResourceLink, Resource, Source, TransferTask
from pan_transfer.base import QuotaExceededError, RiskControlError, ShareInvalidError, TransferError
from pan_transfer.crypto import decrypt_credential, encrypt_credential
from pan_transfer.worker import _process_one, add_pan_account, enqueue_transfer, is_pan_transfer_enabled, run_pending_transfers
import pan_transfer.worker as worker_module
from config import settings

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _reset_pan_transfer_enabled(db_session):
    """种子行默认 enabled=True；每个测试前重置一次，避免某个测试关了开关影响其它测试。"""
    row = await db_session.get(PanTransferSettings, 1)
    row.enabled = True
    await db_session.commit()
    yield


class FakeAdapter:
    """按 outcome 决定 transfer() 的行为，用于驱动 worker 状态机的各个分支。"""

    def __init__(self, outcome="success"):
        self.outcome = outcome
        self.calls = 0

    async def transfer(self, credential, share_url, password):
        self.calls += 1
        if self.outcome == "success":
            return "fake-file-id"
        if self.outcome == "share_invalid":
            raise ShareInvalidError("分享已失效")
        if self.outcome == "quota":
            raise QuotaExceededError("容量不足")
        if self.outcome == "risk":
            raise RiskControlError("风控限制")
        if self.outcome == "transient_then_success":
            if self.calls == 1:
                raise TransferError("网络抖动")
            return "fake-file-id"
        raise TransferError("未知错误")

    async def create_share(self, credential, file_id):
        return "https://pan.quark.cn/s/newshare", "ab12"

    async def check_quota(self, credential):
        return 12.5, 100.0


def _patch_adapter(monkeypatch, adapter):
    monkeypatch.setattr(worker_module, "get_adapter", lambda netdisk_type: adapter)


async def test_credential_roundtrip():
    assert decrypt_credential(encrypt_credential("cookie=abc123")) == "cookie=abc123"


async def test_add_pan_account_encrypts_credential(db_session):
    account_id = await add_pan_account("quark", "test-account", "raw-cookie-value")
    row = await db_session.get(PanAccount, account_id)
    assert row.credential != "raw-cookie-value"
    assert decrypt_credential(row.credential) == "raw-cookie-value"
    assert row.status == "active"


async def test_enqueue_transfer_creates_pending_task(db_session):
    account_id = await add_pan_account("quark", "acc", "cookie")
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password="1234", pan_account_id=account_id, source_title="标题",
    )
    task = await db_session.get(TransferTask, task_id)
    assert task.status == "pending"
    assert task.source_password == "1234"


async def test_process_one_success_updates_task_and_account(db_session, monkeypatch):
    account_id = await add_pan_account("quark", "acc", "cookie")
    _patch_adapter(monkeypatch, FakeAdapter("success"))
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password=None, pan_account_id=account_id,
    )
    await _process_one(task_id)

    task = await db_session.get(TransferTask, task_id)
    assert task.status == "success"
    assert task.saved_share_url == "https://pan.quark.cn/s/newshare"
    assert task.saved_share_password == "ab12"
    assert task.completed_at is not None

    account = await db_session.get(PanAccount, account_id)
    assert account.last_used_at is not None


async def test_process_one_success_writes_back_resource_link(db_session, monkeypatch):
    source = Source(name="s", spider_class="demo")
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    resource = Resource(title="标题", category="电影")
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)
    link = ResourceLink(resource_id=resource.id, source_id=source.id, url="https://old", link_type="pan_quark", is_valid=False)
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)

    account_id = await add_pan_account("quark", "acc", "cookie")
    _patch_adapter(monkeypatch, FakeAdapter("success"))
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password=None, pan_account_id=account_id, resource_link_id=link.id,
    )
    await _process_one(task_id)

    await db_session.refresh(link)
    assert link.url == "https://pan.quark.cn/s/newshare"
    assert link.password == "ab12"
    assert link.is_valid is True


async def test_process_one_share_invalid_marks_failed(db_session, monkeypatch):
    account_id = await add_pan_account("quark", "acc", "cookie")
    _patch_adapter(monkeypatch, FakeAdapter("share_invalid"))
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/dead",
        source_password=None, pan_account_id=account_id,
    )
    await _process_one(task_id)
    task = await db_session.get(TransferTask, task_id)
    assert task.status == "failed"
    assert "失效" in task.error_msg


async def test_process_one_quota_exceeded(db_session, monkeypatch):
    account_id = await add_pan_account("quark", "acc", "cookie")
    _patch_adapter(monkeypatch, FakeAdapter("quota"))
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password=None, pan_account_id=account_id,
    )
    await _process_one(task_id)
    task = await db_session.get(TransferTask, task_id)
    assert task.status == "quota_exceeded"


async def test_process_one_risk_control_disables_account(db_session, monkeypatch):
    account_id = await add_pan_account("quark", "acc", "cookie")
    _patch_adapter(monkeypatch, FakeAdapter("risk"))
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password=None, pan_account_id=account_id,
    )
    await _process_one(task_id)
    task = await db_session.get(TransferTask, task_id)
    assert task.status == "risk_blocked"
    account = await db_session.get(PanAccount, account_id)
    assert account.status == "risk_limited"


async def test_process_one_transient_error_retries_then_succeeds(db_session, monkeypatch):
    account_id = await add_pan_account("quark", "acc", "cookie")
    adapter = FakeAdapter("transient_then_success")
    _patch_adapter(monkeypatch, adapter)
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password=None, pan_account_id=account_id,
    )
    task = await db_session.get(TransferTask, task_id)
    await _process_one(task_id)
    await db_session.refresh(task)
    assert task.status == "pending"
    assert task.retry_count == 1

    await _process_one(task_id)
    await db_session.refresh(task)
    assert task.status == "success"


async def test_process_one_gives_up_after_max_retries(db_session, monkeypatch):
    account_id = await add_pan_account("quark", "acc", "cookie")
    _patch_adapter(monkeypatch, FakeAdapter("generic_fail"))
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password=None, pan_account_id=account_id,
    )
    for _ in range(settings.PAN_TRANSFER_MAX_RETRY + 1):
        await _process_one(task_id)

    task = await db_session.get(TransferTask, task_id)
    assert task.status == "failed"
    assert task.retry_count == settings.PAN_TRANSFER_MAX_RETRY + 1


async def test_process_one_skips_inactive_account(db_session, monkeypatch):
    account_id = await add_pan_account("quark", "acc", "cookie")
    account = await db_session.get(PanAccount, account_id)
    account.status = "risk_limited"
    await db_session.commit()

    called = {"n": 0}

    class ShouldNotBeCalledAdapter(FakeAdapter):
        async def transfer(self, *a, **kw):
            called["n"] += 1
            return await super().transfer(*a, **kw)

    _patch_adapter(monkeypatch, ShouldNotBeCalledAdapter("success"))
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password=None, pan_account_id=account_id,
    )
    await _process_one(task_id)
    task = await db_session.get(TransferTask, task_id)
    assert task.status == "failed"
    assert called["n"] == 0


async def test_run_pending_transfers_processes_multiple_accounts(db_session, monkeypatch):
    monkeypatch.setattr(settings, "PAN_TRANSFER_INTERVAL_SECONDS", 0)
    acc1 = await add_pan_account("quark", "acc1", "cookie1")
    acc2 = await add_pan_account("quark", "acc2", "cookie2")
    _patch_adapter(monkeypatch, FakeAdapter("success"))

    t1 = await enqueue_transfer(netdisk_type="quark", source_url="https://pan.quark.cn/s/a", source_password=None, pan_account_id=acc1)
    t2 = await enqueue_transfer(netdisk_type="quark", source_url="https://pan.quark.cn/s/b", source_password=None, pan_account_id=acc2)

    await run_pending_transfers()

    task1 = await db_session.get(TransferTask, t1)
    task2 = await db_session.get(TransferTask, t2)
    assert task1.status == "success"
    assert task2.status == "success"


async def test_run_pending_transfers_skips_when_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "PAN_TRANSFER_INTERVAL_SECONDS", 0)
    settings_row = await db_session.get(PanTransferSettings, 1)
    settings_row.enabled = False
    await db_session.commit()

    account_id = await add_pan_account("quark", "acc", "cookie")
    _patch_adapter(monkeypatch, FakeAdapter("success"))
    task_id = await enqueue_transfer(
        netdisk_type="quark", source_url="https://pan.quark.cn/s/abc",
        source_password=None, pan_account_id=account_id,
    )

    await run_pending_transfers()

    task = await db_session.get(TransferTask, task_id)
    assert task.status == "pending"


async def test_is_pan_transfer_enabled_reflects_flag(db_session):
    assert await is_pan_transfer_enabled(db_session) is True
    row = await db_session.get(PanTransferSettings, 1)
    row.enabled = False
    await db_session.commit()
    assert await is_pan_transfer_enabled(db_session) is False


def _client():
    from main import app
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _admin_headers(monkeypatch) -> dict:
    from auth import hash_password
    token = "test-admin-token-for-pan-transfer-tests"
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", hash_password(token))
    return {"X-Admin-Token": token}


async def test_submit_transfer_rejected_when_disabled(db_session, monkeypatch):
    row = await db_session.get(PanTransferSettings, 1)
    row.enabled = False
    await db_session.commit()
    headers = _admin_headers(monkeypatch)

    async with _client() as client:
        resp = await client.post(
            "/api/admin/pan/transfer",
            json={"items": [{"netdisk_type": "quark", "url": "https://pan.quark.cn/s/x", "title": "t"}]},
            headers=headers,
        )
    assert resp.status_code == 403


async def test_settings_endpoints_get_and_patch(db_session, monkeypatch):
    headers = _admin_headers(monkeypatch)
    async with _client() as client:
        resp = await client.get("/api/admin/pan/settings", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True}

        resp = await client.patch("/api/admin/pan/settings", json={"enabled": False}, headers=headers)
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False}

        resp = await client.get("/api/admin/pan/settings", headers=headers)
        assert resp.json() == {"enabled": False}
