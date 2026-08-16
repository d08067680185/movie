"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Globe, RefreshCw, Copy, Check, AlertTriangle } from "lucide-react";
import { liveSearch, checkPanLinks, getHotResources, LiveSearchResult, LiveSearchItem, ResourceCard } from "@/lib/api";
import { CLOUD_TYPE_LABELS } from "@/lib/utils";
import PanLinkModal from "./PanLinkModal";

// 聚合视图的伪类型值：合并所有网盘类型按时间/默认顺序展示，而不是必须先选一个类型
const ALL_TYPE = "__all__";

type TaggedItem = LiveSearchItem & { _cloudType: string };

const RANKING_CATEGORIES = [
  { label: "电影", value: "movie" },
  { label: "电视剧", value: "tv" },
  { label: "动漫", value: "anime" },
];

function HotRankings() {
  const [rankings, setRankings] = useState<Record<string, ResourceCard[]>>({});

  useEffect(() => {
    Promise.all(
      RANKING_CATEGORIES.map((c) => getHotResources(c.value, 5).catch(() => [] as ResourceCard[]))
    ).then((results) => {
      const map: Record<string, ResourceCard[]> = {};
      RANKING_CATEGORIES.forEach((c, i) => { map[c.value] = results[i]; });
      setRankings(map);
    });
  }, []);

  return (
    <div className="space-y-5">
      {RANKING_CATEGORIES.map((cat) => {
        const items = rankings[cat.value] || [];
        if (items.length === 0) return null;
        return (
          <div
            key={cat.value}
            className="rounded-xl p-4"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
          >
            <h3 className="text-sm font-bold mb-3 flex items-center gap-1.5">
              <span className="w-1 h-4 rounded" style={{ background: "#e50914" }} />
              {cat.label}热榜
            </h3>
            <ol className="space-y-2">
              {items.map((r, i) => (
                <li key={r.id}>
                  <Link
                    href={`/detail/${r.id}`}
                    className="flex items-center gap-2 text-sm group"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    <span
                      className="w-5 text-center font-bold shrink-0 text-xs"
                      style={{ color: i < 3 ? "#e50914" : "var(--text-muted)" }}
                    >
                      {i + 1}
                    </span>
                    <span className="truncate group-hover:underline">{r.title}</span>
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
    </div>
  );
}

const PAGE_SIZE = 20;

// 画质筛选：纯前端展示层过滤，对标题做子串匹配，不发新请求。跟后端
// dedup.py:QUALITY_WORDS 覆盖的是同一类词，但这里只需要几个常见档位做chip，
// 不需要跟后端共享完整正则表
const QUALITY_TAGS = ["4K", "2K", "1080P", "720P", "480P", "BD"] as const;
const ALL_QUALITY = "__all_quality__";

function formatDate(dt?: string): string {
  if (!dt) return "";
  const d = new Date(dt);
  // 上游偶尔给 0001-01-01 之类的占位时间，不展示
  if (isNaN(d.getTime()) || d.getFullYear() < 1990) return "";
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// "最新"排序用真正的时间数值比较，而不是对 datetime 原始字符串做字典序比较
// （字典序在占位日期 0001-01-01 面前会把假日期随机插到列表中间）；无效/占位
// 日期统一排到最后
function sortKey(dt?: string): number {
  if (!dt) return -Infinity;
  const t = new Date(dt).getTime();
  if (isNaN(t) || new Date(dt).getFullYear() < 1990) return -Infinity;
  return t;
}

interface Props {
  q: string;
  hotWords?: { keyword: string; count: number }[];
  onPickHotWord?: (keyword: string) => void;
  // 只有调用方传了这两个 prop 才渲染板块筛选行；/pan 独立页没有板块概念，不传即可
  sections?: { key: string; name: string; icon: string }[];
  section?: string;
  onSectionChange?: (section: string) => void;
}

export default function LiveSearchResults({
  q,
  hotWords = [],
  onPickHotWord,
  sections,
  section = "",
  onSectionChange,
}: Props) {
  const [result, setResult] = useState<LiveSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeType, setActiveType] = useState<string>(ALL_TYPE);
  const [modalItem, setModalItem] = useState<{ item: LiveSearchItem; type: string } | null>(null);
  const [sortBy, setSortBy] = useState<"default" | "newest">("default");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [activeQuality, setActiveQuality] = useState<string>(ALL_QUALITY);
  const [checkedLinks, setCheckedLinks] = useState<Record<string, boolean>>({});

  function handleCopy(item: LiveSearchItem, key: string) {
    const text = item.password ? `${item.url} 提取码: ${item.password}` : item.url;
    navigator.clipboard?.writeText(text).then(() => {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 1500);
    });
  }

  function doSearch(refresh = false) {
    if (!q.trim()) {
      setResult(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    if (!refresh) { setActiveType(ALL_TYPE); setActiveQuality(ALL_QUALITY); }
    setVisibleCount(PAGE_SIZE);
    setCheckedLinks({});
    liveSearch(q, refresh, section || undefined)
      .then((r) => { if (!cancelled) setResult(r); })
      .catch(() => { if (!cancelled) setError("全网搜服务暂时不可用，请稍后重试"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    return doSearch(false);
  }, [q, section]); // eslint-disable-line react-hooks/exhaustive-deps

  const types = result?.types || [];
  const isAll = activeType === ALL_TYPE;
  const rawItems: TaggedItem[] = isAll
    ? types.flatMap((t) => (result?.by_type[t.type] || []).map((it) => ({ ...it, _cloudType: t.type })))
    : (result?.by_type[activeType] || []).map((it) => ({ ...it, _cloudType: activeType }));
  const allItems = activeQuality === ALL_QUALITY
    ? rawItems
    : rawItems.filter((it) => it.title.toUpperCase().includes(activeQuality));
  const sortedItems = sortBy === "newest"
    ? [...allItems].sort((a, b) => sortKey(b.datetime) - sortKey(a.datetime))
    : allItems;
  const items = sortedItems.slice(0, visibleCount);
  const remaining = sortedItems.length - items.length;

  // 当前可见的结果里，挑出还没检测过有效性的链接批量查一次（后端代理PanSou，覆盖
  // 9种网盘）；用 checkedLinks 记忆已查过的url，避免翻页/切筛选时重复请求同一批链接
  useEffect(() => {
    const pending = items.filter((it) => !(it.url in checkedLinks));
    if (pending.length === 0) return;
    let cancelled = false;
    checkPanLinks(pending.map((it) => ({ url: it.url, cloudType: it._cloudType }))).then((res) => {
      if (cancelled) return;
      setCheckedLinks((prev) => ({ ...prev, ...res }));
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.map((it) => it.url).join(",")]);

  if (!q.trim()) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center" style={{ color: "var(--text-muted)" }}>
        <Globe size={48} className="mb-4 opacity-30" />
        <p className="text-lg">输入关键词，实时聚合全网网盘资源</p>
        <p className="text-sm mt-2">支持夸克 / 百度 / 阿里 / 迅雷 / 115 等网盘</p>
        <p className="text-xs mt-3 opacity-70">支持排除词：如「斗罗大陆 -解说」会过滤掉标题含「解说」的结果</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[170px_minmax(0,1fr)_240px] gap-5">
      {/* 左侧：网盘类型筛选 */}
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <div
          className="rounded-xl p-3 flex lg:flex-col gap-1.5 overflow-x-auto"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
        >
          <h3 className="hidden lg:flex text-sm font-bold mb-1 items-center gap-1.5">
            <span className="w-1 h-4 rounded" style={{ background: "#e50914" }} />
            筛选
          </h3>
          {types.length === 0 && (
            <span className="text-xs py-1" style={{ color: "var(--text-muted)" }}>
              {loading ? "搜索中…" : "暂无来源"}
            </span>
          )}
          {types.length > 0 && (
            <button
              onClick={() => { setActiveType(ALL_TYPE); setVisibleCount(PAGE_SIZE); }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-all text-left"
              style={isAll
                ? { background: "rgba(229,9,20,0.12)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)", fontWeight: 600 }
                : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
            >
              <span>🗂️</span>
              全部
              <span className="ml-auto text-xs" style={{ color: isAll ? "#e50914" : "var(--text-muted)" }}>
                {result?.total ?? 0}
              </span>
            </button>
          )}
          {types.map((t) => {
            const meta = CLOUD_TYPE_LABELS[t.type] || { label: t.type, icon: "🔗" };
            const active = activeType === t.type;
            return (
              <button
                key={t.type}
                onClick={() => { setActiveType(t.type); setVisibleCount(PAGE_SIZE); }}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-all text-left"
                style={active
                  ? { background: "rgba(229,9,20,0.12)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)", fontWeight: 600 }
                  : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
              >
                <span>{meta.icon}</span>
                {meta.label}
                <span className="ml-auto text-xs" style={{ color: active ? "#e50914" : "var(--text-muted)" }}>
                  {t.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* 画质筛选：纯前端标题子串过滤，跟网盘类型筛选可叠加 */}
        {types.length > 0 && (
          <div
            className="rounded-xl p-3 mt-3 flex lg:flex-col gap-1.5 overflow-x-auto"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
          >
            <h3 className="hidden lg:flex text-sm font-bold mb-1 items-center gap-1.5">
              <span className="w-1 h-4 rounded" style={{ background: "#e50914" }} />
              画质
            </h3>
            <button
              onClick={() => { setActiveQuality(ALL_QUALITY); setVisibleCount(PAGE_SIZE); }}
              className="px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-all text-left"
              style={activeQuality === ALL_QUALITY
                ? { background: "rgba(229,9,20,0.12)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)", fontWeight: 600 }
                : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
            >
              不限
            </button>
            {QUALITY_TAGS.map((tag) => (
              <button
                key={tag}
                onClick={() => { setActiveQuality(tag); setVisibleCount(PAGE_SIZE); }}
                className="px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-all text-left"
                style={activeQuality === tag
                  ? { background: "rgba(229,9,20,0.12)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)", fontWeight: 600 }
                  : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </aside>

      {/* 中间：结果列表 */}
      <div
        className="rounded-xl px-4 sm:px-6 py-4 min-h-[300px]"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
      >
        {sections && sections.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pb-3 mb-3" style={{ borderBottom: "1px dashed var(--border)" }}>
            <span className="text-xs shrink-0" style={{ color: "var(--text-muted)" }}>板块:</span>
            {sections.map((s) => {
              const active = section === s.key || (!section && s.key === "video");
              return (
                <button
                  key={s.key}
                  onClick={() => onSectionChange?.(s.key)}
                  className="px-2.5 py-1 rounded-full text-xs transition-all"
                  style={active
                    ? { background: "rgba(229,9,20,0.12)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)" }
                    : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
                >
                  {s.icon} {s.name}
                </button>
              );
            })}
          </div>
        )}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-center" style={{ color: "var(--text-muted)" }}>
            <RefreshCw size={32} className="mb-4 animate-spin opacity-50" />
            <p className="text-sm">正在聚合全网资源，首次搜索约需 5-15 秒…</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="text-4xl mb-4">⚠️</div>
            <p style={{ color: "var(--text-primary)" }}>{error}</p>
          </div>
        ) : result && result.total > 0 ? (
          <>
            <div className="flex flex-col sm:flex-row items-center gap-2 py-2 mb-2">
              <p className="text-sm flex-1 text-center sm:text-left" style={{ color: "var(--text-secondary)" }}>
                为您找到【<span style={{ color: "#e50914", fontWeight: 600 }}>{q}</span>】相关资源{" "}
                <span style={{ color: "#e50914", fontWeight: 600 }}>{result.total}</span> 条
              </p>
              <div className="flex items-center gap-1.5">
                {([["default", "默认"], ["newest", "最新"]] as const).map(([v, label]) => (
                  <button
                    key={v}
                    onClick={() => { setSortBy(v); setVisibleCount(PAGE_SIZE); }}
                    className="px-2.5 py-1 rounded text-xs transition-all"
                    style={sortBy === v
                      ? { background: "rgba(229,9,20,0.12)", color: "#e50914", border: "1px solid rgba(229,9,20,0.3)" }
                      : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
                  >
                    {label}
                  </button>
                ))}
                <button
                  onClick={() => doSearch(true)}
                  className="flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-all"
                  style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
                  title="绕过缓存重新聚合"
                >
                  <RefreshCw size={11} />
                  刷新
                </button>
              </div>
            </div>
            <ul>
              {items.map((item, i) => {
                const key = `${item.url}-${i}`;
                const copied = copiedKey === key;
                return (
                  <li
                    key={key}
                    className="py-4 flex flex-col sm:flex-row sm:items-center gap-3"
                    style={{ borderBottom: "1px dashed var(--border)" }}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium leading-relaxed break-all" style={{ color: "var(--text-primary)" }}>
                        {item.title}
                      </p>
                      <p className="text-xs mt-1.5 flex items-center flex-wrap gap-x-2 gap-y-0.5" style={{ color: "var(--text-muted)" }}>
                        <span className="flex items-center gap-1">
                          <Globe size={11} />
                          来源: {(CLOUD_TYPE_LABELS[item._cloudType] || { label: item._cloudType }).label}
                          {!!item.source_hits && (
                            <span
                              className="opacity-60"
                              title="该来源(TG频道/插件)历史累计命中次数，供参考不代表内容质量"
                            >
                              · 历史命中{item.source_hits}次
                            </span>
                          )}
                        </span>
                        {item.password && <span>提取码: {item.password}</span>}
                        {formatDate(item.datetime) && <span>分享于 {formatDate(item.datetime)}</span>}
                        {checkedLinks[item.url] === false && (
                          <span
                            className="flex items-center gap-1"
                            style={{ color: "#fbbf24" }}
                            title="调用网盘官方分享查询接口检测，覆盖百度/阿里/夸克/天翼/UC/移动云盘/115/迅雷/123"
                          >
                            <AlertTriangle size={11} />
                            链接可能已失效
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                      <button
                        onClick={() => handleCopy(item, key)}
                        title="复制链接和提取码"
                        className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm transition-all"
                        style={copied
                          ? { background: "rgba(34,197,94,0.12)", color: "#22c55e", border: "1px solid rgba(34,197,94,0.3)" }
                          : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
                      >
                        {copied ? <Check size={13} /> : <Copy size={13} />}
                        {copied ? "已复制" : "复制"}
                      </button>
                      <button
                        onClick={() => setModalItem({ item, type: item._cloudType })}
                        className="px-5 py-2 rounded-lg text-sm font-medium transition-all"
                        style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)", color: "#fff" }}
                      >
                        获取资源
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
            {remaining > 0 && (
              <div className="flex justify-center py-4">
                <button
                  onClick={() => setVisibleCount((v) => v + PAGE_SIZE)}
                  className="px-6 py-2 rounded-lg text-sm transition-all"
                  style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
                >
                  加载更多（剩 {remaining} 条）
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-20 text-center" style={{ color: "var(--text-muted)" }}>
            <Search size={40} className="mb-4 opacity-30" />
            <p>全网未找到相关资源，换个关键词试试</p>
            {hotWords.length > 0 && (
              <div className="flex flex-wrap items-center justify-center gap-2 mt-5 max-w-md">
                <span className="text-xs">热门:</span>
                {hotWords.slice(0, 8).map((w) => (
                  <button
                    key={w.keyword}
                    onClick={() => onPickHotWord?.(w.keyword)}
                    className="px-3 py-1 rounded-full text-xs transition-all"
                    style={{ background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
                  >
                    {w.keyword}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 右侧：分类热榜（移动端移到结果下方） */}
      <aside className="hidden lg:block lg:sticky lg:top-20 lg:self-start">
        <HotRankings />
      </aside>
      <div className="block lg:hidden">
        <HotRankings />
      </div>

      {modalItem && (
        <PanLinkModal
          item={modalItem.item}
          cloudType={modalItem.type}
          onClose={() => setModalItem(null)}
        />
      )}
    </div>
  );
}
