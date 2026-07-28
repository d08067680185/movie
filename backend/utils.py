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


# 低风险恢复演练：只读连接对着备份文件本身查，不碰生产库、不做真实的原地覆盖恢复。
# integrity_check 只验证文件结构没损坏，不代表关键表真的能查到预期数据(比如结构对但
# 数据为空/关键表不存在这种情况 integrity_check 是测不出来的)，这里补上这一层。
_RESTORE_DRILL_QUERIES = [
    ("resources", "SELECT COUNT(*) FROM resources"),
    ("resource_links", "SELECT COUNT(*) FROM resource_links"),
    ("sources", "SELECT COUNT(*) FROM sources"),
]


def verify_backup_restorable(db_path: str) -> tuple[bool, str]:
    """对备份文件开一个独立只读连接，跑几条关键表的 sanity query，确认真的能查到
    数据而不是只是"文件结构没坏但内容对不上"。返回 (是否通过, 说明文字)。"""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            counts = {}
            for table, query in _RESTORE_DRILL_QUERIES:
                counts[table] = conn.execute(query).fetchone()[0]
            if counts["resources"] <= 0:
                return False, f"resources 表为空或查询异常: {counts}"
            return True, f"抽查通过: {counts}"
        finally:
            conn.close()
    except sqlite3.Error as e:
        return False, f"恢复演练查询失败: {e}"


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
    """复制数据库文件并校验完整性+可恢复性；任一项校验失败都会删除这份坏备份、
    返回 None。调用方(main.py 的定时任务)据此决定要不要发告警。"""
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

    restorable, detail = verify_backup_restorable(dest)
    if not restorable:
        logger.error(f"备份恢复演练未通过，删除坏备份: {dest}，{detail}")
        try:
            os.remove(dest)
        except OSError:
            pass
        return None
    logger.info(f"备份恢复演练通过: {dest}，{detail}")

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
