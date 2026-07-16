"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Globe, RefreshCw } from "lucide-react";
import { liveSearch, getHotResources, LiveSearchResult, LiveSearchItem, ResourceCard } from "@/lib/api";
import { CLOUD_TYPE_LABELS } from "@/lib/utils";
import PanLinkModal from "./PanLinkModal";

const RANKING_CATEGORIES = [
  { label: "电影", value: "movie" },
  { label: "电视剧", value: "tv" },
  { label: "动漫", value: "anime" },
];

function HotRankings() {
  const [rankings, setRankings] = useState<Record<string, ResourceCard[]>>({});

  useEffect(() => {
    Promise.all(
      RANKING_CATEGORIES.map((c) => getHotResources(c.value, 5).catch(() => [] as ResourceCard[]))
    ).then((results) => {
      const map: Record<string, ResourceCard[]> = {};
      RANKING_CATEGORIES.forEach((c, i) => { map[c.value] = results[i]; });
      setRankings(map);
    });
  }, []);

  return (
    <div className="space-y-5">
      {RANKING_CATEGORIES.map((cat) => {
        const items = rankings[cat.value] || [];
        if (items.length === 0) return null;
        return (
          <div
            key={cat.value}
            className="rounded-xl p-4"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
          >
            <h3 className="text-sm font-bold mb-3 flex items-center gap-1.5">
              <span className="w-1 h-4 rounded" style={{ background: "#e50914" }} />
              {cat.label}热榜
            </h3>
            <ol className="space-y-2">
              {items.map((r, i) => (
                <li key={r.id}>
                  <Link
                    href={`/detail/${r.id}`}
                    className="flex items-center gap-2 text-sm group"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    <span
                      className="w-5 text-center font-bold shrink-0 text-xs"
                      style={{ color: i < 3 ? "#e50914" : "var(--text-muted)" }}
                    >
                      {i + 1}
                    </span>
                    <span className="truncate group-hover:underline">{r.title}</span>
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
    </div>
  );
}

export default function LiveSearchResults({ q }: { q: string }) {
  const [result, setResult] = useState<LiveSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeType, setActiveType] = useState<string>("");
  const [modalItem, setModalItem] = useState<{ item: LiveSearchItem; type: string } | null>(null);

  useEffect(() => {
    if (!q.trim()) {
      setResult(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setActiveType("");
    liveSearch(q)
      .then((r) => { if (!cancelled) setResult(r); })
      .catch(() => { if (!cancelled) setError("全网搜服务暂时不可用，请稍后重试"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [q]);

  if (!q.trim()) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center" style={{ color: "var(--text-muted)" }}>
        <Globe size={48} className="mb-4 opacity-30" />
        <p className="text-lg">输入关键词，实时聚合全网网盘资源</p>
        <p className="text-sm mt-2">支持夸克 / 百度 / 阿里 / 迅雷 / 115 等网盘</p>
      </div>
    );
  }

  const types = result?.types || [];
  const shownType = activeType || (types[0]?.type ?? "");
  const items = result?.by_type[shownType] || [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[170px_minmax(0,1fr)_240px] gap-5">
      {/* 左侧：网盘类型筛选 */}
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <div
          className="rounded-xl p-3 flex lg:flex-col gap-1.5 overflow-x-auto"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
        >
          <h3 className="hidden lg:flex text-sm font-bold mb-1 items-center gap-1.5">
            <span className="w-1 h-4 rounded" style={{ background: "#e50914" }} />
            筛选
          </h3>
          {types.length === 0 && (
            <span className="text-xs py-1" style={{ color: "var(--text-muted)" }}>
              {loading ? "搜索中…" : "暂无来源"}
            </span>
          )}
          {types.map((t) => {
            const meta = CLOUD_TYPE_LABELS[t.type] || { label: t.type, icon: "🔗" };
            const active = shownType === t.type;
            return (
              <button
                key={t.type}
                onClick={() => setActiveType(t.type)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-all text-left"
                style={active
                  ? { background: "rgba(229,9,20,0.12)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)", fontWeight: 600 }
                  : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
              >
                <span>{meta.icon}</span>
                {meta.label}
                <span className="ml-auto text-xs" style={{ color: active ? "#e50914" : "var(--text-muted)" }}>
                  {t.count}
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      {/* 中间：结果列表 */}
      <div
        className="rounded-xl px-4 sm:px-6 py-4 min-h-[300px]"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
      >
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-center" style={{ color: "var(--text-muted)" }}>
            <RefreshCw size={32} className="mb-4 animate-spin opacity-50" />
            <p className="text-sm">正在聚合全网资源，首次搜索约需 5-15 秒…</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="text-4xl mb-4">⚠️</div>
            <p style={{ color: "var(--text-primary)" }}>{error}</p>
          </div>
        ) : result && result.total > 0 ? (
          <>
            <p className="text-center text-sm py-2 mb-2" style={{ color: "var(--text-secondary)" }}>
              为您找到【<span style={{ color: "#e50914", fontWeight: 600 }}>{q}</span>】相关资源{" "}
              <span style={{ color: "#e50914", fontWeight: 600 }}>{result.total}</span> 条
            </p>
            <ul>
              {items.map((item, i) => (
                <li
                  key={`${item.url}-${i}`}
                  className="py-4 flex flex-col sm:flex-row sm:items-center gap-3"
                  style={{ borderBottom: "1px dashed var(--border)" }}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium leading-relaxed break-all" style={{ color: "var(--text-primary)" }}>
                      {item.title}
                    </p>
                    <p className="text-xs mt-1.5 flex items-center gap-1" style={{ color: "var(--text-muted)" }}>
                      <Globe size={11} />
                      来源: {(CLOUD_TYPE_LABELS[shownType] || { label: shownType }).label}
                      {item.password && <span className="ml-2">提取码: {item.password}</span>}
                    </p>
                  </div>
                  <button
                    onClick={() => setModalItem({ item, type: shownType })}
                    className="shrink-0 self-end sm:self-center px-5 py-2 rounded-lg text-sm font-medium transition-all"
                    style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)", color: "#fff" }}
                  >
                    获取资源
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-20 text-center" style={{ color: "var(--text-muted)" }}>
            <Search size={40} className="mb-4 opacity-30" />
            <p>全网未找到相关资源，换个关键词试试</p>
          </div>
        )}
      </div>

      {/* 右侧：分类热榜 */}
      <aside className="hidden lg:block lg:sticky lg:top-20 lg:self-start">
        <HotRankings />
      </aside>

      {modalItem && (
        <PanLinkModal
          item={modalItem.item}
          cloudType={modalItem.type}
          onClose={() => setModalItem(null)}
        />
      )}
    </div>
  );
}
