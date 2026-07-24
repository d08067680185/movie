import time
import pytest
import httpx

from api import livesearch as ls


def test_clean_url_extracts_first_url_and_strips_trailing_punctuation():
    assert ls._clean_url("看这里 https://pan.example.com/s/abc123).") == "https://pan.example.com/s/abc123"
    assert ls._clean_url("没有链接") is None


def test_normalize_strips_trailing_hash_from_password_only():
    # 尾部 # 只在 password 字段清理（提取码尾部#是已知 pansou 噪音），url 本身不做这个假设
    raw = {"merged_by_type": {"quark": [
        {"url": "https://pan.quark.cn/s/x#", "note": "标题", "password": "abcd#"},
    ]}}
    item = ls._normalize(raw)["by_type"]["quark"][0]
    assert item["url"] == "https://pan.quark.cn/s/x#"
    assert item["password"] == "abcd"


def test_normalize_dedupes_and_strips_html_tags():
    raw = {
        "merged_by_type": {
            "quark": [
                {"url": "https://pan.quark.cn/s/a1", "note": "<span>高亮</span>标题", "password": "abcd#"},
                {"url": "https://pan.quark.cn/s/a1", "note": "重复条目应被去重"},
            ],
            "unknown_type": [{"url": "https://x.example.com/y", "note": "不在白名单类型应被忽略"}],
        }
    }
    result = ls._normalize(raw)
    assert result["total"] == 1
    assert len(result["by_type"]["quark"]) == 1
    item = result["by_type"]["quark"][0]
    assert item["title"] == "高亮标题"
    assert item["password"] == "abcd"
    assert "unknown_type" not in result["by_type"]


@pytest.fixture(autouse=True)
def _reset_circuit_state():
    ls._circuit_failures = 0
    ls._circuit_open_until = 0.0
    yield
    ls._circuit_failures = 0
    ls._circuit_open_until = 0.0


def test_circuit_stays_closed_below_threshold():
    for _ in range(ls._CIRCUIT_FAIL_THRESHOLD - 1):
        ls._circuit_record_failure()
    assert not ls._circuit_is_open()


def test_circuit_opens_at_threshold_and_recovers_on_success():
    for _ in range(ls._CIRCUIT_FAIL_THRESHOLD):
        ls._circuit_record_failure()
    assert ls._circuit_is_open()

    ls._circuit_record_success()
    assert ls._circuit_failures == 0
    # 熔断的冷却截止时间不因为后续成功而立即清零（成功只重置失败计数）
    # 但既然计数已清零，后续新的失败需要重新累计到阈值才会再次打开


@pytest.mark.asyncio
async def test_fetch_pansou_uses_short_timeout(monkeypatch):
    captured = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(ls.httpx, "AsyncClient", FakeAsyncClient)
    with pytest.raises(httpx.ConnectError):
        await ls._fetch_pansou("keyword", refresh=False)
    assert captured["timeout"] == 10.0
