"use client";
import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Search, ChevronLeft, ChevronRight, X, SlidersHorizontal } from "lucide-react";
import Navbar from "@/components/Navbar";
import ResourceCardComponent from "@/components/ResourceCard";
import Footer from "@/components/Footer";
import { searchResources, SearchResult } from "@/lib/api";

const CATEGORIES = [
  { label: "全部", value: "" },
  { label: "电影", value: "movie" },
  { label: "电视剧", value: "tv" },
  { label: "动漫", value: "anime" },
  { label: "经典资源", value: "variety" },
];

const SORT_OPTIONS = [
  { label: "热度", value: "popular" },
  { label: "评分", value: "rating" },
  { label: "最新", value: "newest" },
  { label: "入库", value: "latest" },
];

const currentYear = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 10 }, (_, i) => currentYear - i);

const INACTIVE_BTN = {
  background: "var(--bg-input)",
  border: "1px solid var(--border-input)",
  color: "var(--text-secondary)",
} as const;

const HISTORY_KEY = "movie-search-history";
const MAX_HISTORY = 10;

function readHistory(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveToHistory(q: string) {
  if (!q.trim()) return;
  try {
    const prev = readHistory().filter((h) => h !== q.trim());
    localStorage.setItem(HISTORY_KEY, JSON.stringify([q.trim(), ...prev].slice(0, MAX_HISTORY)));
  } catch {}
}

function clearHistory() {
  try { localStorage.removeItem(HISTORY_KEY); } catch {}
}

export default function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const q = searchParams.get("q") || "";
  const category = searchParams.get("category") || "";
  const sort = searchParams.get("sort") || "popular";
  const page = parseInt(searchParams.get("page") || "1");

  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<string[]>([]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHistory(readHistory());
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    if (q) {
      saveToHistory(q);
      setHistory(readHistory());
    }
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
  const activeGenre = searchParams.get("genre") || "";
  const hasFilters = !!(category || activeYear || sort !== "popular" || activeGenre);
  const [jumpInput, setJumpInput] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const GENRE_OPTIONS = ["动作", "爱情", "喜剧", "科幻", "恐怖", "悬疑", "动画", "奇幻", "历史", "犯罪", "剧情"];

  // 有年份/类型筛选时自动展开
  useEffect(() => {
    if (activeYear || activeGenre) setFiltersOpen(true);
  }, [activeYear, activeGenre]);

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 标题 + 结果数 */}
        <div className="flex items-center justify-between mb-4">
          <div>
            {q ? (
              <h1 className="text-xl font-bold">
                搜索 <span style={{ color: "#e50914" }}>{`"${q}"`}</span>
                {result && (
                  <span className="text-sm font-normal ml-2" style={{ color: "var(--text-secondary)" }}>
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

        {/* 搜索历史 */}
        {!q && history.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-5 pb-4" style={{ borderBottom: "1px solid var(--border)" }}>
            <span className="text-xs shrink-0" style={{ color: "var(--text-muted)" }}>最近搜索:</span>
            {history.map((h) => (
              <button
                key={h}
                onClick={() => router.push(`/search?q=${encodeURIComponent(h)}`)}
                className="px-3 py-1 rounded-full text-xs transition-all"
                style={INACTIVE_BTN}
              >
                {h}
              </button>
            ))}
            <button
              onClick={() => { clearHistory(); setHistory([]); }}
              className="text-xs ml-auto"
              style={{ color: "var(--text-muted)" }}
            >
              清除历史
            </button>
          </div>
        )}

        {/* 分类 + 排序 + 筛选切换 */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => updateSearch({ category: cat.value })}
              className="px-3 sm:px-4 py-1.5 rounded-full text-sm font-medium transition-all"
              style={
                category === cat.value
                  ? { background: "#e50914", color: "#fff" }
                  : INACTIVE_BTN
              }
            >
              {cat.label}
            </button>
          ))}

          <div className="flex items-center gap-1.5 ml-auto">
            {/* 排序（始终显示） */}
            {SORT_OPTIONS.map((s) => (
              <button
                key={s.value}
                onClick={() => updateSearch({ sort: s.value })}
                className="px-2.5 py-1.5 rounded text-xs transition-all"
                style={sort === s.value ? { background: "#e50914", color: "#fff" } : INACTIVE_BTN}
              >
                {s.label}
              </button>
            ))}

            {/* 移动端：筛选折叠按钮 */}
            <button
              onClick={() => setFiltersOpen(v => !v)}
              className="sm:hidden flex items-center gap-1 px-2.5 py-1.5 rounded text-xs transition-all"
              style={{
                ...(filtersOpen || activeYear || activeGenre
                  ? { background: "rgba(229,9,20,0.15)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)" }
                  : INACTIVE_BTN),
              }}
            >
              <SlidersHorizontal size={12} />
              筛选{(activeYear || activeGenre) ? " ●" : ""}
            </button>

            {hasFilters && (
              <button
                onClick={clearAllFilters}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded text-xs transition-all"
                style={{ color: "#e50914", border: "1px solid rgba(229,9,20,0.3)", background: "rgba(229,9,20,0.08)" }}
              >
                <X size={11} />
                <span className="hidden sm:inline">清除</span>
              </button>
            )}
          </div>
        </div>

        {/* 年份 + 类型筛选：桌面始终展开，手机可折叠 */}
        <div className={`${filtersOpen ? "block" : "hidden"} sm:block`}>
          {/* 年份筛选 */}
          <div className="flex flex-wrap items-center gap-1.5 mb-3">
            <span className="text-xs self-center shrink-0" style={{ color: "var(--text-muted)" }}>年份:</span>
            {YEAR_OPTIONS.map((y) => (
              <button
                key={y}
                onClick={() => updateSearch({ year: activeYear === String(y) ? "" : String(y) })}
                className="px-2.5 py-1 rounded text-xs transition-all"
                style={activeYear === String(y) ? { background: "#e50914", color: "#fff" } : INACTIVE_BTN}
              >
                {y}
              </button>
            ))}
          </div>

          {/* 类型筛选 */}
          <div className="flex flex-wrap items-center gap-1.5 mb-4 sm:mb-6">
            <span className="text-xs self-center shrink-0" style={{ color: "var(--text-muted)" }}>类型:</span>
            {GENRE_OPTIONS.map((g) => (
              <button
                key={g}
                onClick={() => updateSearch({ genre: activeGenre === g ? "" : g })}
                className="px-2.5 py-1 rounded text-xs transition-all"
                style={activeGenre === g ? { background: "#e50914", color: "#fff" } : INACTIVE_BTN}
              >
                {g}
              </button>
            ))}
          </div>
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
                  style={INACTIVE_BTN}
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
                      <span key={`ellipsis-${i}`} className="w-9 h-9 flex items-center justify-center text-sm" style={{ color: "var(--text-muted)" }}>…</span>
                    ) : (
                      <button
                        key={p}
                        onClick={() => goPage(p)}
                        className="w-9 h-9 rounded-lg text-sm font-medium transition-all"
                        style={
                          p === page
                            ? { background: "#e50914", color: "#fff" }
                            : INACTIVE_BTN
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
                  style={INACTIVE_BTN}
                >
                  <ChevronRight size={16} />
                </button>

                {/* 页码跳转（小屏隐藏） */}
                <div className="hidden sm:flex items-center gap-1.5 ml-2">
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>跳至</span>
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
                      ...INACTIVE_BTN,
                      color: "var(--text-primary)",
                      height: "36px",
                    }}
                  />
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>/ {totalPages} 页</span>
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
          <div className="flex flex-col items-center justify-center py-24 text-center" style={{ color: "var(--text-muted)" }}>
            <Search size={48} className="mb-4 opacity-30" />
            <p className="text-lg">没有找到相关资源</p>
            {q && (
              <div className="mt-4 space-y-1 text-sm">
                <p>试试：</p>
                <div className="flex flex-wrap justify-center gap-2 mt-2">
                  {[
                    q.length > 2 ? q.slice(0, Math.ceil(q.length / 2)) : null,
                    q.replace(/[^一-鿿]/g, "").slice(0, 4) || null,
                  ].filter((s): s is string => !!s && s !== q && s.length >= 1).map((s) => (
                    <button
                      key={s}
                      onClick={() => {
                        const sp = new URLSearchParams(searchParams.toString());
                        sp.set("q", s);
                        sp.delete("page");
                        router.push(`/search?${sp.toString()}`);
                      }}
                      className="px-3 py-1 rounded-full text-xs transition-all"
                      style={INACTIVE_BTN}
                    >
                      {s}
                    </button>
                  ))}
                  <button
                    onClick={() => router.push("/search?sort=latest")}
                    className="px-3 py-1 rounded-full text-xs transition-all"
                    style={INACTIVE_BTN}
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
