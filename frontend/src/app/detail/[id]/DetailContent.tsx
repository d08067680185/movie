"use client";
import { useEffect, useState, useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Star, Clock, Globe, Download, Share2, Heart } from "lucide-react";
import Navbar from "@/components/Navbar";
import LinkItem from "@/components/LinkItem";
import ResourceCardComponent from "@/components/ResourceCard";
import Footer from "@/components/Footer";
import { getResource, getRelated, ResourceCard, ResourceDetail } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/utils";
import { toggleFavorite, isFavorited } from "@/lib/favorites";

interface Props {
  id: number;
}

const LINK_TYPE_GROUPS: Record<string, string> = {
  magnet: "🧲 磁力链接",
  pan_quark: "⚡ 夸克网盘",
  pan_aliyun: "☁️ 阿里云盘",
  pan_baidu: "💾 百度网盘",
  direct: "🔗 直链下载",
  page: "🌐 网页资源",
};

const SYNOPSIS_LIMIT = 200;

export default function DetailContent({ id }: Props) {
  const router = useRouter();
  const [resource, setResource] = useState<ResourceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [related, setRelated] = useState<ResourceCard[]>([]);
  const [shareCopied, setShareCopied] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const shareRef = useRef<HTMLDivElement>(null);
  const [synopsisExpanded, setSynopsisExpanded] = useState(false);
  const [faved, setFaved] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFaved(isFavorited(id));
  }, [id]);

  function handleFav() {
    if (!resource) return;
    const card = {
      id: resource.id,
      title: resource.title,
      title_en: resource.title_en,
      year: resource.year,
      category: resource.category,
      genre: resource.genre,
      rating: resource.rating,
      poster_url: resource.poster_url,
      link_count: resource.links.length,
      view_count: resource.view_count,
    };
    const result = toggleFavorite(card);
    setFaved(result);
    window.dispatchEvent(new Event("favoritesChanged"));
  }

  // 点击外部关闭分享面板
  useEffect(() => {
    if (!shareOpen) return;
    function handler(e: MouseEvent) {
      if (shareRef.current && !shareRef.current.contains(e.target as Node)) {
        setShareOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [shareOpen]);

  function copyLink() {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setShareCopied(true);
      setTimeout(() => { setShareCopied(false); setShareOpen(false); }, 1500);
    });
  }

  function shareToWeibo() {
    const url = encodeURIComponent(window.location.href);
    const title = encodeURIComponent(`${resource?.title} - 影视搜索`);
    window.open(`https://service.weibo.com/share/share.php?url=${url}&title=${title}`, "_blank");
    setShareOpen(false);
  }

  function shareToTelegram() {
    const url = encodeURIComponent(window.location.href);
    const text = encodeURIComponent(resource?.title || "");
    window.open(`https://t.me/share/url?url=${url}&text=${text}`, "_blank");
    setShareOpen(false);
  }

  function shareToTwitter() {
    const url = encodeURIComponent(window.location.href);
    const text = encodeURIComponent(`${resource?.title}${resource?.year ? ` (${resource.year})` : ""}`);
    window.open(`https://twitter.com/intent/tweet?url=${url}&text=${text}`, "_blank");
    setShareOpen(false);
  }

  async function systemShare() {
    try {
      await navigator.share({ title: resource?.title, text: resource?.synopsis?.slice(0, 100), url: window.location.href });
    } catch { /* user cancelled */ }
    setShareOpen(false);
  }

  useEffect(() => {
    Promise.all([getResource(id), getRelated(id)])
      .then(([r, rel]) => {
        setResource(r);
        setRelated(rel);
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
        <div className="max-w-5xl mx-auto px-4 py-8 sm:py-12">
          <div className="flex flex-col sm:flex-row gap-6 sm:gap-8">
            <div className="skeleton w-32 sm:w-48 aspect-[2/3] rounded-xl shrink-0 mx-auto sm:mx-0" />
            <div className="flex-1 space-y-4">
              <div className="skeleton h-7 sm:h-8 w-2/3 rounded" />
              <div className="skeleton h-4 sm:h-5 w-1/3 rounded" />
              <div className="skeleton h-4 w-full rounded" />
              <div className="skeleton h-4 w-5/6 rounded" />
              <div className="skeleton h-4 w-4/6 rounded" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (notFound || !resource) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
        <div className="flex flex-col items-center justify-center py-32 text-center" style={{ color: "var(--text-muted)" }}>
          <p className="text-2xl mb-4">🎬</p>
          <p className="text-lg">资源不存在</p>
          <Link href="/" className="mt-4 text-sm" style={{ color: "#e50914" }}>
            返回首页
          </Link>
        </div>
      </div>
    );
  }

  // 按类型分组链接
  const groupedLinks: Record<string, typeof resource.links> = {};
  for (const link of resource.links) {
    const group = link.link_type || "page";
    if (!groupedLinks[group]) groupedLinks[group] = [];
    groupedLinks[group].push(link);
  }

  const orderedGroups = Object.keys(LINK_TYPE_GROUPS).filter((k) => groupedLinks[k]);

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <Navbar />

      {/* 背景模糊海报 */}
      {resource.backdrop_url && (
        <div className="fixed inset-0 -z-10 opacity-5">
          <Image src={resource.backdrop_url} alt="" fill className="object-cover" unoptimized />
        </div>
      )}

      <div className="max-w-5xl mx-auto px-4 py-6 sm:py-8">
        {/* 返回 + 分享 */}
        <div className="flex items-center justify-between mb-4 sm:mb-6">
          <button
            onClick={() => { if (window.history.length > 1) router.back(); else router.push("/"); }}
            className="flex items-center gap-1.5 text-sm transition-colors hover:text-white"
            style={{ color: "var(--text-secondary)" }}
          >
            <ArrowLeft size={16} />
            返回
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={handleFav}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all"
              style={{
                background: faved ? "rgba(229,9,20,0.15)" : "var(--bg-input)",
                border: `1px solid ${faved ? "rgba(229,9,20,0.3)" : "var(--border-input)"}`,
                color: faved ? "#ff6070" : "var(--text-secondary)",
              }}
            >
              <Heart size={13} fill={faved ? "#ff6070" : "none"} />
              {faved ? "已收藏" : "收藏"}
            </button>
            <div ref={shareRef} className="relative">
              <button
                onClick={() => setShareOpen((v) => !v)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all"
                style={{
                  background: shareOpen ? "rgba(255,255,255,0.08)" : "var(--bg-input)",
                  border: `1px solid ${shareOpen ? "rgba(255,255,255,0.15)" : "var(--border-input)"}`,
                  color: "var(--text-secondary)",
                }}
              >
                <Share2 size={13} />
                分享
              </button>

              {shareOpen && (
                <div
                  className="absolute right-0 top-full mt-1.5 w-44 rounded-xl z-50 overflow-hidden shadow-2xl"
                  style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
                >
                  {[
                    { icon: "📋", label: shareCopied ? "已复制 ✓" : "复制链接", action: copyLink, active: shareCopied },
                    { icon: "🌐", label: "微博", action: shareToWeibo },
                    { icon: "✈️", label: "Telegram", action: shareToTelegram },
                    { icon: "𝕏", label: "Twitter / X", action: shareToTwitter },
                  ].map(({ icon, label, action, active }) => (
                    <button
                      key={label}
                      onClick={action}
                      className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors text-left"
                      style={{
                        color: active ? "#22c55e" : "var(--text-secondary)",
                        borderBottom: "1px solid var(--border)",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                    >
                      <span className="text-base w-5 text-center">{icon}</span>
                      {label}
                    </button>
                  ))}
                  {typeof navigator !== "undefined" && "share" in navigator && (
                    <button
                      onClick={systemShare}
                      className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors text-left"
                      style={{ color: "var(--text-secondary)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                    >
                      <span className="text-base w-5 text-center">📤</span>
                      系统分享
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 主信息区 */}
        <div className="flex flex-col sm:flex-row gap-4 sm:gap-8 mb-8 sm:mb-10">
          {/* 海报 */}
          <div
            className="w-36 sm:w-48 aspect-[2/3] rounded-xl overflow-hidden shrink-0 mx-auto sm:mx-0"
            style={{ border: "1px solid var(--border)" }}
          >
            {resource.poster_url ? (
              <Image
                src={resource.poster_url}
                alt={resource.title}
                width={192}
                height={288}
                className="object-cover w-full h-full"
                unoptimized
              />
            ) : (
              <div
                className="w-full h-full flex items-center justify-center text-5xl"
                style={{ background: "var(--no-poster-bg)" }}
              >
                🎬
              </div>
            )}
          </div>

          {/* 详情 */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              {resource.category && (
                <span
                  className="text-xs px-2 py-0.5 rounded font-medium"
                  style={{ background: "rgba(229,9,20,0.15)", color: "#ff6070", border: "1px solid rgba(229,9,20,0.3)" }}
                >
                  {CATEGORY_LABELS[resource.category] || resource.category}
                </span>
              )}
              {resource.year && (
                <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  {resource.year}
                </span>
              )}
            </div>

            <h1 className="text-xl sm:text-2xl md:text-3xl font-black mb-1" style={{ letterSpacing: "-0.5px" }}>
              {resource.title}
            </h1>
            {resource.title_en && (
              <p className="text-sm sm:text-base mb-2" style={{ color: "var(--text-secondary)" }}>
                {resource.title_en}
              </p>
            )}
            {resource.original_title && resource.original_title !== resource.title && (
              <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>
                原名: {resource.original_title}
              </p>
            )}

            {/* 评分 */}
            {resource.rating && (
              <div className="flex items-center gap-2 mb-3 sm:mb-4">
                <Star size={18} fill="#f5c518" style={{ color: "#f5c518" }} />
                <span className="text-xl sm:text-2xl font-black" style={{ color: "#f5c518" }}>
                  {resource.rating.toFixed(1)}
                </span>
                {resource.rating_count && (
                  <span className="text-xs sm:text-sm" style={{ color: "var(--text-muted)" }}>
                    ({resource.rating_count.toLocaleString()} 人评价)
                  </span>
                )}
              </div>
            )}

            {/* 元数据 */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4 text-sm">
              {resource.country && (
                <div className="flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                  <Globe size={14} style={{ color: "var(--text-muted)" }} />
                  {resource.country}
                </div>
              )}
              {resource.duration && (
                <div className="flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                  <Clock size={14} style={{ color: "var(--text-muted)" }} />
                  {resource.duration} 分钟
                </div>
              )}
              {resource.language && (
                <div className="flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                  <span style={{ color: "var(--text-muted)" }}>语言:</span>
                  {resource.language}
                </div>
              )}
            </div>

            {/* 外部链接 */}
            {resource.imdb_id && (
              <div className="flex flex-wrap gap-2 mb-4">
                <a
                  href={`https://www.imdb.com/title/${resource.imdb_id}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all hover:brightness-110"
                  style={{ background: "#f5c518", color: "#000" }}
                >
                  <span>IMDb</span>
                  <span style={{ opacity: 0.7 }}>↗</span>
                </a>
              </div>
            )}

            {/* 导演/演员 — 可点击跳搜索 */}
            {resource.directors && resource.directors.length > 0 && (
              <div className="mb-2 text-sm flex flex-wrap items-center gap-1">
                <span className="shrink-0" style={{ color: "var(--text-muted)" }}>导演: </span>
                {resource.directors.map((d, i) => (
                  <span key={d}>
                    {i > 0 && <span style={{ color: "var(--text-muted)" }}> / </span>}
                    <a href={`/search?q=${encodeURIComponent(d)}`} className="transition-colors hover:text-white" style={{ color: "var(--text-secondary)" }}>{d}</a>
                  </span>
                ))}
              </div>
            )}
            {resource.actors && resource.actors.length > 0 && (
              <div className="mb-3 text-sm flex flex-wrap items-center gap-1">
                <span className="shrink-0" style={{ color: "var(--text-muted)" }}>主演: </span>
                {resource.actors.slice(0, 6).map((a, i) => (
                  <span key={a}>
                    {i > 0 && <span style={{ color: "var(--text-muted)" }}> / </span>}
                    <a href={`/search?q=${encodeURIComponent(a)}`} className="transition-colors hover:text-white" style={{ color: "var(--text-secondary)" }}>{a}</a>
                  </span>
                ))}
              </div>
            )}

            {/* 类型 badge — 可点击过滤 */}
            {resource.genre && (
              <div className="flex flex-wrap items-center gap-1.5 mb-3">
                {resource.genre.split(/[/，,、]/).map((g) => g.trim()).filter(Boolean).map((g) => (
                  <a
                    key={g}
                    href={`/search?genre=${encodeURIComponent(g)}`}
                    className="text-xs px-2 py-0.5 rounded-full transition-all hover:text-white"
                    style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
                  >
                    {g}
                  </a>
                ))}
              </div>
            )}

            {/* Tags */}
            {resource.tags && resource.tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mb-3">
                {resource.tags.map((tag) => (
                  <a
                    key={tag}
                    href={`/search?q=${encodeURIComponent(tag)}`}
                    className="text-xs px-2 py-0.5 rounded-full transition-all hover:text-white"
                    style={{ background: "rgba(229,9,20,0.08)", border: "1px solid rgba(229,9,20,0.2)", color: "#ff6070" }}
                  >
                    # {tag}
                  </a>
                ))}
              </div>
            )}

            {/* 简介 */}
            {resource.synopsis && (
              <div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  {synopsisExpanded || resource.synopsis.length <= SYNOPSIS_LIMIT
                    ? resource.synopsis
                    : resource.synopsis.slice(0, SYNOPSIS_LIMIT) + "…"}
                </p>
                {resource.synopsis.length > SYNOPSIS_LIMIT && (
                  <button
                    onClick={() => setSynopsisExpanded((v) => !v)}
                    className="mt-1 text-xs transition-colors hover:text-white"
                    style={{ color: "#e50914" }}
                  >
                    {synopsisExpanded ? "收起" : "展开全文"}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* 下载资源区 */}
        <div>
          <div className="flex items-center gap-2 mb-4 sm:mb-6">
            <Download size={18} style={{ color: "#e50914" }} />
            <h2 className="text-lg sm:text-xl font-bold">下载资源</h2>
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: "rgba(229,9,20,0.15)", color: "#ff6070" }}
            >
              {resource.links.length} 个链接
            </span>
            {resource.links.length > 0 && (
              <Link
                href={`/pan?q=${encodeURIComponent(resource.title)}`}
                className="ml-auto text-xs font-medium transition-colors"
                style={{ color: "#22d3ee" }}
              >
                🌐 全网搜更多 →
              </Link>
            )}
          </div>

          {resource.links.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center py-16 rounded-xl text-center"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-muted)" }}
            >
              <Download size={40} className="mb-4 opacity-30" />
              <p>暂无下载资源</p>
              <p className="text-xs mt-2 mb-5">本地库暂时没有收录，可以去全网实时聚合搜索试试</p>
              <Link
                href={`/pan?q=${encodeURIComponent(resource.title)}`}
                className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white"
                style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)" }}
              >
                🌐 去全网搜『{resource.title}』
              </Link>
            </div>
          ) : (
            <div className="space-y-6">
              {orderedGroups.map((groupKey) => (
                <div key={groupKey}>
                  <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
                    {LINK_TYPE_GROUPS[groupKey]}
                    <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>
                      ({groupedLinks[groupKey].length})
                    </span>
                  </h3>
                  <div className="space-y-2">
                    {groupedLinks[groupKey].map((link, i) => (
                      <LinkItem key={link.id} link={link} index={i} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 相关推荐 */}
        {related.length > 0 && (
          <div className="mt-8 sm:mt-12">
            <h2
              className="text-lg sm:text-xl font-bold mb-4 sm:mb-6"
              style={{ borderLeft: "3px solid #e50914", paddingLeft: "12px" }}
            >
              相关推荐
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {related.map((r) => (
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
