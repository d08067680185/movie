import { type ClassValue, clsx } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

// 板块静态兜底列表：与后端 database.py 种子数据的 key 保持一致。导航/首页优先用
// getSections() 请求到的实时数据（含资源数/分类），请求失败时用这份兜底渲染骨架，
// 避免板块入口因为一次接口失败就整体消失
export const SECTIONS_FALLBACK = [
  { key: "video", name: "影视动画", icon: "🎬" },
  { key: "software", name: "软件工具", icon: "💻" },
  { key: "ebook", name: "电子书", icon: "📚" },
  { key: "music", name: "音乐音频", icon: "🎵" },
  { key: "game", name: "游戏", icon: "🎮" },
];

export const CATEGORY_LABELS: Record<string, string> = {
  movie: "电影", tv: "电视剧", anime: "动漫", variety: "经典资源",
  电影: "电影", 电视剧: "电视剧", 动漫: "动漫", 综艺: "经典资源", 资源: "经典资源", 经典资源: "经典资源",
};

// 全网搜（PanSou）返回的网盘类型，顺序即展示顺序
export const CLOUD_TYPE_LABELS: Record<string, { label: string; icon: string; app: string }> = {
  quark:  { label: "夸克网盘", icon: "⚡", app: "夸克APP" },
  baidu:  { label: "百度网盘", icon: "💾", app: "百度网盘APP" },
  aliyun: { label: "阿里云盘", icon: "☁️", app: "阿里云盘APP" },
  uc:     { label: "UC网盘",   icon: "🌀", app: "UC浏览器" },
  xunlei: { label: "迅雷云盘", icon: "⛈️", app: "迅雷APP" },
  "115":  { label: "115网盘",  icon: "📦", app: "115APP" },
  "123":  { label: "123云盘",  icon: "🔢", app: "123云盘APP" },
  tianyi: { label: "天翼云盘", icon: "📡", app: "天翼云盘APP" },
  mobile: { label: "移动云盘", icon: "📱", app: "移动云盘APP" },
  pikpak: { label: "PikPak",   icon: "🚀", app: "PikPak APP" },
  magnet: { label: "磁力/BT",  icon: "🧲", app: "迅雷/BitComet等BT客户端" },
};

export const LINK_TYPE_LABELS: Record<string, { label: string; bg: string; color: string; border: string; icon: string }> = {
  magnet:     { label: "磁力",     bg: "rgba(249,115,22,0.15)",  color: "#fb923c", border: "rgba(249,115,22,0.3)",  icon: "🧲" },
  pan_baidu:  { label: "百度网盘", bg: "rgba(59,130,246,0.15)",  color: "#60a5fa", border: "rgba(59,130,246,0.3)",  icon: "💾" },
  pan_aliyun: { label: "阿里云盘", bg: "rgba(168,85,247,0.15)",  color: "#c084fc", border: "rgba(168,85,247,0.3)",  icon: "☁️" },
  pan_quark:  { label: "夸克网盘", bg: "rgba(6,182,212,0.15)",   color: "#22d3ee", border: "rgba(6,182,212,0.3)",   icon: "⚡" },
  direct:     { label: "直链",     bg: "rgba(34,197,94,0.15)",   color: "#4ade80", border: "rgba(34,197,94,0.3)",   icon: "🔗" },
  page:       { label: "网页",     bg: "rgba(100,116,139,0.15)", color: "#94a3b8", border: "rgba(100,116,139,0.3)", icon: "🌐" },
};

export const QUALITY_COLORS: Record<string, { bg: string; color: string; border: string }> = {
  "4K":   { bg: "rgba(245,197,24,0.15)",  color: "#fbbf24", border: "rgba(245,197,24,0.3)"  },
  "1080P":{ bg: "rgba(34,197,94,0.15)",   color: "#4ade80", border: "rgba(34,197,94,0.3)"   },
  "720P": { bg: "rgba(59,130,246,0.15)",  color: "#60a5fa", border: "rgba(59,130,246,0.3)"  },
  "480P": { bg: "rgba(100,116,139,0.15)", color: "#94a3b8", border: "rgba(100,116,139,0.3)" },
  "HD":   { bg: "rgba(20,184,166,0.15)",  color: "#2dd4bf", border: "rgba(20,184,166,0.3)"  },
  "SD":   { bg: "rgba(100,116,139,0.15)", color: "#94a3b8", border: "rgba(100,116,139,0.3)" },
};

export function formatRating(rating?: number) {
  if (!rating) return null;
  return rating.toFixed(1);
}
