import type { ResourceCard } from "./api";

const KEY = "movie-favorites";
const MAX = 100;

export interface FavoriteItem extends ResourceCard {
  saved_at: number;
}

function read(): FavoriteItem[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

function write(items: FavoriteItem[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {}
}

export function getFavorites(): FavoriteItem[] {
  return read();
}

export function isFavorited(id: number): boolean {
  return read().some((f) => f.id === id);
}

export function toggleFavorite(resource: ResourceCard): boolean {
  const list = read();
  const idx = list.findIndex((f) => f.id === resource.id);
  if (idx >= 0) {
    list.splice(idx, 1);
    write(list);
    return false;
  }
  const item: FavoriteItem = { ...resource, saved_at: Date.now() };
  write([item, ...list].slice(0, MAX));
  return true;
}

export function removeFavorite(id: number) {
  write(read().filter((f) => f.id !== id));
}

export function getFavoritesCount(): number {
  return read().length;
}
