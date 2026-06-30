import { type ClassValue, clsx } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export const CATEGORY_LABELS: Record<string, string> = {
  movie: "电影", tv: "电视剧", anime: "动漫", variety: "资源",
  电影: "电影", 电视剧: "电视剧", 动漫: "动漫", 综艺: "资源", 资源: "资源",
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
