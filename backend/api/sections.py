"""板块列表：/api/sections 供前端导航/首页/搜索页读取(替代原来写死的4个影视分类)。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Section, Category, Resource

router = APIRouter(prefix="/api", tags=["sections"])


@router.get("/sections")
async def list_sections(db: AsyncSession = Depends(get_db)):
    sections = (
        (await db.execute(select(Section).order_by(Section.sort_order)))
        .scalars()
        .all()
    )
    if not sections:
        return []

    count_rows = (
        await db.execute(
            select(Resource.section_id, func.count(Resource.id)).group_by(Resource.section_id)
        )
    ).all()
    counts = {sid: cnt for sid, cnt in count_rows}

    cat_rows = (
        await db.execute(select(Category).order_by(Category.sort_order))
    ).scalars().all()
    cats_by_section: dict = {}
    for c in cat_rows:
        cats_by_section.setdefault(c.section_id, []).append({"id": c.id, "name": c.name})

    return [
        {
            "id": s.id,
            "key": s.key,
            "name": s.name,
            "icon": s.icon,
            "resource_count": counts.get(s.id, 0),
            "categories": cats_by_section.get(s.id, []),
        }
        for s in sections
    ]
