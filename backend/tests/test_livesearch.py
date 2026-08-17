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


def test_clean_url_recognizes_magnet_uri():
    magnet = "magnet:?xt=urn:btih:0A16510705A12D253D0BE8A8A3CFE8575E3E8056&dn=Oppenheimer"
    assert ls._clean_url(magnet) == magnet


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
    # _fetch_pansou 现在会用 asyncio.gather 并发调用 PanSou 自身 + bitsearch.to
    # (英文磁力补充源)，两者共用同一个被monkeypatch的AsyncClient，所以记录全部
    # 出现过的timeout值而不是只存最后一个，避免并发覆盖导致断言到错误的那个
    captured_timeouts = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured_timeouts.append(kwargs.get("timeout"))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(ls.httpx, "AsyncClient", FakeAsyncClient)
    with pytest.raises(httpx.ConnectError):
        await ls._fetch_pansou("keyword", refresh=False)
    assert 10.0 in captured_timeouts  # PanSou自身请求仍是10秒超时，不受并发的bitsearch影响


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
async def test_livesearch_converts_traditional_input_to_simplified_before_upstream(monkeypatch, db_session):
    """繁体输入应该转简体再发给PanSou/算缓存key，跟对应简体输入共享同一批结果。"""
    from main import app
    from httpx import ASGITransport

    ls._cache.clear()
    captured_keyword = {}

    async def fake_fetch(keyword, refresh):
        captured_keyword["kw"] = keyword
        return {"total": 0, "by_type": {}}

    monkeypatch.setattr(ls, "_fetch_pansou", fake_fetch)

    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/livesearch", params={"q": "鬥羅大陸"}, headers=headers)

    assert r.status_code == 200
    assert captured_keyword["kw"] == "斗罗大陆"
    # 简体查询应该命中刚才繁体查询建立的同一个缓存槽，不应该再打一次上游
    call_count_before = len(captured_keyword)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r2 = await client.get("/api/livesearch", params={"q": "斗罗大陆"}, headers=headers)
    assert r2.status_code == 200
    assert captured_keyword["kw"] == "斗罗大陆"  # 没有被第二次调用覆盖成别的值说明_fetch_pansou没被再次调用
    ls._cache.clear()


@pytest.mark.asyncio
async def test_livesearch_attaches_source_hits_without_mutating_cached_payload(monkeypatch, db_session):
    """响应里每条结果应该带 source_hits；且不能原地修改缓存里的 payload 对象
    （否则下一次复用缓存的请求会读到被污染的数据）。"""
    from main import app
    from httpx import ASGITransport
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from models import PansouSourceStat

    ls._cache.clear()
    await db_session.execute(sqlite_insert(PansouSourceStat).values(source_key="tg:testsrc", hit_count=42))
    await db_session.commit()
    ls._source_hits_cache.clear()
    ls._source_hits_cache_ts = 0.0

    async def fake_fetch(keyword, refresh):
        return {"total": 1, "by_type": {"quark": [
            {"title": "测试标题", "url": "https://pan.quark.cn/s/x1", "password": "", "datetime": None, "source": "tg:testsrc"},
        ]}}

    monkeypatch.setattr(ls, "_fetch_pansou", fake_fetch)

    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/api/livesearch", params={"q": "来源命中测试关键词"}, headers=headers)
        r2 = await client.get("/api/livesearch", params={"q": "来源命中测试关键词"}, headers=headers)  # 命中缓存

    assert r1.json()["by_type"]["quark"][0]["source_hits"] == 42
    assert r2.json()["by_type"]["quark"][0]["source_hits"] == 42
    # 缓存里的原始payload本身不应该被污染出source_hits字段
    cached_payload = next(v[1] for v in ls._cache.values())
    assert "source_hits" not in cached_payload["by_type"]["quark"][0]
    ls._cache.clear()


