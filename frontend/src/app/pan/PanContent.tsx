"use client";
import { useEffect, useState, FormEvent } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Search, X } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import LiveSearchResults from "@/components/LiveSearchResults";
import { getHotSearches } from "@/lib/api";

const INACTIVE_BTN = {
  background: "var(--bg-input)",
  border: "1px solid var(--border-input)",
  color: "var(--text-secondary)",
} as const;

export default function PanContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const q = searchParams.get("q") || "";

  const [input, setInput] = useState(q);
  const [hotWords, setHotWords] = useState<{ keyword: string; count: number }[]>([]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setInput(q);
  }, [q]);

  useEffect(() => {
    getHotSearches().then((w) => setHotWords(w.slice(0, 10)));
  }, []);

  function goSearch(keyword: string) {
    const kw = keyword.trim();
    router.push(kw ? `/pan?q=${encodeURIComponent(kw)}` : "/pan");
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    goSearch(input);
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Hero 搜索区 */}
        <div className={`text-center ${q ? "mb-6" : "mb-10 mt-8 sm:mt-16"}`}>
          <h1 className={`font-bold gradient-text ${q ? "text-xl mb-4" : "text-2xl sm:text-4xl mb-3"}`}>
            网盘资源搜索
          </h1>
          {!q && (
            <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>
              实时聚合全网公开网盘分享 · 夸克 / 百度 / 阿里 / 迅雷 / 115 等
            </p>
          )}

          <form onSubmit={handleSubmit} className="max-w-2xl mx-auto">
            <div
              className="flex items-center gap-2 px-4 py-3 rounded-xl search-glow"
              style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)" }}
            >
              <Search size={18} style={{ color: "var(--text-secondary)", flexShrink: 0 }} />
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="搜索网盘资源：影视 / 电子书 / 软件 / 课程…"
                className="flex-1 bg-transparent outline-none text-sm sm:text-base"
                style={{ color: "var(--text-primary)" }}
              />
              {input && (
                <button
                  type="button"
                  onClick={() => { setInput(""); if (q) router.push("/pan"); }}
                  className="shrink-0 rounded-full p-0.5"
                  style={{ color: "var(--text-secondary)" }}
                  aria-label="清除"
                >
                  <X size={15} />
                </button>
              )}
              <button
                type="submit"
                className="shrink-0 px-4 sm:px-6 py-1.5 rounded-lg text-sm font-medium"
                style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)", color: "#fff" }}
              >
                搜索
              </button>
            </div>
          </form>

          {/* 热门搜索词 */}
          {hotWords.length > 0 && (
            <div className="flex flex-wrap items-center justify-center gap-2 mt-4 max-w-2xl mx-auto">
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>热门:</span>
              {hotWords.map((w) => (
                <button
                  key={w.keyword}
                  onClick={() => goSearch(w.keyword)}
                  className="px-3 py-1 rounded-full text-xs transition-all"
                  style={q === w.keyword ? { background: "rgba(229,9,20,0.12)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)" } : INACTIVE_BTN}
                >
                  {w.keyword}
                </button>
              ))}
            </div>
          )}
        </div>

        <LiveSearchResults q={q} />
      </div>
      <Footer />
    </div>
  );
}
