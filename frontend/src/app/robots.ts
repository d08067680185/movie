import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const BASE_URL = "https://movie.mxzshs.com";
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/admin"],
      },
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
  };
}
