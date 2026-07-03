# CLAUDE.md — Frontend (Next.js 16 + React 19)

## Quick Commands

```bash
npm run dev      # http://localhost:3000 (hot-reload)
npm run build    # Production build to .next/
npm run lint     # TypeScript + ESLint check
npm start        # Run production build locally
```

## Critical: TypeScript & Environment

### `API_BASE` must use `??` not `||`

```typescript
// ✓ Correct
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

// ✗ Wrong (breaks Docker Nginx proxy)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

Docker sets `NEXT_PUBLIC_API_URL=""` (empty string). Empty string is falsy, so `||` fallback would override it.

### Async `params` in Dynamic Routes

Next.js 16+ requires `use()` hook for `params`:

```typescript
// ✓ Correct (server component with use())
import { use } from 'react';
export default function Page({ params }: { params: Promise<{id: string}> }) {
  const { id } = use(params);
  return <div>{id}</div>;
}

// ✗ Wrong (old Next.js 13 style)
export default function Page({ params }: { params: {id: string} }) {
  // Won't work in Next.js 16
}
```

## Page Structure

| Route | File | Component | Purpose |
|---|---|---|---|
| `/` | `src/app/page.tsx` | HomeContent.tsx | Hero + stats + hot/latest resources |
| `/search` | `src/app/search/page.tsx` | SearchContent.tsx | Filters + results grid + search history |
| `/detail/[id]` | `src/app/detail/[id]/page.tsx` | DetailContent.tsx | Resource detail + links + related |
| `/admin` | `src/app/admin/page.tsx` | (single-file, no sub) | Data source/resource/link CRUD + settings |
| `/favorites` | `src/app/favorites/page.tsx` | FavoritesContent.tsx | Saved resources grid (localStorage) |

## Key Files

### `src/lib/api.ts` — All Backend Calls

Every fetch goes through `fetchApi()`:

```typescript
async function fetchApi<T>(path: string, cacheSeconds = 60): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);  // 8s timeout
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      next: { revalidate: cacheSeconds },
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}
```

**Pattern**: fetch calls throw on error; callers `.catch(() => [])` for graceful failure.

### `src/lib/utils.ts` — Constants

- `CATEGORY_LABELS` — both English + Chinese keys (source-agnostic components)
- `LINK_TYPE_LABELS` — magnet, pan_quark, pan_baidu, direct, etc.
- `QUALITY_COLORS` — colors for 1080P, 720P, etc.

### `src/lib/favorites.ts` — Persistent Favorites

```typescript
toggleFavorite(resource) → boolean           // toggle + dispatch 'favoritesChanged' event
isFavorited(resourceId) → boolean            // check localStorage
getFavoritesCount() → number                 // count stored favorites
```

Stored in localStorage as JSON array of resource objects. Max ~50KB in browser.

### `src/components/Navbar.tsx`

- Search input (/ key focus, Esc blur)
- Category links (animated color on hover)
- Favorites count badge (red when >0)
- Theme toggle (dark/light stored in localStorage)

**State sync**: listens to `favoritesChanged` custom event; updates badge when user toggles favorite elsewhere.

### `src/components/ResourceCard.tsx`

Reusable card for resource display:

```typescript
<ResourceCard resource={r} />  // Expect: ResourceCard interface from src/lib/api.ts
```

**Features**:
- Hover zoom on poster (requires `group` on container)
- Category + rating badges
- Share (copy link) + favorite buttons
- Link count indicator (green) or "无链接" (red)
- View count display

**Pattern**: `handleFav` callback dispatches `favoritesChanged` event.

## Theme System

### CSS Variables (Dark/Light)

Defined in `src/app/globals.css`:

```css
:root[data-theme="dark"] {
  --bg-primary: #0f0f12;
  --bg-card: #1a1a1f;
  --border: rgba(255, 255, 255, 0.08);
  --text-primary: #f0f0f5;
  --text-secondary: #a0a0b0;
  --text-muted: #606070;
  --accent: #e50914;
}

:root[data-theme="light"] {
  /* Light theme colors */
}
```

**Admin panel**: hardcoded dark theme (ignores user preference); uses inline `DARK` object in `src/app/admin/page.tsx`.

### Tailwind 4

Uses `@import "tailwindcss"` at top of CSS. Mix Tailwind classes with inline styles (both intentional):

```tsx
<div className="p-4 rounded-xl"  // Tailwind
     style={{ background: DARK.bgCard, border: DARK.borderStr }}>  // Inline
  ...
