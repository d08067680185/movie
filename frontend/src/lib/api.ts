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

async function fetchApi<T>(path: string, cacheSeconds = 60): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { next: { revalidate: cacheSeconds } });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getResource(id: number): Promise<ResourceDetail> {
  return fetchApi(`/api/resource/${id}`, 0);
}

export async function searchResources(params: {
  q?: string;
  category?: string;
  year?: number;
  genre?: string;
  min_rating?: number;
  has_links?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}): Promise<SearchResult> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.category) sp.set("category", params.category);
  if (params.year) sp.set("year", String(params.year));
  if (params.genre) sp.set("genre", params.genre);
  if (params.min_rating) sp.set("min_rating", String(params.min_rating));
  if (params.has_links) sp.set("has_links", "true");
  if (params.sort && params.sort !== "popular") sp.set("sort", params.sort);
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  return fetchApi(`/api/search?${sp.toString()}`);
}

export async function getHotResources(): Promise<ResourceCard[]> {
  return fetchApi("/api/hot");
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

export async function getLatestResources(): Promise<ResourceCard[]> {
  try {
    return await fetchApi("/api/latest");
  } catch {
    return [];
  }
}
