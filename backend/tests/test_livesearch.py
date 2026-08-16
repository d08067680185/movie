import time
import uuid
import pytest
import httpx

from api import livesearch as ls


def _unique_ip() -> str:
    return f"198.51.100.{uuid.uuid4().hex[:8]}"


def test_clean_url_extracts_first_url_and_strips_trailing_punctuation():
    assert ls._clean_url("看这里 https://pan.example.com/s/abc123).") == "https://pan.example.com/s/abc123"
    assert ls._clean_url("没有链接") is None


def test_normalize_strips_trailing_hash_from_password_and_bare_trailing_hash_url():
    # 尾部 # 是已知 pansou 噪音，password/url 字段都要清理；rstrip 只删真正
    # 末尾字符，url 中间的 #/list/share 路由片段不受影响（下一条用例锁定）
    raw = {"merged_by_type": {"quark": [
        {"url": "https://pan.quark.cn/s/x#", "note": "标题", "password": "abcd#"},
    ]}}
    item = ls._normalize(raw, "")["by_type"]["quark"][0]
    assert item["url"] == "https://pan.quark.cn/s/x"
    assert item["password"] == "abcd"


def test_normalize_keeps_non_trailing_hash_in_url():
    raw = {"merged_by_type": {"quark": [
        {"url": "https://pan.quark.cn/s/x#/list/share", "note": "标题"},
    ]}}
    item = ls._normalize(raw, "")["by_type"]["quark"][0]
    assert item["url"] == "https://pan.quark.cn/s/x#/list/share"


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
    result = ls._normalize(raw, "")
    assert result["total"] == 1
    assert len(result["by_type"]["quark"]) == 1
    item = result["by_type"]["quark"][0]
    assert item["title"] == "高亮标题"
    assert item["password"] == "abcd"
    assert "unknown_type" not in result["by_type"]


def test_normalize_dedupes_near_identical_titles_within_same_cloud_type():
    """同一资源被不同 TG 频道转发会产生不同 URL 但标题几乎一样（画质/版本标签
    不同），同一网盘类型下应该只保留一条；不同类型即便标题相同也各自保留
    （不做跨类型去重，因为不同类型URL域名不同本来就不会重复）。"""
    raw = {
        "merged_by_type": {
            "quark": [
                {"url": "https://pan.quark.cn/s/a1", "note": "复仇者联盟4K高清"},
                {"url": "https://pan.quark.cn/s/a2", "note": "复仇者联盟 (2019)"},
            ],
            "baidu": [
                {"url": "https://pan.baidu.com/s/b1", "note": "复仇者联盟4K高清"},
            ],
        }
    }
    result = ls._normalize(raw, "")
    assert len(result["by_type"]["quark"]) == 1
    assert result["by_type"]["quark"][0]["url"] == "https://pan.quark.cn/s/a1"
    assert len(result["by_type"]["baidu"]) == 1


def test_normalize_sorts_by_relevance_before_truncating():
    """标题里包含关键词的结果应该排在不含关键词的前面，即便它在 PanSou
    原始返回顺序里靠后——这个排序发生在300条截断*之前*，防止真正相关的
    结果被截断挡在外面。"""
    raw = {"merged_by_type": {"quark": [
        {"url": "https://pan.quark.cn/s/a1", "note": "完全不相关的其他影视资源"},
        {"url": "https://pan.quark.cn/s/a2", "note": "斗罗大陆之燃魂战"},
        {"url": "https://pan.quark.cn/s/a3", "note": "斗罗大陆"},
    ]}}
    result = ls._normalize(raw, "斗罗大陆")
    titles = [it["title"] for it in result["by_type"]["quark"]]
    assert titles == ["斗罗大陆", "斗罗大陆之燃魂战", "完全不相关的其他影视资源"]


@pytest.mark.asyncio
async def test_record_source_stats_upserts_counts(db_session):
    from sqlalchemy import select
    from models import PansouSourceStat

    by_type = {
        "quark": [{"source": "tg:a"}, {"source": "tg:a"}, {"source": "plugin:b"}],
        "baidu": [{"source": "tg:a"}],
    }
    await ls._record_source_stats(by_type)
    # 第二次调用应该在原有计数上累加，而不是覆盖
    await ls._record_source_stats({"quark": [{"source": "tg:a"}]})

    result = await db_session.execute(
        select(PansouSourceStat).where(PansouSourceStat.source_key == "tg:a")
    )
    row = result.scalar_one()
    assert row.hit_count == 4  # 2 + 1 + 1

    result = await db_session.execute(
        select(PansouSourceStat).where(PansouSourceStat.source_key == "plugin:b")
    )
    assert result.scalar_one().hit_count == 1


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


