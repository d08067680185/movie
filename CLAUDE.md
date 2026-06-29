# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (FastAPI + Python 3.14)
```bash
cd backend

# Start dev server
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Install dependencies
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# One-shot DB check
venv/bin/python3 -c "
import asyncio
from database import AsyncSessionLocal, init_db
from sqlalchemy import select, func
from models import Resource
async def check():
    await init_db()
    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(func.count(Resource.id)))).scalar()
        print('resources:', n)
asyncio.run(check())
"

# Direct DB inspection
sqlite3 movie_search.db "SELECT DISTINCT category FROM resources;"
```

### Frontend (Next.js 16 + React 19 + Tailwind 4)
```bash
cd frontend
npm run dev       # http://localhost:3000
npm run build
npm run lint
```

### Start/stop both
```bash
bash start.sh     # nohup, logs to /tmp/movie-search-*.log
bash stop.sh
```

## Critical: Category Values

**The DB stores Chinese category values** ("电影", "电视剧", "动漫", "综艺"), not English.

- URL params and spider `ResourceItem.category` use English ("movie", "tv", "anime", "variety")
- `CATEGORY_MAP` in `api/search.py` translates URL params → DB values at query time
- `_CAT_NORM` in `spiders/scheduler.py` translates spider output → DB values at write time
- `batch-import` in `api/admin.py` also applies normalization before writing
- `CATEGORY_LABELS` and `CATEGORY_COLORS` in `frontend/src/lib/utils.ts` carry **both** English and Chinese keys so they work regardless of source

Any new code querying or writing `Resource.category` must respect this. Adding a new path that stores English values will silently break search filters and category badges.

## Architecture

### Data flow
```
User search → Next.js → GET /api/search?q=&category=anime&sort=rating → FastAPI
  → CATEGORY_MAP translates "anime"→"动漫" → SQLite query → ResourceCard[]
Detail page → GET /api/resource/{id} → increments view_count, returns ResourceDetail with links
```

### Backend structure

**`models.py`** — five SQLAlchemy models:
- `Resource` — canonical record (title, year, category, poster_url, rating, synopsis, tmdb_id, etc.)
- `ResourceLink` — download links (url, link_type, password, quality, is_valid). `is_valid=False` hides a link from the detail page without deleting it.
- `Source` — data source config with `spider_class` name + `config` JSON
- `SpiderLog` — per-run log (status: running/success/failed)
- `SearchLog` — hot-search counter, upserted on every non-empty search hit

**`api/search.py`** — public router (`/api`):
- `GET /search` — supports `q`, `category` (English), `year`, `genre` (ilike substring), `sort` (popular/rating/newest/latest), `page`
- `GET /stats` — 60s in-memory cache (`_stats_cache` module global); safe for single-worker uvicorn only
- `_ORDER_MAP` — module-level dict mapping sort param → SQLAlchemy `order_by()` columns

**`api/admin.py`** — protected by `X-Admin-Token` header (default `admin123`):
- Batch import: dedup by title + year using `scalars().first()` (not `scalar_one_or_none()`, which raises on multiple matches)
- Delete resource: explicitly deletes `ResourceLink` rows first, then `Resource` (cascade not reliable via async execute)
- `invalidate_link` sets `is_valid=False`; `update_link` (PATCH) does NOT touch `is_valid`

**Spider system (`spiders/`)**:
- `SPIDER_REGISTRY` in `__init__.py` — maps `spider_class` string → class; register new spiders here
- `scheduler.py` — `run_spider(source_id)` upserts results; dedup by title+year then by tmdb_id; always normalizes category via `_CAT_NORM`
- `sources/bangumi.py` — NOT in SPIDER_REGISTRY; called via `POST /api/admin/bangumi-enrich`; queries `Resource.category == "动漫"` (Chinese)

**DB**: `init_db()` runs `create_all` + `CREATE INDEX IF NOT EXISTS` on startup. Schema changes are additive only — no migration framework.

**Config** (`config.py`): `.env` file. Key vars: `TMDB_API_KEY`, `ADMIN_PASSWORD`, `CORS_ORIGINS` (comma-separated), `SPIDER_INTERVAL_HOURS`.

### Frontend structure

**Pages** (App Router, `src/app/`):
- `/` → `HomeContent.tsx` — hero search + category cards + hot resources grid
- `/search` → `SearchContent.tsx` — search results with category/year/sort filters; `page.tsx` adds `generateMetadata`
- `/detail/[id]` → `DetailContent.tsx` — resource detail + grouped download links + related; `page.tsx` adds `generateMetadata` via SSR fetch
- `/admin` — single-file admin panel, no sub-components

Next.js 16: `params` must be unwrapped with `use(params)` in server components, not destructured directly.

**`src/lib/api.ts`** — all fetch calls. `API_BASE` from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). `searchResources()` accepts `sort` and `genre` params.

**`src/lib/utils.ts`** — shared constants: `CATEGORY_LABELS` (both English + Chinese keys), `LINK_TYPE_LABELS`, `QUALITY_COLORS`.

**CSS**: dark theme via CSS custom properties (`--bg-primary`, `--bg-card`, `--accent: #e50914`). Tailwind 4 (`@import "tailwindcss"`). Inline styles co-exist with Tailwind — intentional for card/panel backgrounds.

### Key frontend patterns

- **`useEffect` deps in search page**: depend only on `searchParams`, not on derived values (`q`, `category`, etc.) extracted from it — they change in the same render tick anyway and would cause redundant calls.
- **Hover zoom on images**: requires `group` on the container div and `group-hover:scale-105` on the `<Image>`. The `resource-card` CSS class does not provide `group`.
- **`CATEGORY_COLORS`** in `ResourceCard.tsx` uses Chinese keys to match DB values directly.
- **Navbar `q` state**: synced via `useEffect([searchParams])` so it updates when navigating via hot-searches or footer links.

### Admin panel features
- Bangumi metadata enrichment (poster/rating/synopsis from bgm.tv, free, no key)
- Batch import via JSON array (`POST /api/admin/batch-import`)
- Resource list with per-resource link management (expandable rows, add/delete/invalidate links)
- Data source CRUD + manual spider trigger

### Link types
`pan_quark`, `pan_baidu`, `pan_aliyun`, `magnet`, `direct`, `page` — stored in `ResourceLink.link_type`. Baidu extraction code in `ResourceLink.password`. All link types show both a copy button and an open button (including `magnet:` URLs which the OS handles).
