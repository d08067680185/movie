import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "img*.doubanio.com" },
      { protocol: "https", hostname: "image.tmdb.org" },
      { protocol: "https", hostname: "*.doubanio.com" },
      { protocol: "http",  hostname: "lain.bgm.tv" },
      { protocol: "https", hostname: "lain.bgm.tv" },
    ],
    unoptimized: true,
  },
};

export default nextConfig;