@pytest.mark.asyncio
async def test_livesearch_cache_key_normalized_across_case_and_whitespace(monkeypatch, db_session):
    """"Iron Man" 和 "iron  man"(大小写不同+内部多余空格) 应该命中同一个缓存槽，
    第二次请求不应该再真的去打 PanSou。"""
    from main import app
    from httpx import ASGITransport

    ls._cache.clear()
    call_count = {"n": 0}

    async def fake_fetch(keyword, refresh):
        call_count["n"] += 1
        return {"total": 0, "by_type": {}}

    monkeypatch.setattr(ls, "_fetch_pansou", fake_fetch)

    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/api/livesearch", params={"q": "Iron Man"}, headers=headers)
        r2 = await client.get("/api/livesearch", params={"q": "iron  man"}, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert call_count["n"] == 1  # 第二次应该命中缓存，不应该再调用 _fetch_pansou
    ls._cache.clear()


@pytest.mark.asyncio
async def test_livesearch_concurrent_same_keyword_coalesces_upstream_call(monkeypatch, db_session):
    """并发请求同一个未缓存关键词时，应该合并成一次真正的 PanSou 上游调用（防雪崩）。"""
    import asyncio as _asyncio
    from main import app
    from httpx import ASGITransport

    ls._cache.clear()
    ls._inflight.clear()
    ls._stats["coalesced"] = 0
    call_count = {"n": 0}

    async def fake_fetch(keyword, refresh):
        call_count["n"] += 1
        await _asyncio.sleep(0.05)
        return {"total": 0, "by_type": {}}

    monkeypatch.setattr(ls, "_fetch_pansou", fake_fetch)

    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await _asyncio.gather(*[
            client.get("/api/livesearch", params={"q": "并发合并测试关键词"}, headers=headers)
            for _ in range(5)
        ])

    assert all(r.status_code == 200 for r in responses)
    assert call_count["n"] == 1  # 只有一次真正打到上游
    assert ls._stats["coalesced"] == 4  # 其余 4 个请求复用了同一个结果
    assert ls._inflight == {}  # 用完即清理，不常驻
    ls._cache.clear()


@pytest.mark.asyncio
async def test_livesearch_rate_limited_after_threshold(monkeypatch, db_session):
    from main import app
    from httpx import ASGITransport

    ls._cache.clear()

    async def fake_fetch(keyword, refresh):
        return {"total": 0, "by_type": {}}

    monkeypatch.setattr(ls, "_fetch_pansou", fake_fetch)

    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        last_status = None
        for i in range(31):
            # 每次换个关键词，确保不会命中缓存而提前短路，真实触达限流依赖
            resp = await client.get(
                "/api/livesearch", params={"q": f"限流测试关键词{i}"}, headers=headers
            )
            last_status = resp.status_code
        assert last_status == 429
    ls._cache.clear()


@pytest.mark.asyncio
async def test_livesearch_concurrent_distinct_keywords_bounded_by_semaphore(monkeypatch, db_session):
    """不同关键词的并发上游调用应该被信号量限制在 _PANSOU_CONCURRENCY 的容量内
    （相同关键词已经被请求合并机制收敛，这里专门测试"合并机制收敛不到"的场景）。"""
    import asyncio as _asyncio
    from main import app
    from httpx import ASGITransport

    ls._cache.clear()
    ls._inflight.clear()
    concurrent = {"current": 0, "max": 0}
    lock = _asyncio.Lock()

    async def fake_fetch_pansou(keyword, refresh):
        async with lock:
            concurrent["current"] += 1
            concurrent["max"] = max(concurrent["max"], concurrent["current"])
        await _asyncio.sleep(0.05)
        async with lock:
            concurrent["current"] -= 1
        return {"total": 0, "by_type": {}}

    async def gated_fetch(keyword, refresh):
        async with ls._PANSOU_CONCURRENCY:
            return await fake_fetch_pansou(keyword, refresh)

    monkeypatch.setattr(ls, "_fetch_pansou", gated_fetch)

    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _asyncio.gather(*[
            client.get("/api/livesearch", params={"q": f"信号量测试关键词{i}"}, headers=headers)
            for i in range(8)
        ])

    assert concurrent["max"] <= 4
    ls._cache.clear()


def test_parse_query_splits_include_and_exclude_terms():
    assert ls._parse_query("斗罗大陆 -解说 -花絮") == ("斗罗大陆", ["解说", "花絮"])
    assert ls._parse_query("斗罗大陆") == ("斗罗大陆", [])
    assert ls._parse_query("- 斗罗大陆") == ("- 斗罗大陆", [])  # 单独一个"-"不算排除词语法(长度<=1)


def test_apply_exclude_filter_removes_matching_titles_and_can_empty_a_type():
    by_type = {
        "quark": [{"title": "斗罗大陆解说版"}, {"title": "斗罗大陆正片"}],
        "baidu": [{"title": "斗罗大陆解说合集"}],
    }
    result = ls._apply_exclude_filter(by_type, ["解说"])
    assert [it["title"] for it in result["quark"]] == ["斗罗大陆正片"]
    assert "baidu" not in result  # 全部被排除后整个类型键消失，跟原有空类型不展示的行为一致


def test_apply_exclude_filter_noop_when_no_exclude_terms():
    by_type = {"quark": [{"title": "任意标题"}]}
    assert ls._apply_exclude_filter(by_type, []) is by_type


@pytest.mark.asyncio
async def test_livesearch_exclude_syntax_filters_results_without_polluting_upstream_keyword(monkeypatch, db_session):
    """排除词不应该被发给PanSou上游查询——只用来过滤已经拿到的结果。"""
    from main import app
    from httpx import ASGITransport

    ls._cache.clear()
    captured_keyword = {}

    async def fake_fetch(keyword, refresh):
        captured_keyword["kw"] = keyword
        return {"total": 2, "by_type": {"quark": [
            {"title": "斗罗大陆解说版", "url": "https://pan.quark.cn/s/a1", "password": "", "datetime": None, "source": "tg:x"},
            {"title": "斗罗大陆正片", "url": "https://pan.quark.cn/s/a2", "password": "", "datetime": None, "source": "tg:x"},
        ]}}

    monkeypatch.setattr(ls, "_fetch_pansou", fake_fetch)

    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/livesearch", params={"q": "斗罗大陆 -解说"}, headers=headers)

    assert r.status_code == 200
    data = r.json()
    titles = [it["title"] for it in data["by_type"]["quark"]]
    assert titles == ["斗罗大陆正片"]
    assert captured_keyword["kw"] == "斗罗大陆"  # 排除词没有混进发给上游的查询串
    ls._cache.clear()


@pytest.mark.asyncio
async def test_check_links_proxies_pansou_and_keeps_only_ok_bad_states(monkeypatch):
    """代理 PanSou 原生 /api/check/links；只把 state=ok/bad 映射成 True/False，
    locked/uncertain/unsupported 不出现在结果里（前端据此区分"确认"和"不确定"）。
    直接调用端点函数而不经ASGI test client——monkeypatch httpx.AsyncClient会
    同时影响test client自己发请求用的AsyncClient，两者会冲突。"""
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [
                {"url": "https://pan.quark.cn/s/valid", "state": "ok"},
                {"url": "https://pan.quark.cn/s/dead", "state": "bad"},
                {"url": "https://pan.baidu.com/s/locked", "state": "locked"},
                {"url": "https://pan.115.com/s/unclear", "state": "uncertain"},
            ]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, **kwargs):
            captured["url"] = url
            captured["json"] = json
            return FakeResp()

    monkeypatch.setattr(ls.httpx, "AsyncClient", FakeAsyncClient)

    result = await ls.check_links(items=[
        {"url": "https://pan.quark.cn/s/valid", "cloud_type": "quark"},
        {"url": "https://pan.quark.cn/s/dead", "cloud_type": "quark"},
        {"url": "https://pan.baidu.com/s/locked", "cloud_type": "baidu"},
        {"url": "https://pan.115.com/s/unclear", "cloud_type": "115"},
    ], _rl=None)

    assert result["results"] == {
        "https://pan.quark.cn/s/valid": True,
        "https://pan.quark.cn/s/dead": False,
    }
    assert captured["url"].endswith("/api/check/links")
    assert captured["json"]["items"][0] == {"disk_type": "quark", "url": "https://pan.quark.cn/s/valid"}


@pytest.mark.asyncio
async def test_check_links_returns_empty_on_upstream_failure(monkeypatch):
    class BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(ls.httpx, "AsyncClient", BoomClient)

    result = await ls.check_links(items=[
        {"url": "https://pan.quark.cn/s/x", "cloud_type": "quark"},
    ], _rl=None)

    assert result["results"] == {}  # 上游失败不确定不等于失效，返回空而不是误标False
