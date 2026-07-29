"""网盘账号管理 + 批量转存接口。全部挂在 X-Admin-Token 之后——
转存会消耗自己网盘账号的配额且触碰到账号凭证，不做成公开匿名接口，
入口就是管理员在后台手动选中"全网搜"结果发起转存。
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.admin import verify_admin
from database import get_db
from models import PanAccount, PanTransferSettings, TransferTask
from pan_transfer.registry import ADAPTER_REGISTRY
from pan_transfer.worker import add_pan_account, enqueue_transfer, is_pan_transfer_enabled, refresh_quota

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/pan", tags=["pan_transfer"])


def _account_out(a: PanAccount) -> dict:
    return {
        "id": a.id,
        "netdisk_type": a.netdisk_type,
        "alias": a.alias,
        "capacity_used_gb": a.capacity_used_gb,
        "capacity_total_gb": a.capacity_total_gb,
        "status": a.status,
        "last_used_at": a.last_used_at,
        "created_at": a.created_at,
    }


@router.get("/accounts")
async def list_accounts(db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    rows = (await db.execute(select(PanAccount).order_by(PanAccount.created_at.desc()))).scalars().all()
    return [_account_out(a) for a in rows]


@router.post("/accounts")
async def create_account(payload: dict, _=Depends(verify_admin)):
    netdisk_type = payload.get("netdisk_type")
    alias = (payload.get("alias") or "").strip()
    credential = payload.get("credential")  # 明文 cookie/token，仅在此次请求体内出现，落库前立即加密
    if netdisk_type not in ADAPTER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"不支持的网盘类型，目前支持: {list(ADAPTER_REGISTRY)}")
    if not alias or not credential:
        raise HTTPException(status_code=400, detail="alias 和 credential 不能为空")
    account_id = await add_pan_account(netdisk_type, alias, credential)
    return {"id": account_id}


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    account = await db.get(PanAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    await db.delete(account)
    await db.commit()
    return {"ok": True}


@router.post("/accounts/{account_id}/quota")
async def check_account_quota(account_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    account = await db.get(PanAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    try:
        await refresh_quota(account_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"查询配额失败: {e}")
    await db.refresh(account)
    return _account_out(account)


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    return {"enabled": await is_pan_transfer_enabled(db)}


@router.patch("/settings")
async def update_settings(payload: dict, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="enabled 必须是布尔值")
    row = await db.get(PanTransferSettings, 1)
    if not row:
        row = PanTransferSettings(id=1, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
    await db.commit()
    return {"enabled": enabled}


def _pick_account_id(rows: list[PanAccount], netdisk_type: str) -> Optional[int]:
    candidates = [a for a in rows if a.netdisk_type == netdisk_type and a.status == "active"]
    return candidates[0].id if candidates else None


@router.post("/transfer")
async def submit_transfer(payload: dict, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    """body: {items: [{title, url, password, netdisk_type}], pan_account_id?: int}
    items 即"全网搜"(livesearch)返回的条目原样传入；不传 pan_account_id 则按 netdisk_type 自动挑一个可用账号。
    """
    if not await is_pan_transfer_enabled(db):
        raise HTTPException(status_code=403, detail="网盘转存功能已关闭")

    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="items 不能为空")
    forced_account_id = payload.get("pan_account_id")

    accounts = (await db.execute(select(PanAccount).where(PanAccount.status == "active"))).scalars().all()
    accounts_by_id = {a.id: a for a in accounts}

    created, skipped = [], []
    for item in items:
        netdisk_type = item.get("netdisk_type") or item.get("source")
        url = item.get("url")
        if netdisk_type not in ADAPTER_REGISTRY or not url:
            skipped.append({"item": item, "reason": "网盘类型不支持或缺少链接"})
            continue

        account_id = forced_account_id if forced_account_id in accounts_by_id else _pick_account_id(accounts, netdisk_type)
        if not account_id:
            skipped.append({"item": item, "reason": f"没有可用的 {netdisk_type} 网盘账号"})
            continue

        task_id = await enqueue_transfer(
            netdisk_type=netdisk_type,
            source_url=url,
            source_password=item.get("password"),
            pan_account_id=account_id,
            source_title=item.get("title"),
        )
        created.append(task_id)

    return {"created_task_ids": created, "skipped": skipped}


@router.get("/transfer")
async def list_transfers(status: Optional[str] = None, limit: int = 50, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    stmt = select(TransferTask).order_by(TransferTask.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(TransferTask.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": t.id,
            "netdisk_type": t.netdisk_type,
            "source_title": t.source_title,
            "source_url": t.source_url,
            "status": t.status,
            "saved_share_url": t.saved_share_url,
            "saved_share_password": t.saved_share_password,
            "error_msg": t.error_msg,
            "retry_count": t.retry_count,
            "created_at": t.created_at,
            "completed_at": t.completed_at,
        }
        for t in rows
    ]


@router.get("/transfer/{task_id}")
async def get_transfer(task_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    task = await db.get(TransferTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": task.id,
        "netdisk_type": task.netdisk_type,
        "status": task.status,
        "saved_share_url": task.saved_share_url,
        "saved_share_password": task.saved_share_password,
        "error_msg": task.error_msg,
        "retry_count": task.retry_count,
    }
