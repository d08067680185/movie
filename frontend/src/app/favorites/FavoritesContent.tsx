"use client";
import { useState, useEffect } from "react";
import { Heart, Trash2, Globe } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import ResourceCardComponent from "@/components/ResourceCard";
import Footer from "@/components/Footer";
import PanLinkModal from "@/components/PanLinkModal";
import { getFavorites, removeFavorite, FavoriteItem } from "@/lib/favorites";
import { getPanFavorites, removePanFavorite, PanFavoriteItem } from "@/lib/panFavorites";
import { CLOUD_TYPE_LABELS } from "@/lib/utils";

export default function FavoritesContent() {
  const [favorites, setFavorites] = useState<FavoriteItem[]>([]);
  const [panFavorites, setPanFavorites] = useState<PanFavoriteItem[]>([]);
  const [tab, setTab] = useState<"resource" | "pan">("resource");
  const [modalItem, setModalItem] = useState<PanFavoriteItem | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
    setFavorites(getFavorites());
    setPanFavorites(getPanFavorites());
  }, []);

  // 弹窗内取消收藏后同步列表
  useEffect(() => {
    function onChanged() {
      setPanFavorites(getPanFavorites());
      setFavorites(getFavorites());
    }
    window.addEventListener("favoritesChanged", onChanged);
    return () => window.removeEventListener("favoritesChanged", onChanged);
  }, []);

  function clearAll() {
    if (tab === "resource") {
      if (!confirm("确认清空所有影视收藏？")) return;
      for (const f of favorites) removeFavorite(f.id);
      setFavorites([]);
    } else {
      if (!confirm("确认清空所有网盘链接收藏？")) return;
      for (const f of panFavorites) removePanFavorite(f.url);
      setPanFavorites([]);
    }
    window.dispatchEvent(new Event("favoritesChanged"));
  }

  function removeOne(id: number) {
    removeFavorite(id);
    setFavorites((prev) => prev.filter((f) => f.id !== id));
    window.dispatchEvent(new Event("favoritesChanged"));
  }

  function removeOnePan(url: string) {
    removePanFavorite(url);
    setPanFavorites((prev) => prev.filter((f) => f.url !== url));
    window.dispatchEvent(new Event("favoritesChanged"));
  }

  if (!mounted) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
      </div>
    );
  }

  const activeCount = tab === "resource" ? favorites.length : panFavorites.length;

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Heart size={20} fill="#e50914" style={{ color: "#e50914" }} />
            <h1 className="text-xl font-bold">我的收藏</h1>
          </div>
          {activeCount > 0 && (
            <button
              onClick={clearAll}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all"
              style={{
                background: "rgba(239,68,68,0.1)",
                border: "1px solid rgba(239,68,68,0.25)",
                color: "#f87171",
              }}
            >
              <Trash2 size={12} />
              清空{tab === "resource" ? "影视收藏" : "链接收藏"}
            </button>
          )}
        </div>

        {/* 影视资源 / 网盘链接 tabs */}
        <div className="flex items-center gap-2 mb-6">
          {([
            ["resource", `影视资源 (${favorites.length})`],
            ["pan", `网盘链接 (${panFavorites.length})`],
          ] as const).map(([v, label]) => (
            <button
              key={v}
              onClick={() => setTab(v)}
              className="px-4 py-1.5 rounded-full text-sm font-medium transition-all"
              style={tab === v
                ? { background: "#e50914", color: "#fff" }
                : { background: "var(--bg-input)", border: "1px solid var(--border-input)", color: "var(--text-secondary)" }}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "resource" ? (
          favorites.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center py-32 text-center"
              style={{ color: "var(--text-muted)" }}
            >
              <Heart size={48} className="mb-4 opacity-20" />
              <p className="text-lg mb-2">还没有收藏任何影视资源</p>
              <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
                在搜索结果或详情页点击心形图标来收藏
              </p>
              <Link
                href="/search"
                className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white"
                style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)" }}
              >
                去搜索
              </Link>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {favorites.map((fav) => (
                  <div key={fav.id} className="relative group/fav">
                    <ResourceCardComponent resource={fav} />
                    {/* 删除按钮 */}
                    <button
                      onClick={() => removeOne(fav.id)}
                      className="absolute top-1 right-1 p-1 rounded-full opacity-0 group-hover/fav:opacity-100 transition-all z-10"
                      style={{ background: "rgba(0,0,0,0.7)", color: "#f87171" }}
                      title="移出收藏"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                ))}
              </div>
              <p className="text-center text-xs mt-8" style={{ color: "var(--text-muted)" }}>
                收藏数据保存在本地，清除浏览器数据后将丢失
              </p>
            </>
          )
        ) : panFavorites.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-32 text-center"
            style={{ color: "var(--text-muted)" }}
          >
            <Globe size={48} className="mb-4 opacity-20" />
            <p className="text-lg mb-2">还没有收藏任何网盘链接</p>
            <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
              在全网搜的「获取资源」弹窗里点击收藏
            </p>
            <Link
              href="/pan"
              className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white"
              style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)" }}
            >
              去全网搜
            </Link>
          </div>
        ) : (
          <>
            <div
              className="rounded-xl px-4 sm:px-6 py-2"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
            >
              <ul>
                {panFavorites.map((fav) => {
                  const meta = CLOUD_TYPE_LABELS[fav.cloudType] || { label: fav.cloudType, icon: "🔗" };
                  return (
                    <li
                      key={fav.url}
                      className="py-4 flex flex-col sm:flex-row sm:items-center gap-3"
                      style={{ borderBottom: "1px dashed var(--border)" }}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium leading-relaxed break-all" style={{ color: "var(--text-primary)" }}>
                          {fav.title}
                        </p>
                        <p className="text-xs mt-1.5 flex items-center flex-wrap gap-x-2" style={{ color: "var(--text-muted)" }}>
                          <span>{meta.icon} {meta.label}</span>
                          {fav.password && <span>提取码: {fav.password}</span>}
                          <span>收藏于 {new Date(fav.saved_at).toLocaleDateString("zh-CN")}</span>
                        </p>
                      </div>
                      <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                        <button
                          onClick={() => setModalItem(fav)}
                          className="px-4 py-2 rounded-lg text-sm font-medium transition-all"
                          style={{ background: "linear-gradient(135deg, #e50914 0%, #c40812 100%)", color: "#fff" }}
                        >
                          获取资源
                        </button>
                        <button
                          onClick={() => removeOnePan(fav.url)}
                          className="p-2 rounded-lg transition-all"
                          style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.25)", color: "#f87171" }}
                          title="移出收藏"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
            <p className="text-center text-xs mt-8" style={{ color: "var(--text-muted)" }}>
              网盘分享链接可能失效，建议及时转存到自己的网盘
            </p>
          </>
        )}
      </div>

      {modalItem && (
        <PanLinkModal
          item={modalItem}
          cloudType={modalItem.cloudType}
          onClose={() => setModalItem(null)}
        />
      )}
      <Footer />
    </div>
  );
}
