"""
TMDb 元数据补全
GET /api/tmdb/search?q=xxx — 从 TMDb 搜索影片
POST /api/tmdb/enrich/{resource_id} — 用 TMDb 数据补全本地资源
需要 config.py 中设置 TMDB_API_KEY
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Resource
from config import settings
from typing import Optional

router = APIRouter(prefix="/api/tmdb", tags=["tmdb"])

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"


def verify_admin(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401)
    return True


async def tmdb_get(path: str, params: dict = None):
    if not settings.TMDB_API_KEY:
        raise HTTPException(status_code=503, detail="TMDB_API_KEY 未配置")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{TMDB_BASE}{path}",
            params={"api_key": settings.TMDB_API_KEY, "language": "zh-CN", **(params or {})},
        )
        resp.raise_for_status()
        return resp.json()


@router.get("/search")
async def tmdb_search(q: str, _=Depends(verify_admin)):
    data = await tmdb_get("/search/multi", {"query": q})
    results = []
    for item in data.get("results", [])[:10]:
        media_type = item.get("media_type", "movie")
        if media_type not in ("movie", "tv"):
            continue
        results.append({
            "tmdb_id": item["id"],
            "media_type": media_type,
            "title": item.get("title") or item.get("name", ""),
            "original_title": item.get("original_title") or item.get("original_name", ""),
            "year": (item.get("release_date") or item.get("first_air_date") or "")[:4],
            "rating": item.get("vote_average"),
            "poster_url": f"{TMDB_IMG}{item['poster_path']}" if item.get("poster_path") else None,
            "overview": item.get("overview", "")[:200],
        })
    return results


@router.post("/enrich/{resource_id}")
async def enrich_resource(
    resource_id: int,
    tmdb_id: int,
    media_type: str = "movie",
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404)

    if media_type == "movie":
        data = await tmdb_get(f"/movie/{tmdb_id}", {"append_to_response": "credits"})
        resource.title_en = data.get("title", "")
        resource.original_title = data.get("original_title", "")
        release = data.get("release_date", "")
        resource.year = int(release[:4]) if release else resource.year
        resource.duration = data.get("runtime")
        resource.rating = data.get("vote_average")
        resource.rating_count = data.get("vote_count")
        resource.synopsis = data.get("overview", "")
        if data.get("poster_path"):
            resource.poster_url = f"{TMDB_IMG}{data['poster_path']}"
        if data.get("backdrop_path"):
            resource.backdrop_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"
        resource.genre = "/".join(g["name"] for g in data.get("genres", [])[:3])
        resource.country = "/".join(c["name"] for c in data.get("production_countries", [])[:2])
        credits = data.get("credits", {})
        resource.directors = [p["name"] for p in credits.get("crew", []) if p.get("job") == "Director"][:3]
        resource.actors = [p["name"] for p in credits.get("cast", [])[:8]]
    else:
        data = await tmdb_get(f"/tv/{tmdb_id}", {"append_to_response": "credits"})
        resource.title_en = data.get("name", "")
        resource.original_title = data.get("original_name", "")
        air = data.get("first_air_date", "")
        resource.year = int(air[:4]) if air else resource.year
        resource.rating = data.get("vote_average")
        resource.rating_count = data.get("vote_count")
        resource.synopsis = data.get("overview", "")
        if data.get("poster_path"):
            resource.poster_url = f"{TMDB_IMG}{data['poster_path']}"
        if data.get("backdrop_path"):
            resource.backdrop_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"
        resource.genre = "/".join(g["name"] for g in data.get("genres", [])[:3])
        credits = data.get("credits", {})
        resource.directors = [
            p["name"] for p in credits.get("crew", [])
            if p.get("job") in ("Director", "Creator")
        ][:3]
        resource.actors = [p["name"] for p in credits.get("cast", [])[:8]]

    resource.tmdb_id = tmdb_id
    await db.commit()
    return {"message": "补全成功", "title": resource.title}
