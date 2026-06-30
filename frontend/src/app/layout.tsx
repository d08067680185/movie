import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "影视搜索 - 多源影视资源聚合平台",
  description: "搜索电影、电视剧、动漫资源，提供磁力链接、网盘资源下载",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        {/* 防止主题闪烁：在首屏渲染前恢复用户主题偏好 */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('movie-theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}`,
          }}
        />
      </head>
      <body className="min-h-screen flex flex-col">{children}</body>
    </html>
  );
}
