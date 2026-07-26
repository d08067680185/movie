import time
import uuid

import httpx
import pytest
from fastapi import Request
from httpx import ASGITransport

from ratelimit import SlidingWindowLimiter, get_client_ip


def _unique_ip() -> str:
    """测试专用的假IP，用uuid避免不同测试用例之间的限流状态互相污染
    （_public_read_limiter是模块级单例，没有per-test重置）。"""
    return f"198.51.100.{uuid.uuid4().hex[:8]}"


def _make_request(headers: dict, client_host: str = "10.0.0.5") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_get_client_ip_prefers_cf_connecting_ip():
    req = _make_request({"CF-Connecting-IP": "203.0.113.7"}, client_host="172.18.0.3")
    assert get_client_ip(req) == "203.0.113.7"


def test_get_client_ip_falls_back_to_request_client_host():
    req = _make_request({}, client_host="172.18.0.3")
    assert get_client_ip(req) == "172.18.0.3"


def test_get_client_ip_strips_whitespace():
    req = _make_request({"CF-Connecting-IP": "  203.0.113.7  "})
    assert get_client_ip(req) == "203.0.113.7"


def test_sliding_window_limiter_blocks_after_threshold():
    limiter = SlidingWindowLimiter(max_attempts=3, window_seconds=60)
    key = f"test-{time.time()}"
    for _ in range(3):
        limiter.check(key)
        limiter.record(key)
    with pytest.raises(Exception):
        limiter.check(key)


@pytest.mark.asyncio
async def test_search_endpoint_rate_limited_after_60_requests_per_minute():
    from main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"CF-Connecting-IP": _unique_ip()}
        last_status = None
        for _ in range(61):
            resp = await client.get("/api/search", params={"q": "x"}, headers=headers)
            last_status = resp.status_code
        assert last_status == 429


@pytest.mark.asyncio
async def test_search_rate_limit_is_per_ip_not_global():
    from main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ip_a = _unique_ip()
        for _ in range(60):
            await client.get("/api/search", params={"q": "x"}, headers={"CF-Connecting-IP": ip_a})
        # ip_a 现在应该被限流了
        blocked = await client.get("/api/search", params={"q": "x"}, headers={"CF-Connecting-IP": ip_a})
        assert blocked.status_code == 429

        # 不同 IP 不受影响
        ip_b = _unique_ip()
        ok = await client.get("/api/search", params={"q": "x"}, headers={"CF-Connecting-IP": ip_b})
        assert ok.status_code == 200
