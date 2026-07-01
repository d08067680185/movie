"""Shared utility functions: Telegram notifications, DB backup."""
import logging
import shutil
import os
from datetime import datetime

logger = logging.getLogger(__name__)


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


def backup_db(db_path: str = "movie_search.db") -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, f"movie_search_{ts}.db")
    shutil.copy2(db_path, dest)
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
