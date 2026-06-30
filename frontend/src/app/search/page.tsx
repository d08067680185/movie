import type { Metadata } from "next";
import { Suspense } from "react";
import SearchContent from "./SearchContent";

const CAT_LABELS: Record<string, string> = {
  movie: "电影",
  tv: "电视剧",
  anime: "动漫",
  variety: "资源",
};

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; category?: string }>;
}): Promise<Metadata> {
  const sp = await searchParams;
  const catLabel = CAT_LABELS[sp.category || ""] || "";
  const title = sp.q
    ? `搜索"${sp.q}" - 影视搜索`
    : catLabel
    ? `${catLabel}资源 - 影视搜索`
    : "搜索影视资源 - 影视搜索";
  return {
    title,
    description: `搜索${sp.q || catLabel || "影视"}资源，提供磁力链接、网盘资源下载`,
  };
}

export default function SearchPage() {
  return (
    <Suspense>
      <SearchContent />
    </Suspense>
  );
}
