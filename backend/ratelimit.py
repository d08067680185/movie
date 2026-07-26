"""通用滑动窗口限流器，供登录限流(auth.py)和下载限流(api/downloads.py)共用。"""
import time
from collections import defaultdict
from typing import Optional
from fastapi import HTTPException, Request


def get_client_ip(request: Request) -> str:
    """优先取 CF-Connecting-IP（Cloudflare 代理场景下由 Cloudflare 边缘节点写入，
    客户端无法在到达 Cloudflare 前伪造），退回 request.client.host。

    注意：如果源站(本仓库之外的 Nginx 层)没有校验请求确实来自 Cloudflare IP 段，
    理论上仍可能有人绕过 Cloudflare 直接打源站并伪造这个头。这一层校验不在本仓库
    范围内(找不到对应 Nginx 配置)，属于已知的残余风险，未完全解决。
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    return request.client.host if request.client else "unknown"


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
