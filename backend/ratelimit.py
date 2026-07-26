"""通用滑动窗口限流器，供登录限流(auth.py)和下载限流(api/downloads.py)共用。"""
import time
from collections import defaultdict
from typing import Optional
from fastapi import HTTPException, Request


def get_client_ip(request: Request) -> str:
    """优先取 CF-Connecting-IP。实际部署路径是 Cloudflare → Cloudflare Tunnel
    (cloudflared，跑在部署用的 Mac mini 上，配置在仓库之外) → Next.js rewrites
    → backend。已在生产环境实测验证：这条头确实端到端正确传递到这里，且该端口
    没有绕开 Cloudflare 的公网直连路径(隧道只出不进)，伪造这个头在当前拓扑下
    不可行。退回 request.client.host 仅作为兜底。
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    return request.client.host if request.client else "unknown"


# 所有实例的注册表，供 sweep_all_limiters() 定时清理，防止长期运行后
# _attempts 字典里堆积大量已经空了的 key(内存缓慢泄漏)
_ALL_LIMITERS: list["SlidingWindowLimiter"] = []


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: float, message: str = "请求过于频繁，请稍后再试"):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.message = message
        self._attempts: dict[str, list[float]] = defaultdict(list)
        _ALL_LIMITERS.append(self)

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

    def sweep(self):
        """清掉窗口内已经没有任何记录的 key，避免字典无限增长。"""
        now = time.time()
        empty_keys = []
        for key, attempts in self._attempts.items():
            attempts[:] = [t for t in attempts if now - t < self.window_seconds]
            if not attempts:
                empty_keys.append(key)
        for key in empty_keys:
            del self._attempts[key]


def sweep_all_limiters():
    for limiter in _ALL_LIMITERS:
        limiter.sweep()
