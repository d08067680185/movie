import pytest
from sqlalchemy import select

from spiders.base import BaseSpider, ResourceItem
from spiders import SPIDER_REGISTRY
from spiders.scheduler import run_spider
from models import Source, Resource, SpiderLog
import tasks as task_registry


class _FakeSpider(BaseSpider):
    """只返回第一页数据的假爬虫，用于验证 registry 调度 + upsert 落库逻辑，不发真实网络请求。"""
    name = "fake_test_spider"
    _CALLS = {"count": 0}

    async def crawl(self, page: int = 1):
        _FakeSpider._CALLS["count"] += 1
        if page > 1:
            return []
        item = ResourceItem(title="假数据测试影片", year=2024, category="movie")
        item.add_link(url="https://example.com/fake", link_type="page")
        return [item]


@pytest.fixture(autouse=True)
def _register_fake_spider():
    _FakeSpider._CALLS["count"] = 0
    SPIDER_REGISTRY["fake_test_spider"] = _FakeSpider
    yield
    SPIDER_REGISTRY.pop("fake_test_spider", None)


@pytest.mark.asyncio
async def test_run_spider_dispatches_to_registry_and_upserts(db_session):
    source = Source(name="假源", spider_class="fake_test_spider", is_active=True)
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    await run_spider(source.id)

    resources = (await db_session.execute(select(Resource))).scalars().all()
    assert len(resources) == 1
    assert resources[0].title == "假数据测试影片"
    assert resources[0].category == "电影"  # CATEGORY_MAP 翻译 movie -> 电影

    logs = (await db_session.execute(select(SpiderLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].new_resources == 1

    # 假爬虫只返回一页数据，第二页返回空应提前终止翻页
    assert _FakeSpider._CALLS["count"] == 2


@pytest.mark.asyncio
async def test_run_spider_skips_unknown_spider_class(db_session):
    source = Source(name="未知源", spider_class="does_not_exist", is_active=True)
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    await run_spider(source.id)  # 不应抛异常

    logs = (await db_session.execute(select(SpiderLog))).scalars().all()
    assert len(logs) == 0  # 未找到 spider class 时直接返回，不应创建日志


@pytest.mark.asyncio
async def test_run_spider_skips_inactive_source(db_session):
    source = Source(name="停用源", spider_class="fake_test_spider", is_active=False)
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    await run_spider(source.id)

    logs = (await db_session.execute(select(SpiderLog))).scalars().all()
    assert len(logs) == 0
