import type { Metadata } from "next";
import { Suspense } from "react";
import PanContent from "./PanContent";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}): Promise<Metadata> {
  const sp = await searchParams;
  const title = sp.q ? `网盘搜索"${sp.q}" - 影视搜索` : "网盘资源搜索 - 影视搜索";
  const description = `实时聚合全网网盘分享资源${sp.q ? `：${sp.q}` : ""}，支持夸克、百度、阿里云盘、迅雷、115等，影视/电子书/软件/课程一站搜索`;
  return {
    title,
    description,
    openGraph: { title, description, type: "website" },
    twitter: { card: "summary", title, description },
  };
}

export default function PanPage() {
  return (
    <Suspense>
      <PanContent />
    </Suspense>
  );
}
