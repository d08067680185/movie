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

# Run tests (also runs in CI on push/PR to main; see .github/workflows/ci.yml)
venv/bin/python -m pytest tests/ -q

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
ADMIN_PASSWORD=<password>       # First-boot only: plaintext seed, default admin123 (change before first run in production!)
ADMIN_PASSWORD_HASH=<bcrypt>    # Auto-generated on first startup from ADMIN_PASSWORD, which is then erased from .env
CORS_ORIGINS=https://movie.mxzshs.com,https://localhost:3000
SPIDER_INTERVAL_HOURS=6         # Auto-crawl every N hours
TELEGRAM_BOT_TOKEN=<token>      # Optional; for error notifications
TELEGRAM_CHAT_ID=<id>           # Required if bot token set
PANSOU_URL=http://pansou:8888   # 全网搜(PanSou)代理地址，docker-compose 内网服务名
DOWNLOAD_DIR=./downloads              # 视频下载(yt-dlp)落盘目录
DOWNLOAD_MAX_CONCURRENT_GLOBAL=5      # 全站同时下载任务上限
DOWNLOAD_MAX_CONCURRENT_PER_IP=2      # 单IP同时下载任务上限
DOWNLOAD_MAX_SIZE_GB=8                # 单次下载画质选择器已限制<=1080p，此项为预留配额位
DOWNLOAD_RETENTION_HOURS=12           # 完成文件保留时长，超时由 APScheduler 定时清理
DOWNLOAD_QUOTA_GB=30                  # DOWNLOAD_DIR 总占用超过此值时拒绝新任务
```

**Admin auth (2026-07-24 security hardening)**: `X-Admin-Token` is compared against a bcrypt hash (`ADMIN_PASSWORD_HASH`), never plaintext. On first startup, `auth.py:migrate_plaintext_password()` hashes whatever `ADMIN_PASSWORD` is set (env var or `.env`, default `admin123`), writes `ADMIN_PASSWORD_HASH` into `.env`, and deletes the plaintext line — the plaintext is not recoverable afterward. `POST /api/admin/change-password` also stores only the hash. Failed-token attempts are rate-limited per IP (`auth.py`: 10 failures / 5 min → 429 for 5 min).

**Implication for one-off scripts** (`import_movies.py`, `enrich_*.py`, `reverify_review_groups.py`): they read the plaintext token from `ADMIN_PASSWORD` env var or `.env`. Since `.env` no longer holds plaintext after first boot, you must pass it explicitly when running them, e.g. `ADMIN_PASSWORD=<your actual password> venv/bin/python enrich_movies.py`.

**Docker deploy note (2026-07-25 fix)**: `docker-compose.yml` used to inject `ADMIN_PASSWORD` as a container env var on every start — since pydantic-settings prioritizes real env vars over `.env` file values, this silently re-triggered the plaintext→hash migration on every container restart/recreate, discarding any password set via the admin panel's change-password UI (which only persists to `.env`, never mounted). Fixed by removing `ADMIN_PASSWORD` from `docker-compose.yml`'s `environment:` block and instead bind-mounting `./backend/.env:/app/.env` so `ADMIN_PASSWORD_HASH` genuinely persists across container recreates. **This means `backend/.env` must exist and contain a seed `ADMIN_PASSWORD=` (or already-migrated `ADMIN_PASSWORD_HASH=`) line on the deploy server before first bringing the container up** — an empty/missing file will make Docker error on the bind mount, and a fresh container with no seed falls back to config.py's default (`admin123`).

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
| `api/livesearch.py` | `/api/livesearch` — proxies to self-hosted PanSou for netdisk aggregate search ("全网搜"); in-memory TTL cache + circuit breaker on upstream failures |
| `api/downloads.py` | `/api/downloads` — generic video link downloader (YouTube/腾讯视频/优酷 etc, via `ytdlp_client.py`); POST creates a background task, GET polls progress, GET `/{id}/file` streams the finished file. Rate-limited + concurrency-capped (see below) |
| `ytdlp_client.py` | yt-dlp wrapper; runs the sync yt-dlp call via `asyncio.to_thread`; progress_hooks write into an in-memory dict (`get_progress()`) since the hook runs off the event loop and can't await DB writes |
| `ratelimit.py` | `SlidingWindowLimiter` — generic per-key sliding-window rate limiter, shared by admin login (`auth.py`) and download creation (`api/downloads.py`) |
| `spiders/__init__.py` | SPIDER_REGISTRY: maps spider_class name → class (register new spiders here) |
| `spiders/scheduler.py` | `run_spider(source_id)` main scheduler; `run_all_spiders()` for APScheduler; task progress tracking; Telegram on failure |
| `spiders/sources/` | Individual spider implementations: demo, rss_spider, tmdb_batch, pan_search, bangumi (not in registry; called separately) |
| `textnorm.py` | `normalize_keyword()` — casefold + whitespace-fold, shared by `api/livesearch.py`'s in-memory cache key and (deliberately NOT) `SearchLog` display values |

### Backend Key Patterns

**Search relevance/performance (2026-07-26)**:
- `api/search.py:build_fts_query` (≥3 char keywords) now also pulls `bm25(resources_fts)` ranking from the FTS5 query, ordered ascending (lower = more relevant). The final `ORDER BY` chain is: exact/prefix title match tier (unchanged, still wins outright) → bm25 rank position → existing popularity/rating sort as tiebreak. Previously FTS-matched results were sorted purely by popularity, so a barely-relevant-but-popular resource could outrank a strong title match.
- Short keywords (<3 chars, below FTS5 trigram's minimum) used to substring-match (`ILIKE '%kw%'`) across title/title_en/original_title/directors/actors/synopsis — always a full table scan in SQLite regardless of indexing, since a leading `%` wildcard can't use a B-tree index. **Changed to prefix-match only** (`title` starts with the keyword) on title/title_en/original_title — `directors`/`actors`/`synopsis` were dropped from this path entirely, since prefix matching doesn't make sense for those fields and keeping even one unindexable OR-branch would force SQLite back to a full scan for the whole query anyway. **Known UX trade-off, confirmed with the user**: searching "安" now matches "安家" (starts with 安) but no longer matches "长安" (安 mid-string).
- This prefix-match is implemented with **`GLOB`, not `LIKE`** (`api/search.py:build_prefix_glob`) — verified empirically that SQLite's query planner will *only* use an index for a `lower(col) LIKE pattern` when the global `PRAGMA case_sensitive_like` is turned on (too invasive — would silently affect every other `.ilike()` call in the app), whereas `lower(col) GLOB pattern` (GLOB is inherently case-sensitive/binary, so pre-lowering both sides in Python + comparing against `lower()`-expression indexes works) gets picked up correctly, confirmed via `EXPLAIN QUERY PLAN` showing `MULTI-INDEX OR` across three indexes. Backing indexes: `idx_r_title_lower`/`idx_r_title_en_lower`/`idx_r_original_title_lower` on `LOWER(title/title_en/original_title)` (`database.py` inline migration — plain column indexes don't help here since `.ilike()` compiles to `lower(col) LIKE lower(pattern)` in the SQLite dialect). GLOB metacharacters (`* ? [ ]`) in user input are escaped into character classes (e.g. `*` → `[*]`) by `build_prefix_glob` before use.
- `api/livesearch.py`'s in-memory PanSou result cache (`_cache` dict) now keys on `normalize_keyword()` (casefold + whitespace-fold) instead of the raw stripped keyword, so "Iron Man" and "iron  man" share a cache slot. **Deliberately NOT applied to `SearchLog.keyword`** (used both for hot-word dedup counting and as the literal display text for hot-word chips) — casefolding that would visibly turn "Iron Man" into "iron man" on the UI, which is a real display regression, not just an internal optimization. The actual query sent to PanSou still uses the original (non-normalized) keyword too.

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

**Video link downloads (2026-07-25)**:
- `Download` model (`models.py`) tracks task lifecycle: `queued → downloading → complete|error|expired`
- Only generic http(s) links via yt-dlp are supported (YouTube etc — stable; 腾讯视频/优酷 etc — best-effort, frequently breaks on platform changes since they use encrypted streams). **Magnet/BT links are intentionally NOT supported** — considered and explicitly deferred, no aria2/torrent infra in this repo
- Concurrency + quota enforced at creation time in `api/downloads.py:create_download` (`DOWNLOAD_MAX_CONCURRENT_GLOBAL`/`_PER_IP`, `DOWNLOAD_QUOTA_GB` checked against actual `DOWNLOAD_DIR` size)
- Completed files auto-expire after `DOWNLOAD_RETENTION_HOURS` (default 12h); cleanup runs hourly via APScheduler (`main.py` job `cleanup_downloads` → `api.downloads.cleanup_expired_downloads`), which also force-errors any task stuck in queued/downloading for >6h
- `ytdlp_client._run_download` explicitly checks the output file actually exists after `extract_info()` — some sites' generic extractor (e.g. 腾讯视频) can return an `info` dict without raising `yt_dlp.utils.DownloadError` and without producing a file; treat that as a failure too, not a silent "complete"

**Rate limiting + client IP (2026-07-26)**:
- `ratelimit.py:get_client_ip()` — always use this instead of raw `request.client.host`. It prefers the Cloudflare-set `CF-Connecting-IP` header. The real deployment path is Cloudflare → **Cloudflare Tunnel** (`cloudflared`, running on the deploy Mac mini, config at `/Users/xiaofengdai/.cloudflared/config.yml` — **not** an Nginx layer, and not in this git repo) → Next.js `rewrites()` (`frontend/next.config.ts`) → backend container. **Verified end-to-end in production (2026-07-26)**: a fresh request through the full public path correctly recorded a real external IP in `Download.requester_ip`, confirming `cloudflared` and the Next.js rewrite both forward the header intact. Spoofing risk is effectively closed by the network topology itself, not just app-layer trust: port 8092 (frontend) listens on `0.0.0.0` on the Mac mini, but the home router does **not** forward that port from WAN (confirmed by a timed-out direct connection attempt to the box's public IP) — the tunnel is outbound-only, so there is no reachable path to the origin that bypasses Cloudflare to forge this header.
- Public read endpoints `/api/search` and `/api/resource/{id}` are now rate-limited (60 req/60s per IP, `api/search.py:rate_limit_public_read`) — previously completely open to scraping/DoS. Other public endpoints (`/hot`, `/latest`, `/stats`, `/hot-searches`, `/related`) are left unlimited since they're cheap and/or already cached.
- Admin login (`auth.py`) and download creation (`api/downloads.py`) rate limiters were already in place but were previously using the un-fixed `request.client.host` — retroactively fixed to use `get_client_ip()` too.

**Failure alerting (2026-07-26)**: beyond the existing spider-failure Telegram notification, three more failure modes now alert via `utils.send_telegram()`: PanSou circuit breaker opening (`api/livesearch.py:_circuit_record_failure`, fires once per trip, not per failure), download disk quota exceeded (`api/downloads.py:_alert_quota_exceeded`, throttled to once per 10 min), and nightly backup integrity-check failures (`main.py:run_daily_backup`). All the `asyncio.create_task(send_telegram(...))` call sites are wrapped in `try/except RuntimeError` since they can be reached from contexts without a running event loop (matters for tests calling the sync helper functions directly).

**Backup integrity (2026-07-26)**: `utils.backup_db()` now runs `PRAGMA integrity_check` against the copy right after `shutil.copy2` and returns `None` (deleting the bad file) if it fails, instead of silently trusting the copy succeeded. `POST /api/admin/backup` and the daily 03:00 cron job (`main.py:run_daily_backup`) both handle the `None` case. This does not include an automated restore drill (deemed too risky to run against a live DB) — integrity check only covers "did the copy produce a valid, non-corrupted SQLite file," not "is a full restore actually recoverable end-to-end."

**Admin panel additions (2026-07-26)**: `GET /api/admin/downloads` surfaces download task history + disk usage against quota (previously only visible via SSH) — the admin panel's new "下载监控" section polls this on load/manual refresh. The existing "全网搜监控" widget (already fetching the *public* `/api/livesearch/health`) got a small addition: a "熔断中" badge when `circuit_open` is true — no separate admin-gated livesearch-status endpoint was added since the public health endpoint already contains nothing sensitive.

**Download hang mitigation + dedup (2026-07-26)**: `ytdlp_client.py` uses a dedicated bounded `ThreadPoolExecutor` (`_DOWNLOAD_EXECUTOR`, 8 workers) instead of `asyncio.to_thread`'s shared default pool, plus `socket_timeout: 30` in yt-dlp opts — a hung download can only exhaust these 8 slots, not every other `to_thread` call site in the app. `api/downloads.py:_run_download_task` also wraps the whole download in `asyncio.wait_for(timeout=1800)` (30 min) so the DB row gets marked `error` promptly even in the worst case — **this does not kill the underlying thread** (Python threads can't be force-terminated), it only bounds how long the async caller waits. `create_download` now dedupes: a second request for a `source_url` that already has an in-flight (`queued`/`downloading`) row returns that same task's id instead of starting a duplicate yt-dlp process. Same limitation applies to the new `DELETE /api/admin/downloads/{id}` — it removes the DB row + file but can't guarantee killing a still-running thread.

**Rate limiter memory leak fix (2026-07-26)**: `ratelimit.py:SlidingWindowLimiter` used to accumulate empty-list entries in `_attempts` forever (checked/pruned per-key on read, but never removed the key itself). Every `SlidingWindowLimiter` instance now self-registers into a module-level list; `sweep_all_limiters()` (called hourly via APScheduler, `main.py` job `sweep_ratelimiters`) removes keys with no remaining attempts across all instances.

**Content quality tooling (2026-07-26)**: `backend/dedup.py` (title-normalization `clean_key()`, shared with the standalone `find_duplicates.py` script) powers `GET /api/admin/duplicates?fuzzy=true` — groups by `(clean_key(title), year)` instead of exact title match, catching near-duplicates (punctuation/whitespace variants, and — found live in prod — the same title double-entered under two different categories e.g. 动漫 vs 电影). `Resource.poster_checked_at` (new column) + `POST /api/admin/check-posters` rotates through HEAD-checking poster URLs the same way `check-links` does for pan links, nulling out dead ones. `POST /api/admin/bulk-enrich-tmdb` batch-fills missing poster/synopsis/year for 电影/电视剧 resources via TMDb search + `api/tmdb.py:apply_tmdb_data()` (extracted from `enrich_resource` for reuse) — 动漫 still goes through the separate `bangumi-enrich` flow, not covered by this endpoint. `POST /api/admin/resources/bulk-delete` and `POST /api/admin/duplicates/merge-group` (loops `_merge_one()`, extracted from the single-pair merge endpoint) give the admin panel batch actions instead of one-at-a-time clicks.

**Disk usage history (2026-07-26)**: new `DiskUsageSnapshot` table, one row/day via `main.py` cron job (`record_disk_usage_snapshot`, 03:30) — `GET /api/admin/disk-usage-history` feeds a small hand-rolled SVG sparkline in the admin panel's download-monitoring section (no chart library dependency added).

**CI now runs lint + dependency audits (2026-07-26)**: `.github/workflows/ci.yml` added `npm run lint` (blocking) and `pip-audit`/`npm audit --audit-level=high` (both `continue-on-error: true`, report-only — flagged as needing human judgment on whether/when to upgrade, not auto-blocking). First real run surfaced actual outstanding CVEs in `aiohttp==3.11.10` and `starlette==0.41.3` (transitive via FastAPI) — **not yet upgraded as of this note**, needs a deliberate version-bump pass with its own testing, not a drive-by dependency bump.

**运维加固轮 (2026-07-28)**：
- **依赖升级，含强行突破FastAPI官方兼容范围**：`backend/requirements.txt` 升到 FastAPI 0.140.0（其余依赖同步打补丁）。FastAPI 0.140.0 自己声明的依赖范围仍是 `starlette<0.51.0`，但 starlette 的 CVE 修复只在 1.0.1+ 才有（[FastAPI issue #15193](https://github.com/fastapi/fastapi/issues/15193) 记录的已知落差）——按用户明确决定强行固定 `starlette==1.3.1`，突破FastAPI官方测试过的组合范围。全量87个pytest + 手动烟测（含完整 yt-dlp 下载→FileResponse 链路、CORS预检头、admin鉴权、`/api/search`）全部通过，仅 `api/search.py` 需要把废弃的 `Query(..., regex=)` 改成 `pattern=`。**这是有意接受的风险**，一旦 starlette 后续版本出现新的破坏性行为需要单独关注。
- **Docker 资源限制** (`docker-compose.yml`)：backend 512M/1.5cpu、pansou 384M/1.0cpu、frontend 256M/0.5cpu。数字来自实测——部署机（Mac mini）Docker Desktop 的 VM 实际只分到 5 vCPU/2.845GiB（`docker info` 查得，远小于宿主机本身的16GB/10核），且同一台机器上跑着其他项目共13个容器。`docker compose config` 已在部署机上验证 Compose v5.1.4 非 Swarm 模式下也能正确解析 `deploy.resources.limits`。
- **日志轮转** (`auto-pull.sh`)：`auto-pull.log` 从未轮转过（实测已到4.4MB），超过5MB时转存为 `.1` 后清空，只留一代历史。
- **备份恢复演练** (`backend/utils.py:verify_backup_restorable`)：`PRAGMA integrity_check` 只能证明备份文件结构没损坏，测不出"结构对但关键表是空的"这种坏备份。新增只读连接对 `resources`/`resource_links`/`sources` 三张表跑 sanity COUNT，`resources` 为0或查询失败都判定为坏备份并删除。`backup_db()` 在完整性校验通过后再跑这一步。
- **两处静默失败补日志**（不改变行为，只是从完全静默改成 `logger.warning`）：`api/livesearch.py` 热词写入失败、`api/admin.py` Telegram配置写 `.env` 失败。其余故意静默的 `except` 块（HEAD探活/view_count计数竞争）经复核判断维持原样不动。
- **前端首次引入 Vitest**（此前零测试，后端已有87个pytest）：只针对 admin 面板三个破坏性操作写基本测试，不是给整个前端补全测试覆盖。`admin/page.tsx` 里 `deleteDownload`/`bulkDeleteSelectedResources`/`mergeGroup` 三个函数的核心逻辑抽到 `frontend/src/lib/adminDestructiveActions.ts`（`apiFetch`/`confirm` 作为参数注入，不依赖具体实现，纯函数式方便测试）——**这不是重构整个1900+行admin组件**，其余状态更新（`setMsg`/`loadXxx()`）仍留在 `admin/page.tsx` 里调用方内联。10个测试覆盖：取消确认框不发请求、请求URL/方法/body正确、成功/失败路径的返回值。CI (`ci.yml`) 新增 `npm run test` 挡在 `npm run build` 之前。

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
curl -H "X-Admin-Token: <your actual admin password>" http://localhost:8000/api/admin/sources

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
