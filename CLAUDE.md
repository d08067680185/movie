# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

### Local Development (macOS)

```bash
# Clone and setup
git clone <repo> && cd movie-search

# Backend
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev  # http://localhost:3000
```

### Docker (Mac mini @ Tailscale 100.85.130.18)

```bash
# SSH deployment (auto-pulls latest code and rebuilds)
ssh xiaofengdai@100.85.130.18 "cd ~/Documents/claude/movie && git pull && /usr/local/bin/docker compose build --no-cache && /usr/local/bin/docker compose up -d"

# Check logs
ssh xiaofengdai@100.85.130.18 "/usr/local/bin/docker compose -f ~/Documents/claude/movie/docker-compose.yml logs -f"

# Shell into container
ssh xiaofengdai@100.85.130.18 "/usr/local/bin/docker compose -f ~/Documents/claude/movie/docker-compose.yml exec backend bash"
```

## Commands Reference

### Backend (FastAPI + Python 3.9+)

```bash
cd backend

# Dev server (auto-reload)
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Syntax check all backend files
venv/bin/python -c "import ast; [ast.parse(open(f).read()) or print('✓',f) for f in ['tasks.py','utils.py','config.py','main.py','api/admin.py','api/search.py','spiders/scheduler.py','models.py','database.py']]"

# Quick DB count check
venv/bin/python3 -c "
import asyncio
from database import AsyncSessionLocal, init_db
from sqlalchemy import select, func
from models import Resource
async def check():
    await init_db()
    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(func.count(Resource.id)))).scalar()
        print(f'Total resources: {n}')
asyncio.run(check())
"

# SQLite inspection
sqlite3 backend/movie_search.db "SELECT COUNT(*) as resources, SUM(link_count) as total_links FROM resources;"
sqlite3 backend/movie_search.db "SELECT DISTINCT category FROM resources;"
sqlite3 backend/movie_search.db "SELECT * FROM spider_log ORDER BY started_at DESC LIMIT 5;"

# Test imports
venv/bin/python -c "from main import app; from api.search import router as search; print('✓ Imports OK')"
```

### Frontend (Next.js 16 + React 19 + Tailwind 4)

```bash
cd frontend

# Dev (hot-reload on file changes)
npm run dev           # http://localhost:3000

# Build for production
npm run build

# Type-check
npm run lint

# Check build size
npm run build && du -sh .next/
```

### Local Start/Stop (without Docker)

```bash
bash start.sh    # Runs backend + frontend in nohup; logs to /tmp/movie-search-*.log
bash stop.sh     # Kill backend/frontend processes
```

## Critical Concepts

### Category Values: Always Chinese in DB

**Database stores Chinese, URLs/spiders output English.** Never store English in `Resource.category`.

| DB column value | URL param | API output |
|---|---|---|
| `电影` | `category=movie` | varies by context |
| `电视剧` | `category=tv` | — |
| `动漫` | `category=anime` | — |
| `经典资源` | `category=variety` | — |

**Single source of truth**: `backend/config.py:CATEGORY_MAP` (English→Chinese dict). Three points must use it:
- `api/search.py`: translates `?category=` URL param at query time
- `spiders/scheduler.py`: translates spider `ResourceItem.category` at write time  
- `api/admin.py`: translates `batch-import` and `POST /resources` payloads

Frontend: `src/lib/utils.ts:CATEGORY_LABELS` has both English + Chinese keys; components work either way.

### Environment Variables (`backend/.env`)

```bash
TMDB_API_KEY=<key>              # Optional; enables TMDb batch import
ADMIN_PASSWORD=<password>       # Default: admin123 (change in production!)
CORS_ORIGINS=https://movie.mxzshs.com,https://localhost:3000
SPIDER_INTERVAL_HOURS=6         # Auto-crawl every N hours
TELEGRAM_BOT_TOKEN=<token>      # Optional; for error notifications
TELEGRAM_CHAT_ID=<id>           # Required if bot token set
```

### NEXT_PUBLIC_API_URL Must Use `??` Not `||`

