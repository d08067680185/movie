"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, FormEvent } from "react";
import { Search } from "lucide-react";

export default function Navbar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") || "");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
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

  return (
    <nav
      style={{
        background: "rgba(15,15,19,0.95)",
        borderBottom: "1px solid rgba(255,255,255,0.07)",
        backdropFilter: "blur(12px)",
      }}
      className="sticky top-0 z-50"
    >
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
        <Link
          href="/"
          className="text-xl font-bold shrink-0"
          style={{ color: "#e50914", letterSpacing: "-0.5px" }}
        >
          影视搜索
        </Link>

        <form onSubmit={handleSearch} className="flex-1 max-w-xl">
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg search-glow"
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.1)",
              transition: "all 0.2s",
            }}
          >
            <Search size={16} style={{ color: "#a0a0b0", flexShrink: 0 }} />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索电影、电视剧、动漫..."
              className="flex-1 bg-transparent outline-none text-sm"
              style={{ color: "#f0f0f5" }}
            />
          </div>
        </form>

        <div className="flex items-center gap-4 text-sm shrink-0">
          {["电影", "电视剧", "动漫", "综艺"].map((cat) => {
            const val = { 电影: "movie", 电视剧: "tv", 动漫: "anime", 综艺: "variety" }[cat];
            return (
              <Link
                key={cat}
                href={`/search?category=${val}`}
                style={{ color: "#a0a0b0" }}
                className="hover:text-white transition-colors hidden sm:block"
              >
                {cat}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
