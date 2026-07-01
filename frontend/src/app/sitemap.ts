import type { MetadataRoute } from "next";

const API = process.env.BACKEND_URL ?? "http://localhost:8000";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const BASE_URL = "https://movie.mxzshs.com";

  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE_URL, lastModified: new Date(), changeFrequency: "daily", priority: 1 },
    { url: `${BASE_URL}/search`, lastModified: new Date(), changeFrequency: "daily", priority: 0.9 },
    { url: `${BASE_URL}/search?category=movie`, lastModified: new Date(), changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE_URL}/search?category=tv`, lastModified: new Date(), changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE_URL}/search?category=anime`, lastModified: new Date(), changeFrequency: "daily", priority: 0.8 },
  ];

  try {
    // 取最热门的 500 条资源做动态路由
    const res = await fetch(`${API}/api/search?sort=popular&page_size=50&page=1`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return staticPages;
    const data = await res.json();
    const resourcePages: MetadataRoute.Sitemap = (data.items ?? []).map(
      (r: { id: number }) => ({
        url: `${BASE_URL}/detail/${r.id}`,
        changeFrequency: "weekly" as const,
        priority: 0.6,
      })
    );

    // 追加第 2-10 页
    const extraFetches = await Promise.allSettled(
      Array.from({ length: 9 }, (_, i) =>
        fetch(`${API}/api/search?sort=popular&page_size=50&page=${i + 2}`, {
          next: { revalidate: 3600 },
        }).then((r) => r.json())
      )
    );
    const extraPages: MetadataRoute.Sitemap = extraFetches.flatMap((r) => {
      if (r.status !== "fulfilled") return [];
      return (r.value.items ?? []).map((item: { id: number }) => ({
        url: `${BASE_URL}/detail/${item.id}`,
        changeFrequency: "weekly" as const,
        priority: 0.6,
      }));
    });

    return [...staticPages, ...resourcePages, ...extraPages];
  } catch {
    return staticPages;
  }
}
