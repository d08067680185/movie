import time
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import selectinload
from typing import Optional
from database import get_db
from models import Resource, ResourceLink, Source, SearchLog
from schemas import SearchResult, ResourceCardOut, ResourceDetailOut, ResourceLinkOut, StatsOut

router = APIRouter(prefix="/api", tags=["search"])

from config import CATEGORY_MAP

_ORDER_MAP = {
    "popular": [Resource.view_count.desc(), Resource.rating.desc().nulls_last()],
    "rating":  [Resource.rating.desc().nulls_last(), Resource.view_count.desc()],
    "newest":  [Resource.year.desc().nulls_last(), Resource.rating.desc().nulls_last()],
    "latest":  [Resource.id.desc()],
}

_stats_cache: Optional[dict] = None
_stats_cache_ts: float = 0.0
_STATS_TTL = 60.0


@router.get("/search", response_model=SearchResult)
async def search(
    q: str = Query("", description="搜索关键词"),
    category: Optional[str] = None,
    year: Optional[int] = None,
    genre: Optional[str] = None,
    min_rating: Optional[float] = None,
    has_links: Optional[bool] = None,
    sort: str = Query("popular", description="popular|rating|newest|latest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Resource)

    if q.strip():
        kw = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Resource.title.ilike(kw),
                Resource.title_en.ilike(kw),
                Resource.original_title.ilike(kw),
                Resource.directors.ilike(kw),
                Resource.actors.ilike(kw),
                Resource.synopsis.ilike(kw),
            )
        )
        ins = sqlite_insert(SearchLog).values(keyword=q.strip(), count=1)
        ins = ins.on_conflict_do_update(
            index_elements=["keyword"],
            set_={"count": SearchLog.count + 1, "last_searched": func.now()},
        )
        await db.execute(ins)
        await db.commit()

    if category:
        stmt = stmt.where(Resource.category == CATEGORY_MAP.get(category, category))

    if year:
        stmt = stmt.where(Resource.year == year)

    if genre:
        stmt = stmt.where(Resource.genre.ilike(f"%{genre}%"))

    if min_rating is not None:
        stmt = stmt.where(Resource.rating >= min_rating)

    if has_links is True:
        from sqlalchemy import exists
        stmt = stmt.where(
            exists().where(
                (ResourceLink.resource_id == Resource.id) & (ResourceLink.is_valid == True)
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    order_cols = _ORDER_MAP.get(sort, _ORDER_MAP["popular"])
    # 有搜索词时：精确标题匹配排在最前面
    if q.strip():
        from sqlalchemy import case
        exact = q.strip()
        relevance = case(
            (Resource.title == exact, 0),
            (Resource.title.ilike(exact), 1),
            (Resource.title.ilike(f"{exact}%"), 2),
            else_=3,
        )
        stmt = stmt.order_by(relevance, *order_cols)
    else:
        stmt = stmt.order_by(*order_cols)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    resources = (await db.execute(stmt)).scalars().all()

    # 获取每个资源的有效链接数量
    resource_ids = [r.id for r in resources]
    link_counts = {}
    if resource_ids:
        link_count_stmt = (
            select(ResourceLink.resource_id, func.count(ResourceLink.id))
            .where(ResourceLink.resource_id.in_(resource_ids))
            .where(ResourceLink.is_valid == True)
            .group_by(ResourceLink.resource_id)
        )
        for rid, cnt in (await db.execute(link_count_stmt)).all():
            link_counts[rid] = cnt

    items = []
    for r in resources:
        items.append(ResourceCardOut(
            id=r.id,
            title=r.title,
            title_en=r.title_en,
            year=r.year,
            category=r.category,
            genre=r.genre,
            rating=r.rating,
            poster_url=r.poster_url,
            link_count=link_counts.get(r.id, 0),
            view_count=r.view_count,
        ))

    return SearchResult(total=total, page=page, page_size=page_size, items=items)


@router.get("/resource/{resource_id}", response_model=ResourceDetailOut)
async def get_resource(resource_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException

    stmt = (
        select(Resource)
        .where(Resource.id == resource_id)
        .options(selectinload(Resource.links).selectinload(ResourceLink.source))
        .options(selectinload(Resource.tags))
    )
    resource = (await db.execute(stmt)).scalar_one_or_none()

    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    # 增加浏览次数
    await db.execute(update(Resource).where(Resource.id == resource_id).values(view_count=Resource.view_count + 1))
    await db.commit()

    links = []
    for link in resource.links:
        if link.is_valid:
            links.append(ResourceLinkOut(
                id=link.id,
                link_type=link.link_type,
                url=link.url,
                quality=link.quality,
                size=link.size,
                format=link.format,
                subtitle=link.subtitle,
                episode_info=link.episode_info,
                password=link.password,
                source_name=link.source.name if link.source else None,
            ))

    # 按画质排序
    quality_order = {"4K": 0, "1080P": 1, "720P": 2, "480P": 3, "HD": 4, "SD": 5}
    links.sort(key=lambda x: quality_order.get(x.quality or "", 99))

    return ResourceDetailOut(
        id=resource.id,
        title=resource.title,
        title_en=resource.title_en,
        original_title=resource.original_title,
        year=resource.year,
        category=resource.category,
        genre=resource.genre,
        country=resource.country,
        language=resource.language,
        duration=resource.duration,
        rating=resource.rating,
        rating_count=resource.rating_count,
        synopsis=resource.synopsis,
        poster_url=resource.poster_url,
        backdrop_url=resource.backdrop_url,
        directors=resource.directors or [],
        actors=resource.actors or [],
        view_count=resource.view_count,
        imdb_id=resource.imdb_id,
        links=links,
        tags=[t.name for t in resource.tags],
    )


@router.get("/hot", response_model=list)
async def get_hot(db: AsyncSession = Depends(get_db)):
    """获取热门资源"""
    stmt = (
        select(Resource)
        .order_by(Resource.view_count.desc(), Resource.rating.desc().nulls_last())
        .limit(12)
    )
    resources = (await db.execute(stmt)).scalars().all()

    resource_ids = [r.id for r in resources]
    link_counts = {}
    if resource_ids:
        link_count_stmt = (
            select(ResourceLink.resource_id, func.count(ResourceLink.id))
            .where(ResourceLink.resource_id.in_(resource_ids))
            .where(ResourceLink.is_valid == True)
            .group_by(ResourceLink.resource_id)
        )
        for rid, cnt in (await db.execute(link_count_stmt)).all():
            link_counts[rid] = cnt

    return [
        ResourceCardOut(
            id=r.id,
            title=r.title,
            title_en=r.title_en,
            year=r.year,
            category=r.category,
            genre=r.genre,
            rating=r.rating,
            poster_url=r.poster_url,
            link_count=link_counts.get(r.id, 0),
            view_count=r.view_count,
        )
        for r in resources
    ]


@router.get("/stats", response_model=StatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)):
    global _stats_cache, _stats_cache_ts
    if _stats_cache is not None and (time.time() - _stats_cache_ts) < _STATS_TTL:
        return _stats_cache

    total_resources = (await db.execute(select(func.count(Resource.id)))).scalar()
    total_links = (await db.execute(select(func.count(ResourceLink.id)))).scalar()
    total_sources = (await db.execute(select(func.count(Source.id)).where(Source.is_active == True))).scalar()

    cat_stmt = select(Resource.category, func.count(Resource.id)).group_by(Resource.category)
    categories = {}
    for cat, cnt in (await db.execute(cat_stmt)).all():
        categories[cat or "未分类"] = cnt

    result = StatsOut(
        total_resources=total_resources,
        total_links=total_links,
        total_sources=total_sources,
        categories=categories,
    )
    _stats_cache = result
    _stats_cache_ts = time.time()
    return result


@router.get("/latest", response_model=list)
async def get_latest(db: AsyncSession = Depends(get_db)):
    """最新入库资源（按 id 倒序取 12 条有封面的）"""
    stmt = (
        select(Resource)
        .where(Resource.poster_url != None)
        .order_by(Resource.id.desc())
        .limit(12)
    )
    resources = (await db.execute(stmt)).scalars().all()
    resource_ids = [r.id for r in resources]
    link_counts: dict = {}
    if resource_ids:
        lc_stmt = (
            select(ResourceLink.resource_id, func.count(ResourceLink.id))
            .where(ResourceLink.resource_id.in_(resource_ids))
            .where(ResourceLink.is_valid == True)
            .group_by(ResourceLink.resource_id)
        )
        for rid, cnt in (await db.execute(lc_stmt)).all():
            link_counts[rid] = cnt
    return [
        ResourceCardOut(
            id=r.id, title=r.title, title_en=r.title_en,
            year=r.year, category=r.category, genre=r.genre,
            rating=r.rating, poster_url=r.poster_url,
            link_count=link_counts.get(r.id, 0), view_count=r.view_count,
        )
        for r in resources
    ]


@router.get("/hot-searches")
async def hot_searches(limit: int = 8, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchLog).order_by(SearchLog.count.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [{"keyword": l.keyword, "count": l.count} for l in logs]


@router.get("/related/{resource_id}")
async def get_related(resource_id: int, db: AsyncSession = Depends(get_db)):
    resource = await db.get(Resource, resource_id)
    if not resource:
        return []

    import re as _re

    base = _re.sub(r'[\s\(（\[【第\d季部集合].*$', '', resource.title).strip()
    short = base[:4] if len(base) >= 4 else base

    related: list = []

    # 1. 同标题前缀（续集/合集）
    if short:
        kw = f"%{short}%"
        stmt1 = (
            select(Resource)
            .where(Resource.id != resource_id)
            .where(Resource.title.ilike(kw))
            .order_by(Resource.rating.desc().nulls_last())
            .limit(6)
        )
        related = list((await db.execute(stmt1)).scalars().all())

    # 2. 同 genre（补足到 6 个）
    if len(related) < 6 and resource.genre:
        seen = {r.id for r in related} | {resource_id}
        genre_word = resource.genre.split()[0] if resource.genre else ""
        stmt2 = (
            select(Resource)
            .where(Resource.id.notin_(seen))
            .where(Resource.genre.ilike(f"%{genre_word}%"))
            .order_by(Resource.rating.desc().nulls_last())
            .limit(6 - len(related))
        )
        related += list((await db.execute(stmt2)).scalars().all())

    # 3. 兜底：同分类高评分
    if len(related) < 6:
        seen = {r.id for r in related} | {resource_id}
        stmt3 = (
            select(Resource)
            .where(Resource.id.notin_(seen))
            .where(Resource.category == resource.category)
            .order_by(Resource.rating.desc().nulls_last())
            .limit(6 - len(related))
        )
        related += list((await db.execute(stmt3)).scalars().all())

    resource_ids = [r.id for r in related]
    link_counts: dict = {}
    if resource_ids:
        lc_stmt = (
            select(ResourceLink.resource_id, func.count(ResourceLink.id))
            .where(ResourceLink.resource_id.in_(resource_ids))
            .where(ResourceLink.is_valid == True)
            .group_by(ResourceLink.resource_id)
        )
        for rid, cnt in (await db.execute(lc_stmt)).all():
            link_counts[rid] = cnt

    return [
        ResourceCardOut(
            id=r.id, title=r.title, title_en=r.title_en,
            year=r.year, category=r.category, genre=r.genre,
            rating=r.rating, poster_url=r.poster_url,
            link_count=link_counts.get(r.id, 0), view_count=r.view_count,
        )
        for r in related
    ]
