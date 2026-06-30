"use client";
import { useState } from "react";
import Link from "next/link";
import { Settings, Play, ToggleLeft, ToggleRight, Plus, RefreshCw, Database, Search, Upload, Image } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function apiFetch(path: string, opts: RequestInit = {}, token: string) {
  return fetch(`${API}${path}`, {
    ...opts,
    headers: { "X-Admin-Token": token, "Content-Type": "application/json", ...opts.headers },
  });
}

interface LinkDetail {
  id: number; url: string; link_type: string;
  password?: string; quality?: string; is_valid: boolean;
}
interface ResourceDetail {
  id: number; title: string; year?: number; category?: string;
  poster_url?: string; rating?: number; link_count: number; links: LinkDetail[];
}

interface Source {
  id: number;
  name: string;
  base_url?: string;
  spider_class?: string;
  is_active: boolean;
  last_crawled?: string;
  total_resources: number;
}

interface Log {
  id: number;
  source_id?: number;
  status: string;
  new_resources: number;
  updated_resources: number;
  error_msg?: string;
  started_at: string;
  finished_at?: string;
}

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [authed, setAuthed] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [spiderClasses, setSpiderClasses] = useState<string[]>([]);
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newSource, setNewSource] = useState({ name: "", spider_class: "demo", base_url: "", config: "{}" });
  const [msg, setMsg] = useState("");
  const [tmdbForm, setTmdbForm] = useState({ api_key: "", media_type: "both", list_type: "popular", pages: "5", min_rating: "6.0" });
  const [panForm, setPanForm] = useState({ source_id: "", pan_types: "quark,baidu", max_per_run: "20", delay: "3.0" });
  const [tmdbRunning, setTmdbRunning] = useState(false);
  const [panRunning, setPanRunning] = useState(false);
  const [bgmForm, setBgmForm] = useState({ max_per_run: "50", delay: "1.0", overwrite: false });
  const [resSearch, setResSearch] = useState("");
  const [resPage, setResPage] = useState(1);
  const [resData, setResData] = useState<{ total: number; items: ResourceDetail[] } | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [addLinkForm, setAddLinkForm] = useState<{ resource_id: number; url: string; link_type: string; password: string } | null>(null);
  const [bgmRunning, setBgmRunning] = useState(false);
  const [batchJson, setBatchJson] = useState("");
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResult, setBatchResult] = useState<{ created: number; updated: number; links_added: number; skipped: number; errors: string[] } | null>(null);

  async function login(e: React.FormEvent) {
    e.preventDefault();
    const resp = await apiFetch("/api/admin/sources", {}, token);
    if (resp.ok) {
      setAuthed(true);
      loadData(token);
    } else {
      setMsg("密码错误");
    }
  }

  async function loadData(t = token) {
    const [srcRes, logRes, classRes, statsRes] = await Promise.all([
      apiFetch("/api/admin/sources", {}, t),
      apiFetch("/api/admin/logs", {}, t),
      apiFetch("/api/admin/spider-classes", {}, t),
      fetch(`${API}/api/stats`),
    ]);
    if (srcRes.ok) setSources(await srcRes.json());
    if (logRes.ok) setLogs(await logRes.json());
    if (classRes.ok) setSpiderClasses(await classRes.json());
    if (statsRes.ok) {
      const s = await statsRes.json();
      setStats({ 影视资源: s.total_resources, 下载链接: s.total_links, 数据来源: s.total_sources });
    }
  }

  async function toggleSource(id: number) {
    await apiFetch(`/api/admin/sources/${id}/toggle`, { method: "PATCH" }, token);
    loadData();
  }

  async function runSpider(id: number, name: string) {
    setMsg(`正在触发 ${name} 爬虫...`);
    const resp = await apiFetch(`/api/admin/sources/${id}/run`, { method: "POST" }, token);
    const data = await resp.json();
    setMsg(data.message || "已触发");
    setTimeout(() => loadData(), 3000);
  }

  async function createTmdbAndRun(e: React.FormEvent) {
    e.preventDefault();
    setTmdbRunning(true);
    setMsg("正在创建 TMDb 数据源...");
    const sp = new URLSearchParams({
      name: `TMDb ${tmdbForm.list_type} (${tmdbForm.media_type})`,
      media_type: tmdbForm.media_type,
      list_type: tmdbForm.list_type,
      pages: tmdbForm.pages,
      min_rating: tmdbForm.min_rating,
    });
    if (tmdbForm.api_key) sp.set("api_key", tmdbForm.api_key);
    const resp = await apiFetch(`/api/admin/sources/create-tmdb?${sp.toString()}`, { method: "POST" }, token);
    if (resp.ok) {
      const data = await resp.json();
      setMsg(`数据源已创建 (ID: ${data.id})，正在触发爬取...`);
      await apiFetch(`/api/admin/sources/${data.id}/run`, { method: "POST" }, token);
      setMsg(`TMDb 爬取已开始！预计导入 ${parseInt(tmdbForm.pages) * 20} 条影视资源，请稍候后刷新查看。`);
      setTimeout(() => loadData(), 5000);
    } else {
      setMsg("创建失败，请检查 API Key");
    }
    setTmdbRunning(false);
  }

  async function runPanSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!panForm.source_id) { setMsg("请先选择网盘搜索数据源"); return; }
    setPanRunning(true);
    setMsg("正在触发网盘链接搜索...");
    const sp = new URLSearchParams({
      source_id: panForm.source_id,
      pan_types: panForm.pan_types,
      max_per_run: panForm.max_per_run,
      delay: panForm.delay,
    });
    const resp = await apiFetch(`/api/admin/pan-search?${sp.toString()}`, { method: "POST" }, token);
    if (resp.ok) {
      const data = await resp.json();
      setMsg(data.message);
    } else {
      setMsg("触发失败");
    }
    setPanRunning(false);
  }

  async function createPanSource() {
    const sp = new URLSearchParams({
      name: "网盘链接搜索",
      pan_types: panForm.pan_types,
      delay: panForm.delay,
      max_per_run: panForm.max_per_run,
    });
    const resp = await apiFetch(`/api/admin/sources/create-pan-search?${sp.toString()}`, { method: "POST" }, token);
    if (resp.ok) {
      const data = await resp.json();
      setPanForm(f => ({ ...f, source_id: String(data.id) }));
      setMsg(`网盘搜索数据源已创建 (ID: ${data.id})`);
      loadData();
    }
  }

  async function loadResources(q = resSearch, page = resPage) {
    const sp = new URLSearchParams({ page: String(page), page_size: "15" });
    if (q) sp.set("q", q);
    const resp = await apiFetch(`/api/admin/resources?${sp}`, {}, token);
    if (resp.ok) setResData(await resp.json());
  }

  async function deleteLink(linkId: number, resourceId: number) {
    if (!confirm("确认删除此链接？")) return;
    await apiFetch(`/api/admin/links/${linkId}`, { method: "DELETE" }, token);
    loadResources();
  }

  async function addLink(e: React.FormEvent) {
    e.preventDefault();
    if (!addLinkForm) return;
    const src = sources.find(s => s.name === "手动导入");
    const sourceId = src?.id || 1;
    const resp = await apiFetch(`/api/admin/links`, {
      method: "POST",
      body: JSON.stringify({
        resource_id: addLinkForm.resource_id,
        source_id: sourceId,
        url: addLinkForm.url,
        link_type: addLinkForm.link_type,
        password: addLinkForm.password || undefined,
      }),
    }, token);
    if (resp.ok) {
      setAddLinkForm(null);
      loadResources();
      setMsg("链接已添加");
    } else {
      setMsg("添加失败，请检查链接格式");
    }
  }

  async function runBgmEnrich(e: React.FormEvent) {
    e.preventDefault();
    setBgmRunning(true);
    setMsg("正在触发 Bangumi 补全...");
    const sp = new URLSearchParams({
      max_per_run: bgmForm.max_per_run,
      delay: bgmForm.delay,
      overwrite: String(bgmForm.overwrite),
    });
    const resp = await apiFetch(`/api/admin/bangumi-enrich?${sp}`, { method: "POST" }, token);
    if (resp.ok) {
      const data = await resp.json();
      setMsg(data.message + " 请稍候后刷新查看封面");
    } else {
      setMsg("触发失败");
    }
    setBgmRunning(false);
    setTimeout(() => loadData(), 8000);
  }

  async function batchImport(e: React.FormEvent) {
    e.preventDefault();
    setBatchRunning(true);
    setBatchResult(null);
    setMsg("");
    let items;
    try {
      items = JSON.parse(batchJson);
      if (!Array.isArray(items)) throw new Error("需要 JSON 数组");
    } catch (err: unknown) {
      setMsg("JSON 格式错误：" + (err instanceof Error ? err.message : String(err)));
      setBatchRunning(false);
      return;
    }
    const resp = await apiFetch("/api/admin/batch-import", { method: "POST", body: JSON.stringify(items) }, token);
    if (resp.ok) {
      const data = await resp.json();
      setBatchResult(data);
      setMsg(`导入完成：新建 ${data.created} 条，更新 ${data.updated} 条，链接 ${data.links_added} 条`);
      loadData();
    } else {
      setMsg("导入失败");
    }
    setBatchRunning(false);
  }

  async function addSource(e: React.FormEvent) {
    e.preventDefault();
    let config = {};
    try {
      config = JSON.parse(newSource.config);
    } catch {
      setMsg("config JSON 格式错误");
      return;
    }
    const sp = new URLSearchParams({ name: newSource.name, spider_class: newSource.spider_class });
    if (newSource.base_url) sp.set("base_url", newSource.base_url);
    const resp = await apiFetch(`/api/admin/sources?${sp.toString()}`, {
      method: "POST",
      body: JSON.stringify(config),
    }, token);
    if (resp.ok) {
      setMsg("数据源已添加");
      setShowAddForm(false);
      setNewSource({ name: "", spider_class: "demo", base_url: "", config: "{}" });
      loadData();
    } else {
      setMsg("添加失败");
    }
  }

  const inputStyle: React.CSSProperties = {
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.1)",
    color: "#f0f0f5",
  };

  // 后台始终使用暗色硬编码值，不随用户日间主题改变
  const DARK = {
    bg: "#0d0d12",
    bgSecondary: "#13131a",
    bgCard: "#1a1a24",
    border: "rgba(255,255,255,0.1)",
    borderStr: "1px solid rgba(255,255,255,0.1)",
    muted: "#606070",
    text2: "#a0a0b0",
  };

  const statusColors: Record<string, string> = { success: "#4ade80", failed: "#f87171", running: "#fbbf24" };

  if (!authed) {
    return (
      <div
        style={{ minHeight: "100vh", background: DARK.bg, color: "#f2f2f8", display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <div
          style={{ width: 360, background: DARK.bgCard, border: DARK.borderStr, borderRadius: 16, padding: 32 }}
        >
          <div className="flex items-center gap-2 mb-8">
            <Settings size={24} style={{ color: "#e50914" }} />
            <h1 className="text-xl font-bold">管理后台</h1>
          </div>
          <form onSubmit={login} className="space-y-4">
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="管理密码（默认 admin123）"
              className="w-full px-4 py-3 rounded-lg outline-none text-sm"
              style={inputStyle}
            />
            {msg && <p className="text-sm" style={{ color: "#ff6070" }}>{msg}</p>}
            <button
              type="submit"
              className="w-full py-3 rounded-lg font-semibold text-white"
              style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)" }}
            >
              登录
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: DARK.bg, color: "#f2f2f8" }}>
      {/* 顶部栏 */}
      <div style={{ background: DARK.bgSecondary, borderBottom: DARK.borderStr }}>
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings size={18} style={{ color: "#e50914" }} />
            <span className="font-bold">管理后台</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => loadData()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm"
              style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}
            >
              <RefreshCw size={14} /> 刷新
            </button>
            <Link href="/" className="text-sm" style={{ color: "#606070" }}>← 返回前台</Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {/* 统计 */}
        {stats && (
          <div className="grid grid-cols-3 gap-4">
            {Object.entries(stats).map(([label, value]) => (
              <div
                key={label}
                className="p-4 rounded-xl text-center"
                style={{ background: DARK.bgCard, border: DARK.borderStr }}
              >
                <div className="text-2xl font-black" style={{ color: "#e50914" }}>{value}</div>
                <div className="text-xs mt-1" style={{ color: "#606070" }}>{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* ══ 手动批量导入 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: "1px solid rgba(34,211,238,0.25)" }}>
          <div className="flex items-center gap-2 mb-1">
            <Upload size={18} style={{ color: "#22d3ee" }} />
            <h2 className="text-lg font-bold">手动批量导入</h2>
            <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(34,211,238,0.12)", color: "#22d3ee" }}>
              粘贴 JSON 一键导入
            </span>
          </div>
          <p className="text-xs mb-3" style={{ color: "#606070" }}>
            将资源数据转为 JSON 数组后粘贴到下方，支持夸克/百度/阿里云盘链接批量写入。
          </p>
          <details className="mb-3">
            <summary className="text-xs cursor-pointer" style={{ color: "#22d3ee" }}>查看 JSON 格式示例</summary>
            <pre className="mt-2 p-3 rounded text-xs overflow-x-auto" style={{ background: "rgba(0,0,0,0.4)", color: "#a0f0c0", lineHeight: 1.6 }}>{`[
  {
    "title": "斗罗大陆 第二季",
    "year": 2023,
    "category": "动漫",
    "status": "更新中",
    "links": [
      { "url": "https://pan.quark.cn/s/完整链接", "link_type": "pan_quark" },
      { "url": "https://pan.baidu.com/s/1完整链接", "link_type": "pan_baidu", "password": "888" }
    ]
  },
  {
    "title": "神印王座",
    "year": 2022,
    "category": "动漫",
    "links": [
      { "url": "https://pan.quark.cn/s/完整链接", "link_type": "pan_quark" }
    ]
  }
]`}</pre>
          </details>
          <form onSubmit={batchImport} className="space-y-3">
            <textarea
              value={batchJson}
              onChange={e => setBatchJson(e.target.value)}
              placeholder='粘贴 JSON 数组到这里...'
              rows={10}
              className="w-full px-3 py-2 rounded-lg outline-none text-xs font-mono resize-y"
              style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(34,211,238,0.2)", color: "#e0e0f0", minHeight: 200 }}
            />
            <div className="flex items-center gap-4">
              <button type="submit" disabled={batchRunning || !batchJson.trim()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-white disabled:opacity-50"
                style={{ background: "linear-gradient(135deg, #0891b2 0%, #0e7490 100%)" }}>
                <Upload size={14} />
                {batchRunning ? "导入中..." : "开始导入"}
              </button>
              {batchResult && (
                <div className="text-sm flex gap-4">
                  <span style={{ color: "#4ade80" }}>新建 {batchResult.created}</span>
                  <span style={{ color: "#60a5fa" }}>更新 {batchResult.updated}</span>
                  <span style={{ color: "#a78bfa" }}>链接 {batchResult.links_added}</span>
                  {batchResult.skipped > 0 && <span style={{ color: "#f87171" }}>失败 {batchResult.skipped}</span>}
                </div>
              )}
            </div>
            {batchResult?.errors?.length ? (
              <div className="text-xs p-2 rounded" style={{ background: "rgba(239,68,68,0.1)", color: "#fca5a5" }}>
                {batchResult.errors.map((e, i) => <div key={i}>{e}</div>)}
              </div>
            ) : null}
          </form>
        </div>

        {/* ══ TMDb 批量导入 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: "1px solid rgba(229,9,20,0.2)" }}>
          <div className="flex items-center gap-2 mb-4">
            <Database size={18} style={{ color: "#e50914" }} />
            <h2 className="text-lg font-bold">TMDb 批量导入</h2>
            <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(229,9,20,0.12)", color: "#ff6070" }}>
              一键导入万部影视元数据
            </span>
          </div>
          <form onSubmit={createTmdbAndRun} className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>TMDb API Key（可选）</label>
                <input value={tmdbForm.api_key} onChange={e => setTmdbForm(f => ({ ...f, api_key: e.target.value }))}
                  placeholder="留空则用 .env 中的 key"
                  className="w-full px-3 py-2 rounded outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>媒体类型</label>
                <select value={tmdbForm.media_type} onChange={e => setTmdbForm(f => ({ ...f, media_type: e.target.value }))}
                  className="w-full px-3 py-2 rounded outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}>
                  <option value="both">电影+剧集</option>
                  <option value="movie">仅电影</option>
                  <option value="tv">仅剧集</option>
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>榜单类型</label>
                <select value={tmdbForm.list_type} onChange={e => setTmdbForm(f => ({ ...f, list_type: e.target.value }))}
                  className="w-full px-3 py-2 rounded outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}>
                  <option value="popular">热门</option>
                  <option value="top_rated">高分</option>
                  <option value="now_playing">上映中</option>
                  <option value="trending">趋势</option>
                  <option value="upcoming">即将上映</option>
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>爬取页数 × 最低评分</label>
                <div className="flex gap-2">
                  <input type="number" min="1" max="20" value={tmdbForm.pages}
                    onChange={e => setTmdbForm(f => ({ ...f, pages: e.target.value }))}
                    className="w-16 px-2 py-2 rounded outline-none text-sm text-center"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                  <input type="number" min="0" max="10" step="0.5" value={tmdbForm.min_rating}
                    onChange={e => setTmdbForm(f => ({ ...f, min_rating: e.target.value }))}
                    className="flex-1 px-2 py-2 rounded outline-none text-sm text-center"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button type="submit" disabled={tmdbRunning}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-white disabled:opacity-50"
                style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)" }}>
                <Database size={14} />
                {tmdbRunning ? "导入中..." : `一键创建并导入（约 ${parseInt(tmdbForm.pages) * 20} 条）`}
              </button>
              <p className="text-xs" style={{ color: "#606070" }}>
                每页 20 条，{tmdbForm.pages} 页 × 2 种媒体 ≈ {parseInt(tmdbForm.pages) * 20 * (tmdbForm.media_type === "both" ? 2 : 1)} 条资源
              </p>
            </div>
          </form>
        </div>

        {/* ══ Bangumi 封面补全 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: "1px solid rgba(168,85,247,0.25)" }}>
          <div className="flex items-center gap-2 mb-1">
            <Image size={18} style={{ color: "#a855f7" }} />
            <h2 className="text-lg font-bold">Bangumi 封面补全</h2>
            <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(168,85,247,0.12)", color: "#c084fc" }}>
              免费 · 无需 Key · 国漫覆盖率高
            </span>
          </div>
          <p className="text-xs mb-4" style={{ color: "#606070" }}>
            通过 bgm.tv 搜索动漫标题，自动补全封面图、评分、简介、年份。每条约 1 秒，50 条约 1 分钟。
          </p>
          <form onSubmit={runBgmEnrich} className="space-y-3">
            <div className="flex gap-3 items-end flex-wrap">
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>每次处理数量</label>
                <input type="number" min="10" max="200" value={bgmForm.max_per_run}
                  onChange={e => setBgmForm(f => ({ ...f, max_per_run: e.target.value }))}
                  className="w-24 px-3 py-2 rounded outline-none text-sm text-center"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>请求间隔（秒）</label>
                <input type="number" min="0.5" max="5" step="0.5" value={bgmForm.delay}
                  onChange={e => setBgmForm(f => ({ ...f, delay: e.target.value }))}
                  className="w-24 px-3 py-2 rounded outline-none text-sm text-center"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <label className="flex items-center gap-2 cursor-pointer pb-2">
                <input type="checkbox" checked={bgmForm.overwrite}
                  onChange={e => setBgmForm(f => ({ ...f, overwrite: e.target.checked }))}
                  className="w-4 h-4 rounded" />
                <span className="text-sm" style={{ color: "#a0a0b0" }}>覆盖已有封面</span>
              </label>
            </div>
            <button type="submit" disabled={bgmRunning}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-white disabled:opacity-50"
              style={{ background: "linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%)" }}>
              <Image size={14} />
              {bgmRunning ? "补全中..." : `开始补全（${bgmForm.max_per_run} 条动漫封面）`}
            </button>
          </form>
        </div>

        {/* ══ 网盘链接搜索 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: "1px solid rgba(6,182,212,0.2)" }}>
          <div className="flex items-center gap-2 mb-1">
            <Search size={18} style={{ color: "#22d3ee" }} />
            <h2 className="text-lg font-bold">网盘链接搜索</h2>
            <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(6,182,212,0.12)", color: "#22d3ee" }}>
              Bing 自动搜索夸克/百度链接
            </span>
          </div>
          <p className="text-xs mb-4" style={{ color: "#606070" }}>
            对数据库中无下载链接的影视资源，通过 Bing 搜索公开分享的网盘链接并自动写入。命中率约 30-60%，受限于 Bing 索引内容。
          </p>
          <form onSubmit={runPanSearch} className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>数据源</label>
                <div className="flex gap-1">
                  <select value={panForm.source_id} onChange={e => setPanForm(f => ({ ...f, source_id: e.target.value }))}
                    className="flex-1 px-2 py-2 rounded outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}>
                    <option value="">-- 选择 pan_search 源 --</option>
                    {sources.filter(s => s.spider_class === "pan_search").map(s => (
                      <option key={s.id} value={String(s.id)}>{s.name}</option>
                    ))}
                  </select>
                  <button type="button" onClick={createPanSource}
                    className="px-2 py-1 rounded text-xs shrink-0"
                    style={{ background: "rgba(6,182,212,0.15)", color: "#22d3ee", border: "1px solid rgba(6,182,212,0.3)" }}
                    title="自动创建 pan_search 数据源">
                    +新建
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>目标网盘</label>
                <select value={panForm.pan_types} onChange={e => setPanForm(f => ({ ...f, pan_types: e.target.value }))}
                  className="w-full px-3 py-2 rounded outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}>
                  <option value="quark,baidu">夸克+百度</option>
                  <option value="quark">仅夸克</option>
                  <option value="baidu">仅百度</option>
                  <option value="quark,baidu,aliyun">夸克+百度+阿里</option>
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>每次处理数量</label>
                <input type="number" min="1" max="100" value={panForm.max_per_run}
                  onChange={e => setPanForm(f => ({ ...f, max_per_run: e.target.value }))}
                  className="w-full px-3 py-2 rounded outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>搜索间隔（秒，建议 ≥ 2）</label>
                <input type="number" min="1" max="10" step="0.5" value={panForm.delay}
                  onChange={e => setPanForm(f => ({ ...f, delay: e.target.value }))}
                  className="w-full px-3 py-2 rounded outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
            </div>
            <button type="submit" disabled={panRunning || !panForm.source_id}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-white disabled:opacity-50"
              style={{ background: "linear-gradient(135deg, #0891b2 0%, #0e7490 100%)" }}>
              <Search size={14} />
              {panRunning ? "搜索中..." : `开始搜索网盘链接（${panForm.max_per_run} 个资源）`}
            </button>
          </form>
        </div>

        {/* ══ 资源链接管理 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: DARK.borderStr }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">资源链接管理</h2>
            <span className="text-xs" style={{ color: "#606070" }}>可搜索影片、查看/添加/删除下载链接</span>
          </div>
          <div className="flex gap-2 mb-4">
            <input value={resSearch} onChange={e => setResSearch(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") { setResPage(1); loadResources(resSearch, 1); } }}
              placeholder="搜索影片名称..." className="flex-1 px-3 py-2 rounded outline-none text-sm"
              style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
            <button onClick={() => { setResPage(1); loadResources(resSearch, 1); }}
              className="px-4 py-2 rounded text-sm font-semibold text-white"
              style={{ background: "#e50914" }}>搜索</button>
          </div>

          {resData && (
            <div className="space-y-2">
              <div className="text-xs mb-2" style={{ color: "#606070" }}>共 {resData.total} 条，每页 15 条</div>
              {resData.items.map(res => (
                <div key={res.id} className="rounded-lg overflow-hidden"
                  style={{ border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.02)" }}>
                  {/* 影片行 */}
                  <div className="flex items-center gap-3 px-4 py-3 cursor-pointer"
                    onClick={() => setExpandedId(expandedId === res.id ? null : res.id)}>
                    {res.poster_url
                      ? <img src={res.poster_url} className="w-8 h-11 object-cover rounded flex-shrink-0" />
                      : <div className="w-8 h-11 rounded flex-shrink-0" style={{ background: "rgba(255,255,255,0.06)" }} />}
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">{res.title}</div>
                      <div className="text-xs mt-0.5" style={{ color: "#606070" }}>
                        {res.year && <span className="mr-2">{res.year}</span>}
                        {res.rating && <span className="mr-2">⭐ {res.rating}</span>}
                        <span style={{ color: res.link_count > 0 ? "#4ade80" : "#f87171" }}>
                          {res.link_count} 条链接
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={e => { e.stopPropagation(); setAddLinkForm({ resource_id: res.id, url: "", link_type: "pan_quark", password: "" }); }}
                        className="px-2 py-1 rounded text-xs"
                        style={{ background: "rgba(74,222,128,0.12)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.2)" }}>
                        + 添加链接
                      </button>
                      <span className="text-xs" style={{ color: "#404050" }}>{expandedId === res.id ? "▲" : "▼"}</span>
                    </div>
                  </div>

                  {/* 链接详情 */}
                  {expandedId === res.id && (
                    <div className="px-4 pb-3 space-y-2 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      {res.links.length === 0
                        ? <p className="text-xs py-2" style={{ color: "#606070" }}>暂无下载链接</p>
                        : res.links.map(lk => (
                          <div key={lk.id} className="flex items-center gap-2 py-1.5">
                            <span className="text-xs px-1.5 py-0.5 rounded flex-shrink-0"
                              style={{ background: lk.link_type.includes("quark") ? "rgba(249,115,22,0.15)" : "rgba(59,130,246,0.15)",
                                       color: lk.link_type.includes("quark") ? "#fb923c" : "#60a5fa" }}>
                              {lk.link_type.replace("pan_", "")}
                            </span>
                            <span className="text-xs flex-1 truncate font-mono" style={{ color: lk.is_valid ? "#c0c0d0" : "#606070" }}>
                              {lk.url}
                            </span>
                            {lk.password && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>密码:{lk.password}</span>}
                            <button onClick={() => deleteLink(lk.id, res.id)}
                              className="text-xs px-2 py-0.5 rounded flex-shrink-0"
                              style={{ background: "rgba(239,68,68,0.12)", color: "#f87171" }}>删除</button>
                          </div>
                        ))
                      }
                    </div>
                  )}
                </div>
              ))}

              {/* 分页 */}
              <div className="flex items-center gap-2 pt-2">
                <button disabled={resPage <= 1} onClick={() => { const p = resPage - 1; setResPage(p); loadResources(resSearch, p); }}
                  className="px-3 py-1.5 rounded text-sm disabled:opacity-30"
                  style={{ background: "rgba(255,255,255,0.06)" }}>上一页</button>
                <span className="text-sm" style={{ color: "#606070" }}>第 {resPage} 页</span>
                <button disabled={resPage * 15 >= (resData?.total || 0)} onClick={() => { const p = resPage + 1; setResPage(p); loadResources(resSearch, p); }}
                  className="px-3 py-1.5 rounded text-sm disabled:opacity-30"
                  style={{ background: "rgba(255,255,255,0.06)" }}>下一页</button>
              </div>
            </div>
          )}

          {!resData && (
            <button onClick={() => loadResources()} className="px-4 py-2 rounded text-sm"
              style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>
              点击加载资源列表
            </button>
          )}
        </div>

        {/* 添加链接弹窗 */}
        {addLinkForm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.7)" }}>
            <div className="w-full max-w-md p-6 rounded-2xl" style={{ background: DARK.bgCard, border: DARK.borderStr }}>
              <h3 className="font-bold text-lg mb-4">添加下载链接</h3>
              <form onSubmit={addLink} className="space-y-3">
                <div>
                  <label className="block text-xs mb-1" style={{ color: "#606070" }}>链接类型</label>
                  <select value={addLinkForm.link_type} onChange={e => setAddLinkForm(f => f && ({ ...f, link_type: e.target.value }))}
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}>
                    <option value="pan_quark">夸克网盘</option>
                    <option value="pan_baidu">百度网盘</option>
                    <option value="pan_aliyun">阿里云盘</option>
                    <option value="magnet">磁力链接</option>
                    <option value="direct">直链</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: "#606070" }}>链接地址</label>
                  <input value={addLinkForm.url} onChange={e => setAddLinkForm(f => f && ({ ...f, url: e.target.value }))}
                    placeholder="https://pan.quark.cn/s/..." required
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: "#606070" }}>提取码（可选）</label>
                  <input value={addLinkForm.password} onChange={e => setAddLinkForm(f => f && ({ ...f, password: e.target.value }))}
                    placeholder="如：8888"
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
                <div className="flex gap-3 pt-2">
                  <button type="submit" className="flex-1 py-2.5 rounded-lg font-semibold text-white"
                    style={{ background: "#e50914" }}>确认添加</button>
                  <button type="button" onClick={() => setAddLinkForm(null)}
                    className="flex-1 py-2.5 rounded-lg font-semibold"
                    style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>取消</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* 数据源管理 */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">数据源管理</h2>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
              style={{ background: "rgba(229,9,20,0.15)", color: "#ff6070", border: "1px solid rgba(229,9,20,0.3)" }}
            >
              <Plus size={14} /> 添加数据源
            </button>
          </div>

          {showAddForm && (
            <form
              onSubmit={addSource}
              className="p-4 rounded-xl mb-4 space-y-3"
              style={{ background: DARK.bgCard, border: DARK.borderStr }}
            >
              <h3 className="text-sm font-semibold">添加新数据源</h3>
              <div className="grid grid-cols-2 gap-3">
                <input
                  value={newSource.name}
                  onChange={(e) => setNewSource((s) => ({ ...s, name: e.target.value }))}
                  placeholder="数据源名称"
                  required
                  className="px-3 py-2 rounded text-sm outline-none"
                  style={inputStyle}
                />
                <select
                  value={newSource.spider_class}
                  onChange={(e) => setNewSource((s) => ({ ...s, spider_class: e.target.value }))}
                  className="px-3 py-2 rounded text-sm outline-none"
                  style={inputStyle}
                >
                  {spiderClasses.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <input
                value={newSource.base_url}
                onChange={(e) => setNewSource((s) => ({ ...s, base_url: e.target.value }))}
                placeholder="基础URL（可选）"
                className="w-full px-3 py-2 rounded text-sm outline-none"
                style={inputStyle}
              />
              <div>
                <p className="text-xs mb-1" style={{ color: "#606070" }}>
                  配置 JSON（RSS 源填 {`{"feed_url":"..."}`}）
                </p>
                <textarea
                  value={newSource.config}
                  onChange={(e) => setNewSource((s) => ({ ...s, config: e.target.value }))}
                  rows={3}
                  className="w-full px-3 py-2 rounded text-sm outline-none font-mono"
                  style={{ ...inputStyle, resize: "vertical" }}
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="px-4 py-2 rounded text-sm font-medium text-white"
                  style={{ background: "#e50914" }}
                >
                  确认添加
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 rounded text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}
                >
                  取消
                </button>
              </div>
            </form>
          )}

          <div className="space-y-2">
            {sources.map((src) => (
              <div
                key={src.id}
                className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 rounded-xl"
                style={{ background: DARK.bgCard, border: DARK.borderStr }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{src.name}</span>
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}
                    >
                      {src.spider_class}
                    </span>
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{
                        background: src.is_active ? "rgba(74,222,128,0.1)" : "rgba(100,116,139,0.1)",
                        color: src.is_active ? "#4ade80" : "#64748b",
                      }}
                    >
                      {src.is_active ? "运行中" : "已禁用"}
                    </span>
                  </div>
                  <div className="text-xs mt-1 flex gap-3 flex-wrap" style={{ color: "#606070" }}>
                    <span>资源: {src.total_resources}</span>
                    {src.last_crawled && (
                      <span>最后爬取: {new Date(src.last_crawled).toLocaleString("zh-CN")}</span>
                    )}
                    {src.base_url && <span className="truncate max-w-xs">{src.base_url}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => toggleSource(src.id)}
                    className="flex items-center gap-1 px-3 py-1.5 rounded text-xs transition-all"
                    style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0", border: "1px solid rgba(255,255,255,0.08)" }}
                  >
                    {src.is_active
                      ? <ToggleRight size={14} style={{ color: "#4ade80" }} />
                      : <ToggleLeft size={14} />}
                    {src.is_active ? "禁用" : "启用"}
                  </button>
                  <button
                    onClick={() => runSpider(src.id, src.name)}
                    className="flex items-center gap-1 px-3 py-1.5 rounded text-xs"
                    style={{ background: "rgba(229,9,20,0.15)", color: "#ff6070", border: "1px solid rgba(229,9,20,0.3)" }}
                  >
                    <Play size={12} /> 立即爬取
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 爬虫日志 */}
        <div>
          <h2 className="text-lg font-bold mb-4">最近爬虫日志</h2>
          <div className="space-y-2">
            {logs.length === 0 ? (
              <p className="text-sm" style={{ color: "#606070" }}>暂无日志</p>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center gap-4 p-3 rounded-lg text-sm"
                  style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
                >
                  <span className="font-bold" style={{ color: statusColors[log.status] || "#a0a0b0", minWidth: 52 }}>
                    {log.status}
                  </span>
                  <span style={{ color: "#a0a0b0" }}>+{log.new_resources} 新增</span>
                  <span style={{ color: "#a0a0b0" }}>~{log.updated_resources} 更新</span>
                  <span className="flex-1 text-xs truncate" style={{ color: "#606070" }}>
                    {log.error_msg || ""}
                  </span>
                  <span className="text-xs shrink-0" style={{ color: "#606070" }}>
                    {new Date(log.started_at).toLocaleString("zh-CN")}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* 消息提示 */}
      {msg && (
        <div
          className="fixed bottom-6 right-6 px-4 py-3 rounded-lg text-sm font-medium"
          style={{ background: DARK.bgCard, border: DARK.borderStr, color: "#f0f0f5", zIndex: 100 }}
        >
          {msg}
          <button onClick={() => setMsg("")} className="ml-3" style={{ color: "#606070" }}>✕</button>
        </div>
      )}
    </div>
  );
}
