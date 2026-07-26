"""Shared utility functions: Telegram notifications, DB backup."""
import logging
import shutil
import os
import sqlite3
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _verify_backup_integrity(db_path: str) -> bool:
    """只读连接跑 PRAGMA integrity_check，校验备份文件本身没有损坏
    （文件复制过程出错/源库当时正在写入导致的半写状态等）。"""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            return bool(result) and result[0] == "ok"
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning(f"备份完整性校验失败: {e}")
        return False


async def send_telegram(message: str):
    from config import settings
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)
    if not token or not chat_id:
        return
    try:
        import aiohttp
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=aiohttp.ClientTimeout(total=10),
            )
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


def backup_db(db_path: str = "movie_search.db") -> Optional[str]:
    """复制数据库文件并校验完整性；校验失败会删除这份坏备份、返回 None。
    调用方(main.py 的定时任务)据此决定要不要发告警。"""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, f"movie_search_{ts}.db")
    shutil.copy2(db_path, dest)

    if not _verify_backup_integrity(dest):
        logger.error(f"备份完整性校验未通过，删除坏备份: {dest}")
        try:
            os.remove(dest)
        except OSError:
            pass
        return None

    return dest


def list_backups() -> list[dict]:
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        return []
    files = []
    for fname in sorted(os.listdir(backup_dir), reverse=True):
        if fname.endswith(".db"):
            fpath = os.path.join(backup_dir, fname)
            files.append({
                "name": fname,
                "size_mb": round(os.path.getsize(fpath) / 1024 / 1024, 2),
                "created_at": datetime.utcfromtimestamp(os.path.getctime(fpath)).isoformat(),
            })
    return files[:20]
