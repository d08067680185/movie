"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getSections } from "@/lib/api";
import { SECTIONS_FALLBACK } from "@/lib/utils";

export default function Footer() {
  const [sections, setSections] = useState(SECTIONS_FALLBACK);

  useEffect(() => {
    getSections().then((data) => {
      if (data.length > 0) {
        setSections(data.map((s) => ({ key: s.key, name: s.name, icon: s.icon || "" })));
      }
    });
  }, []);

  return (
    <footer
      className="mt-16 py-10 text-center text-sm"
      style={{
        borderTop: "1px solid rgba(255,255,255,0.07)",
        color: "#404050",
      }}
    >
      <div className="max-w-7xl mx-auto px-4">
        <p className="mb-2 text-base font-semibold" style={{ color: "#606070" }}>
          资源共享平台
        </p>
        <p className="mb-4">聚合影视、软件、电子书、音乐、游戏等多类资源，仅供学习交流使用</p>
        <div className="flex items-center justify-center gap-6 text-xs">
          {sections.map((s) => (
            <Link
              key={s.key}
              href={`/s/${s.key}`}
              className="transition-colors hover:text-white"
              style={{ color: "#404050" }}
            >
              {s.name}
            </Link>
          ))}
        </div>
        <p className="mt-6 text-xs" style={{ color: "#303040" }}>
          © {new Date().getFullYear()} 资源共享平台 · 资源均来自互联网
        </p>
      </div>
    </footer>
  );
}
