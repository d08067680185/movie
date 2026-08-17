"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, useRef, FormEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import { Search, X, Sun, Moon, Menu, Heart } from "lucide-react";
import { getFavoritesCount } from "@/lib/favorites";
import { getPanFavoritesCount } from "@/lib/panFavorites";
import { getSections, getSearchSuggestions } from "@/lib/api";
import { SECTIONS_FALLBACK } from "@/lib/utils";

const totalFavCount = () => getFavoritesCount() + getPanFavoritesCount();

const SECTION_UTILITY_LINKS = [
  { label: "💽 网盘搜索", val: "__pan" },
  { label: "⬇️ 视频下载", val: "__download" },
];

export default function Navbar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [favCount, setFavCount] = useState(0);
  const [sections, setSections] = useState(SECTIONS_FALLBACK);
  const [suggestions, setSuggestions] = useState<{ keyword: string; count: number }[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getSections().then((data) => {
      if (data.length > 0) {
        setSections(data.map((s) => ({ key: s.key, name: s.name, icon: s.icon || "" })));
      }
    });
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setQ(searchParams.get("q") || "");
  }, [searchParams]);

  // 输入时防抖300ms拉一次候选词，避免每敲一个字都发请求
  useEffect(() => {
    if (!q.trim()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSuggestions([]);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      getSearchSuggestions(q).then((res) => {
        if (!cancelled) setSuggestions(res);
      });
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [q]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("movie-theme");
      if (saved === "light" || saved === "dark") {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setTheme(saved);
        document.documentElement.setAttribute("data-theme", saved);
      }
    } catch {}
    setFavCount(totalFavCount());
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

  // 监听收藏数变化事件
  useEffect(() => {
    function onFavoritesChanged() {
      setFavCount(totalFavCount());
    }
    window.addEventListener("favoritesChanged", onFavoritesChanged);
    return () => window.removeEventListener("favoritesChanged", onFavoritesChanged);
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("movie-theme", next); } catch {}
  }

  function doSearch(keyword: string) {
    setShowSuggestions(false);
    setActiveSuggestion(-1);
    if (keyword.trim()) {
      router.push(`/search?q=${encodeURIComponent(keyword.trim())}`);
    } else {
      router.push("/search");
    }
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    doSearch(q);
  }

  function pickSuggestion(keyword: string) {
    setQ(keyword);
    doSearch(keyword);
  }

  function handleInputKeyDown(e: ReactKeyboardEvent<HTMLInputElement>) {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveSuggestion((i) => (i + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveSuggestion((i) => (i <= 0 ? suggestions.length - 1 : i - 1));
    } else if (e.key === "Enter" && activeSuggestion >= 0) {
      e.preventDefault();
      pickSuggestion(suggestions[activeSuggestion].keyword);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
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
      <div className="max-w-7xl mx-auto px-3 sm:px-4 h-14 flex items-center gap-1.5 sm:gap-6">
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
          资源共享
        </Link>

        <form onSubmit={handleSearch} className="relative flex-1 min-w-0 max-w-xl">
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
              onChange={(e) => { setQ(e.target.value); setShowSuggestions(true); setActiveSuggestion(-1); }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setShowSuggestions(false)}
              onKeyDown={handleInputKeyDown}
              placeholder="搜索影视、软件、电子书、音乐、游戏… (按 / 快速定位)"
              className="flex-1 bg-transparent outline-none text-sm"
              style={{ color: "var(--text-primary)" }}
              autoComplete="off"
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

          {/* 搜索建议下拉：复用SearchLog热词统计，输入时防抖300ms拉取 */}
          {showSuggestions && suggestions.length > 0 && (
            <ul
              className="absolute left-0 right-0 top-full mt-1.5 rounded-lg overflow-hidden z-50"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 8px 24px rgba(0,0,0,0.25)" }}
            >
              {suggestions.map((s, i) => (
                <li key={s.keyword}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => pickSuggestion(s.keyword)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors"
                    style={i === activeSuggestion
                      ? { background: "rgba(229,9,20,0.1)", color: "#e50914" }
                      : { color: "var(--text-secondary)" }}
                  >
                    <Search size={12} className="shrink-0 opacity-60" />
                    <span className="flex-1 truncate">{s.keyword}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </form>

        <div className="flex items-center gap-2.5 sm:gap-4 text-sm shrink-0">
          <Link
            href="/pan"
            className="transition-colors hidden sm:block font-medium"
            style={{ color: "var(--text-secondary)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#22d3ee")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            网盘搜索
          </Link>
          <Link
            href="/download"
            className="transition-colors hidden sm:block font-medium"
            style={{ color: "var(--text-secondary)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#22d3ee")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            视频下载
          </Link>
          {sections.map(({ key, name, icon }) => (
            <Link
              key={key}
              href={`/s/${key}`}
              className="transition-colors hidden sm:block font-medium"
              style={{ color: "var(--text-secondary)" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#22d3ee")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
            >
              {icon} {name}
            </Link>
          ))}

          <Link
            href="/favorites"
            className="relative shrink-0 transition-colors"
            style={{ color: favCount > 0 ? "#e50914" : "var(--text-secondary)" }}
            title={`收藏夹 (${favCount})`}
            aria-label={`收藏夹 (${favCount})`}
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
          {SECTION_UTILITY_LINKS.map(({ label, val }) => (
            <Link
              key={val}
              href={val === "__pan" ? "/pan" : "/download"}
              onClick={() => setMobileOpen(false)}
              className="flex items-center gap-3 px-5 py-3.5 text-sm font-medium transition-colors"
              style={{ color: "var(--text-secondary)", borderBottom: "1px solid var(--border)" }}
            >
              {label}
            </Link>
          ))}
          {sections.map(({ key, name, icon }) => (
            <Link
              key={key}
              href={`/s/${key}`}
              onClick={() => setMobileOpen(false)}
              className="flex items-center gap-3 px-5 py-3.5 text-sm font-medium transition-colors"
              style={{ color: "var(--text-secondary)", borderBottom: "1px solid var(--border)" }}
            >
              {icon} {name}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
