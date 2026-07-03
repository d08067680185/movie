"""
TMDb 批量导入爬虫
从 TMDb 批量拉取影视元数据写入数据库（仅元数据，无下载链接）

配置示例:
{
  "api_key": "",           // 留空则用 settings.TMDB_API_KEY
  "media_type": "both",    // movie | tv | both
  "list_type": "popular",  // popular | now_playing | top_rated | upcoming | trending
  "pages": 5,
  "min_rating": 6.0,
  "language": "zh-CN",
  "region": "CN"
}
"""
import asyncio
import logging
from typing import List, Optional
from spiders.base import BaseSpider, ResourceItem
from config import settings

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
IMG_W500  = "https://image.tmdb.org/t/p/w500"
IMG_W1280 = "https://image.tmdb.org/t/p/w1280"


class TMDbBatchSpider(BaseSpider):
    name = "tmdb_batch"
    base_url = TMDB_BASE

    def _key(self) -> str:
        k = self.config.get("api_key") or settings.TMDB_API_KEY
        if not k:
            raise RuntimeError("未配置 TMDB_API_KEY，请在 .env 中设置或在数据源 config.api_key 中传入")
        return k

    async def _tmdb(self, path: str, extra: dict = None) -> dict:
        params = {
            "api_key": self._key(),
            "language": self.config.get("language", "zh-CN"),
        }
        if extra:
            params.update(extra)
        resp = await self.client.get(f"{TMDB_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── 电影详情 ──────────────────────────────────────────────
    async def _movie_detail(self, tmdb_id: int) -> Optional[ResourceItem]:
        try:
            d = await self._tmdb(f"/movie/{tmdb_id}", {"append_to_response": "credits"})
            await asyncio.sleep(0.25)
        except Exception as e:
            logger.warning(f"TMDb movie {tmdb_id}: {e}")
            return None

        credits  = d.get("credits", {})
        directors = [p["name"] for p in credits.get("crew", []) if p.get("job") == "Director"][:3]
        actors    = [p["name"] for p in credits.get("cast", [])[:8]]
        release   = d.get("release_date", "")
        year      = int(release[:4]) if len(release) >= 4 else None
        genres    = "/".join(g["name"] for g in d.get("genres", [])[:4])
        countries = "/".join(c["iso_3166_1"] for c in d.get("production_countries", [])[:2])
        lang      = d.get("original_language", "")

        item = ResourceItem(
            title      = d.get("title", ""),
            year       = year,
            category   = "movie",
            genre      = genres or None,
            country    = countries or None,
            rating     = round(d.get("vote_average", 0), 1) or None,
            synopsis   = (d.get("overview") or "")[:500] or None,
            poster_url = f"{IMG_W500}{d['poster_path']}"  if d.get("poster_path")  else None,
            directors  = directors,
            actors     = actors,
        )
        item._tmdb_id      = tmdb_id
        item._title_en     = d.get("original_title", "")
        item._imdb_id      = d.get("imdb_id", "")
        item._language     = lang
        item._duration     = d.get("runtime")
        item._rating_count = d.get("vote_count", 0)
        item._backdrop_url = f"{IMG_W1280}{d['backdrop_path']}" if d.get("backdrop_path") else None
        return item

    # ── 剧集详情 ──────────────────────────────────────────────
    async def _tv_detail(self, tmdb_id: int) -> Optional[ResourceItem]:
        try:
            d = await self._tmdb(f"/tv/{tmdb_id}", {"append_to_response": "aggregate_credits"})
            await asyncio.sleep(0.25)
        except Exception as e:
            logger.warning(f"TMDb tv {tmdb_id}: {e}")
            return None

        credits  = d.get("aggregate_credits", {})
        actors   = [p["name"] for p in credits.get("cast", [])[:8]]
        creators = [c["name"] for c in d.get("created_by", [])[:3]]
        air      = d.get("first_air_date", "")
        year     = int(air[:4]) if len(air) >= 4 else None
        genres   = "/".join(g["name"] for g in d.get("genres", [])[:4])
        # 动漫判断：日本 + 动画类型 (id=16)
        genre_ids = [g["id"] for g in d.get("genres", [])]
        origin    = d.get("origin_country", [])
        category  = "anime" if (16 in genre_ids and "JP" in origin) else "tv"
        countries = "/".join(origin[:2])

        item = ResourceItem(
            title      = d.get("name", ""),
            year       = year,
            category   = category,
            genre      = genres or None,
            country    = countries or None,
            rating     = round(d.get("vote_average", 0), 1) or None,
            synopsis   = (d.get("overview") or "")[:500] or None,
            poster_url = f"{IMG_W500}{d['poster_path']}"  if d.get("poster_path")  else None,
            directors  = creators,
            actors     = actors,
        )
        item._tmdb_id      = tmdb_id
        item._title_en     = d.get("original_name", "")
        item._language     = d.get("original_language", "")
        item._rating_count = d.get("vote_count", 0)
        item._backdrop_url = f"{IMG_W1280}{d['backdrop_path']}" if d.get("backdrop_path") else None
        item._duration     = d.get("episode_run_time", [None])[0]
        return item

    # ── 主爬取逻辑 ────────────────────────────────────────────
    async def crawl(self, page: int = 1) -> List[ResourceItem]:
        media_type = self.config.get("media_type", "both")   # movie | tv | both
        list_type  = self.config.get("list_type", "popular")
        min_rating = float(self.config.get("min_rating", 6.0))
        region     = self.config.get("region", "CN")

        mtypes = ["movie", "tv"] if media_type == "both" else [media_type]
        items: List[ResourceItem] = []

        for mtype in mtypes:
            # 构建列表接口
            if list_type == "trending":
                path   = f"/trending/{mtype}/week"
                extra  = {"page": page}
            elif list_type == "now_playing" and mtype == "tv":
                path, extra = "/tv/on_the_air", {"page": page}
            elif list_type == "upcoming" and mtype == "tv":
                path, extra = "/tv/popular", {"page": page}
            else:
                path   = f"/{mtype}/{list_type}"
                extra  = {"page": page, "region": region}

            try:
                data = await self._tmdb(path, extra)
            except Exception as e:
                logger.error(f"TMDb list {path} p{page}: {e}")
                continue

            results = data.get("results", [])
            logger.info(f"TMDb {mtype}/{list_type} p{page}: {len(results)} entries")

            for r in results:
                if r.get("vote_average", 0) < min_rating:
                    continue
                tmdb_id = r["id"]
                if mtype == "movie":
                    item = await self._movie_detail(tmdb_id)
                else:
                    item = await self._tv_detail(tmdb_id)
                if item and item.title:
                    items.append(item)

        return items
