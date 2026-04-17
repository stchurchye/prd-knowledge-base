import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "知识库",
  description: "材料分析与业务规则管理平台",
};

const nav = [
  { href: "/upload", label: "材料库", icon: "doc.badge.plus" },
  { href: "/rules", label: "规则库", icon: "list.bullet.rectangle" },
  { href: "/wiki", label: "Wiki", icon: "book" },
  { href: "/review", label: "规则审核", icon: "checkmark.shield" },
  { href: "/risks", label: "矛盾检测", icon: "exclamationmark.shield" },
  { href: "/health", label: "数据概览", icon: "heart.text.square" },
];

const NavIcon = ({ name }: { name: string }) => {
  const icons: Record<string, string> = {
    "doc.badge.plus": "M9 12h6m-3-3v6m-4 4h8a2 2 0 002-2V7a2 2 0 00-2-2h-3l-1-2H9L8 5H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    "list.bullet.rectangle": "M4 6h16M4 10h16M4 14h10M4 18h7",
    "exclamationmark.shield": "M12 9v2m0 4h.01M5.07 19H19a2 2 0 001.75-2.96l-6.93-12a2 2 0 00-3.5 0l-6.93 12A2 2 0 005.07 19z",
    "heart.text.square": "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    "book": "M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25",
    "checkmark.shield": "M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z",
  };
  return (
    <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d={icons[name] || ""} />
    </svg>
  );
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="h-full flex text-[var(--foreground)]" style={{ background: "var(--background)" }}>
        <aside className="w-[220px] sidebar-glass flex flex-col shrink-0 h-full">
          <div className="px-5 pt-6 pb-4">
            <h1 className="text-[15px] font-semibold tracking-tight">知识库</h1>
            <p className="text-[11px] mt-0.5" style={{ color: "var(--muted)" }}>材料分析与规则管理</p>
          </div>
          <nav className="flex-1 px-3 space-y-0.5">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-2.5 px-3 py-[7px] rounded-lg text-[13px] font-medium transition-all duration-150 hover:bg-black/[0.04] active:bg-black/[0.06]"
                style={{ color: "var(--foreground)" }}
              >
                <NavIcon name={item.icon} />
                <span>{item.label}</span>
              </Link>
            ))}
          </nav>
          <div className="px-5 py-4 text-[11px]" style={{ color: "var(--muted)" }}>
            v1.0
          </div>
        </aside>
        <main className="flex-1 overflow-auto px-8 py-6">{children}</main>
      </body>
    </html>
  );
}