Docker sets `NEXT_PUBLIC_API_URL=""` (empty string) as build arg. Empty string is falsy, so `|| fallback` breaks the Nginx proxy. **Always use nullish coalesce:**

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";  // ✓ Correct
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "..."; // ✗ Wrong
```

## Architecture

### Data Flow

```
User Browser → Nginx (movie.mxzshs.com:443)
              ├─ /api/* → FastAPI :8000 (backend)
              └─ /* → Next.js :3000 (frontend)

Docker internal:
  Frontend ↔ Backend via http://backend:8000 (docker network)
  Both share SQLite volume at ./backend/movie_search.db
```

### Backend Core Files

| File | Purpose |
|------|---------|
| `models.py` | SQLAlchemy ORM: Resource, ResourceLink, Source, SpiderLog, SearchLog |
| `database.py` | SQLite async session + schema init with indexes |
| `tasks.py` | In-memory registry for background task progress (1hr lifetime) |
| `utils.py` | `send_telegram()`, `backup_db()` utilities |
| `config.py` | Pydantic Settings from `.env`; CATEGORY_MAP dict |
| `main.py` | FastAPI app, CORS, APScheduler jobs (crawl every N hrs, daily backup at 03:00) |
| `api/search.py` | Public router: `/search`, `/stats` (60s cache), `/hot`, `/latest`, `/resource/{id}`, `/related/{id}`, `/hot-searches` |
| `api/admin.py` | Protected `/api/admin/*` endpoints (X-Admin-Token header); resource/link CRUD, batch import, duplicates, check-links, backups, Telegram config, stats-detail, logs pagination |
| `spiders/__init__.py` | SPIDER_REGISTRY: maps spider_class name → class (register new spiders here) |
| `spiders/scheduler.py` | `run_spider(source_id)` main scheduler; `run_all_spiders()` for APScheduler; task progress tracking; Telegram on failure |
| `spiders/sources/` | Individual spider implementations: demo, rss_spider, tmdb_batch, pan_search, bangumi (not in registry; called separately) |

### Backend Key Patterns

**Database operations**:
- Use `AsyncSessionLocal` from `database.py`; always `await db.commit()` after mutations
- Batch operations: call `commit()` once after loop, not per iteration (performance)
- Delete cascade: SQLAlchemy cascade doesn't work reliably with async `execute()` — explicitly delete child rows first (e.g., delete ResourceLink before Resource)

**Background tasks**: 
- Use `asyncio.create_task()` to spawn tasks; they get **own** `AsyncSessionLocal` session
- **Never reuse** the FastAPI-injected `db` session in a background coroutine — it's closed by response time
- Update progress in `tasks.py` registry so admin panel can poll

**Resource duplication**:
- Detected via `GROUP BY title + year HAVING count > 1`
- Merge: move links to keep resource, patch metadata, delete duplicate

**Link validation**:
- `POST /api/admin/check-links` does HEAD requests on `pan_*` links
- Marks 404/403/410 as `is_valid=False` (soft-delete; hides from detail page)

### Frontend Core Files

| File | Purpose |
|------|---------|
| `src/app/page.tsx` → `HomeContent.tsx` | Hero, hot/latest resources, category cards, stats |
| `src/app/search/page.tsx` → `SearchContent.tsx` | Search filters (q/category/year/genre/sort/page), results grid, search history (localStorage, max 10) |
| `src/app/detail/[id]/page.tsx` → `DetailContent.tsx` | Resource detail, grouped links by type, related resources |
| `src/app/admin/page.tsx` | Single-file admin panel (no sub-components); dark-only theme; task progress polling (3s), resource/link CRUD, batch import, backups, Telegram config, link validity toggle, search logs |
| `src/lib/api.ts` | All fetch calls; `fetchApi()` wrapper with 8s timeout, signal abort; error throwing pattern |
| `src/lib/utils.ts` | Constants: CATEGORY_LABELS (both EN+ZH keys), LINK_TYPE_LABELS, QUALITY_COLORS |
| `src/lib/favorites.ts` | localStorage-based favorite management; toggleFavorite, isFavorited, getFavoritesCount |
| `src/components/` | Navbar (search, favorites count, theme toggle), ResourceCard, Footer |

### Frontend Key Patterns

**App Router (Next.js 16)**:
- Dynamic route params: use `use(params)` in server components, not destructured destructure
- `src/lib/api.ts` imports must use `const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""`

**State synchronization**:
- `favoritesChanged` custom event dispatched by ResourceCard/DetailContent after toggle
- Navbar listens: updates favCount badge in real-time
- No Redux/Context needed for simple cross-component updates

**Search page deps**:
- `useEffect` depends only on `searchParams` (not derived `q`/`category`)
- Both change in same render tick; depending on derived vars → redundant API calls

**Admin page**:
- 1900+ line single component (intentional; no sub-components for risk reasons)
- Task polling: `hasRunningTasks` state drives `setInterval(loadTasks, 3000)` via useEffect
- Conditions: `{editResId && <dialog>}`, `{editLinkId && <dialog>}`, etc. for modals
- Batch import dedup: `scalars().first()` on `title + year` (not `scalar_one_or_none()`)

**Admin resource editing**:
- genre/country/synopsis fields are optional; must be populated correctly from existing resource on edit
- Links can be edited (PATCH /api/admin/links/{id}), not just deleted/toggled

**CSS theme**:
- Dark/light via `--bg-primary`, `--bg-card`, `--border`, `--text-*` CSS vars
- Tailwind 4 with `@import "tailwindcss"` at top of CSS file
- Inline styles coexist with Tailwind for card backgrounds (intentional split)

## Recent Improvements (2026-07-03)

Six admin features shipped:

1. **A1**: Searched hot keywords moved into max-w-6xl container (was full-width)
2. **A2**: Resource edit bug fix — genre/country/synopsis now populate correctly from existing resource
3. **A3**: Link editing UI — blue "Edit" button opens dialog to modify url/link_type/quality/password
4. **A4**: Daily stats — `GET /api/admin/stats-detail` returns today_resources + today_links (created_at >= today)
5. **A5**: Log pagination — `GET /api/admin/logs?offset=0&limit=20` supports pagination; "Load More" button appends 20 logs
6. **A6**: Link subtitle field — added to add/edit link dialogs (ResourceLink.subtitle optional field)

## Common Dev Tasks

### Add a new spider

1. Create `backend/spiders/sources/my_spider.py` inheriting from `BaseSpider`
2. Register in `backend/spiders/__init__.py:SPIDER_REGISTRY`
3. POST `/api/admin/sources` with `spider_class: "my_spider"` to create a data source
4. APScheduler auto-runs it every SPIDER_INTERVAL_HOURS; or manual POST `/api/admin/sources/{id}/run`

### Query resources from DB

```python
from database import AsyncSessionLocal
from models import Resource
from sqlalchemy import select, and_

async with AsyncSessionLocal() as db:
    # Get resource by ID
    r = await db.get(Resource, 1)
    
    # Find by title+year
    result = await db.execute(
        select(Resource).where(and_(
            Resource.title == "...",
            Resource.year == 2023
        ))
    )
    resources = result.scalars().all()
```

### Update admin panel

Edit `frontend/src/app/admin/page.tsx` directly (no sub-components). Rebuild with `npm run build` locally to catch TS errors before git push. System auto-deploys on push.

### Debug API endpoint

```bash
# Mock request to backend (from terminal)
curl -H "X-Admin-Token: admin123" http://localhost:8000/api/admin/sources

# Check live logs (Docker)
ssh xiaofengdai@100.85.130.18 "/usr/local/bin/docker compose -f ~/Documents/claude/movie/docker-compose.yml logs -f backend"
```

## Deployment

### GitHub → Automatic Deploy

- `git push` → GitHub Actions (if configured) OR manual SSH pull on server
- Server runs `git pull && docker compose build && docker compose up -d`
- Health check: `/health` endpoint must return 200

### Manual Docker Rebuild

```bash
ssh xiaofengdai@100.85.130.18
cd ~/Documents/claude/movie
git pull
/usr/local/bin/docker compose build --no-cache
/usr/local/bin/docker compose up -d
/usr/local/bin/docker compose logs -f
```

### Database Backup

- Automatic: daily at 03:00 UTC+8 via APScheduler → `backend/backups/`
- Manual: `POST /api/admin/backup` (requires X-Admin-Token)
- Restore: copy `.db` file to `backend/movie_search.db`, restart container

## Notes

- **Python 3.9 compatibility**: No PEP 604 union syntax (`int | str`); use `Optional[int]` instead
- **Cloudflare CDN**: Movie.mxzshs.com behind Cloudflare; cache issues solved by version bumps in page.tsx + manual clear
- **SQLite concurrency**: Single-writer lock; background tasks get own sessions to avoid blocks
- **TypeScript strict mode**: Frontend enforces; ResourceDetail/ResourceLink/ResourceCard interfaces in `src/lib/api.ts` must match backend responses
