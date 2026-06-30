import Link from "next/link";
import Image from "next/image";
import { Star, Link2, Eye } from "lucide-react";
import { ResourceCard as ResourceCardType } from "@/lib/api";
import { CATEGORY_LABELS as CAT_LABELS } from "@/lib/utils";

interface Props {
  resource: ResourceCardType;
}

const BADGE_CLASS: Record<string, string> = {
  动漫: "badge-anime",
  电影: "badge-movie",
  电视剧: "badge-tv",
  综艺: "badge-variety", 资源: "badge-variety", 经典资源: "badge-variety",
};

export default function ResourceCard({ resource }: Props) {
  return (
    <Link href={`/detail/${resource.id}`} className="block resource-card">
      <div
        className="card-inner rounded-xl overflow-hidden"
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          transition: "border-color 0.2s",
        }}
      >
        {/* 海报 */}
        <div className="group relative aspect-[2/3] overflow-hidden">
          {resource.poster_url ? (
            <Image
              src={resource.poster_url}
              alt={resource.title}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-108"
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 200px"
              unoptimized
            />
          ) : (
            <div
              className="w-full h-full flex items-center justify-center text-4xl"
              style={{ background: "var(--no-poster-bg)" }}
            >
              🎬
            </div>
          )}

          {/* 评分角标 */}
          {resource.rating && (
            <div
              className="absolute top-2 right-2 flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-bold"
              style={{
                background: "rgba(0,0,0,0.82)",
                color: "#fbbf24",
                backdropFilter: "blur(4px)",
              }}
            >
              <Star size={9} fill="#fbbf24" color="#fbbf24" />
              {resource.rating.toFixed(1)}
            </div>
          )}

          {/* 分类角标 */}
          {resource.category && (
            <div
              className={`absolute top-2 left-2 px-2 py-0.5 rounded text-xs font-semibold ${BADGE_CLASS[resource.category] ?? "bg-gray-500/20 text-gray-300"}`}
            >
              {CAT_LABELS[resource.category] || resource.category}
            </div>
          )}

          {/* 悬停渐变遮罩 */}
          <div
            className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
            style={{
              background: "linear-gradient(0deg, rgba(229,9,20,0.12) 0%, transparent 50%)",
            }}
          />
        </div>

        {/* 信息 */}
        <div className="p-3">
          <h3
            className="text-sm font-semibold truncate leading-snug"
            style={{ color: "var(--text-primary)" }}
          >
            {resource.title}
          </h3>
          {resource.title_en && (
            <p className="text-xs truncate mt-0.5" style={{ color: "var(--text-secondary)" }}>
              {resource.title_en}
            </p>
          )}

          <div className="flex items-center justify-between mt-2">
            <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
              {resource.year || ""}
            </span>
            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
              {resource.link_count > 0 && (
                <span className="flex items-center gap-0.5" style={{ color: "#34d399" }}>
                  <Link2 size={10} />
                  {resource.link_count}
                </span>
              )}
              {resource.view_count > 0 && (
                <span className="flex items-center gap-0.5">
                  <Eye size={10} />
                  {resource.view_count}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}
