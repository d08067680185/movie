const KEY = "movie-blocked-sources";
const MAX = 200;

// 用户主动屏蔽的全网搜来源(source_key，格式 tg:<频道>/plugin:<插件>/api:<接口>)，
// 纯本地生效，不发到服务端——跟 pansou_source_stats 是两回事，那个是全站共享
// 的运维统计，这个是每个用户自己的个人偏好
export interface BlockedSource {
  source: string;
  blocked_at: number;
}

function read(): BlockedSource[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

function write(items: BlockedSource[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {}
}

export function getBlockedSources(): BlockedSource[] {
  return read();
}

export function getBlockedSourceKeys(): Set<string> {
  return new Set(read().map((b) => b.source));
}

export function isSourceBlocked(source: string): boolean {
  return read().some((b) => b.source === source);
}

export function blockSource(source: string) {
  const list = read();
  if (list.some((b) => b.source === source)) return;
  write([{ source, blocked_at: Date.now() }, ...list].slice(0, MAX));
}

export function unblockSource(source: string) {
  write(read().filter((b) => b.source !== source));
}

export function getBlockedSourcesCount(): number {
  return read().length;
}
