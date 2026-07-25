"use client";
import { useEffect, useRef, useState } from "react";
import { Download, Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";
import { createDownload, getDownloadStatus, downloadFileUrl, DownloadStatus } from "@/lib/api";

function formatBytes(n: number | null): string {
  if (!n) return "";
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function formatSpeed(n: number | null): string {
  if (!n) return "";
  return `${(n / 1024 / 1024).toFixed(2)} MB/s`;
}

interface Props {
  url: string;
  title?: string;
  /** 磁力链接目前不支持，展示禁用提示而非发起请求 */
  disabled?: boolean;
  disabledReason?: string;
}

export default function DownloadTaskButton({ url, title, disabled, disabledReason }: Props) {
  const [taskId, setTaskId] = useState<number | null>(null);
  const [status, setStatus] = useState<DownloadStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function start() {
    if (disabled) return;
    setStarting(true);
    setError(null);
    try {
      const { id } = await createDownload(url, title);
      setTaskId(id);
      poll(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建下载任务失败");
    } finally {
      setStarting(false);
    }
  }

  function poll(id: number) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await getDownloadStatus(id);
        setStatus(s);
        if (s.status === "complete" || s.status === "error" || s.status === "expired") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {
        setError("查询下载进度失败");
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 2000);
  }

  if (disabled) {
    return (
      <div
        className="flex items-center gap-2 text-xs rounded-lg py-2.5 px-3"
        style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-muted)" }}
      >
        <AlertTriangle size={14} />
        {disabledReason || "暂不支持该类型链接的下载"}
      </div>
    );
  }

  if (!taskId) {
    return (
      <div>
        <button
          onClick={start}
          disabled={starting}
          className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium transition-all w-full"
          style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)", color: "#fff", opacity: starting ? 0.7 : 1 }}
        >
          {starting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          {starting ? "正在创建任务…" : "下载视频"}
        </button>
        {error && <p className="text-xs mt-2" style={{ color: "#f87171" }}>{error}</p>}
      </div>
    );
  }

  if (!status || status.status === "queued" || status.status === "downloading") {
    const pct = status?.total_bytes && status.downloaded_bytes
      ? Math.min(100, Math.round((status.downloaded_bytes / status.total_bytes) * 100))
      : null;
    return (
      <div className="rounded-lg p-3" style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)" }}>
        <div className="flex items-center gap-2 text-sm mb-2" style={{ color: "var(--text-secondary)" }}>
          <Loader2 size={14} className="animate-spin" />
          {status?.status === "downloading" ? "下载中…" : "排队中…"}
          {pct !== null && <span className="ml-auto font-mono">{pct}%</span>}
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border-input)" }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: pct !== null ? `${pct}%` : "30%",
              background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)",
            }}
          />
        </div>
        <p className="text-xs mt-1.5" style={{ color: "var(--text-muted)" }}>
          {formatBytes(status?.downloaded_bytes ?? null)}
          {status?.total_bytes ? ` / ${formatBytes(status.total_bytes)}` : ""}
          {status?.download_speed ? ` · ${formatSpeed(status.download_speed)}` : ""}
        </p>
      </div>
    );
  }

  if (status.status === "error" || status.status === "expired") {
    return (
      <div
        className="flex items-start gap-2 text-xs rounded-lg py-2.5 px-3"
        style={{ background: "rgba(248,113,113,0.1)", color: "#f87171", border: "1px solid rgba(248,113,113,0.3)" }}
      >
        <AlertTriangle size={14} className="shrink-0 mt-0.5" />
        <span>{status.error_message || "下载失败，该网站/平台可能不受支持"}</span>
      </div>
    );
  }

  // complete
  return (
    <div className="space-y-2">
      <a
        href={downloadFileUrl(status.id)}
        className="flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium transition-all"
        style={{ background: "linear-gradient(135deg, #22c55e 0%, #16a34a 100%)", color: "#fff" }}
      >
        <CheckCircle2 size={14} />
        下载完成，点击保存 ({formatBytes(status.total_bytes)})
      </a>
      <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
        文件将在 12 小时后自动清理，请及时保存
      </p>
    </div>
  );
}
