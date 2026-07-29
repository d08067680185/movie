"""转存任务队列：落库(TransferTask) + APScheduler 轮询执行，不引入 Redis/Celery
——与本项目现有 spiders/scheduler.py 一致的单进程 asyncio 模式。

限速设计：同一个 pan_account 的任务严格顺序执行、间隔至少
PAN_TRANSFER_INTERVAL_SECONDS 秒，这是对"账号被网盘风控/封禁"风险唯一的实质缓解手段
（不同账号之间可以并发）。
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal
from models import PanAccount, PanTransferSettings, ResourceLink, TransferTask
from pan_transfer.base import QuotaExceededError, RiskControlError, ShareInvalidError, TransferError
from pan_transfer.crypto import decrypt_credential, encrypt_credential
from pan_transfer.registry import get_adapter

logger = logging.getLogger(__name__)

# 每个网盘账号最近一次操作时间，用于账号内限速；仅本进程内存有效，重启后重新计时无妨
_last_used_at: dict[int, float] = {}


async def is_pan_transfer_enabled(db) -> bool:
    row = await db.get(PanTransferSettings, 1)
    return bool(row and row.enabled)


async def enqueue_transfer(
    netdisk_type: str,
    source_url: str,
    source_password: Optional[str],
    pan_account_id: int,
    source_title: Optional[str] = None,
    resource_link_id: Optional[int] = None,
) -> int:
    async with AsyncSessionLocal() as db:
        task = TransferTask(
            resource_link_id=resource_link_id,
            pan_account_id=pan_account_id,
            netdisk_type=netdisk_type,
            source_url=source_url,
            source_password=source_password,
            source_title=source_title,
            status="pending",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task.id


async def _process_one(task_id: int):
    async with AsyncSessionLocal() as db:
        task = await db.get(TransferTask, task_id)
        if not task or task.status != "pending":
            return
        account = await db.get(PanAccount, task.pan_account_id)
        if not account or account.status != "active":
            task.status = "failed"
            task.error_msg = "目标网盘账号不可用(未找到/已禁用/风控中)"
            task.completed_at = datetime.utcnow()
            await db.commit()
            return

        task.status = "running"
        task.started_at = datetime.utcnow()
        await db.commit()

        credential = decrypt_credential(account.credential)
        adapter = get_adapter(task.netdisk_type)

        try:
            file_id = await adapter.transfer(credential, task.source_url, task.source_password)
            share_url, share_password = await adapter.create_share(credential, file_id)
        except ShareInvalidError as e:
            task.status = "failed"
            task.error_msg = str(e)
        except QuotaExceededError as e:
            task.status = "quota_exceeded"
            task.error_msg = str(e)
        except RiskControlError as e:
            task.status = "risk_blocked"
            task.error_msg = str(e)
            account.status = "risk_limited"
            logger.warning("网盘账号触发风控，已停用 account_id=%s type=%s", account.id, account.netdisk_type)
        except TransferError as e:
            task.retry_count += 1
            if task.retry_count > settings.PAN_TRANSFER_MAX_RETRY:
                task.status = "failed"
                task.error_msg = f"重试{task.retry_count}次后仍失败: {e}"
            else:
                task.status = "pending"  # 留给下一轮轮询重试
                task.error_msg = str(e)
        else:
            task.status = "success"
            task.saved_share_url = share_url
            task.saved_share_password = share_password
            if task.resource_link_id:
                link = await db.get(ResourceLink, task.resource_link_id)
                if link:
                    link.url = share_url
                    link.password = share_password
                    link.is_valid = True

        task.completed_at = datetime.utcnow() if task.status != "pending" else None
        account.last_used_at = datetime.utcnow()
        await db.commit()

    _last_used_at[account.id] = asyncio.get_event_loop().time()


async def run_pending_transfers():
    """main.py 里通过 APScheduler 定期调用。按账号分组，账号内串行+限速，账号间并发。"""
    async with AsyncSessionLocal() as db:
        if not await is_pan_transfer_enabled(db):
            return
        pending = (
            await db.execute(select(TransferTask).where(TransferTask.status == "pending"))
        ).scalars().all()

    if not pending:
        return

    by_account: dict[int, list[int]] = {}
    for task in pending:
        by_account.setdefault(task.pan_account_id, []).append(task.id)

    async def run_account_queue(account_id: int, task_ids: list[int]):
        for task_id in task_ids:
            now = asyncio.get_event_loop().time()
            last = _last_used_at.get(account_id)
            if last is not None:
                wait = settings.PAN_TRANSFER_INTERVAL_SECONDS - (now - last)
                if wait > 0:
                    await asyncio.sleep(wait)
            try:
                await _process_one(task_id)
            except Exception:
                logger.exception("转存任务异常 task_id=%s", task_id)

    await asyncio.gather(*(run_account_queue(acc_id, ids) for acc_id, ids in by_account.items()))


async def add_pan_account(netdisk_type: str, alias: str, credential_plaintext: str) -> int:
    async with AsyncSessionLocal() as db:
        account = PanAccount(
            netdisk_type=netdisk_type,
            alias=alias,
            credential=encrypt_credential(credential_plaintext),
            status="active",
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account.id


async def refresh_quota(account_id: int):
    async with AsyncSessionLocal() as db:
        account = await db.get(PanAccount, account_id)
        if not account:
            return
        credential = decrypt_credential(account.credential)
        adapter = get_adapter(account.netdisk_type)
        used, total = await adapter.check_quota(credential)
        account.capacity_used_gb = used
        account.capacity_total_gb = total
        await db.commit()
