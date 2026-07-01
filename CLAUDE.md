# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (FastAPI + Python)
```bash
cd backend

# Start dev server
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Install dependencies
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# Syntax-check all backend files at once
venv/bin/python -c "import ast,sys; [ast.parse(open(f).read()) or print('✓',f) for f in ['tasks.py','utils.py','config.py','main.py','api/admin.py','api/search.py','spiders/scheduler.py']]"

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

### Docker deployment (Mac mini via Tailscale 100.85.130.18)
```bash
ssh xiaofengdai@100.85.130.18 "cd ~/Documents/claude/movie && git pull && /usr/local/bin/docker compose build --no-cache && /usr/local/bin/docker compose up -d"
```

### Start/stop (local dev without Docker)
```bash
bash start.sh     # nohup, logs to /tmp/movie-search-*.log
bash stop.sh
```

## Critical: Category Values

**The DB stores Chinese values** — never store English values in `Resource.category`.

| DB value | URL param / spider output |
|----------|--------------------------|
| `电影` | `movie` |
| `电视剧` | `tv` |
| `动漫` | `anime` |
| `经典资源` | `variety` |

The single source of truth is **`backend/config.py:CATEGORY_MAP`** (dict mapping English→Chinese). All three translation points import from it:
- `api/search.py` — translates URL `category=` param at query time
- `spiders/scheduler.py` — translates spider `ResourceItem.category` at write time
- `api/admin.py` — translates `batch-import` and `create_resource` payloads

`frontend/src/lib/utils.ts:CATEGORY_LABELS` carries both English and Chinese keys so components work regardless of source.

## Critical: `NEXT_PUBLIC_API_URL` Must Use `??` Not `||`

Docker sets `NEXT_PUBLIC_API_URL=""` (empty string) as a build arg. Empty string is falsy, so `|| "http://localhost:8000"` would silently override it and break the Nginx proxy. Always use:
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
```

## Architecture

### Data flow
```
Browser → Nginx (movie.mxzshs.com) → /api/* → FastAPI :8000
                                    → /*     → Next.js :3000
Docker internal: frontend container calls backend via http://backend:8000
```

### Backend structure

**`models.py`** — five SQLAlchemy models:
- `Resource` — canonical record (title, year, category, poster_url, rating, synopsis, tmdb_id, etc.)
- `ResourceLink` — download links (url, link_type, password, quality, is_valid). `is_valid=False` hides a link from the detail page without deleting it.
- `Source` — data source config with `spider_class` name + `config` JSON
- `SpiderLog` — per-run log (status: running/success/failed)
- `SearchLog` — hot-search counter, upserted on every non-empty search hit

**`tasks.py`** — in-memory background task registry. `start_task(id, name)` / `update_task(id, done, message)` / `finish_task(id, status, message)`. Used by spider scheduler and check-links to report progress visible in the admin panel. Tasks are cleared after 1 hour.

**`utils.py`** — two utilities:
- `send_telegram(message)` — posts to Telegram Bot API using `settings.TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`; no-ops silently if unconfigured
- `backup_db(db_path)` → copies SQLite DB to `backups/movie_search_<timestamp>.db`

**`api/search.py`** — public router (`/api`):
- `GET /search` — supports `q`, `category` (English), `year`, `genre` (ilike), `sort` (popular/rating/newest/latest), `page`
- `GET /stats` — 60s in-memory cache (`_stats_cache` global); safe for single-worker only

**`api/admin.py`** — protected by `X-Admin-Token` header:
- Batch import: dedup by title + year using `scalars().first()` (not `scalar_one_or_none()`)
- Delete resource: explicitly deletes `ResourceLink` rows first (cascade not reliable via async execute)
- Background tasks (`check-links`, `bangumi-enrich`, `pan-search`) use `asyncio.create_task()` — they get their **own** `AsyncSessionLocal` sessions; never reuse the request's `db` session in a background coroutine
- `GET /tasks` — returns `task_registry.get_tasks()` for admin progress polling
- `GET /duplicates` — raw SQL GROUP BY title+year HAVING count > 1
- `POST /resources/{keep_id}/merge/{dup_id}` — moves links, patches metadata, deletes duplicate
- `POST /check-links` — HEAD requests on `pan_*` links; marks 404/403/410 as `is_valid=False`
- `POST /backup` + `GET /backups` — manual DB backup and listing
- `POST /telegram-config` + `GET /telegram-status` — runtime Telegram configuration

**Spider system (`spiders/`)**:
- `SPIDER_REGISTRY` in `__init__.py` — maps `spider_class` string → class; register new spiders here
- `scheduler.py` — `run_spider(source_id)` writes task progress to `tasks.py` and sends Telegram on failure
- `sources/bangumi.py` — NOT in SPIDER_REGISTRY; called via `POST /api/admin/bangumi-enrich`; queries `Resource.category == "动漫"` (Chinese)

**`config.py`** — `Settings` (pydantic-settings, reads `.env`). Key vars: `TMDB_API_KEY`, `ADMIN_PASSWORD`, `CORS_ORIGINS` (comma-separated), `SPIDER_INTERVAL_HOURS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

**DB**: `init_db()` runs `create_all` + `CREATE INDEX IF NOT EXISTS` on startup. Schema changes are additive only — no migration framework. Historical category cleanup SQL also runs in `init_db`.

**APScheduler jobs** (registered in `main.py`):
- `crawl_all` — runs `run_all_spiders()` every `SPIDER_INTERVAL_HOURS`
- `daily_backup` — runs `backup_db()` at 03:00 daily

### Frontend structure

**Pages** (App Router, `src/app/`):
- `/` → `HomeContent.tsx` — hero search + category cards + hot/latest resource grids
- `/search` → `SearchContent.tsx` — filters (category/year/genre/sort) + results grid + search history (localStorage, max 10)
- `/detail/[id]` → `DetailContent.tsx` — detail + grouped download links + related
- `/admin` — single-file admin panel (no sub-components); always dark theme regardless of user preference

Next.js 16: `params` must be unwrapped with `use(params)` in server components, not destructured directly.

**`src/lib/api.ts`** — all public fetch calls. `API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""`.

**`src/lib/utils.ts`** — shared constants: `CATEGORY_LABELS` (both English + Chinese keys), `LINK_TYPE_LABELS`, `QUALITY_COLORS`.

**CSS**: dark/light theme via CSS custom properties (`--bg-primary`, `--bg-card`, `--accent: #e50914`). Tailwind 4 (`@import "tailwindcss"`). Inline styles co-exist with Tailwind for card/panel backgrounds — intentional.

### Key frontend patterns

- **`useEffect` deps in search page**: depend only on `searchParams`, not on derived `q`/`category` — they change in the same tick and would cause redundant calls.
- **Hover zoom**: requires `group` on container + `group-hover:scale-[1.08]` on `<Image>`. The `.resource-card` CSS class does not add `group`.
- **Admin task polling**: `hasRunningTasks = tasks.some(t => t.status === "running")` drives a `setInterval(loadTasks, 3000)` via `useEffect([hasRunningTasks])`.
- **Background tasks in admin.py**: always create a new `AsyncSessionLocal` inside the coroutine — the FastAPI-injected `db` session is closed by the time the background task runs.
