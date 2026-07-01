from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, text
from sqlalchemy.orm import selectinload
from typing import Optional, List
from database import get_db
from models import Source, SpiderLog, Resource, ResourceLink, SearchLog
from schemas import SourceOut, SpiderLogOut, ResourceCreate, LinkCreate, BatchResourceIn, BatchImportResult
from spiders.scheduler import run_spider
from config import settings, CATEGORY_MAP as _CAT_NORM
import tasks as task_registry
from utils import backup_db, list_backups, send_telegram
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


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404)
    await db.delete(source)
    await db.commit()
    return {"message": "已删除"}


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


@router.patch("/resources/{resource_id}")
async def update_resource(
    resource_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404)
    editable = ["title", "title_en", "year", "category", "genre", "country", "synopsis", "poster_url", "rating"]
    for field in editable:
        if field in data and data[field] is not None:
            val = data[field]
            if field == "category":
                val = _CAT_NORM.get(val, val)
            setattr(resource, field, val)
    await db.commit()
    return {"message": "已更新"}


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
    no_poster: Optional[bool] = None,
    no_links: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    from sqlalchemy import func, exists
    stmt = select(Resource)
    if q:
        stmt = stmt.where(Resource.title.contains(q))
    if category:
        stmt = stmt.where(Resource.category == category)
    if no_poster:
        stmt = stmt.where(Resource.poster_url == None)
    if no_links:
        stmt = stmt.where(
            ~exists().where(
                (ResourceLink.resource_id == Resource.id) & (ResourceLink.is_valid == True)
            )
        )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
    stmt = (stmt.options(selectinload(Resource.links))
                .order_by(Resource.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size))
    items = (await db.execute(stmt)).scalars().all()
    result = []
    for r in items:
        valid_count = sum(1 for l in r.links if l.is_valid)
        result.append({
            "id": r.id, "title": r.title, "year": r.year,
            "category": r.category, "poster_url": r.poster_url,
            "rating": r.rating, "link_count": valid_count,
            "links": [{"id": l.id, "url": l.url, "link_type": l.link_type,
                        "password": l.password, "quality": l.quality, "is_valid": l.is_valid} for l in r.links]
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/search-logs")
async def get_search_logs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    result = await db.execute(
        select(SearchLog).order_by(SearchLog.count.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [{"keyword": l.keyword, "count": l.count,
             "last_searched": l.last_searched.isoformat() if l.last_searched else None}
            for l in logs]


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
    await db.delete(link)
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


@router.post("/set-tmdb-key")
async def set_tmdb_key(payload: dict, _=Depends(verify_admin)):
    """设置 TMDb API Key，写入 .env 并更新内存"""
    key = payload.get("api_key", "").strip()
    settings.TMDB_API_KEY = key or None
    env_path = ".env"
    try:
        import os
        lines = []
        found = False
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    if line.startswith("TMDB_API_KEY="):
                        lines.append(f"TMDB_API_KEY={key}\n")
                        found = True
                    else:
                        lines.append(line)
        if not found:
            lines.append(f"TMDB_API_KEY={key}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)
        return {"message": "TMDb API Key 已更新", "configured": bool(key)}
    except Exception as e:
        return {"message": "Key 已更新（本次重启有效）", "configured": bool(key), "warning": str(e)}


@router.get("/tmdb-key-status")
async def get_tmdb_key_status(_=Depends(verify_admin)):
    """检查 TMDb API Key 是否已配置"""
    return {"configured": bool(settings.TMDB_API_KEY)}


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


@router.get("/tasks")
async def get_tasks(_=Depends(verify_admin)):
    """A: 返回后台任务进度列表"""
    task_registry.clear_old_tasks()
    return task_registry.get_tasks()


@router.get("/duplicates")
async def get_duplicates(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    """B: 找出重复标题的资源（按标题+年份去重）"""
    stmt = text("""
        SELECT title, year, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
        FROM resources
        GROUP BY title, year
        HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT :limit
    """)
    rows = (await db.execute(stmt, {"limit": limit})).fetchall()
    result = []
    for row in rows:
        ids = [int(i) for i in row.ids.split(",")]
        resources = (await db.execute(
            select(Resource).where(Resource.id.in_(ids)).options(selectinload(Resource.links))
        )).scalars().all()
        result.append({
            "title": row.title,
            "year": row.year,
            "count": row.cnt,
            "resources": [{
                "id": r.id, "title": r.title, "year": r.year,
                "category": r.category, "poster_url": r.poster_url,
                "link_count": len(r.links),
            } for r in resources],
        })
    return result


@router.post("/resources/{keep_id}/merge/{dup_id}")
async def merge_resources(
    keep_id: int,
    dup_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    """B: 将 dup_id 的链接合并到 keep_id，然后删除 dup_id"""
    keep = await db.get(Resource, keep_id)
    dup = await db.get(Resource, dup_id)
    if not keep or not dup:
        raise HTTPException(status_code=404, detail="资源不存在")

    # 移动链接（URL去重）
    dup_links = (await db.execute(
        select(ResourceLink).where(ResourceLink.resource_id == dup_id)
    )).scalars().all()
    keep_urls = set(r[0] for r in (await db.execute(
        select(ResourceLink.url).where(ResourceLink.resource_id == keep_id)
    )).all())

    moved = 0
    for lk in dup_links:
        if lk.url not in keep_urls:
            lk.resource_id = keep_id
            keep_urls.add(lk.url)
            moved += 1
        else:
            await db.delete(lk)

    # 补全缺失元数据
    for field in ("poster_url", "synopsis", "rating", "genre", "country", "directors", "actors"):
        if not getattr(keep, field) and getattr(dup, field):
            setattr(keep, field, getattr(dup, field))

    await db.flush()
    await db.execute(delete(Resource).where(Resource.id == dup_id))
    await db.commit()
    return {"message": f"已合并：移动 {moved} 条链接，删除资源 {dup_id}"}


@router.post("/check-links")
async def check_links(
    max_per_run: int = 30,
    _=Depends(verify_admin),
):
    """C: 对网盘链接发送 HEAD 请求，将无法访问的标记为失效"""
    from database import AsyncSessionLocal
    task_id = f"check_links_{int(asyncio.get_event_loop().time())}"
    task_registry.start_task(task_id, f"链接有效性检测（最多 {max_per_run} 条）", total=max_per_run)

    async def _run():
        import aiohttp
        pan_types = {"pan_quark", "pan_baidu", "pan_aliyun", "direct"}
        # 独立 session 加载链接列表
        async with AsyncSessionLocal() as fetch_db:
            stmt = (select(ResourceLink)
                    .where(ResourceLink.is_valid == True, ResourceLink.link_type.in_(pan_types))
                    .order_by(func.random())
                    .limit(max_per_run))
            link_rows = (await fetch_db.execute(stmt)).scalars().all()
            links = [(lk.id, lk.url) for lk in link_rows]

        invalid_count = 0
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(headers=headers) as session:
            for i, (link_id, url) in enumerate(links):
                try:
                    async with session.head(url, timeout=aiohttp.ClientTimeout(total=8), allow_redirects=True) as resp:
                        if resp.status in (404, 403, 410):
                            async with AsyncSessionLocal() as inner_db:
                                link = await inner_db.get(ResourceLink, link_id)
                                if link:
                                    link.is_valid = False
                                    await inner_db.commit()
                            invalid_count += 1
                except Exception:
                    pass
                task_registry.update_task(task_id, done=i + 1, message=f"已检测 {i+1}/{len(links)}，失效 {invalid_count} 条")

        task_registry.finish_task(task_id, "success", f"检测完成：{len(links)} 条，失效 {invalid_count} 条")


    asyncio.create_task(_run())
    return {"message": f"链接检测已启动，任务 ID: {task_id}", "task_id": task_id}


@router.post("/backup")
async def create_backup(_=Depends(verify_admin)):
    """E: 创建数据库备份"""
    try:
        path = backup_db()
        return {"message": f"备份成功：{path}", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backups")
async def get_backups(_=Depends(verify_admin)):
    """E: 列出历史备份"""
    return list_backups()


@router.post("/telegram-config")
async def set_telegram_config(payload: dict, _=Depends(verify_admin)):
    """E: 配置 Telegram 通知"""
    token = payload.get("bot_token", "").strip()
    chat_id = payload.get("chat_id", "").strip()
    settings.TELEGRAM_BOT_TOKEN = token or None
    settings.TELEGRAM_CHAT_ID = chat_id or None
    env_path = ".env"
    try:
        import os
        lines = []
        existing = set()
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        lines.append(f"TELEGRAM_BOT_TOKEN={token}\n")
                        existing.add("token")
                    elif line.startswith("TELEGRAM_CHAT_ID="):
                        lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
                        existing.add("chat_id")
                    else:
                        lines.append(line)
        if "token" not in existing:
            lines.append(f"TELEGRAM_BOT_TOKEN={token}\n")
        if "chat_id" not in existing:
            lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)
    except Exception:
        pass

    if token and chat_id:
        await send_telegram("✅ 影视搜索系统 Telegram 通知已配置成功！")
        return {"message": "已配置，测试消息已发送"}
    return {"message": "已清除 Telegram 配置"}


@router.get("/telegram-status")
async def telegram_status(_=Depends(verify_admin)):
    return {
        "configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
        "has_token": bool(settings.TELEGRAM_BOT_TOKEN),
        "has_chat_id": bool(settings.TELEGRAM_CHAT_ID),
    }


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
