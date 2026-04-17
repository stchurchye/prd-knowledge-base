"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

const METHOD_INFO: Record<string, { label: string; desc: string; color: string; bg: string }> = {
  keyword: { label: "关键词匹配", desc: "反义词对 + 参数比对，速度快", color: "#0071e3", bg: "rgba(0,113,227,0.1)" },
  embedding: { label: "向量语义", desc: "Embedding 相似度分析，需先生成向量", color: "#8944ab", bg: "rgba(175,82,222,0.1)" },
  llm: { label: "LLM 深度分析", desc: "Claude 逐对语义分析，最准确，消耗 API 额度", color: "#c93400", bg: "rgba(255,159,10,0.1)" },
};

function formatTime(ts?: string) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function RisksPage() {
  const [risks, setRisks] = useState<any>(null);
  const [records, setRecords] = useState<any[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detectingMethod, setDetectingMethod] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" | "info" }>({ text: "", type: "info" });

  const loadRecords = useCallback(async () => {
    try { setRecords(await api.conflictRecords()); } catch {}
  }, []);

  useEffect(() => {
    api.riskOverview().then(setRisks).catch((e: Error) => setError(e.message));
    loadRecords();
  }, [loadRecords]);

  const handleDetect = async (method: string) => {
    if (method === "llm") {
      const ok = confirm("LLM 检测将调用 Claude API，会消耗 API 额度。确认执行？");
      if (!ok) return;
    }
    setDetectingMethod(method);
    setMsg({ text: "", type: "info" });
    const startTime = Date.now();
    try {
      const res = await api.detectConflicts(undefined, method);
      const info = METHOD_INFO[method];
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      setMsg({
        text: res.message
          ? `${res.message}（耗时 ${elapsed}s）`
          : `[${info.label}] 检测完成，共比较 ${res.total_compared} 条规则，发现 ${res.conflicts?.length || 0} 个冲突（耗时 ${elapsed}s）`,
        type: res.conflicts?.length ? "error" : "success",
      });
      await loadRecords();
    } catch (e: any) {
      setMsg({ text: e.message, type: "error" });
    } finally {
      setDetectingMethod(null);
    }
  };
  const methodBadge = (method: string) => {
    const info = METHOD_INFO[method] || METHOD_INFO.keyword;
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
        style={{ background: info.bg, color: info.color }}>{info.label}</span>
    );
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-[22px] font-semibold tracking-tight">逻辑规则冲突处理</h2>
        <p className="text-[13px] mt-0.5" style={{ color: "var(--muted)" }}>规则冲突检测与处理</p>
      </div>

      {/* 三种检测方法按钮 */}
      <div className="apple-card p-5 mb-6">
        <h3 className="text-[13px] font-semibold mb-3">选择检测方法</h3>
        <div className="flex gap-3 flex-wrap">
          {(["keyword", "embedding", "llm"] as const).map((m) => {
            const info = METHOD_INFO[m];
            const isRunning = detectingMethod === m;
            const isDisabled = detectingMethod !== null;
            return (
              <button key={m} onClick={() => handleDetect(m)} disabled={isDisabled}
                className={`flex-1 min-w-[180px] p-4 rounded-2xl text-left transition-all ${isDisabled && !isRunning ? "opacity-40" : ""} ${isRunning ? "ring-2" : "hover:scale-[1.01]"}`}
                style={{ background: info.bg, borderColor: info.color }}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[14px] font-semibold" style={{ color: info.color }}>{info.label}</span>
                  {isRunning && <span className="text-[11px] animate-pulse" style={{ color: info.color }}>检测中...</span>}
                </div>
                <p className="text-[12px]" style={{ color: "var(--muted)" }}>{info.desc}</p>
              </button>
            );
          })}
        </div>
      </div>

      {msg.text && (
        <div className={`mb-4 px-4 py-3 rounded-xl text-[13px] font-medium ${
          msg.type === "success" ? "bg-[#34c75910] text-[#248a3d]" :
          msg.type === "error" ? "bg-[#ff3b3010] text-[#d70015]" :
          "bg-[#0071e310] text-[#0071e3]"
        }`}>{msg.text}</div>
      )}
      {error && <div className="mb-4 px-4 py-3 rounded-xl text-[13px] bg-[#ff3b3010] text-[#d70015]">{error}</div>}

      {/* 统计卡片 */}
      {risks && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {(() => {
            const labels: Record<string, string> = { total_rules: "总规则数", high_risk_count: "高风险", avg_risk_score: "平均风险分" };
            return Object.entries(risks.summary || risks).map(([k, v]) => (
              <div key={k} className="apple-card p-4">
                <p className="text-[24px] font-semibold">{typeof v === "number" ? (Number.isInteger(v) ? v : (v as number).toFixed(1)) : JSON.stringify(v)}</p>
                <p className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>{labels[k] || k.replace(/_/g, " ")}</p>
              </div>
            ));
          })()}
        </div>
      )}

      {/* 检测记录列表 */}
      <div className="apple-card overflow-hidden mb-6" style={{ borderRadius: 16 }}>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] font-medium uppercase tracking-wider" style={{ color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
              <th className="py-3 px-4">检测时间</th>
              <th className="py-3 px-4">检测方法</th>
              <th className="py-3 px-4">比较规则数</th>
              <th className="py-3 px-4">冲突数</th>
              <th className="py-3 px-4">耗时</th>
              <th className="py-3 px-4 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.id} className="transition-colors hover:bg-black/[0.02]" style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="py-3 px-4 text-[12px]" style={{ color: "var(--muted)" }}>{formatTime(r.created_at)}</td>
                <td className="py-3 px-4">{methodBadge(r.method)}</td>
                <td className="py-3 px-4 font-mono text-[12px]">{r.total_compared}</td>
                <td className="py-3 px-4">
                  <span className={`font-mono text-[12px] ${r.conflicts_count > 0 ? "text-[#d70015] font-medium" : ""}`}>{r.conflicts_count}</span>
                </td>
                <td className="py-3 px-4 font-mono text-[12px]" style={{ color: "var(--muted)" }}>{r.elapsed_seconds}s</td>
                <td className="py-3 px-4 text-right">
                  {r.conflicts_count > 0 && (
                    <button onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                      className="apple-btn apple-btn-secondary text-[12px]">
                      {expandedId === r.id ? "收起" : "查看冲突"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {records.length === 0 && <p className="text-center py-10 text-[13px]" style={{ color: "var(--muted)" }}>暂无检测记录，请点击上方按钮执行检测</p>}
      </div>

      {/* 展开的冲突详情 */}
      {expandedId && (() => {
        const rec = records.find((r) => r.id === expandedId);
        if (!rec || !rec.conflicts?.length) return null;
        return (
          <div className="apple-card p-5 mb-6">
            <h3 className="text-[15px] font-semibold mb-3 flex items-center gap-2" style={{ color: "#c93400" }}>
              冲突详情（{rec.conflicts.length} 个）
              {methodBadge(rec.method)}
              <span className="text-[11px] font-normal" style={{ color: "var(--muted)" }}>{formatTime(rec.created_at)} · 耗时 {rec.elapsed_seconds}s</span>
            </h3>
            <div className="space-y-2">
              {rec.conflicts.map((c: any, i: number) => (
                <div key={i} className="text-[13px] py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                  <div className="flex items-center gap-2 mb-1">
                    {methodBadge(c.method || rec.method)}
                    <span className="font-medium">{c.type}</span>
                    {c.severity && (
                      <span className={`text-[11px] px-1.5 py-0.5 rounded ${
                        c.severity === "high" ? "bg-[#ff3b3015] text-[#d70015]" :
                        c.severity === "medium" ? "bg-[#ff9f0a15] text-[#c93400]" :
                        "bg-[#86868b15] text-[#86868b]"
                      }`}>{c.severity === "high" ? "高" : c.severity === "medium" ? "中" : "低"}</span>
                    )}
                  </div>
                  <p className="whitespace-pre-line">{c.description}</p>
                  <p className="mt-1" style={{ color: "var(--muted)" }}>规则 #{c.rule_ids?.join(", #")}</p>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {!risks && <p className="text-center py-10 text-[13px]" style={{ color: "var(--muted)" }}>加载中...</p>}
    </div>
  );
}