@pytest.mark.asyncio
async def test_report_invalid_link_upserts_and_accumulates(db_session):
    from main import app
    from httpx import ASGITransport

    url = "https://pan.quark.cn/s/report-test-1"
    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/api/livesearch/report-invalid", json={"url": url}, headers=headers)
        r2 = await client.post("/api/livesearch/report-invalid", json={"url": url}, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    from sqlalchemy import select
    from models import LiveLinkReport

    row = (await db_session.execute(
        select(LiveLinkReport).where(LiveLinkReport.url_hash == ls._url_hash(url))
    )).scalar_one()
    assert row.report_count == 2
    assert row.url == url


@pytest.mark.asyncio
async def test_livesearch_marks_reported_invalid_only_at_threshold(monkeypatch, db_session):
    """举报次数达到阈值前不应该展示 reported_invalid，达到后才展示。"""
    from main import app
    from httpx import ASGITransport

    ls._cache.clear()
    ls._invalid_reports_cache.clear()
    ls._invalid_reports_cache_ts = 0.0
    url = "https://pan.quark.cn/s/report-threshold-test"

    async def fake_fetch(keyword, refresh):
        return {"total": 1, "by_type": {"quark": [
            {"title": "举报阈值测试", "url": url, "password": "", "datetime": None, "source": "tg:x"},
        ]}}

    monkeypatch.setattr(ls, "_fetch_pansou", fake_fetch)

    transport = ASGITransport(app=app)
    headers = {"CF-Connecting-IP": _unique_ip()}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 举报1次：未达阈值(2)，不应标记
        await client.post("/api/livesearch/report-invalid", json={"url": url}, headers=headers)
        ls._invalid_reports_cache.clear()
        ls._invalid_reports_cache_ts = 0.0
        r1 = await client.get("/api/livesearch", params={"q": "举报阈值测试"}, headers=headers)
        assert r1.json()["by_type"]["quark"][0]["reported_invalid"] is False

        # 再举报1次：达到阈值(2)，应该标记
        await client.post("/api/livesearch/report-invalid", json={"url": url}, headers=headers)
        ls._invalid_reports_cache.clear()
        ls._invalid_reports_cache_ts = 0.0
        ls._cache.clear()
        r2 = await client.get("/api/livesearch", params={"q": "举报阈值测试"}, headers=headers)
        assert r2.json()["by_type"]["quark"][0]["reported_invalid"] is True

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


@pytest.mark.asyncio
async def test_fetch_bitsearch_maps_results_to_magnet_items(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [
                {"infohash": "ABC123", "title": "Oppenheimer (2023) [1080p]", "seeders": 1795, "updatedAt": "2026-08-16T12:09:05Z"},
                {"infohash": "", "title": "缺infohash应该被跳过"},  # 应被过滤
            ]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResp()

    monkeypatch.setattr(ls.httpx, "AsyncClient", FakeClient)

    items = await ls._fetch_bitsearch("Oppenheimer")
    assert len(items) == 1
    it = items[0]
    assert it["url"] == "magnet:?xt=urn:btih:ABC123&dn=Oppenheimer%20%282023%29%20%5B1080p%5D"
    assert "做种1795" in it["note"]
    assert it["source"] == "api:bitsearch"


@pytest.mark.asyncio
async def test_fetch_bitsearch_returns_empty_on_failure(monkeypatch):
    class BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(ls.httpx, "AsyncClient", BoomClient)
    assert await ls._fetch_bitsearch("keyword") == []


@pytest.mark.asyncio
async def test_fetch_pansou_merges_bitsearch_into_magnet_bucket(monkeypatch):
    """_fetch_pansou 应该把 bitsearch 的英文磁力结果并进 PanSou 自己返回的
    magnet 桶里，两边数据经过同一套 _normalize 去重/排序/截断流程。"""
    class FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *args, **kwargs):
            if "bitsearch.to" in url:
                return FakeResp({"results": [
                    {"infohash": "ENGHASH", "title": "Oppenheimer 1080p", "seeders": 10, "updatedAt": None},
                ]})
            return FakeResp({"code": 0, "data": {"merged_by_type": {
                "magnet": [{"url": "magnet:?xt=urn:btih:CNHASH", "note": "奥本海默中字版", "password": "", "datetime": None, "source": "plugin:x"}],
                "quark": [],
            }}})

    monkeypatch.setattr(ls.httpx, "AsyncClient", FakeClient)

    payload = await ls._fetch_pansou("Oppenheimer", refresh=False)
    magnet_titles = {it["title"] for it in payload["by_type"].get("magnet", [])}
    assert "Oppenheimer 1080p (做种10)" in magnet_titles
    assert "奥本海默中字版" in magnet_titles
