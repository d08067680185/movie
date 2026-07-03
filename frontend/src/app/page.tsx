import { Suspense } from "react";
import HomeContent from "./HomeContent";

// Cache buster: 2026-07-03T11:40:00Z
export default function HomePage() {
  return (
    <Suspense>
      <HomeContent />
    </Suspense>
  );
}
