import type { Metadata } from "next";
import { Suspense, use } from "react";
import DetailContent from "./DetailContent";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const res = await fetch(`${API}/api/resource/${id}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return { title: "资源详情 - 影视搜索" };
    const data = await res.json();
    return {
      title: `${data.title}${data.year ? ` (${data.year})` : ""} - 影视搜索`,
      description: data.synopsis
        ? String(data.synopsis).slice(0, 150)
        : `${data.title}的影视资源，提供磁力链接、网盘资源下载`,
    };
  } catch {
    return { title: "资源详情 - 影视搜索" };
  }
}

export default function DetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <Suspense>
      <DetailContent id={parseInt(id)} />
    </Suspense>
  );
}
