"use client";
import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Search, TrendingUp, Film, Star, Clock } from "lucide-react";
import { getHotResources, getLatestResources, getStats, getHotSearches, ResourceCard, Stats } from "@/lib/api";
import ResourceCardComponent from "@/components/ResourceCard";
import Footer from "@/components/Footer";

const CATEGORY_META: { label: string; value: string; icon: string; color: string }[] = [
  { label: "电影", value: "movie", icon: "🎬", color: "#3b82f6" },
  { label: "电视剧", value: "tv", icon: "📺", color: "#a855f7" },
  { label: "动漫", value: "anime", icon: "⛩️", color: "#ec4899" },
  { label: "综艺", value: "variety", icon: "🎪", color: "#f97316" },
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
    if (q.trim()) {
      router.push(`/search?q=${encodeURIComponent(q.trim())}`);
    }
  }

  // 只显示有内容的分类
  const activeCategories = CATEGORY_META.filter(
    (c) => stats && (stats.categories[c.label] ?? 0) > 0
  );

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      {/* Hero 区域 */}
      <div
        className="relative overflow-hidden"
        style={{
          background: "linear-gradient(180deg, #0a0a10 0%, #0f0f13 100%)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div
          className="absolute inset-0 opacity-20"
          style={{
            background: "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(229,9,20,0.15) 0%, transparent 70%)",
          }}
        />

        <div className="relative max-w-4xl mx-auto px-4 py-20 text-center">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Film size={32} style={{ color: "#e50914" }} />
            <h1 className="text-4xl font-black" style={{ letterSpacing: "-1px" }}>
              影视资源搜索
            </h1>
          </div>
          <p className="mb-10 text-lg" style={{ color: "#a0a0b0" }}>
            聚合多源影视资源，一键搜索电影、电视剧、动漫
          </p>

          {/* 搜索框 */}
          <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
            <div
              className="flex items-center gap-3 px-5 py-4 rounded-2xl search-glow"
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.12)",
              }}
            >
              <Search size={20} style={{ color: "#a0a0b0", flexShrink: 0 }} />
              <input
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="输入电影、电视剧、动漫名称..."
                className="flex-1 bg-transparent outline-none text-lg"
                style={{ color: "#f0f0f5" }}
                autoFocus
              />
              <button
                type="submit"
                className="px-6 py-2 rounded-xl font-semibold text-white transition-all shrink-0"
                style={{
                  background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)",
                  fontSize: "15px",
                }}
              >
                搜索
              </button>
            </div>
          </form>

          {/* 热门搜索 */}
          {hotKeywords.length > 0 && (
            <div className="flex flex-wrap items-center justify-center gap-2 mt-6">
              <span className="text-sm flex items-center gap-1" style={{ color: "#606070" }}>
                <TrendingUp size={14} /> 热搜:
              </span>
              {hotKeywords.slice(0, 8).map((kw) => (
                <button
                  key={kw}
                  onClick={() => router.push(`/search?q=${encodeURIComponent(kw)}`)}
                  className="px-3 py-1 rounded-full text-sm transition-all hover:text-white"
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    color: "#a0a0b0",
                  }}
                >
                  {kw}
                </button>
              ))}
            </div>
          )}

          {/* 统计数字 */}
          {stats && (
            <div className="flex items-center justify-center gap-8 mt-10">
              {[
                { label: "影视资源", value: stats.total_resources.toLocaleString() },
                { label: "下载链接", value: stats.total_links.toLocaleString() },
                { label: "数据来源", value: stats.total_sources.toString() },
              ].map((item) => (
                <div key={item.label} className="text-center">
                  <div className="text-2xl font-black" style={{ color: "#e50914" }}>
                    {item.value}
                  </div>
                  <div className="text-xs mt-1" style={{ color: "#606070" }}>
                    {item.label}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 分类导航（只显示有内容的分类） */}
        {activeCategories.length > 0 && (
          <div className={`grid gap-4 mb-12 ${activeCategories.length === 1 ? "grid-cols-1 max-w-xs" : activeCategories.length === 2 ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>
            {activeCategories.map((cat) => (
              <button
                key={cat.value}
                onClick={() => router.push(`/search?category=${cat.value}`)}
                className="flex items-center gap-3 p-4 rounded-xl transition-all hover:scale-105"
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                }}
              >
                <span className="text-2xl">{cat.icon}</span>
                <div className="text-left">
                  <div className="font-semibold">{cat.label}</div>
                  <div className="text-xs" style={{ color: "#606070" }}>
                    {stats?.categories[cat.label]?.toLocaleString() ?? 0} 部
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* 热门资源 */}
        <div className="flex items-center gap-2 mb-6">
          <Star size={18} style={{ color: "#f5c518" }} fill="#f5c518" />
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
          <div className="flex flex-col items-center py-16" style={{ color: "#606070" }}>
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
          <div className="mt-12">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <Clock size={18} style={{ color: "#60a5fa" }} />
                <h2 className="text-xl font-bold">最新入库</h2>
              </div>
              <button
                onClick={() => router.push("/search?sort=latest")}
                className="text-sm transition-colors hover:text-white"
                style={{ color: "#606070" }}
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
