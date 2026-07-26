"""通用视频链接下载(YouTube/腾讯视频/优酷等)：POST 创建任务 -> 轮询进度 -> 下载文件。
基于 yt-dlp(ytdlp_client.py)，公开开放但严格限流+配额，完成文件保留
DOWNLOAD_RETENTION_HOURS 小时后由 main.py 里的定时任务清理(见 cleanup_expired_downloads)。
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import ytdlp_client
from config import settings
from database import AsyncSessionLocal, get_db
from models import Download
from ratelimit import SlidingWindowLimiter, get_client_ip
from utils import send_telegram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/downloads", tags=["downloads"])

_create_limiter = SlidingWindowLimiter(
    max_attempts=5, window_seconds=60, message="下载请求过于频繁，请稍后再试"
)

# 单个下载任务的总时长硬上限；超时后调用方会尽快把状态标为 error 不再干等，
# 但注意这不保证底层线程真的停止(Python线程无法强制杀死)，只是让"整站被一个
# 卡死任务拖住等待"这件事有上限——真正防卡死靠 ytdlp_client.py 的独立线程池+socket_timeout
_DOWNLOAD_WALL_CLOCK_TIMEOUT = 1800.0

# 磁盘配额告警节流：避免高峰期每次拒绝请求都发一条 Telegram 刷屏
_QUOTA_ALERT_COOLDOWN = 600.0
_last_quota_alert_ts = 0.0


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="请提供合法的视频链接（http/https）")
    return url


async def _active_count(db: AsyncSession, requester_ip: Optional[str] = None) -> int:
    stmt = select(func.count()).select_from(Download).where(Download.status.in_(["queued", "downloading"]))
    if requester_ip is not None:
        stmt = stmt.where(Download.requester_ip == requester_ip)
    return (await db.execute(stmt)).scalar() or 0


async def _find_in_flight_task(db: AsyncSession, url: str) -> Optional[Download]:
    """同一链接已有人在下(queued/downloading)时直接复用那条任务，避免重复起
    yt-dlp 进程浪费带宽/磁盘配额。"""
    stmt = select(Download).where(Download.source_url == url, Download.status.in_(["queued", "downloading"]))
    return (await db.execute(stmt)).scalars().first()


def _alert_quota_exceeded(used_gb: float):
    global _last_quota_alert_ts
    now = time.time()
    if now - _last_quota_alert_ts < _QUOTA_ALERT_COOLDOWN:
        return
    _last_quota_alert_ts = now
    try:
        asyncio.create_task(send_telegram(
            f"⚠️ <b>下载空间已满</b>\n已用 {used_gb:.1f}GB / 配额 {settings.DOWNLOAD_QUOTA_GB}GB，新下载请求正被拒绝"
        ))
    except RuntimeError:
        logger.warning("下载空间告警未发送：无运行中的事件循环")


def _dir_size_bytes(path: str) -> int:
    total = 0
    if not os.path.isdir(path):
        return 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
    return total


async def _run_download_task(download_id: int, url: str):
    async with AsyncSessionLocal() as db:
        row = await db.get(Download, download_id)
        if not row:
            return
        row.status = "downloading"
        await db.commit()

    try:
        result = await asyncio.wait_for(
            ytdlp_client.download(url, settings.DOWNLOAD_DIR, download_id),
            timeout=_DOWNLOAD_WALL_CLOCK_TIMEOUT,
        )
    except ytdlp_client.DownloadError as e:
        async with AsyncSessionLocal() as db:
            row = await db.get(Download, download_id)
            if row:
                row.status = "error"
                row.error_message = f"该链接暂不支持下载，或该网站/平台不受支持：{e.message[:300]}"
                await db.commit()
        return
    except asyncio.TimeoutError:
        logger.warning("下载任务超过 %.0f 秒未完成，标记失败 download_id=%s", _DOWNLOAD_WALL_CLOCK_TIMEOUT, download_id)
        async with AsyncSessionLocal() as db:
            row = await db.get(Download, download_id)
            if row:
                row.status = "error"
                row.error_message = "下载耗时过长（超过30分钟），已自动终止"
                await db.commit()
        return
    except Exception as e:
        logger.exception("下载任务异常 download_id=%s", download_id)
        async with AsyncSessionLocal() as db:
            row = await db.get(Download, download_id)
            if row:
                row.status = "error"
                row.error_message = f"下载失败：{e}"[:500]
                await db.commit()
        return

    async with AsyncSessionLocal() as db:
        row = await db.get(Download, download_id)
        if row:
            row.status = "complete"
            row.file_path = result["file_path"]
            row.total_bytes = result.get("total_bytes")
            row.downloaded_bytes = result.get("total_bytes")
            row.title = row.title or result.get("title")
            row.completed_at = datetime.utcnow()
            row.expires_at = datetime.utcnow() + timedelta(hours=settings.DOWNLOAD_RETENTION_HOURS)
            await db.commit()


@router.post("")
async def create_download(payload: dict, request: Request, db: AsyncSession = Depends(get_db)):
    url = _validate_url(payload.get("url", ""))
    title = (payload.get("title") or "").strip()[:500] or None

    client_ip = get_client_ip(request)
    _create_limiter.check(client_ip)

    existing = await _find_in_flight_task(db, url)
    if existing:
        return {"id": existing.id}

    global_active = await _active_count(db)
    if global_active >= settings.DOWNLOAD_MAX_CONCURRENT_GLOBAL:
        raise HTTPException(status_code=429, detail="当前下载任务过多，请稍后再试")

    ip_active = await _active_count(db, client_ip)
    if ip_active >= settings.DOWNLOAD_MAX_CONCURRENT_PER_IP:
        raise HTTPException(status_code=429, detail="你已有正在进行的下载任务，请等待完成后再试")

    used_gb = _dir_size_bytes(settings.DOWNLOAD_DIR) / (1024 ** 3)
    if used_gb >= settings.DOWNLOAD_QUOTA_GB:
        _alert_quota_exceeded(used_gb)
        raise HTTPException(status_code=503, detail="服务器下载空间已满，请稍后再试")

    _create_limiter.record(client_ip)

    row = Download(source_url=url, title=title, status="queued", requester_ip=client_ip)
    db.add(row)
    await db.commit()
    await db.refresh(row)

    asyncio.create_task(_run_download_task(row.id, url))

    return {"id": row.id}


@router.get("/{download_id}")
async def get_download(download_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(Download, download_id)
    if not row:
        raise HTTPException(status_code=404, detail="下载任务不存在")

    downloaded_bytes = row.downloaded_bytes
    total_bytes = row.total_bytes
    speed = None
    if row.status == "downloading":
        live = ytdlp_client.get_progress(download_id)
        if live:
            downloaded_bytes = live.get("downloaded_bytes")
            total_bytes = live.get("total_bytes") or total_bytes
            speed = live.get("speed")

    return {
        "id": row.id,
        "status": row.status,
        "title": row.title,
        "downloaded_bytes": downloaded_bytes,
        "total_bytes": total_bytes,
        "download_speed": speed,
        "error_message": row.error_message,
    }


async def cleanup_expired_downloads():
    """清理已过期的完成任务文件+DB行，以及长时间卡死(视为异常)的任务。main.py 里按小时调度。"""
    now = datetime.utcnow()
    stall_cutoff = now - timedelta(hours=6)

    async with AsyncSessionLocal() as db:
        expired = (
            await db.execute(
                select(Download).where(Download.status == "complete", Download.expires_at < now)
            )
        ).scalars().all()
        for row in expired:
            if row.file_path and os.path.exists(row.file_path):
                try:
                    os.remove(row.file_path)
                except OSError:
                    logger.warning("清理下载文件失败 id=%s path=%s", row.id, row.file_path)
            row.status = "expired"
            row.file_path = None

        stalled = (
            await db.execute(
                select(Download).where(
                    Download.status.in_(["queued", "downloading"]),
                    Download.created_at < stall_cutoff,
                )
            )
        ).scalars().all()
        for row in stalled:
            row.status = "error"
            row.error_message = "下载超时（超过6小时未完成），已自动终止"

        if expired or stalled:
            await db.commit()
            logger.info("下载清理：过期 %d 个，超时终止 %d 个", len(expired), len(stalled))
        if stalled:
            await send_telegram(f"⚠️ <b>下载任务卡死清理</b>\n发现 {len(stalled)} 个超过6小时未完成的下载任务，已自动终止")


@router.get("/{download_id}/file")
async def get_download_file(download_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(Download, download_id)
    if not row:
        raise HTTPException(status_code=404, detail="下载任务不存在")
    if row.status != "complete":
        raise HTTPException(status_code=409, detail="文件尚未准备好")
    if row.expires_at and row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="文件已过期清理，请重新下载")
    if not row.file_path or not os.path.exists(row.file_path):
        raise HTTPException(status_code=404, detail="文件不存在，可能已被清理")

    filename = os.path.basename(row.file_path)
    return FileResponse(row.file_path, filename=filename, media_type="application/octet-stream")
