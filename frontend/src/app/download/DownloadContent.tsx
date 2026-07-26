"use client";
import { FormEvent, useState } from "react";
import { Link2 } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import DownloadTaskButton from "@/components/DownloadTaskButton";

export default function DownloadContent() {
  const [input, setInput] = useState("");
  const [activeUrl, setActiveUrl] = useState<string | null>(null);
  const [key, setKey] = useState(0);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const url = input.trim();
    if (!url) return;
    setActiveUrl(url);
    setKey((k) => k + 1); // 强制 DownloadTaskButton 重新挂载，重置上一次的任务状态
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <Navbar />

      <main className="max-w-2xl mx-auto px-4 py-8 sm:py-16">
        <div className="text-center mb-8">
          <h1 className="font-bold gradient-text text-2xl sm:text-4xl mb-3">视频下载</h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            粘贴 YouTube 等视频链接，一键下载保存到本地
          </p>
          <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
            YouTube 等海外平台支持较稳定；腾讯视频/优酷等国内平台受限于平台加密与反爬机制，尽力而为，不保证一定成功
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mb-6">
          <div
            className="flex items-center gap-2 px-4 py-3 rounded-xl search-glow"
            style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)" }}
          >
            <Link2 size={18} style={{ color: "var(--text-secondary)", flexShrink: 0 }} />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="粘贴视频链接，如 https://www.youtube.com/watch?v=..."
              className="flex-1 bg-transparent outline-none text-sm sm:text-base"
              style={{ color: "var(--text-primary)" }}
            />
            <button
              type="submit"
              className="shrink-0 px-4 sm:px-6 py-1.5 rounded-lg text-sm font-medium"
              style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)", color: "#fff" }}
            >
              下载
            </button>
          </div>
        </form>

        {activeUrl && (
          <div className="rounded-xl p-5" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <p className="text-xs mb-3 break-all" style={{ color: "var(--text-muted)" }}>{activeUrl}</p>
            <DownloadTaskButton key={key} url={activeUrl} />
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
