"use client";
import { useState } from "react";
import { ExternalLink, Copy, Check, Lock } from "lucide-react";
import { ResourceLink } from "@/lib/api";
import { LINK_TYPE_LABELS, QUALITY_COLORS } from "@/lib/utils";

interface Props {
  link: ResourceLink;
  index: number;
}

export default function LinkItem({ link, index }: Props) {
  const [copied, setCopied] = useState(false);
  const typeInfo = LINK_TYPE_LABELS[link.link_type] || LINK_TYPE_LABELS.page;

  async function copyUrl() {
    await navigator.clipboard.writeText(link.url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 rounded-lg"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      {/* 序号 */}
      <span
        className="text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center shrink-0"
        style={{ background: "rgba(255,255,255,0.08)", color: "#a0a0b0" }}
      >
        {index + 1}
      </span>

      {/* 标签组 */}
      <div className="flex flex-wrap items-center gap-2 flex-1">
        {/* 类型 */}
        <span
          className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded border font-medium"
          style={{ background: typeInfo.bg, color: typeInfo.color, borderColor: typeInfo.border }}
        >
          {typeInfo.icon} {typeInfo.label}
        </span>

        {/* 画质 */}
        {link.quality && QUALITY_COLORS[link.quality] && (
          <span
            className="text-xs px-2 py-0.5 rounded border font-bold"
            style={{
              background: QUALITY_COLORS[link.quality].bg,
              color: QUALITY_COLORS[link.quality].color,
              borderColor: QUALITY_COLORS[link.quality].border,
            }}
          >
            {link.quality}
          </span>
        )}

        {/* 格式 */}
        {link.format && (
          <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>
            {link.format}
          </span>
        )}

        {/* 字幕 */}
        {link.subtitle && (
          <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>
            💬 {link.subtitle}
          </span>
        )}

        {/* 集数 */}
        {link.episode_info && (
          <span className="text-xs" style={{ color: "#a0a0b0" }}>
            {link.episode_info}
          </span>
        )}

        {/* 提取码 */}
        {link.password && (
          <span
            className="text-xs flex items-center gap-1 px-2 py-0.5 rounded"
            style={{ background: "rgba(245,197,24,0.1)", color: "#f5c518" }}
          >
            <Lock size={10} />
            提取码: {link.password}
          </span>
        )}

        {/* 来源 */}
        {link.source_name && (
          <span className="text-xs" style={{ color: "#606070" }}>
            来源: {link.source_name}
          </span>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={copyUrl}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-all"
          style={{
            background: copied ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.06)",
            color: copied ? "#22c55e" : "#a0a0b0",
            border: `1px solid ${copied ? "rgba(34,197,94,0.3)" : "rgba(255,255,255,0.08)"}`,
          }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "已复制" : "复制"}
        </button>

        <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-all"
            style={{
              background: "rgba(229,9,20,0.15)",
              color: "#ff6070",
              border: "1px solid rgba(229,9,20,0.3)",
            }}
          >
            <ExternalLink size={12} />
            打开
          </a>
      </div>
    </div>
  );
}
