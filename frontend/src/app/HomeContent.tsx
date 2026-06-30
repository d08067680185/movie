"use client";
import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Search, TrendingUp, Film, Star, Clock, X } from "lucide-react";
import { getHotResources, getLatestResources, getStats, getHotSearches, ResourceCard, Stats } from "@/lib/api";
import ResourceCardComponent from "@/components/ResourceCard";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const CATEGORY_META = [
  { label: "电影", value: "movie", icon: "🎬", color: "#60a5fa", glow: "rgba(96,165,250,0.2)" },
  { label: "电视剧", value: "tv", icon: "📺", color: "#a78bfa", glow: "rgba(167,139,250,0.2)" },
  { label: "动漫", value: "anime", icon: "⛩️", color: "#f472b6", glow: "rgba(244,114,182,0.2)" },
  { label: "综艺", value: "variety", icon: "🎪", color: "#fb923c", glow: "rgba(251,146,60,0.2)" },
];

export default function HomeContent() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hotResources, setHotResources] = useState<ResourceCard[]>([]);
  const [latestResources, setLatestResources] = useState<ResourceCard[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hotKeywords, setHotKeywords] = useState<string[]>([]);

  useEffect(() => {
    Promise.all([getHotResources(), getLatestResources(), getStats()])
      .then(([hot, latest, s]) => {
        setHotResources(hot);
        setLatestResources(latest);
        setStats(s);
      })
      .catch(() => setError("加载失败，请刷新页面重试"))
      .finally(() => setLoading(false));
    getHotSearches().then((hs) => {
      if (hs.length > 0) setHotKeywords(hs.map((h) => h.keyword));
    });
  }, []);

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  }

  const activeCategories = CATEGORY_META.filter(
    (c) => stats && (stats.categories[c.label] ?? 0) > 0
  );

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <Navbar />
      {/* Hero */}
      <div
        className="relative overflow-hidden"
        style={{
          background: "linear-gradient(180deg, var(--hero-start) 0%, var(--hero-end) 100%)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        {/* 背景光晕 */}
        <div className="absolute inset-0 pointer-events-none">
          <div style={{
            position: "absolute", top: "-20%", left: "50%", transform: "translateX(-50%)",
            width: "700px", height: "400px",
            background: "radial-gradient(ellipse, rgba(229,9,20,0.12) 0%, transparent 70%)",
          }} />
          <div style={{
            position: "absolute", bottom: "0", left: "15%",
            width: "300px", height: "200px",
            background: "radial-gradient(ellipse, rgba(96,165,250,0.08) 0%, transparent 70%)",
          }} />
          <div style={{
            position: "absolute", bottom: "0", right: "15%",
            width: "300px", height: "200px",
            background: "radial-gradient(ellipse, rgba(244,114,182,0.08) 0%, transparent 70%)",
          }} />
        </div>

        <div className="relative max-w-4xl mx-auto px-4 py-20 text-center">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Film size={32} style={{ color: "#e50914" }} />
            <h1 className="text-4xl font-black gradient-text" style={{ letterSpacing: "-1px" }}>
              影视资源搜索
            </h1>
          </div>
          <p className="mb-10 text-base" style={{ color: "var(--text-secondary)" }}>
            聚合多源影视资源，一键搜索电影、电视剧、动漫
          </p>

          {/* 搜索框 */}
          <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
            <div
              className="flex items-center gap-3 px-5 py-4 rounded-2xl search-glow"
              style={{
                background: "var(--bg-input)",
                border: "1px solid var(--border-input)",
              }}
            >
              <Search size={20} style={{ color: "var(--text-secondary)", flexShrink: 0 }} />
              <input
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="输入电影、电视剧、动漫名称..."
                className="flex-1 bg-transparent outline-none text-lg"
                style={{ color: "var(--text-primary)" }}
                autoFocus
              />
              {q && (
                <button
                  type="button"
                  onClick={() => setQ("")}
                  className="shrink-0 rounded-full p-1 transition-all"
                  style={{ color: "var(--text-secondary)" }}
                  aria-label="清除"
                >
                  <X size={16} />
                </button>
              )}
              <button
                type="submit"
                className="px-6 py-2 rounded-xl font-semibold text-white transition-all shrink-0 hover:brightness-110 active:scale-95"
                style={{
                  background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)",
                  fontSize: "15px",
                  boxShadow: "0 2px 12px rgba(229,9,20,0.4)",
                }}
              >
                搜索
              </button>
            </div>
          </form>

          {/* 热门搜索 */}
          {hotKeywords.length > 0 && (
            <div className="flex flex-wrap items-center justify-center gap-2 mt-6">
              <span className="text-sm flex items-center gap-1" style={{ color: "var(--text-muted)" }}>
                <TrendingUp size={14} /> 热搜:
              </span>
              {hotKeywords.slice(0, 8).map((kw) => (
                <button
                  key={kw}
                  onClick={() => router.push(`/search?q=${encodeURIComponent(kw)}`)}
                  className="px-3 py-1 rounded-full text-sm transition-all hover:text-white"
                  style={{
                    background: "var(--bg-input)",
                    border: "1px solid var(--border)",
                    color: "var(--text-secondary)",
                  }}
                >
                  {kw}
                </button>
              ))}
            </div>
          )}

          {/* 统计数字 */}
          {stats && (
            <div className="flex items-center justify-center gap-10 mt-10">
              {[
                { label: "影视资源", value: stats.total_resources.toLocaleString(), color: "#e50914" },
                { label: "下载链接", value: stats.total_links.toLocaleString(), color: "#60a5fa" },
                { label: "数据来源", value: stats.total_sources.toString(), color: "#f472b6" },
              ].map((item) => (
                <div key={item.label} className="text-center">
                  <div className="text-2xl font-black" style={{ color: item.color }}>
                    {item.value}
                  </div>
                  <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                    {item.label}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 分类导航 */}
        {activeCategories.length > 0 && (
          <div
            className={`grid gap-4 mb-12 ${
              activeCategories.length === 1
                ? "grid-cols-1 max-w-xs"
                : activeCategories.length === 2
                ? "grid-cols-2"
                : "grid-cols-2 sm:grid-cols-4"
            }`}
          >
            {activeCategories.map((cat) => (
              <button
                key={cat.value}
                onClick={() => router.push(`/search?category=${cat.value}`)}
                className="cat-card flex items-center gap-3 p-4 rounded-xl text-left"
                style={{
                  background: "var(--bg-card)",
                  border: `1px solid var(--border)`,
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.borderColor = cat.color;
                  (e.currentTarget as HTMLElement).style.boxShadow = `0 4px 20px ${cat.glow}`;
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                  (e.currentTarget as HTMLElement).style.boxShadow = "";
                }}
              >
                <span className="text-2xl">{cat.icon}</span>
                <div>
                  <div className="font-semibold" style={{ color: cat.color }}>
                    {cat.label}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    {stats?.categories[cat.label]?.toLocaleString() ?? 0} 部
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* 热门资源 */}
        <div className="flex items-center gap-2 mb-6">
          <Star size={18} fill="#fbbf24" style={{ color: "#fbbf24" }} />
          <h2 className="text-xl font-bold">热门资源</h2>
        </div>

        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i}>
                <div className="skeleton aspect-[2/3] rounded-xl" />
                <div className="skeleton h-4 mt-2 rounded" />
                <div className="skeleton h-3 mt-1 w-2/3 rounded" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center py-16" style={{ color: "var(--text-muted)" }}>
            <p>{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 rounded-lg text-sm transition-all"
              style={{ background: "rgba(229,9,20,0.15)", color: "#ff6070", border: "1px solid rgba(229,9,20,0.3)" }}
            >
              重试
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {hotResources.map((r) => (
              <ResourceCardComponent key={r.id} resource={r} />
            ))}
          </div>
        )}

        {/* 最新入库 */}
        {!loading && !error && latestResources.length > 0 && (
          <div className="mt-14">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <Clock size={18} style={{ color: "#60a5fa" }} />
                <h2 className="text-xl font-bold">最新入库</h2>
              </div>
              <button
                onClick={() => router.push("/search?sort=latest")}
                className="text-sm transition-colors hover:text-white"
                style={{ color: "var(--text-muted)" }}
              >
                查看全部 →
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {latestResources.map((r) => (
                <ResourceCardComponent key={r.id} resource={r} />
              ))}
            </div>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
