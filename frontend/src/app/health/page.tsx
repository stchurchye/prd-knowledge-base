"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

function formatTime(ts?: string) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function HealthPage() {
  const [overview, setOverview] = useState<any>(null);
  const [topHits, setTopHits] = useState<any[]>([]);
  const [coldRules, setColdRules] = useState<any[]>([]);
  const [activity, setActivity] = useState<any[]>([]);
  const [challengeStats, setChallengeStats] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const handleErr = (e: Error) => setError(e.message);
    api.healthOverview().then(setOverview).catch(handleErr);
    api.topHits().then(setTopHits).catch(handleErr);
    api.coldRules().then(setColdRules).catch(handleErr);
    api.recentActivity().then(setActivity).catch(handleErr);
    api.challengeStats().then(setChallengeStats).catch(handleErr);
  }, []);

  const labelMap: Record<string, string> = {
    total_rules: "总规则", active_rules: "活跃", challenged_rules: "被质疑",
    deprecated_rules: "已废弃", open_challenges: "待处理质疑", total_hits: "总调用", cold_rules: "冷数据",
    total: "总计", open: "待处理", resolved: "已解决", rejected: "已驳回",
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-[22px] font-semibold tracking-tight">数据使用情况</h2>
        <p className="text-[13px] mt-0.5" style={{ color: "var(--muted)" }}>知识库数据调用与使用统计</p>
      </div>

      {error && <div className="mb-4 px-4 py-3 rounded-xl text-[13px] bg-[#ff3b3010] text-[#d70015]">{error}</div>}

      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {Object.entries(overview).map(([k, v]) => (
            <div key={k} className="apple-card p-4">
              <p className="text-[24px] font-semibold">{v as number}</p>
              <p className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>{labelMap[k] || k}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="apple-card p-5">
          <h3 className="text-[15px] font-semibold mb-3 flex items-center gap-2">
            <svg className="w-4 h-4 text-[#0071e3]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" /></svg>
            热门规则 Top 10</h3>
          {topHits.length > 0 ? (
            <div className="space-y-0">
              {topHits.map((r, i) => (
                <div key={r.id} className="flex justify-between items-center py-2 text-[13px]" style={{ borderBottom: i < topHits.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <span className="truncate max-w-[75%]">{r.rule_text}</span>
                  <span className="font-mono font-medium" style={{ color: "var(--accent)" }}>{r.hit_count}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-[13px]" style={{ color: "var(--muted)" }}>暂无数据</p>}
        </div>

        <div className="apple-card p-5">
          <h3 className="text-[15px] font-semibold mb-3 flex items-center gap-2">
            <svg className="w-4 h-4" style={{ color: "var(--muted)" }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008Zm0 2.25h.008v.008H8.25V13.5Zm0 2.25h.008v.008H8.25v-.008Zm0 2.25h.008v.008H8.25V18Zm2.498-6.75h.007v.008h-.007v-.008Zm0 2.25h.007v.008h-.007V13.5Zm0 2.25h.007v.008h-.007v-.008Zm0 2.25h.007v.008h-.007V18Zm2.504-6.75h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V13.5ZM8.25 6h7.5v2.25h-7.5V6ZM12 2.25c-1.892 0-3.758.11-5.593.322C5.307 2.7 4.5 3.65 4.5 4.757V19.5a2.25 2.25 0 0 0 2.25 2.25h10.5a2.25 2.25 0 0 0 2.25-2.25V4.757c0-1.108-.806-2.057-1.907-2.185A48.507 48.507 0 0 0 12 2.25Z" /></svg>
            冷数据预警</h3>
          {coldRules.length > 0 ? (
            <div className="space-y-0">
              {coldRules.map((r, i) => (
                <div key={r.id} className="flex justify-between items-center py-2 text-[13px]" style={{ borderBottom: i < coldRules.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <span className="truncate max-w-[75%]">{r.rule_text}</span>
                  <span className="text-[12px]" style={{ color: "var(--muted)" }}>{r.domain || "-"}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-[13px]" style={{ color: "var(--muted)" }}>暂无冷数据</p>}
        </div>

        <div className="apple-card p-5">
          <h3 className="text-[15px] font-semibold mb-3 flex items-center gap-2">
            <svg className="w-4 h-4 text-[#af52de]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" /></svg>
            质疑统计</h3>
          {challengeStats ? (
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(challengeStats).map(([k, v]) => (
                <div key={k} className="py-2">
                  <p className="text-[20px] font-semibold">{v as number}</p>
                  <p className="text-[11px]" style={{ color: "var(--muted)" }}>{labelMap[k] || k}</p>
                </div>
              ))}
            </div>
          ) : <p className="text-[13px]" style={{ color: "var(--muted)" }}>加载中...</p>}
        </div>

        <div className="apple-card p-5">
          <h3 className="text-[15px] font-semibold mb-3 flex items-center gap-2">
            <svg className="w-4 h-4" style={{ color: "var(--muted)" }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>
            最近操作</h3>
          {activity.length > 0 ? (
            <div className="space-y-0">
              {activity.slice(0, 10).map((a, i) => (
                <div key={a.id} className="flex justify-between items-center py-2 text-[13px]" style={{ borderBottom: i < Math.min(activity.length, 10) - 1 ? "1px solid var(--border)" : "none" }}>
                  <span><span style={{ color: "var(--muted)" }}>{a.actor || "系统"}</span> {a.action} 规则#{a.rule_id}</span>
                  <span className="text-[11px]" style={{ color: "var(--muted)" }}>{formatTime(a.created_at)}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-[13px]" style={{ color: "var(--muted)" }}>暂无操作记录</p>}
        </div>
      </div>
    </div>
  );
}
