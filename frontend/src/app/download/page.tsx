import type { Metadata } from "next";
import { Suspense } from "react";
import DownloadContent from "./DownloadContent";

export const metadata: Metadata = {
  title: "视频下载 - 影视搜索",
  description: "粘贴 YouTube 等视频链接，一键下载保存",
  openGraph: { title: "视频下载 - 影视搜索", description: "粘贴 YouTube 等视频链接，一键下载保存", type: "website" },
};

export default function DownloadPage() {
  return (
    <Suspense>
      <DownloadContent />
    </Suspense>
  );
}
