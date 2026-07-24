"""管理员鉴权：密码哈希存取 + 登录失败限流。"""
import time
import logging
import bcrypt
from collections import defaultdict
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# IP -> 失败时间戳列表（滑动窗口）
_failed_attempts: dict[str, list[float]] = defaultdict(list)
MAX_ATTEMPTS = 10
WINDOW_SECONDS = 300  # 5 分钟内失败超过 MAX_ATTEMPTS 次则锁定
LOCKOUT_SECONDS = 300  # 锁定 5 分钟


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def check_rate_limit(client_ip: str):
    """超过失败次数阈值则拒绝，并清理过期记录。"""
    now = time.time()
    attempts = _failed_attempts[client_ip]
    attempts[:] = [t for t in attempts if now - t < WINDOW_SECONDS]
    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="登录尝试过多，请稍后再试")


def record_failure(client_ip: str):
    _failed_attempts[client_ip].append(time.time())


def record_success(client_ip: str):
    _failed_attempts.pop(client_ip, None)


def migrate_plaintext_password(settings) -> None:
    """首次启动时把 .env 里的明文 ADMIN_PASSWORD 迁移为哈希，并清除明文。"""
    if settings.ADMIN_PASSWORD_HASH:
        return
    plain = settings.ADMIN_PASSWORD or "admin123"
    settings.ADMIN_PASSWORD_HASH = hash_password(plain)
    settings.ADMIN_PASSWORD = None

    import os
    env_path = ".env"
    lines = []
    found_hash = False
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("ADMIN_PASSWORD="):
                    continue  # 移除明文行
                if line.startswith("ADMIN_PASSWORD_HASH="):
                    lines.append(f"ADMIN_PASSWORD_HASH={settings.ADMIN_PASSWORD_HASH}\n")
                    found_hash = True
                else:
                    lines.append(line)
    if not found_hash:
        lines.append(f"ADMIN_PASSWORD_HASH={settings.ADMIN_PASSWORD_HASH}\n")
    try:
        with open(env_path, "w") as f:
            f.writelines(lines)
        logger.info("已将 ADMIN_PASSWORD 明文迁移为哈希并写入 .env")
    except OSError as e:
        logger.warning(f"迁移密码哈希写入 .env 失败（本次运行仍生效于内存）: {e}")
