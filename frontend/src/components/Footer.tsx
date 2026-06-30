import Link from "next/link";

export default function Footer() {
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
          影视搜索
        </p>
        <p className="mb-4">聚合多源影视资源，仅供学习交流使用</p>
        <div className="flex items-center justify-center gap-6 text-xs">
          {[
            { label: "电影", value: "movie" },
            { label: "电视剧", value: "tv" },
            { label: "动漫", value: "anime" },
            { label: "综艺", value: "variety" },
          ].map((cat) => (
            <Link
              key={cat.value}
              href={`/search?category=${cat.value}`}
              className="transition-colors hover:text-white"
              style={{ color: "#404050" }}
            >
              {cat.label}
            </Link>
          ))}
        </div>
        <p className="mt-6 text-xs" style={{ color: "#303040" }}>
          © {new Date().getFullYear()} 影视搜索 · 资源均来自互联网
        </p>
      </div>
    </footer>
  );
}
