"use client";
import { useState, useEffect } from "react";
import { Heart, Trash2 } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import ResourceCardComponent from "@/components/ResourceCard";
import Footer from "@/components/Footer";
import { getFavorites, removeFavorite, FavoriteItem } from "@/lib/favorites";

export default function FavoritesContent() {
  const [favorites, setFavorites] = useState<FavoriteItem[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
    setFavorites(getFavorites());
  }, []);

  function clearAll() {
    if (!confirm("确认清空所有收藏？")) return;
    for (const f of favorites) removeFavorite(f.id);
    setFavorites([]);
  }

  function removeOne(id: number) {
    removeFavorite(id);
    setFavorites((prev) => prev.filter((f) => f.id !== id));
  }

  if (!mounted) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Heart size={20} fill="#e50914" style={{ color: "#e50914" }} />
            <h1 className="text-xl font-bold">我的收藏</h1>
            {favorites.length > 0 && (
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: "rgba(229,9,20,0.15)", color: "#ff6070" }}
              >
                {favorites.length}
              </span>
            )}
          </div>
          {favorites.length > 0 && (
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
              清空收藏
            </button>
          )}
        </div>

        {favorites.length === 0 ? (
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
        )}
      </div>
      <Footer />
    </div>
  );
}
