"use client";
import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Search, ChevronLeft, ChevronRight, X } from "lucide-react";
import Navbar from "@/components/Navbar";
import ResourceCardComponent from "@/components/ResourceCard";
import Footer from "@/components/Footer";
import { searchResources, SearchResult } from "@/lib/api";

const CATEGORIES = [
  { label: "全部", value: "" },
  { label: "电影", value: "movie" },
  { label: "电视剧", value: "tv" },
  { label: "动漫", value: "anime" },
  { label: "综艺", value: "variety" },
];

const SORT_OPTIONS = [
  { label: "热度", value: "popular" },
  { label: "评分", value: "rating" },
  { label: "最新", value: "newest" },
  { label: "入库", value: "latest" },
];

const currentYear = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 10 }, (_, i) => currentYear - i);

export default function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const q = searchParams.get("q") || "";
  const category = searchParams.get("category") || "";
  const sort = searchParams.get("sort") || "popular";
  const page = parseInt(searchParams.get("page") || "1");

  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    const year = searchParams.get("year");
    searchResources({
      q,
      category: category || undefined,
      year: year ? parseInt(year) : undefined,
      sort,
      page,
      page_size: 24,
    })
      .then(setResult)
      .finally(() => setLoading(false));
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  function updateSearch(params: Record<string, string>) {
    const sp = new URLSearchParams(searchParams.toString());
    Object.entries(params).forEach(([k, v]) => {
      if (v) sp.set(k, v);
      else sp.delete(k);
    });
    sp.delete("page");
    router.push(`/search?${sp.toString()}`);
  }

  function goPage(p: number) {
    const sp = new URLSearchParams(searchParams.toString());
    sp.set("page", String(p));
    router.push(`/search?${sp.toString()}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function clearAllFilters() {
    router.push(q ? `/search?q=${encodeURIComponent(q)}` : "/search");
  }

  const totalPages = result ? Math.ceil(result.total / 24) : 0;
  const activeYear = searchParams.get("year");
  const hasFilters = !!(category || activeYear || sort !== "popular");
  const [jumpInput, setJumpInput] = useState("");

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 标题 + 结果数 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            {q ? (
              <h1 className="text-xl font-bold">
                搜索 <span style={{ color: "#e50914" }}>{`"${q}"`}</span>
                {result && (
                  <span className="text-sm font-normal ml-2" style={{ color: "#a0a0b0" }}>
                    共 {result.total} 个结果
                  </span>
                )}
              </h1>
            ) : (
              <h1 className="text-xl font-bold">
                {CATEGORIES.find((c) => c.value === category)?.label || "全部"} 资源
              </h1>
            )}
          </div>
        </div>

        {/* 分类筛选 */}
        <div className="flex flex-wrap gap-2 mb-4">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => updateSearch({ category: cat.value })}
              className="px-4 py-1.5 rounded-full text-sm font-medium transition-all"
              style={
                category === cat.value
                  ? { background: "#e50914", color: "#fff" }
                  : {
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      color: "#a0a0b0",
                    }
              }
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* 年份 + 排序 + 清除筛选 */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs self-center" style={{ color: "#606070" }}>年份:</span>
            {YEAR_OPTIONS.map((y) => (
              <button
                key={y}
                onClick={() => updateSearch({ year: activeYear === String(y) ? "" : String(y) })}
                className="px-3 py-1 rounded text-xs transition-all"
                style={
                  activeYear === String(y)
                    ? { background: "#e50914", color: "#fff" }
                    : { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)", color: "#a0a0b0" }
                }
              >
                {y}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs" style={{ color: "#606070" }}>排序:</span>
            {SORT_OPTIONS.map((s) => (
              <button
                key={s.value}
                onClick={() => updateSearch({ sort: s.value })}
                className="px-3 py-1 rounded text-xs transition-all"
                style={
                  sort === s.value
                    ? { background: "#e50914", color: "#fff" }
                    : { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)", color: "#a0a0b0" }
                }
              >
                {s.label}
              </button>
            ))}
          </div>

          {hasFilters && (
            <button
              onClick={clearAllFilters}
              className="flex items-center gap-1 px-3 py-1 rounded text-xs transition-all"
              style={{ color: "#e50914", border: "1px solid rgba(229,9,20,0.3)", background: "rgba(229,9,20,0.08)" }}
            >
              <X size={11} />
              清除筛选
            </button>
          )}
        </div>

        {/* 结果网格 */}
        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {Array.from({ length: 24 }).map((_, i) => (
              <div key={i}>
                <div className="skeleton aspect-[2/3] rounded-xl" />
                <div className="skeleton h-4 mt-2 rounded" />
                <div className="skeleton h-3 mt-1 w-2/3 rounded" />
              </div>
            ))}
          </div>
        ) : result && result.items.length > 0 ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {result.items.map((r) => (
                <ResourceCardComponent key={r.id} resource={r} />
              ))}
            </div>

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-10">
                <button
                  onClick={() => goPage(page - 1)}
                  disabled={page <= 1}
                  className="p-2 rounded-lg disabled:opacity-30 transition-all"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
                >
                  <ChevronLeft size={16} />
                </button>

                {(() => {
                  const pages: (number | "...")[] = [];
                  if (totalPages <= 9) {
                    for (let i = 1; i <= totalPages; i++) pages.push(i);
                  } else {
                    pages.push(1);
                    if (page > 4) pages.push("...");
                    const start = Math.max(2, page - 2);
                    const end = Math.min(totalPages - 1, page + 2);
                    for (let i = start; i <= end; i++) pages.push(i);
                    if (page < totalPages - 3) pages.push("...");
                    pages.push(totalPages);
                  }
                  return pages.map((p, i) =>
                    p === "..." ? (
                      <span key={`ellipsis-${i}`} className="w-9 h-9 flex items-center justify-center text-sm" style={{ color: "#606070" }}>…</span>
                    ) : (
                      <button
                        key={p}
                        onClick={() => goPage(p)}
                        className="w-9 h-9 rounded-lg text-sm font-medium transition-all"
                        style={
                          p === page
                            ? { background: "#e50914", color: "#fff" }
                            : {
                                background: "rgba(255,255,255,0.06)",
                                border: "1px solid rgba(255,255,255,0.08)",
                                color: "#a0a0b0",
                              }
                        }
                      >
                        {p}
                      </button>
                    )
                  );
                })()}

                <button
                  onClick={() => goPage(page + 1)}
                  disabled={page >= totalPages}
                  className="p-2 rounded-lg disabled:opacity-30 transition-all"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
                >
                  <ChevronRight size={16} />
                </button>

                {/* 页码跳转 */}
                <div className="flex items-center gap-1.5 ml-2">
                  <span className="text-xs" style={{ color: "#606070" }}>跳至</span>
                  <input
                    type="number"
                    min={1}
                    max={totalPages}
                    value={jumpInput}
                    onChange={(e) => setJumpInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const p = parseInt(jumpInput);
                        if (p >= 1 && p <= totalPages) { goPage(p); setJumpInput(""); }
                      }
                    }}
                    placeholder={String(page)}
                    className="w-12 text-center text-sm rounded-lg outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      color: "#f0f0f5",
                      height: "36px",
                    }}
                  />
                  <span className="text-xs" style={{ color: "#606070" }}>/ {totalPages} 页</span>
                  <button
                    onClick={() => {
                      const p = parseInt(jumpInput);
                      if (p >= 1 && p <= totalPages) { goPage(p); setJumpInput(""); }
                    }}
                    disabled={!jumpInput || parseInt(jumpInput) < 1 || parseInt(jumpInput) > totalPages}
                    className="px-3 rounded-lg text-xs font-medium transition-all disabled:opacity-30"
                    style={{
                      background: "rgba(229,9,20,0.15)",
                      border: "1px solid rgba(229,9,20,0.3)",
                      color: "#e50914",
                      height: "36px",
                    }}
                  >
                    GO
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-24 text-center" style={{ color: "#606070" }}>
            <Search size={48} className="mb-4 opacity-30" />
            <p className="text-lg">没有找到相关资源</p>
            {q && (
              <div className="mt-4 space-y-1 text-sm">
                <p>试试：</p>
                <div className="flex flex-wrap justify-center gap-2 mt-2">
                  {[q.slice(0, 2), q.replace(/[^一-龥]/g, "").slice(0, 4)].filter((s) => s && s !== q).map((s) => (
                    <button
                      key={s}
                      onClick={() => {
                        const sp = new URLSearchParams(searchParams.toString());
                        sp.set("q", s);
                        sp.delete("page");
                        router.push(`/search?${sp.toString()}`);
                      }}
                      className="px-3 py-1 rounded-full text-xs transition-all hover:text-white"
                      style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)", color: "#a0a0b0" }}
                    >
                      {s}
                    </button>
                  ))}
                  <button
                    onClick={() => router.push("/search?sort=latest")}
                    className="px-3 py-1 rounded-full text-xs transition-all hover:text-white"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)", color: "#a0a0b0" }}
                  >
                    浏览全部资源
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
