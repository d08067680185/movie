import Link from "next/link";
import Image from "next/image";
import { Star, Link2, Eye } from "lucide-react";
import { ResourceCard as ResourceCardType } from "@/lib/api";
import { CATEGORY_LABELS as CAT_LABELS } from "@/lib/utils";

interface Props {
  resource: ResourceCardType;
}

const CATEGORY_COLORS: Record<string, string> = {
  电影: "bg-blue-500/20 text-blue-400",
  电视剧: "bg-purple-500/20 text-purple-400",
  动漫: "bg-pink-500/20 text-pink-400",
  综艺: "bg-orange-500/20 text-orange-400",
};

export default function ResourceCard({ resource }: Props) {
  return (
    <Link href={`/detail/${resource.id}`} className="block resource-card">
      <div
        className="rounded-xl overflow-hidden"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
      >
        {/* 海报 */}
        <div className="group relative aspect-[2/3] overflow-hidden">
          {resource.poster_url ? (
            <Image
              src={resource.poster_url}
              alt={resource.title}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 200px"
              unoptimized
            />
          ) : (
            <div
              className="w-full h-full flex items-center justify-center text-4xl"
              style={{ background: "linear-gradient(135deg, #1c1c26 0%, #22222f 100%)" }}
            >
              🎬
            </div>
          )}

          {/* 评分角标 */}
          {resource.rating && (
            <div
              className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold"
              style={{ background: "rgba(0,0,0,0.75)", color: "#f5c518" }}
            >
              <Star size={10} fill="#f5c518" />
              {resource.rating.toFixed(1)}
            </div>
          )}

          {/* 分类角标 */}
          {resource.category && (
            <div
              className={`absolute top-2 left-2 px-2 py-0.5 rounded text-xs font-medium ${CATEGORY_COLORS[resource.category] || "bg-gray-500/20 text-gray-400"}`}
            >
              {CAT_LABELS[resource.category] || resource.category}
            </div>
          )}
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
            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
              {resource.year || ""}
            </span>
            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
              {resource.link_count > 0 && (
                <span className="flex items-center gap-0.5">
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
