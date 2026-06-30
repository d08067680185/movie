"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, FormEvent } from "react";
import { Search, X, Sun, Moon } from "lucide-react";

export default function Navbar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    setQ(searchParams.get("q") || "");
  }, [searchParams]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("movie-theme");
      if (saved === "light" || saved === "dark") setTheme(saved);
    } catch {}
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
    router.push("/search");
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
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
        <Link
          href="/"
          className="text-xl font-bold shrink-0 gradient-text"
          style={{ letterSpacing: "-0.5px" }}
        >
          影视搜索
        </Link>

        <form onSubmit={handleSearch} className="flex-1 max-w-xl">
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg search-glow"
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-input)",
              transition: "all 0.2s",
            }}
          >
            <Search size={16} style={{ color: "var(--text-secondary)", flexShrink: 0 }} />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索电影、电视剧、动漫..."
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
            { label: "资源", val: "variety", color: "#fb923c" },
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
    </nav>
  );
}
