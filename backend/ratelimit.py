"""通用滑动窗口限流器，供登录限流(auth.py)和下载限流(api/downloads.py)共用。"""
import time
from collections import defaultdict
from fastapi import HTTPException


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: float, message: str = "请求过于频繁，请稍后再试"):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.message = message
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str):
        """超过阈值则抛 429，并顺带清理该 key 下的过期记录。"""
        now = time.time()
        attempts = self._attempts[key]
        attempts[:] = [t for t in attempts if now - t < self.window_seconds]
        if len(attempts) >= self.max_attempts:
            raise HTTPException(status_code=429, detail=self.message)

    def record(self, key: str):
        self._attempts[key].append(time.time())

    def reset(self, key: str):
        self._attempts.pop(key, None)
