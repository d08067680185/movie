import logging
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from models import Source, Resource, ResourceLink, SpiderLog
from spiders import SPIDER_REGISTRY
from config import settings

logger = logging.getLogger(__name__)

_CAT_NORM = {"movie": "电影", "tv": "电视剧", "anime": "动漫", "variety": "综艺"}


async def run_spider(source_id: int):
    async with AsyncSessionLocal() as db:
        source = await db.get(Source, source_id)
        if not source or not source.is_active:
            return

        spider_class = SPIDER_REGISTRY.get(source.spider_class)
        if not spider_class:
            logger.error(f"Spider class '{source.spider_class}' not found")
            return

        log = SpiderLog(source_id=source_id, status="running")
        db.add(log)
        await db.commit()
        await db.refresh(log)

        new_count = 0
        updated_count = 0

        try:
            async with spider_class(source.config or {}) as spider:
                for page in range(1, settings.MAX_PAGES_PER_SOURCE + 1):
                    items = await spider.crawl(page)
                    if not items:
                        break

                    for item in items:
                        result = await upsert_resource(db, item, source.id)
                        if result == "new":
                            new_count += 1
                        elif result == "updated":
                            updated_count += 1

                    await db.commit()

            await db.execute(
                update(Source)
                .where(Source.id == source_id)
                .values(
                    last_crawled=datetime.utcnow(),
                    total_resources=Source.total_resources + new_count
                )
            )
            await db.execute(
                update(SpiderLog)
                .where(SpiderLog.id == log.id)
                .values(
                    status="success",
                    new_resources=new_count,
                    updated_resources=updated_count,
                    finished_at=datetime.utcnow(),
                )
            )
            await db.commit()
            logger.info(f"Spider {source.name}: +{new_count} new, ~{updated_count} updated")

        except Exception as e:
            logger.error(f"Spider {source.name} failed: {e}")
            await db.execute(
                update(SpiderLog)
                .where(SpiderLog.id == log.id)
                .values(status="failed", error_msg=str(e), finished_at=datetime.utcnow())
            )
            await db.commit()


async def upsert_resource(db: AsyncSession, item, source_id: int) -> str:
    from sqlalchemy import func as sqlfunc

    # 先按标题+年份查找
    stmt = select(Resource).where(
        Resource.title == item.title,
        Resource.year == item.year,
    )
    result = await db.execute(stmt)
    resource = result.scalars().first()

    # TMDb 专属：按 tmdb_id 优先去重
    tmdb_id = getattr(item, "_tmdb_id", None)
    if tmdb_id and resource is None:
        r2 = (await db.execute(select(Resource).where(Resource.tmdb_id == tmdb_id))).scalars().first()
        if r2:
            resource = r2

    if resource is None:
        category_raw = item.category or "movie"
        resource = Resource(
            title=item.title,
            year=item.year,
            category=_CAT_NORM.get(category_raw, category_raw),
            genre=item.genre,
            country=item.country,
            rating=item.rating,
            synopsis=item.synopsis,
            poster_url=item.poster_url,
            directors=item.directors,
            actors=item.actors,
        )
        # 写入 TMDb 专属字段
        if tmdb_id:
            resource.tmdb_id = tmdb_id
        for attr in ("_title_en", "_imdb_id", "_language", "_duration",
                     "_rating_count", "_backdrop_url"):
            val = getattr(item, attr, None)
            if val:
                setattr(resource, attr.lstrip("_"), val)
        db.add(resource)
        await db.flush()
        status = "new"
    else:
        # 补全缺失字段
        if item.poster_url and not resource.poster_url:
            resource.poster_url = item.poster_url
        if item.synopsis and not resource.synopsis:
            resource.synopsis = item.synopsis
        if item.rating and not resource.rating:
            resource.rating = item.rating
        if tmdb_id and not resource.tmdb_id:
            resource.tmdb_id = tmdb_id
        for attr in ("_title_en", "_backdrop_url", "_language", "_duration"):
            val = getattr(item, attr, None)
            col = attr.lstrip("_")
            if val and not getattr(resource, col, None):
                setattr(resource, col, val)
        status = "updated"

    # 添加链接（去重）
    for link_data in item.links:
        existing = await db.execute(
            select(ResourceLink).where(
                ResourceLink.resource_id == resource.id,
                ResourceLink.url == link_data["url"],
            )
        )
        if existing.scalar_one_or_none() is None:
            link = ResourceLink(
                resource_id=resource.id,
                source_id=source_id,
                **{k: v for k, v in link_data.items() if v is not None},
            )
            db.add(link)

    return status


async def run_all_spiders():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source).where(Source.is_active == True))
        sources = result.scalars().all()

    for source in sources:
        await run_spider(source.id)
