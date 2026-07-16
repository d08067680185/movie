"use client";
import { useEffect } from "react";
import { QRCodeSVG } from "qrcode.react";
import { X, ExternalLink, Copy, Check, Heart } from "lucide-react";
import { useState } from "react";
import { LiveSearchItem } from "@/lib/api";
import { CLOUD_TYPE_LABELS } from "@/lib/utils";
import { isPanFavorited, togglePanFavorite } from "@/lib/panFavorites";

interface Props {
  item: LiveSearchItem;
  cloudType: string;
  onClose: () => void;
}

export default function PanLinkModal({ item, cloudType, onClose }: Props) {
  const [copied, setCopied] = useState(false);
  const [faved, setFaved] = useState(() => isPanFavorited(item.url));
  const meta = CLOUD_TYPE_LABELS[cloudType] || { label: "网盘", icon: "🔗", app: "网盘APP" };

  function handleFav() {
    setFaved(togglePanFavorite(item, cloudType));
    window.dispatchEvent(new Event("favoritesChanged"));
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  function copyLink() {
    const text = item.password ? `${item.url} 提取码: ${item.password}` : item.url;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl p-6 relative max-h-[90vh] overflow-y-auto"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 rounded-full transition-colors"
          style={{ color: "var(--text-muted)" }}
          aria-label="关闭"
        >
          <X size={20} />
        </button>

        <h3 className="text-center text-lg font-bold mb-1">
          请使用 <span style={{ color: "#e50914" }}>{meta.app}</span> 扫码获取
        </h3>
        <p className="text-center text-xs mb-4" style={{ color: "var(--text-secondary)" }}>
          打开{meta.app} - 点击搜索框中的相机 - 扫码即可保存
        </p>

        {/* 二维码（白底保证扫码识别率） */}
        <div className="flex justify-center mb-4">
          <div className="p-3 rounded-xl" style={{ background: "#fff" }}>
            <QRCodeSVG value={item.url} size={200} level="M" />
          </div>
        </div>

        {item.password && (
          <div
            className="text-center text-sm rounded-lg py-2 px-3 mb-3"
            style={{ background: "rgba(245,197,24,0.12)", color: "#fbbf24", border: "1px solid rgba(245,197,24,0.3)" }}
          >
            提取码: <span className="font-mono font-bold">{item.password}</span>
          </div>
        )}

        <div
          className="flex items-center gap-2 text-xs rounded-lg py-2.5 px-3 mb-4"
          style={{ background: "rgba(59,130,246,0.12)", color: "#60a5fa", border: "1px solid rgba(59,130,246,0.3)" }}
        >
          <span className="text-base">💡</span>
          网盘分享链接可能随时失效，请及时转存到自己的网盘！
        </div>

        <p className="text-sm font-medium mb-4 text-center break-all" style={{ color: "var(--text-primary)" }}>
          {item.title}
        </p>

        <div className="flex gap-2 mb-4">
          <button
            onClick={handleFav}
            className="flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all"
            style={{
              background: faved ? "rgba(229,9,20,0.12)" : "var(--bg-input)",
              border: faved ? "1px solid rgba(229,9,20,0.3)" : "1px solid var(--border-input)",
              color: faved ? "#e50914" : "var(--text-secondary)",
            }}
            title={faved ? "取消收藏" : "收藏此链接"}
          >
            <Heart size={14} fill={faved ? "#e50914" : "none"} />
            {faved ? "已收藏" : "收藏"}
          </button>
          <button
            onClick={copyLink}
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-sm font-medium transition-all"
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-input)",
              color: copied ? "#22c55e" : "var(--text-secondary)",
            }}
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "已复制" : "复制链接"}
          </button>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-sm font-medium transition-all"
            style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)", color: "#fff" }}
          >
            <ExternalLink size={14} />
            直接打开
          </a>
        </div>

        <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-muted)", borderTop: "1px solid var(--border)", paddingTop: "12px" }}>
          🔔 声明：本站链接均由程序自动收集自公开网盘分享，不存储、不传播任何文件，跳转链接指向网盘官网。文件内容请自行辨别，如发现违规请向网盘平台举报。本站仅供学习交流，无任何收费行为。
        </p>
      </div>
    </div>
  );
}
