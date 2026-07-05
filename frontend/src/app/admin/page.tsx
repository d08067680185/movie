"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { Settings, Play, ToggleLeft, ToggleRight, Plus, RefreshCw, Database, Search, Upload, Image as ImageIcon, Lock, FilePlus, Bell, HardDrive, GitMerge, AlertTriangle, CheckCircle } from "lucide-react";

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
  subtitle?: string; episode_info?: string;
}
interface ResourceDetail {
  id: number; title: string; year?: number; category?: string;
  genre?: string; synopsis?: string; country?: string;
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
  source_name?: string;
  status: string;
  new_resources: number;
  updated_resources: number;
  error_msg?: string;
  started_at: string;
  finished_at?: string;
}

interface TaskItem {
  id: string; name: string; status: "running" | "success" | "failed";
  total: number; done: number; message: string;
  started_at: string; finished_at: string | null;
}

interface DupResource {
  id: number; title: string; year?: number; category?: string; link_count: number;
}
interface DupGroup {
  title: string; year?: number; count: number; resources: DupResource[];
}
interface BackupItem { name: string; size_mb: number; created_at: string; }

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [authed, setAuthed] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [logsOffset, setLogsOffset] = useState(0);
  const [logsLoadingMore, setLogsLoadingMore] = useState(false);
  const [spiderClasses, setSpiderClasses] = useState<string[]>([]);
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [statsDetail, setStatsDetail] = useState<{ today_resources: number; today_links: number } | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newSource, setNewSource] = useState({ name: "", spider_class: "demo", base_url: "", config: "{}" });
  const [msg, setMsg] = useState("");
  const [tmdbForm, setTmdbForm] = useState({ api_key: "", media_type: "both", list_type: "popular", pages: "5", min_rating: "6.0" });
  const [panForm, setPanForm] = useState({ source_id: "", pan_types: "quark,baidu", max_per_run: "20", delay: "3.0" });
  const [tmdbRunning, setTmdbRunning] = useState(false);
  const [panRunning, setPanRunning] = useState(false);
  const [bgmForm, setBgmForm] = useState({ max_per_run: "50", delay: "1.0", overwrite: false });
  const [resSearch, setResSearch] = useState("");
  const [resCategory, setResCategory] = useState("");
  const [resPage, setResPage] = useState(1);
  const [resData, setResData] = useState<{ total: number; items: ResourceDetail[] } | null>(null);
  const [resNoPoster, setResNoPoster] = useState(false);
  const [resNoLinks, setResNoLinks] = useState(false);
  const [searchLogs, setSearchLogs] = useState<{ keyword: string; count: number; last_searched: string | null }[]>([]);
  const [logsLoaded, setLogsLoaded] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [addLinkForm, setAddLinkForm] = useState<{ resource_id: number; url: string; link_type: string; password: string; quality?: string; subtitle?: string } | null>(null);
  const [bgmRunning, setBgmRunning] = useState(false);
  const [batchJson, setBatchJson] = useState("");
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResult, setBatchResult] = useState<{ created: number; updated: number; links_added: number; skipped: number; errors: string[] } | null>(null);
  // 密码修改
  const [pwForm, setPwForm] = useState({ newPw: "", confirmPw: "" });
  const [pwMsg, setPwMsg] = useState("");
  const [pwLoading, setPwLoading] = useState(false);
  // 手动添加单条资源
  const [addResForm, setAddResForm] = useState({
    title: "", title_en: "", year: "", category: "电影", genre: "",
    country: "", synopsis: "", poster_url: "", rating: "",
  });
  const [addResResultId, setAddResResultId] = useState<number | null>(null);
  const [addResMsg, setAddResMsg] = useState("");
  const [addResRunning, setAddResRunning] = useState(false);
  // 表单内的链接列表（提交时一起创建）
  interface LinkRow { url: string; link_type: string; password: string }
  const [addResLinks, setAddResLinks] = useState<LinkRow[]>([]);
  const [linkInput, setLinkInput] = useState({ url: "", link_type: "pan_quark", password: "" });
  // TMDb API Key 配置
  const [tmdbKey, setTmdbKey] = useState("");
  const [tmdbKeyConfigured, setTmdbKeyConfigured] = useState<boolean | null>(null);
  const [tmdbKeyLoading, setTmdbKeyLoading] = useState(false);
  // A: 任务进度
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  // B: 重复检测
  const [dupData, setDupData] = useState<DupGroup[] | null>(null);
  const [dupLoading, setDupLoading] = useState(false);
  // C: 链接检测
  const [linkCheckRunning, setLinkCheckRunning] = useState(false);
  // E: 备份
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [backupRunning, setBackupRunning] = useState(false);
  // E: Telegram
  const [telegramForm, setTelegramForm] = useState({ bot_token: "", chat_id: "" });
  const [telegramConfigured, setTelegramConfigured] = useState<boolean | null>(null);
  const [telegramLoading, setTelegramLoading] = useState(false);
  const [showTelegramForm, setShowTelegramForm] = useState(false);
  // 资源编辑
  const [editResId, setEditResId] = useState<number | null>(null);
  const [editResForm, setEditResForm] = useState({ title: "", year: "", category: "电影", genre: "", synopsis: "", country: "", poster_url: "", rating: "" });
  const [editResRunning, setEditResRunning] = useState(false);
  // 链接编辑
  const [editLinkId, setEditLinkId] = useState<number | null>(null);
  const [editLinkForm, setEditLinkForm] = useState({ url: "", link_type: "magnet", quality: "", password: "", subtitle: "", format: "", size: "", episode_info: "" });
  const [editLinkRunning, setEditLinkRunning] = useState(false);
  // TMDb 补全
  const [tmdbEnrichId, setTmdbEnrichId] = useState<number | null>(null);
  const [tmdbEnrichForm, setTmdbEnrichForm] = useState({ tmdb_id: "", media_type: "movie", search_query: "" });
  const [tmdbSearchResults, setTmdbSearchResults] = useState<any[]>([]);
  const [tmdbEnrichRunning, setTmdbEnrichRunning] = useState(false);
  const [tmdbSearchRunning, setTmdbSearchRunning] = useState(false);

  // msg 5 秒后自动消除
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(""), 5000);
    return () => clearTimeout(t);
  }, [msg]);

  // 登录后加载任务列表和状态
  useEffect(() => {
    if (!authed) return;
    loadTasks();
    loadTelegramStatus();
    loadBackups();
    loadSearchLogs();
  }, [authed]); // eslint-disable-line

  // 有运行中任务时每 3s 轮询
  const hasRunningTasks = tasks.some(t => t.status === "running");
  useEffect(() => {
    if (!hasRunningTasks) return;
    const id = setInterval(loadTasks, 3000);
    return () => clearInterval(id);
  }, [hasRunningTasks]); // eslint-disable-line

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
    const [srcRes, logRes, classRes, statsRes, statsDetailRes, keyRes] = await Promise.all([
      apiFetch("/api/admin/sources", {}, t),
      apiFetch("/api/admin/logs", {}, t),
      apiFetch("/api/admin/spider-classes", {}, t),
      fetch(`${API}/api/stats`),
      apiFetch("/api/admin/stats-detail", {}, t),
      apiFetch("/api/admin/tmdb-key-status", {}, t),
    ]);
    if (srcRes.ok) setSources(await srcRes.json());
    if (logRes.ok) setLogs(await logRes.json());
    if (classRes.ok) setSpiderClasses(await classRes.json());
    if (statsRes.ok) {
      const s = await statsRes.json();
      setStats({ 影视资源: s.total_resources, 下载链接: s.total_links, 数据来源: s.total_sources });
    }
    if (statsDetailRes.ok) {
      setStatsDetail(await statsDetailRes.json());
    }
    if (keyRes.ok) {
      const k = await keyRes.json();
      setTmdbKeyConfigured(k.configured);
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

  async function loadResources(q = resSearch, page = resPage, cat = resCategory, noPoster = resNoPoster, noLinks = resNoLinks) {
    const sp = new URLSearchParams({ page: String(page), page_size: "15" });
    if (q) sp.set("q", q);
    if (cat) sp.set("category", cat);
    if (noPoster) sp.set("no_poster", "true");
    if (noLinks) sp.set("no_links", "true");
    const resp = await apiFetch(`/api/admin/resources?${sp}`, {}, token);
    if (resp.ok) setResData(await resp.json());
  }

  async function loadSearchLogs() {
    const resp = await apiFetch("/api/admin/search-logs?limit=50", {}, token);
    if (resp.ok) {
      setSearchLogs(await resp.json());
      setLogsLoaded(true);
    }
  }

  async function deleteLink(linkId: number) {
    if (!confirm("确认删除此链接？")) return;
    const resp = await apiFetch(`/api/admin/links/${linkId}`, { method: "DELETE" }, token);
    setMsg(resp.ok ? "链接已删除" : "删除失败，请重试");
    loadResources();
  }

  async function toggleLinkValidity(linkId: number, currentValid: boolean) {
    const action = currentValid ? "invalidate" : "validate";
    await apiFetch(`/api/admin/links/${linkId}/${action}`, { method: "PATCH" }, token);
    loadResources();
  }

  async function updateLink(linkId: number) {
    if (!editLinkForm.url.trim()) {
      setMsg("URL不能为空");
      return;
    }
    setEditLinkRunning(true);
    const body: Record<string, any> = {};
    if (editLinkForm.url) body.url = editLinkForm.url;
    if (editLinkForm.link_type) body.link_type = editLinkForm.link_type;
    if (editLinkForm.quality) body.quality = editLinkForm.quality;
    if (editLinkForm.password) body.password = editLinkForm.password;
    if (editLinkForm.subtitle) body.subtitle = editLinkForm.subtitle;
    if (editLinkForm.format) body.format = editLinkForm.format;
    if (editLinkForm.size) body.size = editLinkForm.size;
    if (editLinkForm.episode_info) body.episode_info = editLinkForm.episode_info;

    const resp = await apiFetch(`/api/admin/links/${linkId}`, { method: "PATCH", body: JSON.stringify(body) }, token);
    setEditLinkRunning(false);
    if (resp.ok) {
      setMsg("链接已更新");
      setEditLinkId(null);
      loadResources();
    } else {
      setMsg("更新失败，请重试");
    }
  }

  async function searchTMDb(query: string) {
    if (!query.trim()) return;
    setTmdbSearchRunning(true);
    const resp = await apiFetch(`/api/tmdb/search?q=${encodeURIComponent(query)}`, {}, token);
    if (resp.ok) {
      const data = await resp.json();
      setTmdbSearchResults(data.results || []);
    } else {
      setMsg("搜索失败");
    }
    setTmdbSearchRunning(false);
  }

  async function enrichResourceTMDb() {
    if (!tmdbEnrichId) return;
    if (!tmdbEnrichForm.tmdb_id.trim()) {
      setMsg("请输入或选择 TMDb ID");
      return;
    }
    setTmdbEnrichRunning(true);
    const url = `/api/tmdb/enrich/${tmdbEnrichId}?tmdb_id=${tmdbEnrichForm.tmdb_id}&media_type=${tmdbEnrichForm.media_type}`;
    const resp = await apiFetch(url, { method: "POST" }, token);
    if (resp.ok) {
      setMsg("资源已补全");
      setTmdbEnrichId(null);
      loadResources();
    } else {
      setMsg("补全失败");
    }
    setTmdbEnrichRunning(false);
  }

  async function deleteResource(resourceId: number, title: string) {
    if (!confirm(`确认删除「${title}」及其所有链接？此操作不可恢复。`)) return;
    const resp = await apiFetch(`/api/admin/resources/${resourceId}`, { method: "DELETE" }, token);
    if (resp.ok) {
      setMsg(`已删除「${title}」`);
      loadResources();
    } else {
      setMsg("删除失败");
    }
  }

  async function addLink(e: React.FormEvent) {
    e.preventDefault();
    if (!addLinkForm) return;
    const src = sources.find(s => s.name === "手动导入");
    const sourceId = src?.id ?? 0; // 0 → 后端自动查找/创建"手动导入"Source
    const resp = await apiFetch(`/api/admin/links`, {
      method: "POST",
      body: JSON.stringify({
        resource_id: addLinkForm.resource_id,
        source_id: sourceId,
        url: addLinkForm.url,
        link_type: addLinkForm.link_type,
        password: addLinkForm.password || undefined,
        quality: addLinkForm.quality || undefined,
        subtitle: addLinkForm.subtitle || undefined,
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

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    if (pwForm.newPw !== pwForm.confirmPw) { setPwMsg("两次密码不一致"); return; }
    if (pwForm.newPw.length < 6) { setPwMsg("密码至少 6 位"); return; }
    setPwLoading(true);
    setPwMsg("");
    const resp = await apiFetch("/api/admin/change-password", { method: "POST", body: JSON.stringify({ new_password: pwForm.newPw }) }, token);
    if (resp.ok) {
      const d = await resp.json().catch(() => ({}));
      setPwMsg(d.warning ? `⚠️ ${d.warning}` : `✓ ${d.message}`);
      setToken(pwForm.newPw);
      setPwForm({ newPw: "", confirmPw: "" });
    } else {
      const d = await resp.json().catch(() => ({}));
      const msg = Array.isArray(d.detail) ? d.detail.map((e: {msg?: string}) => e.msg || "").join("; ") : (d.detail || "修改失败");
      setPwMsg(msg);
    }
    setPwLoading(false);
  }

  async function addResource(e: React.FormEvent) {
    e.preventDefault();
    setAddResRunning(true);
    setAddResMsg("");
    setAddResResultId(null);
    const body: Record<string, string | number | undefined> = { title: addResForm.title };
    if (addResForm.title_en) body.title_en = addResForm.title_en;
    if (addResForm.year) body.year = parseInt(addResForm.year);
    if (addResForm.category) body.category = addResForm.category;
    if (addResForm.genre) body.genre = addResForm.genre;
    if (addResForm.country) body.country = addResForm.country;
    if (addResForm.synopsis) body.synopsis = addResForm.synopsis;
    if (addResForm.poster_url) body.poster_url = addResForm.poster_url;
    if (addResForm.rating) body.rating = parseFloat(addResForm.rating);
    const resp = await apiFetch("/api/admin/resources", { method: "POST", body: JSON.stringify(body) }, token);
    if (resp.ok) {
      const data = await resp.json();
      // 同时写入所有链接
      const src = sources.find(s => s.name === "手动导入");
      const sourceId = src?.id || 1;
      let linkCount = 0;
      for (const lk of addResLinks) {
        const lr = await apiFetch("/api/admin/links", {
          method: "POST",
          body: JSON.stringify({ resource_id: data.id, source_id: sourceId, url: lk.url, link_type: lk.link_type, password: lk.password || undefined }),
        }, token);
        if (lr.ok) linkCount++;
      }
      setAddResResultId(data.id);
      setAddResMsg(`✓ 已添加《${data.title}》(ID: ${data.id})${linkCount > 0 ? `，含 ${linkCount} 条链接` : ""}`);
      setAddResForm({ title: "", title_en: "", year: "", category: "电影", genre: "", country: "", synopsis: "", poster_url: "", rating: "" });
      setAddResLinks([]);
      setLinkInput({ url: "", link_type: "pan_quark", password: "" });
      loadData();
    } else {
      const d = await resp.json().catch(() => ({}));
      setAddResMsg(d.detail || "添加失败");
    }
    setAddResRunning(false);
  }

  function addLinkRow() {
    if (!linkInput.url.trim()) return;
    setAddResLinks(l => [...l, { ...linkInput }]);
    setLinkInput(f => ({ ...f, url: "", password: "" }));
  }

  async function updateResource(e: React.FormEvent) {
    e.preventDefault();
    if (!editResId) return;
    setEditResRunning(true);
    const body: Record<string, string | number | undefined> = {};
    if (editResForm.title) body.title = editResForm.title;
    if (editResForm.year) body.year = parseInt(editResForm.year);
    if (editResForm.category) body.category = editResForm.category;
    if (editResForm.genre) body.genre = editResForm.genre;
    if (editResForm.synopsis) body.synopsis = editResForm.synopsis;
    if (editResForm.country) body.country = editResForm.country;
    if (editResForm.poster_url) body.poster_url = editResForm.poster_url;
    if (editResForm.rating) body.rating = parseFloat(editResForm.rating);
    const resp = await apiFetch(`/api/admin/resources/${editResId}`, { method: "PATCH", body: JSON.stringify(body) }, token);
    if (resp.ok) {
      setMsg("资源已更新");
      setEditResId(null);
      loadResources();
    } else {
      setMsg("更新失败");
    }
    setEditResRunning(false);
  }

  async function deleteSource(sourceId: number, name: string) {
    if (!confirm(`确认删除数据源「${name}」？相关爬虫日志将保留，已爬取的资源不受影响。`)) return;
    const resp = await apiFetch(`/api/admin/sources/${sourceId}`, { method: "DELETE" }, token);
    if (resp.ok) {
      setMsg(`已删除数据源「${name}」`);
      loadData();
    } else {
      setMsg("删除失败");
    }
  }

  async function saveTmdbKey(e: React.FormEvent) {
    e.preventDefault();
    setTmdbKeyLoading(true);
    const resp = await apiFetch("/api/admin/set-tmdb-key", { method: "POST", body: JSON.stringify({ api_key: tmdbKey }) }, token);
    if (resp.ok) {
      const data = await resp.json();
      setTmdbKeyConfigured(data.configured);
      setMsg(data.message);
      if (data.configured) setTmdbKey("");
    } else {
      setMsg("保存失败");
    }
    setTmdbKeyLoading(false);
  }

  async function loadTmdbKeyStatus() {
    const resp = await apiFetch("/api/admin/tmdb-key-status", {}, token);
    if (resp.ok) {
      const data = await resp.json();
      setTmdbKeyConfigured(data.configured);
    }
  }

  async function loadMoreLogs() {
    setLogsLoadingMore(true);
    const resp = await apiFetch(`/api/admin/logs?offset=${logsOffset + 20}&limit=20`, {}, token);
    if (resp.ok) {
      const newLogs = await resp.json();
      setLogs(prev => [...prev, ...newLogs]);
      setLogsOffset(prev => prev + 20);
    }
    setLogsLoadingMore(false);
  }

  async function loadTasks() {
    const resp = await apiFetch("/api/admin/tasks", {}, token);
    if (resp.ok) setTasks(await resp.json());
  }

  async function loadDuplicates() {
    setDupLoading(true);
    const resp = await apiFetch("/api/admin/duplicates?limit=30", {}, token);
    if (resp.ok) setDupData(await resp.json());
    setDupLoading(false);
  }

  async function mergeDuplicate(keepId: number, dupId: number, title: string) {
    if (!confirm(`合并「${title}」的重复项？\n将把 ID:${dupId} 的链接移到 ID:${keepId}，然后删除 ID:${dupId}。`)) return;
    const resp = await apiFetch(`/api/admin/resources/${keepId}/merge/${dupId}`, { method: "POST" }, token);
    if (resp.ok) {
      const d = await resp.json();
      setMsg(d.message);
      loadDuplicates();
    }
  }

  async function triggerLinkCheck() {
    setLinkCheckRunning(true);
    const resp = await apiFetch("/api/admin/check-links?max_per_run=30", { method: "POST" }, token);
    if (resp.ok) {
      const d = await resp.json();
      setMsg(d.message);
      setTimeout(loadTasks, 1000);
    } else {
      setMsg("链接检测触发失败");
    }
    setLinkCheckRunning(false);
  }

  async function createBackup() {
    setBackupRunning(true);
    const resp = await apiFetch("/api/admin/backup", { method: "POST" }, token);
    if (resp.ok) {
      const d = await resp.json();
      setMsg(d.message);
      loadBackups();
    } else {
      setMsg("备份失败");
    }
    setBackupRunning(false);
  }

  async function loadBackups() {
    const resp = await apiFetch("/api/admin/backups", {}, token);
    if (resp.ok) setBackups(await resp.json());
  }

  async function saveTelegramConfig(e: React.FormEvent) {
    e.preventDefault();
    setTelegramLoading(true);
    const resp = await apiFetch("/api/admin/telegram-config", { method: "POST", body: JSON.stringify(telegramForm) }, token);
    if (resp.ok) {
      const d = await resp.json();
      setMsg(d.message);
      setTelegramConfigured(true);
      setTelegramForm({ bot_token: "", chat_id: "" });
      setShowTelegramForm(false);
    } else {
      setMsg("保存失败");
    }
    setTelegramLoading(false);
  }

  async function loadTelegramStatus() {
    const resp = await apiFetch("/api/admin/telegram-status", {}, token);
    if (resp.ok) {
      const d = await resp.json();
      setTelegramConfigured(d.configured);
    }
  }

  async function addRssSource(name: string, url: string) {
    const sp = new URLSearchParams({ name, spider_class: "rss", base_url: url });
    const resp = await apiFetch(`/api/admin/sources?${sp.toString()}`, { method: "POST", body: JSON.stringify({}) }, token);
    if (resp.ok) {
      const data = await resp.json();
      setMsg(`✓ 已添加 ${name} (ID: ${data.id})`);
      loadData();
    } else {
      setMsg(`添加 ${name} 失败`);
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
          <div>
            <div className="grid grid-cols-3 gap-4">
              {Object.entries(stats).map(([label, value]) => (
                <div
                  key={label}
                  className="p-4 rounded-xl text-center"
                  style={{ background: DARK.bgCard, border: DARK.borderStr }}
                >
                  <div className="text-2xl font-black" style={{ color: "#e50914" }}>{value}</div>
                  <div className="text-xs mt-1" style={{ color: "#606070" }}>{label}</div>
                  {/* 今日新增小字 */}
                  {statsDetail && (
                    <div className="text-xs mt-2 pt-2 border-t" style={{ borderColor: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>
                      {label === "影视资源" && `今日: +${statsDetail.today_resources}`}
                      {label === "下载链接" && `今日: +${statsDetail.today_links}`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ══ A: 后台任务进度 ══ */}
        {tasks.length > 0 && (
          <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: `1px solid ${hasRunningTasks ? "rgba(251,191,36,0.4)" : "rgba(255,255,255,0.08)"}` }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <RefreshCw size={16} className={hasRunningTasks ? "animate-spin" : ""} style={{ color: "#fbbf24" }} />
                <h2 className="text-base font-bold">后台任务</h2>
                {hasRunningTasks && <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(251,191,36,0.15)", color: "#fbbf24" }}>进行中</span>}
              </div>
              <button onClick={loadTasks} className="text-xs px-2 py-1 rounded" style={{ background: "rgba(255,255,255,0.06)", color: "#606070" }}>刷新</button>
            </div>
            <div className="space-y-2">
              {tasks.slice(0, 8).map(t => {
                const pct = t.total > 0 ? Math.min(100, Math.round(t.done / t.total * 100)) : null;
                const color = t.status === "success" ? "#4ade80" : t.status === "failed" ? "#f87171" : "#fbbf24";
                return (
                  <div key={t.id} className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-bold w-12 shrink-0" style={{ color }}>{t.status}</span>
                      <span className="text-sm flex-1 truncate">{t.name}</span>
                      <span className="text-xs shrink-0" style={{ color: "#606070" }}>{new Date(t.started_at + "Z").toLocaleTimeString("zh-CN")}</span>
                    </div>
                    {t.message && <p className="text-xs mt-1.5 pl-14" style={{ color: "#a0a0b0" }}>{t.message}</p>}
                    {pct !== null && t.status === "running" && (
                      <div className="mt-2 pl-14">
                        <div className="h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.08)" }}>
                          <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: "#fbbf24" }} />
                        </div>
                        <span className="text-xs mt-0.5" style={{ color: "#606070" }}>{t.done}/{t.total} ({pct}%)</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ══ E: 系统工具（备份 + 链接检测 + Telegram）══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: "1px solid rgba(96,165,250,0.25)" }}>
          <div className="flex items-center gap-2 mb-4">
            <HardDrive size={18} style={{ color: "#60a5fa" }} />
            <h2 className="text-lg font-bold">系统工具</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* 数据库备份 */}
            <div className="p-4 rounded-lg" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <p className="text-sm font-medium mb-1">数据库备份</p>
              <p className="text-xs mb-3" style={{ color: "#606070" }}>
                手动备份 SQLite 到 backups/ 目录（每日凌晨 3 点自动备份）
                {backups.length > 0 && <span className="ml-2" style={{ color: "#4ade80" }}>已有 {backups.length} 个备份</span>}
              </p>
              <button onClick={createBackup} disabled={backupRunning}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)" }}>
                <HardDrive size={14} /> {backupRunning ? "备份中..." : "立即备份"}
              </button>
              {backups.slice(0, 3).map(b => (
                <div key={b.name} className="mt-2 text-xs" style={{ color: "#606070" }}>
                  📦 {b.name} ({b.size_mb} MB)
                </div>
              ))}
            </div>

            {/* 链接有效性检测 */}
            <div className="p-4 rounded-lg" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <p className="text-sm font-medium mb-1">链接有效性检测</p>
              <p className="text-xs mb-3" style={{ color: "#606070" }}>优先检测最久未检测的 30 条网盘链接，发送 HEAD 请求，将失效链接标记为失效（另有定时任务每 2 小时自动批量检测 300 条）</p>
              <button onClick={triggerLinkCheck} disabled={linkCheckRunning}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "linear-gradient(135deg, #0891b2 0%, #0e7490 100%)" }}>
                <AlertTriangle size={14} /> {linkCheckRunning ? "检测中..." : "开始检测"}
              </button>
              <p className="text-xs mt-2" style={{ color: "#404050" }}>检测进度可在「后台任务」面板中查看</p>
            </div>

            {/* Telegram 通知 */}
            <div className="p-4 rounded-lg" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <div className="flex items-center gap-2 mb-1">
                <Bell size={14} style={{ color: "#60a5fa" }} />
                <p className="text-sm font-medium">Telegram 通知</p>
                {telegramConfigured === true && <CheckCircle size={12} style={{ color: "#4ade80" }} />}
              </div>
              <p className="text-xs mb-3" style={{ color: "#606070" }}>
                {telegramConfigured ? "已配置，爬虫失败时自动推送通知" : "配置后，爬虫失败时自动推送通知"}
              </p>
              {!showTelegramForm ? (
                <button onClick={() => setShowTelegramForm(true)}
                  className="px-3 py-2 rounded-lg text-sm font-medium"
                  style={{ background: "rgba(96,165,250,0.15)", color: "#60a5fa", border: "1px solid rgba(96,165,250,0.3)" }}>
                  {telegramConfigured ? "重新配置" : "配置通知"}
                </button>
              ) : (
                <form onSubmit={saveTelegramConfig} className="space-y-2">
                  <input value={telegramForm.bot_token} onChange={e => setTelegramForm(f => ({ ...f, bot_token: e.target.value }))}
                    placeholder="Bot Token (来自 @BotFather)" required
                    className="w-full px-2 py-1.5 rounded text-xs outline-none"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                  <input value={telegramForm.chat_id} onChange={e => setTelegramForm(f => ({ ...f, chat_id: e.target.value }))}
                    placeholder="Chat ID (@userinfobot 可获取)" required
                    className="w-full px-2 py-1.5 rounded text-xs outline-none"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                  <div className="flex gap-2">
                    <button type="submit" disabled={telegramLoading}
                      className="flex-1 py-1.5 rounded text-xs font-medium text-white disabled:opacity-50"
                      style={{ background: "#2563eb" }}>
                      {telegramLoading ? "保存中..." : "保存"}
                    </button>
                    <button type="button" onClick={() => setShowTelegramForm(false)}
                      className="px-3 py-1.5 rounded text-xs"
                      style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>取消</button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>

        {/* ══ B: 重复数据检测 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: "1px solid rgba(251,146,60,0.25)" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <GitMerge size={18} style={{ color: "#fb923c" }} />
              <h2 className="text-lg font-bold">重复数据检测</h2>
              <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(251,146,60,0.12)", color: "#fb923c" }}>
                按标题+年份去重
              </span>
            </div>
            <button onClick={loadDuplicates} disabled={dupLoading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm"
              style={{ background: "rgba(251,146,60,0.12)", color: "#fb923c", border: "1px solid rgba(251,146,60,0.25)" }}>
              <RefreshCw size={13} className={dupLoading ? "animate-spin" : ""} />
              {dupData === null ? "扫描重复项" : "重新扫描"}
            </button>
          </div>

          {dupData === null && !dupLoading && (
            <p className="text-sm" style={{ color: "#606070" }}>点击「扫描重复项」检查数据库中是否存在同名同年的重复资源</p>
          )}
          {dupLoading && <p className="text-sm" style={{ color: "#a0a0b0" }}>扫描中...</p>}
          {dupData !== null && dupData.length === 0 && (
            <div className="flex items-center gap-2 text-sm" style={{ color: "#4ade80" }}>
              <CheckCircle size={16} /> 未发现重复资源
            </div>
          )}
          {dupData !== null && dupData.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs" style={{ color: "#fb923c" }}>发现 {dupData.length} 组重复资源，点击「保留」将保留该条并合并链接，另一条将被删除</p>
              {dupData.map((group, gi) => (
                <div key={gi} className="p-3 rounded-lg" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(251,146,60,0.15)" }}>
                  <div className="text-sm font-medium mb-2">
                    {group.title} {group.year && <span style={{ color: "#606070" }}>({group.year})</span>}
                    <span className="ml-2 text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(251,146,60,0.12)", color: "#fb923c" }}>{group.count} 条</span>
                  </div>
                  <div className="space-y-1.5">
                    {group.resources.map((r, ri) => (
                      <div key={r.id} className="flex items-center gap-2 text-xs">
                        <span style={{ color: "#606070" }}>ID:{r.id}</span>
                        <span style={{ color: r.link_count > 0 ? "#4ade80" : "#f87171" }}>{r.link_count} 条链接</span>
                        <span style={{ color: "#a0a0b0" }}>{r.category}</span>
                        <div className="flex gap-1 ml-auto">
                          {group.resources.filter((_, j) => j !== ri).map(other => (
                            <button key={other.id}
                              onClick={() => mergeDuplicate(r.id, other.id, group.title)}
                              className="px-2 py-0.5 rounded text-xs"
                              style={{ background: "rgba(74,222,128,0.12)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.2)" }}>
                              保留此条，删除 ID:{other.id}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ══ 账号密码管理 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: "1px solid rgba(251,191,36,0.25)" }}>
          <div className="flex items-center gap-2 mb-4">
            <Lock size={18} style={{ color: "#fbbf24" }} />
            <h2 className="text-lg font-bold">账号密码管理</h2>
          </div>
          <form onSubmit={changePassword} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>新密码（至少 6 位）</label>
                <input
                  type="password"
                  value={pwForm.newPw}
                  onChange={e => setPwForm(f => ({ ...f, newPw: e.target.value }))}
                  placeholder="输入新密码"
                  required
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>确认新密码</label>
                <input
                  type="password"
                  value={pwForm.confirmPw}
                  onChange={e => setPwForm(f => ({ ...f, confirmPw: e.target.value }))}
                  placeholder="再次输入新密码"
                  required
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}
                />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button type="submit" disabled={pwLoading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-white disabled:opacity-50"
                style={{ background: "linear-gradient(135deg, #d97706 0%, #b45309 100%)" }}>
                <Lock size={14} />
                {pwLoading ? "修改中..." : "修改密码"}
              </button>
              {pwMsg && (
                <span className="text-sm" style={{ color: pwMsg.startsWith("✓") ? "#4ade80" : "#f87171" }}>{pwMsg}</span>
              )}
            </div>
          </form>
        </div>

        {/* ══ 手动添加单条资源 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: "1px solid rgba(74,222,128,0.25)" }}>
          <div className="flex items-center gap-2 mb-1">
            <FilePlus size={18} style={{ color: "#4ade80" }} />
            <h2 className="text-lg font-bold">手动添加单条资源</h2>
          </div>
          <p className="text-xs mb-4" style={{ color: "#606070" }}>填写表单新增一条影视资源，添加成功后可立即为其添加下载链接。</p>
          <form onSubmit={addResource} className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
              <div className="sm:col-span-2">
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>标题 *</label>
                <input value={addResForm.title} onChange={e => setAddResForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="影视名称（必填）" required
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>分类</label>
                <select value={addResForm.category} onChange={e => setAddResForm(f => ({ ...f, category: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(30,30,40,1)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}>
                  <option value="电影">电影</option>
                  <option value="电视剧">电视剧</option>
                  <option value="动漫">动漫</option>
                  <option value="经典资源">经典资源</option>
                </select>
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>英文名</label>
                <input value={addResForm.title_en} onChange={e => setAddResForm(f => ({ ...f, title_en: e.target.value }))}
                  placeholder="English Title"
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>年份</label>
                <input type="number" min="1900" max="2099" value={addResForm.year}
                  onChange={e => setAddResForm(f => ({ ...f, year: e.target.value }))}
                  placeholder="2024"
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>评分（0-10）</label>
                <input type="number" min="0" max="10" step="0.1" value={addResForm.rating}
                  onChange={e => setAddResForm(f => ({ ...f, rating: e.target.value }))}
                  placeholder="8.5"
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>类型（风格）</label>
                <input value={addResForm.genre} onChange={e => setAddResForm(f => ({ ...f, genre: e.target.value }))}
                  placeholder="动作/爱情/科幻"
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>国家/地区</label>
                <input value={addResForm.country} onChange={e => setAddResForm(f => ({ ...f, country: e.target.value }))}
                  placeholder="中国 / 美国 / 日本"
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div className="sm:col-span-3">
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>封面图 URL</label>
                <input value={addResForm.poster_url} onChange={e => setAddResForm(f => ({ ...f, poster_url: e.target.value }))}
                  placeholder="https://..."
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
              <div className="sm:col-span-3">
                <label className="block text-xs mb-1" style={{ color: "#606070" }}>简介</label>
                <textarea value={addResForm.synopsis} onChange={e => setAddResForm(f => ({ ...f, synopsis: e.target.value }))}
                  placeholder="影片简介..."
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg outline-none text-sm resize-y"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
              </div>
            </div>
            {/* ── 下载链接（内嵌在表单里）── */}
            <div className="pt-3 border-t" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
              <p className="text-xs mb-2 font-medium" style={{ color: "#a0a0b0" }}>下载链接（可选，可添加多条）</p>
              {/* 已添加的链接列表 */}
              {addResLinks.length > 0 && (
                <div className="space-y-1 mb-3">
                  {addResLinks.map((lk, i) => (
                    <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
                      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
                      <span className="px-1.5 py-0.5 rounded flex-shrink-0"
                        style={{ background: "rgba(74,222,128,0.12)", color: "#4ade80" }}>
                        {lk.link_type.replace("pan_", "")}
                      </span>
                      <span className="flex-1 truncate font-mono" style={{ color: "#c0c0d0" }}>{lk.url}</span>
                      {lk.password && <span style={{ color: "#a0a0b0" }}>密码:{lk.password}</span>}
                      <button type="button" onClick={() => setAddResLinks(l => l.filter((_, j) => j !== i))}
                        className="text-xs px-2 py-0.5 rounded flex-shrink-0"
                        style={{ background: "rgba(239,68,68,0.12)", color: "#f87171" }}>删除</button>
                    </div>
                  ))}
                </div>
              )}
              {/* 输入新链接行 */}
              <div className="flex flex-wrap gap-2 items-end">
                <div>
                  <select value={linkInput.link_type} onChange={e => setLinkInput(f => ({ ...f, link_type: e.target.value }))}
                    className="px-3 py-2 rounded-lg outline-none text-sm"
                    style={{ background: "rgba(30,30,40,1)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}>
                    <option value="pan_quark">夸克网盘</option>
                    <option value="pan_baidu">百度网盘</option>
                    <option value="pan_aliyun">阿里云盘</option>
                    <option value="magnet">磁力链接</option>
                    <option value="direct">直链</option>
                  </select>
                </div>
                <div className="flex-1 min-w-48">
                  <input value={linkInput.url} onChange={e => setLinkInput(f => ({ ...f, url: e.target.value }))}
                    onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addLinkRow(); } }}
                    placeholder="粘贴链接地址..."
                    className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
                <div className="w-28">
                  <input value={linkInput.password} onChange={e => setLinkInput(f => ({ ...f, password: e.target.value }))}
                    placeholder="提取码（选填）"
                    className="w-full px-3 py-2 rounded-lg outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
                <button type="button" onClick={addLinkRow}
                  className="px-4 py-2 rounded-lg text-sm font-medium"
                  style={{ background: "rgba(74,222,128,0.15)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.25)" }}>
                  + 加入列表
                </button>
              </div>
              <p className="text-xs mt-1.5" style={{ color: "#404050" }}>按 Enter 或点「加入列表」暂存，点「添加资源」时一起提交</p>
            </div>

            <div className="flex items-center gap-4 pt-1">
              <button type="submit" disabled={addResRunning || !addResForm.title.trim()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-white disabled:opacity-50"
                style={{ background: "linear-gradient(135deg, #16a34a 0%, #15803d 100%)" }}>
                <FilePlus size={14} />
                {addResRunning ? "提交中..." : `添加资源${addResLinks.length > 0 ? `（含 ${addResLinks.length} 条链接）` : ""}`}
              </button>
              {addResMsg && (
                <span className="text-sm flex items-center gap-2" style={{ color: addResMsg.startsWith("✓") ? "#4ade80" : "#f87171" }}>
                  {addResMsg}
                  {addResResultId && (
                    <Link href={`/detail/${addResResultId}`} target="_blank"
                      className="underline text-xs" style={{ color: "#60a5fa" }}>查看详情</Link>
                  )}
                </span>
              )}
            </div>
          </form>
        </div>

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

        {/* ══ 系统配置：TMDb API Key ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: `1px solid ${DARK.border}` }}>
          <div className="flex items-center gap-2 mb-4">
            <Settings size={18} style={{ color: "#e50914" }} />
            <h2 className="text-lg font-bold">系统配置</h2>
          </div>
          <div className="space-y-4">
            {/* TMDb Key */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium">TMDb API Key</span>
                {tmdbKeyConfigured === true && (
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(74,222,128,0.12)", color: "#4ade80" }}>✓ 已配置</span>
                )}
                {tmdbKeyConfigured === false && (
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(239,68,68,0.12)", color: "#f87171" }}>✗ 未配置</span>
                )}
                {tmdbKeyConfigured === null && (
                  <button onClick={loadTmdbKeyStatus} className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.06)", color: DARK.muted }}>检查状态</button>
                )}
              </div>
              <form onSubmit={saveTmdbKey} className="flex gap-2">
                <input
                  value={tmdbKey}
                  onChange={e => setTmdbKey(e.target.value)}
                  placeholder="粘贴 TMDb API Key（v3 Auth）..."
                  className="flex-1 px-3 py-2 rounded outline-none text-sm"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}
                />
                <button
                  type="submit"
                  disabled={tmdbKeyLoading || !tmdbKey.trim()}
                  className="px-4 py-2 rounded text-sm font-medium transition-all disabled:opacity-40"
                  style={{ background: "#e50914", color: "#fff" }}
                >
                  {tmdbKeyLoading ? "保存中..." : "保存"}
                </button>
              </form>
              <p className="text-xs mt-1.5" style={{ color: DARK.muted }}>
                Key 存储于服务器 .env，重建容器后需重新设置。获取地址：developer.themoviedb.org
              </p>
            </div>

            {/* RSS 预置源 */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium">快速添加 RSS 数据源</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => addRssSource("Nyaa 动漫", "https://nyaa.si/?page=rss&c=1_2&f=0")}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-all"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", color: "#f0f0f5" }}
                >
                  <Plus size={13} />
                  Nyaa 动漫磁力
                </button>
                <button
                  onClick={() => addRssSource("YTS 电影", "https://yts.mx/rss/0/0/0/0")}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-all"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", color: "#f0f0f5" }}
                >
                  <Plus size={13} />
                  YTS 电影磁力
                </button>
              </div>
              <p className="text-xs mt-1.5" style={{ color: DARK.muted }}>
                添加后在下方数据源列表中手动触发爬取
              </p>
            </div>
          </div>
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
            <ImageIcon size={18} style={{ color: "#a855f7" }} />
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
              <ImageIcon size={14} />
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
          <div className="flex gap-2 mb-3 flex-wrap">
            <input value={resSearch} onChange={e => setResSearch(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") { setResPage(1); loadResources(resSearch, 1, resCategory); } }}
              placeholder="搜索影片名称..." className="flex-1 min-w-36 px-3 py-2 rounded outline-none text-sm"
              style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
            <select value={resCategory} onChange={e => { setResCategory(e.target.value); setResPage(1); loadResources(resSearch, 1, e.target.value); }}
              className="px-3 py-2 rounded outline-none text-sm"
              style={{ background: "rgba(30,30,40,1)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }}>
              <option value="">全部分类</option>
              <option value="电影">电影</option>
              <option value="电视剧">电视剧</option>
              <option value="动漫">动漫</option>
              <option value="经典资源">经典资源</option>
            </select>
            <button onClick={() => { setResPage(1); loadResources(resSearch, 1, resCategory); }}
              className="px-4 py-2 rounded text-sm font-semibold text-white"
              style={{ background: "#e50914" }}>搜索</button>
          </div>
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => { const v = !resNoPoster; setResNoPoster(v); setResPage(1); loadResources(resSearch, 1, resCategory, v, resNoLinks); }}
              className="px-3 py-1.5 rounded text-xs font-medium transition-all"
              style={resNoPoster ? { background: "#e50914", color: "#fff" } : { background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)", color: "#aaa" }}
            >
              无封面
            </button>
            <button
              onClick={() => { const v = !resNoLinks; setResNoLinks(v); setResPage(1); loadResources(resSearch, 1, resCategory, resNoPoster, v); }}
              className="px-3 py-1.5 rounded text-xs font-medium transition-all"
              style={resNoLinks ? { background: "#e50914", color: "#fff" } : { background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)", color: "#aaa" }}
            >
              无有效链接
            </button>
          </div>

          {resData && (
            <div className="space-y-2">
              <div className="text-xs mb-2" style={{ color: "#606070" }}>
                共 {resData.total} 条，第 {resPage} / {Math.ceil(resData.total / 15) || 1} 页
              </div>
              {resData.items.map(res => (
                <div key={res.id} className="rounded-lg overflow-hidden"
                  style={{ border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.02)" }}>
                  {/* 影片行 */}
                  <div className="flex items-center gap-3 px-4 py-3 cursor-pointer"
                    onClick={() => setExpandedId(expandedId === res.id ? null : res.id)}>
                    {res.poster_url
                      // eslint-disable-next-line @next/next/no-img-element
                      ? <img src={res.poster_url} alt={res.title} className="w-8 h-11 object-cover rounded flex-shrink-0" />
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
                    <div className="flex items-center gap-1.5">
                      <button onClick={e => { e.stopPropagation(); setAddLinkForm({ resource_id: res.id, url: "", link_type: "pan_quark", password: "" }); }}
                        className="px-2 py-1 rounded text-xs"
                        style={{ background: "rgba(74,222,128,0.12)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.2)" }}>
                        + 链接
                      </button>
                      <button onClick={e => {
                        e.stopPropagation();
                        setEditResId(res.id);
                        setEditResForm({ title: res.title, year: res.year ? String(res.year) : "", category: res.category || "电影", genre: res.genre || "", synopsis: res.synopsis || "", country: res.country || "", poster_url: res.poster_url || "", rating: res.rating ? String(res.rating) : "" });
                      }}
                        className="px-2 py-1 rounded text-xs"
                        style={{ background: "rgba(96,165,250,0.12)", color: "#60a5fa", border: "1px solid rgba(96,165,250,0.2)" }}>
                        编辑
                      </button>
                      <button onClick={e => { e.stopPropagation(); setTmdbEnrichId(res.id); setTmdbEnrichForm({ tmdb_id: "", media_type: "movie", search_query: "" }); setTmdbSearchResults([]); }}
                        className="px-2 py-1 rounded text-xs"
                        style={{ background: "rgba(168,85,247,0.12)", color: "#a855f7", border: "1px solid rgba(168,85,247,0.2)" }}>
                        TMDb补全
                      </button>
                      <button onClick={e => { e.stopPropagation(); deleteResource(res.id, res.title); }}
                        className="px-2 py-1 rounded text-xs"
                        style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}>
                        删除
                      </button>
                      <span className="text-xs" style={{ color: "#404050" }}>{expandedId === res.id ? "▲" : "▼"}</span>
                    </div>
                  </div>

                  {/* 链接详情 */}
                  {expandedId === res.id && (
                    <div className="px-4 pb-3 space-y-1.5 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      {res.links.length === 0
                        ? <p className="text-xs py-2" style={{ color: "#606070" }}>暂无下载链接</p>
                        : res.links.map(lk => {
                          const TYPE_STYLE: Record<string, [string, string]> = {
                            pan_quark:  ["rgba(249,115,22,0.15)", "#fb923c"],
                            pan_baidu:  ["rgba(59,130,246,0.15)", "#60a5fa"],
                            pan_aliyun: ["rgba(168,85,247,0.15)", "#c084fc"],
                            magnet:     ["rgba(34,197,94,0.15)",  "#4ade80"],
                            direct:     ["rgba(234,179,8,0.15)",  "#facc15"],
                          };
                          const [bg, color] = TYPE_STYLE[lk.link_type] ?? ["rgba(100,116,139,0.15)", "#94a3b8"];
                          return (
                            <div key={lk.id} className="flex items-center gap-2 py-1.5">
                              <span className="text-xs px-1.5 py-0.5 rounded flex-shrink-0" style={{ background: bg, color }}>
                                {lk.link_type.replace("pan_", "")}
                              </span>
                              {!lk.is_valid && (
                                <span className="text-xs px-1.5 py-0.5 rounded flex-shrink-0"
                                  style={{ background: "rgba(239,68,68,0.12)", color: "#f87171" }}>失效</span>
                              )}
                              <span className="text-xs flex-1 truncate font-mono"
                                style={{ color: lk.is_valid ? "#c0c0d0" : "#505060", textDecoration: lk.is_valid ? "none" : "line-through" }}>
                                {lk.url}
                              </span>
                              {lk.password && (
                                <span className="text-xs px-1.5 py-0.5 rounded flex-shrink-0"
                                  style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>密码:{lk.password}</span>
                              )}
                              <button onClick={() => {
                                setEditLinkId(lk.id);
                                setEditLinkForm({ url: lk.url, link_type: lk.link_type, quality: lk.quality || "", password: lk.password || "", subtitle: lk.subtitle || "", format: "", size: "", episode_info: lk.episode_info || "" });
                              }}
                                className="text-xs px-2 py-0.5 rounded flex-shrink-0"
                                style={{ background: "rgba(59,130,246,0.12)", color: "#60a5fa" }}>编辑</button>
                              <button onClick={() => toggleLinkValidity(lk.id, lk.is_valid)}
                                className="text-xs px-2 py-0.5 rounded flex-shrink-0"
                                style={lk.is_valid
                                  ? { background: "rgba(234,179,8,0.12)", color: "#facc15" }
                                  : { background: "rgba(34,197,94,0.12)", color: "#4ade80" }}>
                                {lk.is_valid ? "失效" : "恢复"}
                              </button>
                              <button onClick={() => deleteLink(lk.id)}
                                className="text-xs px-2 py-0.5 rounded flex-shrink-0"
                                style={{ background: "rgba(239,68,68,0.12)", color: "#f87171" }}>删除</button>
                            </div>
                          );
                        })
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

        {/* 资源编辑弹窗 */}
        {editResId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.7)" }}>
            <div className="w-full max-w-lg p-6 rounded-2xl mx-4" style={{ background: DARK.bgCard, border: DARK.borderStr }}>
              <h3 className="font-bold text-lg mb-4">编辑资源 <span className="text-sm font-normal" style={{ color: DARK.muted }}>#{editResId}</span></h3>
              <form onSubmit={updateResource} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: DARK.muted }}>标题 *</label>
                    <input value={editResForm.title} onChange={e => setEditResForm(f => ({ ...f, title: e.target.value }))}
                      className="w-full px-3 py-2 rounded outline-none text-sm"
                      style={inputStyle} required />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: DARK.muted }}>年份</label>
                    <input type="number" value={editResForm.year} onChange={e => setEditResForm(f => ({ ...f, year: e.target.value }))}
                      className="w-full px-3 py-2 rounded outline-none text-sm"
                      style={inputStyle} placeholder="2024" />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: DARK.muted }}>分类</label>
                    <select value={editResForm.category} onChange={e => setEditResForm(f => ({ ...f, category: e.target.value }))}
                      className="w-full px-3 py-2 rounded outline-none text-sm" style={{ ...inputStyle, background: "rgba(30,30,40,1)" }}>
                      <option value="电影">电影</option>
                      <option value="电视剧">电视剧</option>
                      <option value="动漫">动漫</option>
                      <option value="经典资源">经典资源</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: DARK.muted }}>评分</label>
                    <input type="number" step="0.1" min="0" max="10" value={editResForm.rating} onChange={e => setEditResForm(f => ({ ...f, rating: e.target.value }))}
                      className="w-full px-3 py-2 rounded outline-none text-sm"
                      style={inputStyle} placeholder="8.5" />
                  </div>
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: DARK.muted }}>类型（genre）</label>
                  <input value={editResForm.genre} onChange={e => setEditResForm(f => ({ ...f, genre: e.target.value }))}
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={inputStyle} placeholder="动作/科幻/爱情" />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: DARK.muted }}>国家/地区</label>
                  <input value={editResForm.country} onChange={e => setEditResForm(f => ({ ...f, country: e.target.value }))}
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={inputStyle} placeholder="中国/日本/美国" />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: DARK.muted }}>封面图 URL</label>
                  <input value={editResForm.poster_url} onChange={e => setEditResForm(f => ({ ...f, poster_url: e.target.value }))}
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={inputStyle} placeholder="https://..." />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: DARK.muted }}>简介（留空则不修改）</label>
                  <textarea value={editResForm.synopsis} onChange={e => setEditResForm(f => ({ ...f, synopsis: e.target.value }))}
                    rows={3} className="w-full px-3 py-2 rounded outline-none text-sm resize-none"
                    style={inputStyle} placeholder="剧情简介..." />
                </div>
                <div className="flex gap-2 pt-1">
                  <button type="submit" disabled={editResRunning || !editResForm.title}
                    className="flex-1 py-2 rounded font-semibold text-white disabled:opacity-40 text-sm"
                    style={{ background: "#e50914" }}>
                    {editResRunning ? "保存中..." : "保存修改"}
                  </button>
                  <button type="button" onClick={() => setEditResId(null)}
                    className="px-6 py-2 rounded text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>
                    取消
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* TMDb 补全弹窗 */}
        {tmdbEnrichId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.7)" }}>
            <div className="w-full max-w-md p-6 rounded-2xl mx-4" style={{ background: DARK.bgCard, border: DARK.borderStr }}>
              <h3 className="font-bold text-lg mb-4">TMDb 补全资源</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs mb-1" style={{ color: DARK.muted }}>类型</label>
                  <select value={tmdbEnrichForm.media_type} onChange={e => setTmdbEnrichForm(f => ({ ...f, media_type: e.target.value }))}
                    className="w-full px-3 py-2 rounded outline-none text-sm" style={{ ...inputStyle, background: "rgba(30,30,40,1)" }}>
                    <option value="movie">电影</option>
                    <option value="tv">电视剧</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: DARK.muted }}>搜索或输入 TMDb ID</label>
                  <div className="flex gap-2 mb-2">
                    <input value={tmdbEnrichForm.search_query} onChange={e => setTmdbEnrichForm(f => ({ ...f, search_query: e.target.value }))}
                      className="flex-1 px-3 py-2 rounded outline-none text-sm"
                      style={inputStyle} placeholder="输入标题搜索..." />
                    <button type="button" onClick={() => searchTMDb(tmdbEnrichForm.search_query)} disabled={tmdbSearchRunning}
                      className="px-4 py-2 rounded text-sm font-semibold text-white disabled:opacity-40"
                      style={{ background: "#e50914" }}>
                      {tmdbSearchRunning ? "搜索中..." : "搜索"}
                    </button>
                  </div>
                  {tmdbSearchResults.length > 0 && (
                    <div className="max-h-48 overflow-y-auto space-y-1 mb-3 p-2 rounded" style={{ background: "rgba(30,30,40,1)", border: "1px solid rgba(255,255,255,0.1)" }}>
                      {tmdbSearchResults.map((result: any) => (
                        <button key={result.id} type="button" onClick={() => setTmdbEnrichForm(f => ({ ...f, tmdb_id: String(result.id) }))}
                          className="w-full text-left px-2 py-1.5 text-xs rounded hover:bg-purple-700/20"
                          style={{ color: "#a0a0b0" }}>
                          <div className="font-semibold text-white">{result.title || result.name}</div>
                          <div className="text-xs" style={{ color: "#606070" }}>{result.release_date || result.first_air_date || "无日期"}</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: DARK.muted }}>TMDb ID</label>
                  <input type="number" value={tmdbEnrichForm.tmdb_id} onChange={e => setTmdbEnrichForm(f => ({ ...f, tmdb_id: e.target.value }))}
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={inputStyle} placeholder="如：550" />
                </div>
                <div className="flex gap-2 pt-1">
                  <button type="button" onClick={enrichResourceTMDb} disabled={tmdbEnrichRunning || !tmdbEnrichForm.tmdb_id}
                    className="flex-1 py-2 rounded font-semibold text-white disabled:opacity-40 text-sm"
                    style={{ background: "#a855f7" }}>
                    {tmdbEnrichRunning ? "补全中..." : "确认补全"}
                  </button>
                  <button type="button" onClick={() => setTmdbEnrichId(null)}
                    className="px-6 py-2 rounded text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}>
                    取消
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

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
                <div>
                  <label className="block text-xs mb-1" style={{ color: "#606070" }}>字幕（可选）</label>
                  <input value={addLinkForm.subtitle || ""} onChange={e => setAddLinkForm(f => f && ({ ...f, subtitle: e.target.value }))}
                    placeholder="如：中文, 英文"
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

        {/* 编辑链接弹窗 */}
        {editLinkId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.7)" }}>
            <div className="w-full max-w-md p-6 rounded-2xl" style={{ background: DARK.bgCard, border: DARK.borderStr }}>
              <h3 className="font-bold text-lg mb-4">编辑链接</h3>
              <form onSubmit={e => { e.preventDefault(); updateLink(editLinkId); }} className="space-y-3">
                <div>
                  <label className="block text-xs mb-1" style={{ color: "#606070" }}>链接类型</label>
                  <select value={editLinkForm.link_type} onChange={e => setEditLinkForm(f => ({ ...f, link_type: e.target.value }))}
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
                  <input value={editLinkForm.url} onChange={e => setEditLinkForm(f => ({ ...f, url: e.target.value }))}
                    required
                    className="w-full px-3 py-2 rounded outline-none text-sm font-mono"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: "#606070" }}>画质（可选）</label>
                  <input value={editLinkForm.quality} onChange={e => setEditLinkForm(f => ({ ...f, quality: e.target.value }))}
                    placeholder="1080P, 720P, 等..."
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: "#606070" }}>提取码（可选）</label>
                  <input value={editLinkForm.password} onChange={e => setEditLinkForm(f => ({ ...f, password: e.target.value }))}
                    placeholder="如：8888"
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: "#606070" }}>字幕（可选）</label>
                  <input value={editLinkForm.subtitle} onChange={e => setEditLinkForm(f => ({ ...f, subtitle: e.target.value }))}
                    placeholder="如：中文, 英文"
                    className="w-full px-3 py-2 rounded outline-none text-sm"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "#606070" }}>格式（可选）</label>
                    <input value={editLinkForm.format} onChange={e => setEditLinkForm(f => ({ ...f, format: e.target.value }))}
                      placeholder="mkv, mp4..."
                      className="w-full px-3 py-2 rounded outline-none text-sm"
                      style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "#606070" }}>文件大小（可选）</label>
                    <input value={editLinkForm.size} onChange={e => setEditLinkForm(f => ({ ...f, size: e.target.value }))}
                      placeholder="2.5GB..."
                      className="w-full px-3 py-2 rounded outline-none text-sm"
                      style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: "#606070" }}>集数（可选）</label>
                    <input value={editLinkForm.episode_info} onChange={e => setEditLinkForm(f => ({ ...f, episode_info: e.target.value }))}
                      placeholder="1-12..."
                      className="w-full px-3 py-2 rounded outline-none text-sm"
                      style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#f0f0f5" }} />
                  </div>
                </div>
                <div className="flex gap-3 pt-2">
                  <button type="submit" disabled={editLinkRunning}
                    className="flex-1 py-2.5 rounded-lg font-semibold text-white disabled:opacity-40"
                    style={{ background: "#e50914" }}>
                    {editLinkRunning ? "保存中..." : "保存修改"}
                  </button>
                  <button type="button" onClick={() => setEditLinkId(null)}
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
                  <button
                    onClick={() => deleteSource(src.id, src.name)}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded text-xs"
                    style={{ background: "rgba(239,68,68,0.08)", color: "#f87171", border: "1px solid rgba(239,68,68,0.15)" }}
                    title="删除此数据源"
                  >
                    ✕
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
                  {log.source_name && (
                    <span className="text-xs px-2 py-1 rounded flex-shrink-0" style={{ background: "rgba(139,92,246,0.15)", color: "#8b5cf6" }}>
                      {log.source_name}
                    </span>
                  )}
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
          {logs.length > 0 && (
            <button
              onClick={loadMoreLogs}
              disabled={logsLoadingMore}
              className="mt-3 px-4 py-2 rounded text-sm transition-all disabled:opacity-40"
              style={{ background: "rgba(255,255,255,0.06)", color: "#a0a0b0" }}
            >
              {logsLoadingMore ? "加载中..." : "加载更多"}
            </button>
          )}
        </div>

        {/* ══ 搜索热词统计 ══ */}
        <div className="p-5 rounded-xl" style={{ background: DARK.bgCard, border: DARK.borderStr }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">搜索热词统计</h2>
            <button
              onClick={loadSearchLogs}
              className="px-4 py-2 rounded text-sm font-semibold text-white"
              style={{ background: "#e50914" }}
            >
              {logsLoaded ? "刷新" : "加载"}
            </button>
          </div>
          {logsLoaded && (
            <div className="space-y-1.5">
              {searchLogs.length === 0 ? (
                <p className="text-sm" style={{ color: "#606070" }}>暂无搜索日志</p>
              ) : (
                searchLogs.map((log, i) => (
                  <div key={log.keyword} className="flex items-center gap-3 px-3 py-2 rounded" style={{ background: "rgba(255,255,255,0.03)" }}>
                    <span className="text-xs w-5 text-center font-bold" style={{ color: i < 3 ? "#e50914" : "#606070" }}>
                      {i + 1}
                    </span>
                    <span className="flex-1 text-sm" style={{ color: "#f0f0f5" }}>{log.keyword}</span>
                    <span className="text-sm font-semibold" style={{ color: "#e50914" }}>{log.count}</span>
                    <span className="text-xs" style={{ color: "#606070" }}>
                      {log.last_searched ? new Date(log.last_searched).toLocaleDateString("zh-CN") : ""}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
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
