from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import Optional, List
from database import get_db
from models import Source, SpiderLog, Resource, ResourceLink
from schemas import SourceOut, SpiderLogOut, ResourceCreate, LinkCreate, BatchResourceIn, BatchImportResult
from spiders.scheduler import run_spider
from config import settings, CATEGORY_MAP as _CAT_NORM
import asyncio

router = APIRouter(prefix="/api/admin", tags=["admin"])


def verify_admin(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(select(Source).order_by(Source.id))
    return result.scalars().all()


@router.post("/sources", response_model=SourceOut)
async def create_source(
    name: str,
    spider_class: str,
    base_url: Optional[str] = None,
    config: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    source = Source(name=name, spider_class=spider_class, base_url=base_url, config=config or {})
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.patch("/sources/{source_id}/toggle")
async def toggle_source(source_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404)
    source.is_active = not source.is_active
    await db.commit()
    return {"is_active": source.is_active}


@router.post("/sources/{source_id}/run")
async def trigger_spider(source_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404)
    asyncio.create_task(run_spider(source_id))
    return {"message": f"Spider '{source.name}' triggered"}


@router.get("/logs", response_model=list[SpiderLogOut])
async def list_logs(limit: int = 20, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    result = await db.execute(
        select(SpiderLog).order_by(SpiderLog.started_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.post("/resources", response_model=dict)
async def create_resource(data: ResourceCreate, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    dump = data.model_dump(exclude_none=True)
    if "category" in dump:
        dump["category"] = _CAT_NORM.get(dump["category"], dump["category"])
    resource = Resource(**dump)
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return {"id": resource.id, "title": resource.title}


@router.delete("/resources/{resource_id}")
async def delete_resource(resource_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404)
    await db.execute(delete(ResourceLink).where(ResourceLink.resource_id == resource_id))
    await db.execute(delete(Resource).where(Resource.id == resource_id))
    await db.commit()
    return {"message": "deleted"}


@router.post("/links", response_model=dict)
async def create_link(data: LinkCreate, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    # 若 source_id 对应的 Source 不存在，自动使用/创建"手动导入"
    src = await db.get(Source, data.source_id)
    if not src:
        src = (await db.execute(select(Source).where(Source.name == "手动导入"))).scalar_one_or_none()
        if not src:
            src = Source(name="手动导入", spider_class="manual", is_active=True, config={})
            db.add(src)
            await db.flush()
        data = data.model_copy(update={"source_id": src.id})
    link = ResourceLink(**data.model_dump(exclude_none=True))
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return {"id": link.id}


@router.get("/resources")
async def list_resources(
    q: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    from sqlalchemy import func
    stmt = select(Resource)
    if q:
        stmt = stmt.where(Resource.title.contains(q))
    if category:
        stmt = stmt.where(Resource.category == category)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
    stmt = (stmt.options(selectinload(Resource.links))
                .order_by(Resource.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size))
    items = (await db.execute(stmt)).scalars().all()
    result = []
    for r in items:
        result.append({
            "id": r.id, "title": r.title, "year": r.year,
            "category": r.category, "poster_url": r.poster_url,
            "rating": r.rating, "link_count": len(r.links),
            "links": [{"id": l.id, "url": l.url, "link_type": l.link_type,
                        "password": l.password, "quality": l.quality, "is_valid": l.is_valid} for l in r.links]
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.patch("/links/{link_id}")
async def update_link(
    link_id: int,
    url: Optional[str] = None,
    link_type: Optional[str] = None,
    password: Optional[str] = None,
    quality: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    link = await db.get(ResourceLink, link_id)
    if not link:
        raise HTTPException(status_code=404)
    if url is not None: link.url = url
    if link_type is not None: link.link_type = link_type
    if password is not None: link.password = password
    if quality is not None: link.quality = quality
    await db.commit()
    return {"message": "已更新"}


@router.delete("/links/{link_id}")
async def delete_link(link_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    link = await db.get(ResourceLink, link_id)
    if not link:
        raise HTTPException(status_code=404)
    db.delete(link)
    await db.commit()
    return {"message": "已删除"}


@router.patch("/links/{link_id}/invalidate")
async def invalidate_link(link_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    link = await db.get(ResourceLink, link_id)
    if not link:
        raise HTTPException(status_code=404)
    link.is_valid = False
    await db.commit()
    return {"message": "marked invalid"}


@router.patch("/links/{link_id}/validate")
async def validate_link(link_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    link = await db.get(ResourceLink, link_id)
    if not link:
        raise HTTPException(status_code=404)
    link.is_valid = True
    await db.commit()
    return {"message": "marked valid"}


@router.post("/bangumi-enrich")
async def trigger_bangumi_enrich(
    max_per_run: int = 50,
    delay: float = 1.0,
    overwrite: bool = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    """触发 Bangumi 批量补全：封面图、评分、简介、年份"""
    from spiders.sources.bangumi import run_bangumi_enrich
    src = (await db.execute(select(Source).where(Source.name == "Bangumi补全"))).scalar_one_or_none()
    if not src:
        src = Source(name="Bangumi补全", spider_class="bangumi", is_active=True, config={})
        db.add(src)
        await db.commit()
        await db.refresh(src)
    config = {"max_per_run": max_per_run, "delay": delay, "overwrite": overwrite, "source_id": src.id}
    asyncio.create_task(run_bangumi_enrich(config))
    return {"message": f"Bangumi 补全已触发，将处理最多 {max_per_run} 条动漫"}


@router.get("/spider-classes")
async def list_spider_classes(_=Depends(verify_admin)):
    from spiders import SPIDER_REGISTRY
    return list(SPIDER_REGISTRY.keys())


@router.post("/pan-search")
async def trigger_pan_search(
    source_id: int,
    max_per_run: int = 20,
    min_links: int = 0,
    pan_types: str = "quark,baidu",
    delay: float = 3.0,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    """
    触发网盘链接搜索：对数据库中无下载链接的影视资源，
    通过 Bing 搜索寻找夸克/百度网盘公开分享链接。
    source_id: pan_search 类型数据源的 ID
    pan_types: 逗号分隔，支持 quark,baidu,aliyun
    """
    from spiders.sources.pan_search import run_pan_search
    config = {
        "max_per_run": max_per_run,
        "min_links": min_links,
        "pan_types": [p.strip() for p in pan_types.split(",")],
        "delay": delay,
    }
    asyncio.create_task(run_pan_search(source_id, config))
    return {"message": f"网盘搜索已触发，将处理最多 {max_per_run} 个资源"}


@router.post("/sources/create-tmdb")
async def create_tmdb_source(
    name: str = "TMDb 热门影视",
    media_type: str = "both",
    list_type: str = "popular",
    pages: int = 5,
    min_rating: float = 6.0,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    """快速创建 TMDb 批量导入数据源"""
    source = Source(
        name=name,
        base_url="https://api.themoviedb.org/3",
        spider_class="tmdb_batch",
        is_active=True,
        config={
            "media_type": media_type,
            "list_type": list_type,
            "pages": pages,
            "min_rating": min_rating,
            "language": "zh-CN",
            "region": "CN",
        },
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {"id": source.id, "name": source.name, "message": "创建成功，可立即触发爬取"}


@router.post("/change-password")
async def change_password(
    payload: dict,
    _=Depends(verify_admin),
):
    new_password: str = payload.get("new_password", "")
    """修改管理员密码，写入 .env 并更新内存"""
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    settings.ADMIN_PASSWORD = new_password
    env_path = ".env"
    try:
        import os
        lines = []
        found = False
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    if line.startswith("ADMIN_PASSWORD="):
                        lines.append(f"ADMIN_PASSWORD={new_password}\n")
                        found = True
                    else:
                        lines.append(line)
        if not found:
            lines.append(f"ADMIN_PASSWORD={new_password}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)
        return {"message": "密码已修改，已持久化到 .env"}
    except Exception as e:
        return {"message": "密码已修改（本次重启有效）", "warning": f".env 写入失败，重启后将恢复旧密码：{e}"}


@router.post("/batch-import", response_model=BatchImportResult)
async def batch_import(
    items: List[BatchResourceIn],
    source_name: str = "手动导入",
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    """
    批量导入资源+链接。
    - 按标题+年份去重（已存在则追加链接，不覆盖元数据）
    - link_type: pan_quark / pan_baidu / pan_aliyun / magnet / direct
    """
    # 确保有一个"手动导入"数据源
    src = (await db.execute(select(Source).where(Source.name == source_name))).scalar_one_or_none()
    if not src:
        src = Source(name=source_name, spider_class="manual", is_active=True, config={})
        db.add(src)
        await db.commit()
        await db.refresh(src)

    created = updated = links_added = skipped = 0
    errors = []

    for item in items:
        try:
            # 查找已有资源（标题匹配）
            stmt = select(Resource).where(Resource.title == item.title)
            if item.year:
                stmt = stmt.where(Resource.year == item.year)
            existing = (await db.execute(stmt)).scalars().first()

            if existing:
                res = existing
                updated += 1  # 已存在，追加链接；不覆盖元数据
            else:
                cat = _CAT_NORM.get(item.category, item.category)
                if item.category not in _CAT_NORM and item.category not in _CAT_NORM.values():
                    errors.append(f"未知分类 '{item.category}'，已原样存入")
                res = Resource(
                    title=item.title,
                    year=item.year,
                    category=cat,
                    genre=item.genre,
                    country=item.country,
                    synopsis=item.synopsis,
                    poster_url=item.poster_url,
                    rating=item.rating,
                )
                db.add(res)
                await db.flush()
                created += 1

            # 写入链接（URL 去重）
            existing_urls = set(
                r[0] for r in (await db.execute(
                    select(ResourceLink.url).where(ResourceLink.resource_id == res.id)
                )).all()
            )
            for lk in item.links:
                if lk.url in existing_urls:
                    continue
                db.add(ResourceLink(
                    resource_id=res.id,
                    source_id=src.id,
                    url=lk.url,
                    link_type=lk.link_type,
                    quality=lk.quality,
                    episode_info=lk.episode_info,
                    password=lk.password,
                    is_valid=True,
                ))
                existing_urls.add(lk.url)
                links_added += 1

            await db.commit()
        except Exception as e:
            await db.rollback()
            errors.append(f"{item.title}: {e}")
            skipped += 1

    return BatchImportResult(created=created, updated=updated, links_added=links_added, skipped=skipped, errors=errors)


@router.post("/sources/create-pan-search")
async def create_pan_search_source(
    name: str = "网盘链接搜索",
    pan_types: str = "quark,baidu",
    delay: float = 3.0,
    max_per_run: int = 20,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    """快速创建网盘搜索数据源"""
    source = Source(
        name=name,
        base_url="https://www.bing.com",
        spider_class="pan_search",
        is_active=True,
        config={
            "pan_types": [p.strip() for p in pan_types.split(",")],
            "delay": delay,
            "max_per_run": max_per_run,
        },
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {"id": source.id, "name": source.name, "message": "创建成功"}
