import type { LiveSearchItem } from "./api";

const KEY = "movie-pan-favorites";
const MAX = 200;

// 全网搜到的网盘链接收藏，以 url 为主键（无本地资源 id）
export interface PanFavoriteItem extends LiveSearchItem {
  cloudType: string;
  saved_at: number;
}

function read(): PanFavoriteItem[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

function write(items: PanFavoriteItem[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {}
}

export function getPanFavorites(): PanFavoriteItem[] {
  return read();
}

export function isPanFavorited(url: string): boolean {
  return read().some((f) => f.url === url);
}

export function togglePanFavorite(item: LiveSearchItem, cloudType: string): boolean {
  const list = read();
  const idx = list.findIndex((f) => f.url === item.url);
  if (idx >= 0) {
    list.splice(idx, 1);
    write(list);
    return false;
  }
  const fav: PanFavoriteItem = { ...item, cloudType, saved_at: Date.now() };
  write([fav, ...list].slice(0, MAX));
  return true;
}

export function removePanFavorite(url: string) {
  write(read().filter((f) => f.url !== url));
}

export function getPanFavoritesCount(): number {
  return read().length;
}
