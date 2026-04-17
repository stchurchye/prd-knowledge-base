"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

function formatTime(ts?: string) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const statusLabel: Record<string, string> = {
  draft: "草稿", active: "生效中", challenged: "待确认", deprecated: "已废弃",
};

export default function RulesPage() {
  const [rules, setRules] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ domain: "", category: "", status: "", q: "" });

  const load = async (p = page) => {
    const params: Record<string, string> = { page: String(p), page_size: "20" };
    Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
    const [res, s] = await Promise.all([api.listRules(params), api.ruleStats()]);
    setRules(res.items);
    setTotal(res.total);
    setTotalPages(res.total_pages);
    setPage(res.page);
    setStats(s);
  };

  useEffect(() => { load(1); }, []);

  const search = () => { setPage(1); load(1); };
  const goPage = (p: number) => { if (p >= 1 && p <= totalPages) load(p); };

  const statusColor = (s: string) => {
    if (s === "active") return "bg-[#34c75920] text-[#248a3d]";
    if (s === "challenged") return "bg-[#ff3b3020] text-[#d70015]";
    if (s === "deprecated") return "bg-[#86868b20] text-[#86868b]";
    return "bg-[#0071e310] text-[#0071e3]";
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-[22px] font-semibold tracking-tight">规则库</h2>
          <p className="text-[13px] mt-0.5" style={{ color: "var(--muted)" }}>共 {total} 条规则</p>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
          <div className="apple-card p-4">
            <p className="text-[24px] font-semibold">{stats.total}</p>
            <p className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>总规则</p>
          </div>
          {Object.entries(stats.by_status || {}).map(([k, v]) => (
            <div key={k} className="apple-card p-4">
              <p className="text-[24px] font-semibold">{v as number}</p>
              <p className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>{statusLabel[k] || k}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2 mb-5 flex-wrap items-center">
        <div className="flex-1 min-w-[200px] relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: "var(--muted)" }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" /></svg>
          <input placeholder="搜索规则内容..." value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} onKeyDown={(e) => e.key === "Enter" && search()} className="apple-input w-full pl-9" />
        </div>
        <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="apple-input">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="active">生效中</option>
          <option value="challenged">待确认</option>
          <option value="deprecated">已废弃</option>
        </select>
        <button onClick={search} className="apple-btn apple-btn-primary">筛选</button>
      </div>

      <div className="apple-card overflow-hidden">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] font-medium uppercase tracking-wider" style={{ color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
              <th className="py-3 px-4">ID</th>
              <th className="py-3 px-4">规则内容</th>
              <th className="py-3 px-4">来源文档</th>
              <th className="py-3 px-4">功能模块</th>
              <th className="py-3 px-4">分类</th>
              <th className="py-3 px-4">状态</th>
              <th className="py-3 px-4">提取时间</th>
              <th className="py-3 px-4 text-right">调用</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id} className="transition-colors hover:bg-black/[0.02]" style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="py-3 px-4 font-mono text-[12px]" style={{ color: "var(--muted)" }}>{r.id}</td>
                <td className="py-3 px-4 max-w-md">
                  <Link href={`/rules/${r.id}`} className="hover:underline decoration-[var(--accent)] underline-offset-2" style={{ color: "var(--accent)" }}>
                    {r.rule_text?.slice(0, 80)}{(r.rule_text?.length || 0) > 80 ? "..." : ""}
                  </Link>
                </td>
                <td className="py-3 px-4 text-[12px] max-w-[160px]">
                  {(r.source_docs && r.source_docs.length > 0) ? (
                    <div className="space-y-0.5">
                      {r.source_docs.map((doc: string, i: number) => (
                        <div key={i} className="truncate" style={{ color: "var(--muted)" }} title={doc}>{doc}</div>
                      ))}
                    </div>
                  ) : <span style={{ color: "var(--muted)" }}>-</span>}
                </td>
                <td className="py-3 px-4" style={{ color: "var(--muted)" }}>{r.domain || "-"}</td>
                <td className="py-3 px-4" style={{ color: "var(--muted)" }}>{r.category || "-"}</td>
                <td className="py-3 px-4"><span className={`apple-badge ${statusColor(r.status)}`}>{statusLabel[r.status] || r.status}</span></td>
                <td className="py-3 px-4 text-[12px]" style={{ color: "var(--muted)" }}>{formatTime(r.created_at)}</td>
                <td className="py-3 px-4 text-right font-mono text-[12px]" style={{ color: "var(--muted)" }}>{r.hit_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rules.length === 0 && <p className="text-center py-10 text-[13px]" style={{ color: "var(--muted)" }}>暂无规则</p>}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-[12px]" style={{ color: "var(--muted)" }}>第 {page}/{totalPages} 页，共 {total} 条</p>
          <div className="flex gap-1">
            <button onClick={() => goPage(page - 1)} disabled={page <= 1} className="apple-btn apple-btn-secondary disabled:opacity-30 gap-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" /></svg>上一页
            </button>
            <button onClick={() => goPage(page + 1)} disabled={page >= totalPages} className="apple-btn apple-btn-secondary disabled:opacity-30 gap-1">
              下一页<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" /></svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}