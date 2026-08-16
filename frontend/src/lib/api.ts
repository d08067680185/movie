const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface ResourceCard {
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

export interface ResourceLink {
  id: number;
  link_type: string;
  url: string;
  quality?: string;
  size?: string;
  format?: string;
  subtitle?: string;
  episode_info?: string;
  episode_number?: number;
  password?: string;
  source_name?: string;
}

export interface ResourceDetail {
  id: number;
  title: string;
  title_en?: string;
  original_title?: string;
  year?: number;
  category?: string;
  genre?: string;
  country?: string;
  language?: string;
  duration?: number;
  rating?: number;
  rating_count?: number;
  synopsis?: string;
  poster_url?: string;
  backdrop_url?: string;
  directors?: string[];
  actors?: string[];
  view_count: number;
  imdb_id?: string;
  links: ResourceLink[];
  tags: string[];
}

export interface SearchResult {
  total: number;
  page: number;
  page_size: number;
  items: ResourceCard[];
}

export interface Stats {
  total_resources: number;
  total_links: number;
  total_sources: number;
  categories: Record<string, number>;
}

export interface Section {
  id: number;
  key: string;
  name: string;
  icon?: string;
  resource_count: number;
  categories: { id: number; name: string }[];
}

export async function getSections(): Promise<Section[]> {
  try {
    return await fetchApi("/api/sections", 300);
  } catch {
    return [];
  }
}

async function fetchApi<T>(path: string, cacheSeconds = 60): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
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

export async function getResource(id: number): Promise<ResourceDetail> {
  return fetchApi(`/api/resource/${id}`, 0);
}

export async function searchResources(params: {
  q?: string;
  section?: string;
  category?: string;
  year?: number;
  genre?: string;
  country?: string;
  min_rating?: number;
  has_links?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}): Promise<SearchResult> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.section) sp.set("section", params.section);
  if (params.category) sp.set("category", params.category);
  if (params.year) sp.set("year", String(params.year));
  if (params.genre) sp.set("genre", params.genre);
  if (params.country) sp.set("country", params.country);
  if (params.min_rating) sp.set("min_rating", String(params.min_rating));
  if (params.has_links) sp.set("has_links", "true");
  if (params.sort && params.sort !== "popular") sp.set("sort", params.sort);
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  return fetchApi(`/api/search?${sp.toString()}`);
}

export async function getHotResources(category?: string, limit?: number, section?: string): Promise<ResourceCard[]> {
  const sp = new URLSearchParams();
  if (category) sp.set("category", category);
  if (limit) sp.set("limit", String(limit));
  if (section) sp.set("section", section);
  const qs = sp.toString();
  return fetchApi(`/api/hot${qs ? `?${qs}` : ""}`);
}

export interface LiveSearchItem {
  title: string;
  url: string;
  password: string;
  datetime?: string;
  source: string;
  source_hits?: number;
}

export interface LiveSearchResult {
  total: number;
  types: { type: string; count: number }[];
  by_type: Record<string, LiveSearchItem[]>;
}

// 全网搜聚合上游较慢（首次可达十几秒），单独用 35s 超时且不走缓存
export async function liveSearch(q: string, refresh = false, section?: string): Promise<LiveSearchResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 35000);
  try {
    const params = `?q=${encodeURIComponent(q)}${refresh ? "&refresh=true" : ""}${section ? `&section=${encodeURIComponent(section)}` : ""}`;
    const res = await fetch(`${API_BASE}/api/livesearch${params}`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

// 网盘链接有效性检测：后端代理PanSou自带的 /api/check/links，覆盖百度/阿里/夸克/
// 天翼/UC/移动云盘/115/迅雷/123共9种网盘。返回结果里没出现的url表示"不确定/
// 不支持检测"而非"有效"，前端不应据此展示任何标记。最多一次查30个(一页可见量级)。
export async function checkPanLinks(items: { url: string; cloudType: string }[]): Promise<Record<string, boolean>> {
  if (items.length === 0) return {};
  try {
    const res = await fetch(`${API_BASE}/api/livesearch/check-links`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: items.slice(0, 30).map((it) => ({ url: it.url, cloud_type: it.cloudType })),
      }),
    });
    if (!res.ok) return {};
    const data = await res.json();
    return data.results ?? {};
  } catch {
    return {};
  }
}

export async function getStats(): Promise<Stats> {
  return fetchApi("/api/stats");
}

export async function getHotSearches(): Promise<{ keyword: string; count: number }[]> {
  try {
    return await fetchApi("/api/hot-searches");
  } catch {
    return [];
  }
}

export async function getRelated(id: number): Promise<ResourceCard[]> {
  try {
    return await fetchApi(`/api/related/${id}`);
  } catch {
    return [];
  }
}

export async function getLatestResources(section?: string): Promise<ResourceCard[]> {
  try {
    return await fetchApi(`/api/latest${section ? `?section=${section}` : ""}`);
  } catch {
    return [];
  }
}

export interface DownloadStatus {
  id: number;
  status: "queued" | "downloading" | "complete" | "error" | "expired";
  title: string | null;
  downloaded_bytes: number | null;
  total_bytes: number | null;
  download_speed: number | null;
  error_message: string | null;
}

export async function createDownload(url: string, title?: string): Promise<{ id: number }> {
  const res = await fetch(`${API_BASE}/api/downloads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `创建下载任务失败 (${res.status})`);
  }
  return res.json();
}

export async function getDownloadStatus(id: number): Promise<DownloadStatus> {
  const res = await fetch(`${API_BASE}/api/downloads/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`查询下载状态失败 (${res.status})`);
  return res.json();
}

export function downloadFileUrl(id: number): string {
  return `${API_BASE}/api/downloads/${id}/file`;
}