</div>
```

## Admin Panel (`src/app/admin/page.tsx`)

**Single 1900+-line file** (no sub-components for risk reasons).

### Features by Section

1. **Login** — X-Admin-Token header input; verify against backend
2. **Stats** — Total resources/links/sources + daily added (calls `/api/admin/stats-detail`)
3. **Tasks** — Running background tasks; 3s polling while running
4. **Tools** — DB backup, link validity check, Telegram config
5. **Duplicates** — Find & merge by title+year
6. **Add Resource** — Form + inline link list (multi-link batch add)
7. **Batch Import** — JSON array paste
8. **TMDb Config** — API key + batch import params
9. **Bangumi Enrich** — Cover art backfill for anime
10. **Pan Search** — Bing pan link discovery
11. **Resource Management** — Search + edit/delete + link CRUD + validity toggle
12. **Data Sources** — List + toggle active + trigger crawl + delete
13. **Logs** — Last 20 spider logs + "Load More" pagination
14. **Search Stats** — Top keywords

### State Management

~30 useState hooks; no Redux/Context. Key patterns:

- `editResId`: opens resource edit modal
- `editLinkId`: opens link edit modal  
- `expandedId`: toggles link detail visibility
- `tasks[]`: background task progress; drives polling
- `hasRunningTasks`: computed; stops polling when false

### API Calls Pattern

```typescript
async function apiFetch(path, opts = {}, token) {
  return fetch(`${API}${path}`, {
    ...opts,
    headers: { "X-Admin-Token": token, "Content-Type": "application/json", ...opts.headers }
  });
}
```

All admin endpoints require `X-Admin-Token` header.

## Search Page Specifics

### `useEffect` Dependencies

⚠️ **Common bug**: depend on `searchParams`, NOT derived `q`/`category`:

```typescript
// ✓ Correct
useEffect(() => {
  loadResources();
}, [searchParams]);  // Only searchParams changes cause fetch

// ✗ Wrong (causes double-fetch; q and category change together)
useEffect(() => {
  loadResources();
}, [q, category, ...]);
```

Both `q` and `category` are derived from `searchParams` in same tick; depending on them triggers double-fetch.

### Search History

Stored in localStorage; max 10 items. Updated when user searches (if query is non-empty).

## Common Patterns

### State Sync Across Components

Use custom events instead of Context/Redux:

```typescript
// In ResourceCard (after favorite toggle)
window.dispatchEvent(new Event("favoritesChanged"));

// In Navbar (listen)
useEffect(() => {
  window.addEventListener("favoritesChanged", () => setFavCount(getFavoritesCount()));
  return () => window.removeEventListener("favoritesChanged", ...);
}, []);
```

### Graceful API Failure

```typescript
// ✓ Correct — independent promises, catch per request
const [hot, latest, stats] = await Promise.all([
  getHotResources().catch(() => []),
  getLatestResources().catch(() => []),
  getStats().catch(() => null),
]);

// ✗ Wrong — one failure breaks whole Promise.all
const [hot, latest, stats] = await Promise.all([
  getHotResources(),
  getLatestResources(),
  getStats(),
]);
```

### Image Error Handling

```typescript
const [imgError, setImgError] = useState(false);

<Image
  src={poster_url}
  onError={() => setImgError(true)}
  fallback={<div>🎬</div>}  // If poster fails, show emoji
/>
```

## TypeScript Interfaces

All defined in `src/lib/api.ts`:

```typescript
interface ResourceCard {
  id: number;
  title: string;
  title_en?: string;
  year?: number;
  category?: string;
  genre?: string;
  rating?: number;
  poster_url?: string;
  link_count: number;
  view_count: number;
}

interface ResourceDetail extends ResourceCard {
  original_title?: string;
  country?: string;
  language?: string;
  duration?: number;
  rating_count?: number;
  synopsis?: string;
  backdrop_url?: string;
  directors?: string[];
  actors?: string[];
  imdb_id?: string;
  links: ResourceLink[];
  tags: string[];
}

interface ResourceLink {
  id: number;
  link_type: string;
  url: string;
  quality?: string;
  size?: string;
  format?: string;
  subtitle?: string;  // Added in A6
  episode_info?: string;
  password?: string;
  source_name?: string;
}
```

## Build & Deployment

### Local Build

```bash
npm run build
```

Creates `.next/` directory. Check for TypeScript errors before deploying.

### Docker Build

```dockerfile
# In Dockerfile (during build)
ARG NEXT_PUBLIC_API_URL=""
ARG BACKEND_URL="http://backend:8000"

# During development/SSR:
ENV BACKEND_URL=http://backend:8000
```

- `NEXT_PUBLIC_API_URL`: exposed to browser (empty in Docker = use Nginx proxy)
- `BACKEND_URL`: used only by Next.js server (generateMetadata, SSR calls)

### Development Tips

- **Hot reload**: `npm run dev` reloads on file save
- **Build speed**: First build ~1-2 min; subsequent builds faster
- **Cache busting**: Cloudflare may cache old version; add comment in page.tsx or manual clear
