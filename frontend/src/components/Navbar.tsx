"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, FormEvent } from "react";
import { Search, X } from "lucide-react";

export default function Navbar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") || "");

  useEffect(() => {
    setQ(searchParams.get("q") || "");
  }, [searchParams]);

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
        background: "rgba(13,13,18,0.96)",
        borderBottom: "1px solid rgba(255,255,255,0.09)",
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
              background: "rgba(255,255,255,0.07)",
              border: "1px solid rgba(255,255,255,0.12)",
              transition: "all 0.2s",
            }}
          >
            <Search size={16} style={{ color: "#9898b0", flexShrink: 0 }} />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索电影、电视剧、动漫..."
              className="flex-1 bg-transparent outline-none text-sm"
              style={{ color: "#f2f2f8" }}
            />
            {q && (
              <button
                type="button"
                onClick={clearSearch}
                className="shrink-0 rounded-full p-0.5 transition-all hover:bg-white/10"
                style={{ color: "#9898b0" }}
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
          ].map(({ label, val, color }) => (
            <Link
              key={val}
              href={`/search?category=${val}`}
              className="hover:text-white transition-colors hidden sm:block font-medium"
              style={{ color: "#9898b0" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = color)}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#9898b0")}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
