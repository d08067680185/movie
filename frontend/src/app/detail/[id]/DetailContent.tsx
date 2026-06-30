"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Star, Clock, Globe, Download, Share2 } from "lucide-react";
import Navbar from "@/components/Navbar";
import LinkItem from "@/components/LinkItem";
import ResourceCardComponent from "@/components/ResourceCard";
import Footer from "@/components/Footer";
import { getResource, getRelated, ResourceCard, ResourceDetail } from "@/lib/api";
import { CATEGORY_LABELS } from "@/lib/utils";

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
  const [synopsisExpanded, setSynopsisExpanded] = useState(false);

  function handleShare() {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2000);
    });
  }

  useEffect(() => {
    getResource(id)
      .then((r) => {
        setResource(r);
        getRelated(id).then(setRelated);
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
        <div className="max-w-5xl mx-auto px-4 py-12">
          <div className="flex gap-8">
            <div className="skeleton w-48 aspect-[2/3] rounded-xl shrink-0" />
            <div className="flex-1 space-y-4">
              <div className="skeleton h-8 w-2/3 rounded" />
              <div className="skeleton h-5 w-1/3 rounded" />
              <div className="skeleton h-4 w-full rounded" />
              <div className="skeleton h-4 w-5/6 rounded" />
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
        <div className="flex flex-col items-center justify-center py-32 text-center" style={{ color: "#606070" }}>
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

      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* 返回 + 分享 */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => { if (window.history.length > 1) router.back(); else router.push("/"); }}
            className="flex items-center gap-1.5 text-sm hover:text-white transition-colors"
            style={{ color: "#a0a0b0" }}
          >
            <ArrowLeft size={16} />
            返回
          </button>
          <button
            onClick={handleShare}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all"
            style={{
              background: shareCopied ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.06)",
              border: `1px solid ${shareCopied ? "rgba(34,197,94,0.3)" : "rgba(255,255,255,0.08)"}`,
              color: shareCopied ? "#22c55e" : "#a0a0b0",
            }}
          >
            <Share2 size={13} />
            {shareCopied ? "已复制链接 ✓" : "分享"}
          </button>
        </div>

        {/* 主信息区 */}
        <div className="flex flex-col sm:flex-row gap-8 mb-10">
          {/* 海报 */}
          <div
            className="w-48 aspect-[2/3] rounded-xl overflow-hidden shrink-0 mx-auto sm:mx-0"
            style={{ border: "1px solid rgba(255,255,255,0.1)" }}
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
                style={{ background: "linear-gradient(135deg, #1c1c26 0%, #22222f 100%)" }}
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
                <span className="text-sm" style={{ color: "#a0a0b0" }}>
                  {resource.year}
                </span>
              )}
            </div>

            <h1 className="text-3xl font-black mb-1" style={{ letterSpacing: "-0.5px" }}>
              {resource.title}
            </h1>
            {resource.title_en && (
              <p className="text-base mb-2" style={{ color: "#a0a0b0" }}>
                {resource.title_en}
              </p>
            )}
            {resource.original_title && resource.original_title !== resource.title && (
              <p className="text-sm mb-4" style={{ color: "#606070" }}>
                原名: {resource.original_title}
              </p>
            )}

            {/* 评分 */}
            {resource.rating && (
              <div className="flex items-center gap-2 mb-4">
                <Star size={20} fill="#f5c518" style={{ color: "#f5c518" }} />
                <span className="text-2xl font-black" style={{ color: "#f5c518" }}>
                  {resource.rating.toFixed(1)}
                </span>
                {resource.rating_count && (
                  <span className="text-sm" style={{ color: "#606070" }}>
                    ({resource.rating_count.toLocaleString()} 人评价)
                  </span>
                )}
              </div>
            )}

            {/* 元数据 */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-5 text-sm">
              {resource.genre && (
                <div className="flex items-center gap-2" style={{ color: "#a0a0b0" }}>
                  <span style={{ color: "#606070" }}>类型:</span>
                  {resource.genre}
                </div>
              )}
              {resource.country && (
                <div className="flex items-center gap-2" style={{ color: "#a0a0b0" }}>
                  <Globe size={14} style={{ color: "#606070" }} />
                  {resource.country}
                </div>
              )}
              {resource.duration && (
                <div className="flex items-center gap-2" style={{ color: "#a0a0b0" }}>
                  <Clock size={14} style={{ color: "#606070" }} />
                  {resource.duration} 分钟
                </div>
              )}
              {resource.language && (
                <div className="flex items-center gap-2" style={{ color: "#a0a0b0" }}>
                  <span style={{ color: "#606070" }}>语言:</span>
                  {resource.language}
                </div>
              )}
            </div>

            {/* 导演/演员 */}
            {resource.directors && resource.directors.length > 0 && (
              <div className="mb-2 text-sm">
                <span style={{ color: "#606070" }}>导演: </span>
                <span style={{ color: "#a0a0b0" }}>{resource.directors.join(" / ")}</span>
              </div>
            )}
            {resource.actors && resource.actors.length > 0 && (
              <div className="mb-4 text-sm">
                <span style={{ color: "#606070" }}>主演: </span>
                <span style={{ color: "#a0a0b0" }}>{resource.actors.slice(0, 6).join(" / ")}</span>
              </div>
            )}

            {/* 简介 */}
            {resource.synopsis && (
              <div>
                <p className="text-sm leading-relaxed" style={{ color: "#a0a0b0" }}>
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
          <div className="flex items-center gap-2 mb-6">
            <Download size={20} style={{ color: "#e50914" }} />
            <h2 className="text-xl font-bold">下载资源</h2>
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: "rgba(229,9,20,0.15)", color: "#ff6070" }}
            >
              {resource.links.length} 个链接
            </span>
          </div>

          {resource.links.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center py-16 rounded-xl text-center"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)", color: "#606070" }}
            >
              <Download size={40} className="mb-4 opacity-30" />
              <p>暂无下载资源</p>
            </div>
          ) : (
            <div className="space-y-6">
              {orderedGroups.map((groupKey) => (
                <div key={groupKey}>
                  <h3 className="text-sm font-semibold mb-3" style={{ color: "#a0a0b0" }}>
                    {LINK_TYPE_GROUPS[groupKey]}
                    <span className="ml-2 text-xs" style={{ color: "#606070" }}>
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
          <div className="mt-12">
            <h2
              className="text-xl font-bold mb-6"
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
