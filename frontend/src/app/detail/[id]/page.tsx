import type { Metadata } from "next";
import { Suspense } from "react";
import DetailContent from "./DetailContent";

// Server-side SSR: use BACKEND_URL (runtime env), not NEXT_PUBLIC_API_URL (build-time baked)
const API = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const res = await fetch(`${API}/api/resource/${id}`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return { title: "资源详情 - 影视搜索" };
    const data = await res.json();
    const title = `${data.title}${data.year ? ` (${data.year})` : ""} - 影视搜索`;
    const description = data.synopsis
      ? String(data.synopsis).slice(0, 150)
      : `${data.title}的影视资源，提供磁力链接、网盘资源下载`;
    return {
      title,
      description,
      openGraph: {
        title,
        description,
        type: "video.movie",
        images: data.poster_url ? [{ url: data.poster_url }] : undefined,
      },
      twitter: {
        card: "summary_large_image",
        title,
        description,
        images: data.poster_url ? [data.poster_url] : undefined,
      },
    };
  } catch {
    return { title: "资源详情 - 影视搜索" };
  }
}

async function fetchResourceForSchema(id: string) {
  try {
    const res = await fetch(`${API}/api/resource/${id}`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function DetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await fetchResourceForSchema(id);

  const jsonLd = data
    ? {
        "@context": "https://schema.org",
        "@type": data.category === "电视剧" || data.category === "tv" ? "TVSeries" : "Movie",
        name: data.title,
        ...(data.year ? { datePublished: String(data.year) } : {}),
        ...(data.genre ? { genre: String(data.genre).split(/[,、/]/).map((g: string) => g.trim()).filter(Boolean) } : {}),
        ...(data.country ? { countryOfOrigin: data.country } : {}),
        ...(data.synopsis ? { description: data.synopsis } : {}),
        ...(data.poster_url ? { image: data.poster_url } : {}),
        ...(data.directors?.length ? { director: data.directors.map((name: string) => ({ "@type": "Person", name })) } : {}),
        ...(data.actors?.length ? { actor: data.actors.map((name: string) => ({ "@type": "Person", name })) } : {}),
        ...(data.rating ? { aggregateRating: { "@type": "AggregateRating", ratingValue: data.rating, ratingCount: data.rating_count || 1 } } : {}),
      }
    : null;

  return (
    <Suspense>
      {jsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      )}
      <DetailContent id={parseInt(id)} />
    </Suspense>
  );
}
