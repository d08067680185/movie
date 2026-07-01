import { Suspense } from "react";
import FavoritesContent from "./FavoritesContent";

export const metadata = { title: "我的收藏 - 影视搜索" };

export default function FavoritesPage() {
  return (
    <Suspense>
      <FavoritesContent />
    </Suspense>
  );
}
