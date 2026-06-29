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

## Architecture

### Data flow
User search → Next.js (SSR/client) → `GET /api/search?q=...` → FastAPI → SQLite → returns `ResourceCard[]`
Detail page → `GET /api/resource/{id}` → increments `view_count`, returns full `ResourceDetail` with links

### Backend structure

**`models.py`** — five SQLAlchemy models:
- `Resource` — the canonical record (title, year, category, poster_url, rating, synopsis, tmdb_id, etc.)
- `ResourceLink` — download links per resource (url, link_type: `pan_quark/pan_baidu/pan_aliyun/magnet/direct`, password, quality, is_valid)
- `Source` — a data source record with `spider_class` name + `config` JSON; scheduler runs all active sources
- `SpiderLog` — per-run log (status: running/success/failed, new_resources count)
- `SearchLog` — hot-search counter (upsert on every search hit)

**`api/`** — three routers:
- `search.py` (`/api`) — public: search, resource detail, hot, stats, hot-searches, related
- `admin.py` (`/api/admin`) — protected by `X-Admin-Token: admin123` header; sources CRUD, batch-import, bangumi-enrich, resource+link management
- `tmdb.py` (`/api/tmdb`) — TMDb proxy (requires `TMDB_API_KEY` in `.env`)

**Spider system (`spiders/`)**:
- `base.py` — `BaseSpider` (abstract) + `ResourceItem` (standard output format)
- `SPIDER_REGISTRY` in `__init__.py` — maps `spider_class` string → class; add new spiders here
- `scheduler.py` — `run_spider(source_id)` instantiates the registered class, calls `crawl(page)`, upserts results; dedup by title+year or tmdb_id
- `sources/bangumi.py` — **not** in SPIDER_REGISTRY; called directly via `POST /api/admin/bangumi-enrich`; enriches 动漫 resources with poster/rating/synopsis from bgm.tv (free, no key)

**DB init**: `init_db()` calls `Base.metadata.create_all` on startup — no migration framework, schema changes are additive only.

**Config** (`config.py`): reads from `.env`. Key vars: `TMDB_API_KEY`, `ADMIN_PASSWORD` (default `admin123`), `SPIDER_INTERVAL_HOURS` (default 6).

### Frontend structure

**Pages** (App Router, all under `src/app/`):
- `/` (`page.tsx` → `HomeContent.tsx`) — hero search + hot resources grid
- `/search` (`page.tsx` → `SearchContent.tsx`) — filtered search results with category tabs
- `/detail/[id]` (`page.tsx` → `DetailContent.tsx`) — resource detail + download links
- `/admin` (`page.tsx`) — single-file admin panel (no separate components)

Next.js 16 requires `params` to be unwrapped with `use()`: `const { id } = use(params)` — not destructured directly.

**`src/lib/api.ts`** — all fetch calls; `API_BASE` from `NEXT_PUBLIC_API_URL` env var (default `http://localhost:8000`). Uses `{ next: { revalidate: 60 } }` for ISR caching.

**CSS**: dark theme via CSS custom properties (`--bg-primary`, `--bg-card`, `--accent: #e50914`). Tailwind 4 (imported as `@import "tailwindcss"`). Inline styles are used alongside Tailwind throughout — this is intentional for card/panel backgrounds.

### Admin panel features
- Bangumi metadata enrichment (poster/rating/synopsis from bgm.tv, free, no key needed)
- Batch import via JSON (`POST /api/admin/batch-import`)
- Resource list with per-resource link management (add/delete links, expandable rows)
- Data source CRUD + manual spider trigger
- TMDb source creation helper

### Link types
`pan_quark`, `pan_baidu`, `pan_aliyun`, `magnet`, `direct` — stored in `ResourceLink.link_type`. Baidu password stored separately in `ResourceLink.password` (stripped from URL).

### Bangumi enrichment notes
`spiders/sources/bangumi.py` `clean_title()` strips season/year/合集 suffixes before searching bgm.tv. It also extracts Japanese kana substrings first for JP titles. If a title mismatches, clear `poster_url/rating/synopsis` on that resource and re-enrich with `overwrite=False`, or fix directly via `PATCH /api/admin/links/{id}` / DB script.
