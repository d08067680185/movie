"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, useRef, FormEvent } from "react";
import { Search, X, Sun, Moon, Menu, Heart } from "lucide-react";
import { getFavoritesCount } from "@/lib/favorites";

const MOBILE_CATEGORIES = [
  { label: "🎬 电影", val: "movie" },
  { label: "📺 电视剧", val: "tv" },
  { label: "⛩️ 动漫", val: "anime" },
  { label: "📦 经典资源", val: "variety" },
];

export default function Navbar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [favCount, setFavCount] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setQ(searchParams.get("q") || "");
  }, [searchParams]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("movie-theme");
      if (saved === "light" || saved === "dark") {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setTheme(saved);
        document.documentElement.setAttribute("data-theme", saved);
      }
    } catch {}
    setFavCount(getFavoritesCount());
  }, []);

  // 按 / 聚焦搜索框，Esc 失去焦点
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape") {
        inputRef.current?.blur();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("movie-theme", next); } catch {}
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (q.trim()) {
      router.push(`/search?q=${encodeURIComponent(q.trim())}`);
    } else {
      router.push("/search");
    }
  }

  function clearSearch() {
    setQ("");
    const sp = new URLSearchParams(searchParams.toString());
    sp.delete("q");
    sp.delete("page");
    router.push(`/search?${sp.toString()}`);
  }

  return (
    <nav
      style={{
        background: "var(--nav-bg)",
        borderBottom: "1px solid var(--border)",
        backdropFilter: "blur(14px)",
      }}
      className="sticky top-0 z-50"
    >
      <div className="max-w-7xl mx-auto px-3 sm:px-4 h-14 flex items-center gap-2 sm:gap-6">
        {/* 移动端汉堡按钮 */}
        <button
          className="sm:hidden p-1.5 rounded-lg transition-colors shrink-0"
          style={{ color: "var(--text-secondary)" }}
          onClick={() => setMobileOpen(o => !o)}
          aria-label="菜单"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <Link
          href="/"
          className="text-base sm:text-xl font-bold shrink-0 gradient-text"
          style={{ letterSpacing: "-0.5px" }}
        >
          影视搜索
        </Link>

        <form onSubmit={handleSearch} className="flex-1 max-w-xl">
          <div
            className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-2 rounded-lg search-glow"
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-input)",
              transition: "all 0.2s",
            }}
          >
            <Search size={16} style={{ color: "var(--text-secondary)", flexShrink: 0 }} />
            <input
              ref={inputRef}
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索电影、电视剧、动漫… (按 / 快速定位)"
              className="flex-1 bg-transparent outline-none text-sm"
              style={{ color: "var(--text-primary)" }}
            />
            {q && (
              <button
                type="button"
                onClick={clearSearch}
                className="shrink-0 rounded-full p-0.5 transition-all"
                style={{ color: "var(--text-secondary)" }}
                aria-label="清除搜索"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </form>

        <div className="flex items-center gap-4 text-sm shrink-0">
          {[
            { label: "动漫", val: "anime", color: "#f472b6" },
            { label: "电影", val: "movie", color: "#60a5fa" },
            { label: "电视剧", val: "tv", color: "#a78bfa" },
            { label: "经典资源", val: "variety", color: "#fb923c" },
          ].map(({ label, val, color }) => (
            <Link
              key={val}
              href={`/search?category=${val}`}
              className="transition-colors hidden sm:block font-medium"
              style={{ color: "var(--text-secondary)" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = color)}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
            >
              {label}
            </Link>
          ))}

          <Link
            href="/favorites"
            className="relative shrink-0 transition-colors"
            style={{ color: favCount > 0 ? "#e50914" : "var(--text-secondary)" }}
            title={`收藏夹 (${favCount})`}
          >
            <Heart size={16} fill={favCount > 0 ? "#e50914" : "none"} />
            {favCount > 0 && (
              <span
                className="absolute -top-1.5 -right-1.5 text-[9px] font-bold w-3.5 h-3.5 flex items-center justify-center rounded-full"
                style={{ background: "#e50914", color: "#fff" }}
              >
                {favCount > 9 ? "9+" : favCount}
              </span>
            )}
          </Link>

          <button
            onClick={toggleTheme}
            className="theme-toggle shrink-0"
            aria-label={theme === "dark" ? "切换到日间模式" : "切换到夜间模式"}
            title={theme === "dark" ? "日间模式" : "夜间模式"}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </div>

      {/* 移动端下拉菜单 */}
      {mobileOpen && (
        <div
          className="sm:hidden absolute left-0 right-0 z-40 border-t"
          style={{ background: "var(--nav-bg)", borderColor: "var(--border)" }}
        >
          {MOBILE_CATEGORIES.map(({ label, val }) => (
            <Link
              key={val}
              href={`/search?category=${val}`}
              onClick={() => setMobileOpen(false)}
              className="flex items-center gap-3 px-5 py-3.5 text-sm font-medium transition-colors"
              style={{ color: "var(--text-secondary)", borderBottom: "1px solid var(--border)" }}
            >
              {label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
