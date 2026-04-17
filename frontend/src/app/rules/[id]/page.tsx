"use client";

import { useState, useEffect, use } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

function formatTime(ts?: string) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
}

export default function RuleDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const ruleId = Number(id);
  const [rule, setRule] = useState<any>(null);
  const [challenges, setChallenges] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [challengeForm, setChallengeForm] = useState({ challenger: "", content: "" });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const handleErr = (e: Error) => setError(e.message);
    api.getRule(ruleId).then(setRule).catch(handleErr);
    api.listChallenges(ruleId).then(setChallenges).catch(handleErr);
    api.ruleLogs(ruleId).then(setLogs).catch(handleErr);
  }, [ruleId]);

  const submitChallenge = async () => {
    if (!challengeForm.content) return;
    try {
      await api.createChallenge(ruleId, challengeForm);
      setMsg("质疑已提交");
      setChallengeForm({ challenger: "", content: "" });
      const [r, c] = await Promise.all([api.getRule(ruleId), api.listChallenges(ruleId)]);
      setRule(r);
      setChallenges(c);
    } catch (e: any) { setMsg(e.message); }
  };

  const statusLabel: Record<string, string> = {
    draft: "草稿", active: "生效中", challenged: "待确认", deprecated: "已废弃",
  };

  const statusColor = (s: string) => {
    if (s === "active") return "bg-[#34c75920] text-[#248a3d]";
    if (s === "challenged") return "bg-[#ff3b3020] text-[#d70015]";
    return "bg-[#0071e310] text-[#0071e3]";
  };

  if (!rule) return (
    <div className="py-10">
      {error ? <p className="text-[#d70015]">{error}</p> : <p style={{ color: "var(--muted)" }}>加载中...</p>}
    </div>
  );

  return (
    <div className="max-w-3xl">
      <Link href="/rules" className="inline-flex items-center gap-1 text-[13px] mb-4 hover:underline underline-offset-2" style={{ color: "var(--accent)" }}>
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" /></svg>
        返回规则库
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <h2 className="text-[22px] font-semibold tracking-tight">规则 #{rule.id}</h2>
        <span className={`apple-badge ${statusColor(rule.status)}`}>{statusLabel[rule.status] || rule.status}</span>
      </div>

      <div className="apple-card p-5 space-y-4">
        <p className="text-[14px] leading-relaxed">{rule.rule_text}</p>

        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] pt-3" style={{ borderTop: "1px solid var(--border)" }}>
          <div><span style={{ color: "var(--muted)" }}>功能模块：</span>{rule.domain || "-"}</div>
          <div><span style={{ color: "var(--muted)" }}>分类：</span>{rule.category || "-"}</div>
          <div><span style={{ color: "var(--muted)" }}>来源章节：</span>{rule.source_section || "-"}</div>
          <div><span style={{ color: "var(--muted)" }}>风险评分：</span>{rule.risk_score}</div>
        </div>

        {rule.source_docs && rule.source_docs.length > 0 && (
          <div className="pt-3" style={{ borderTop: "1px solid var(--border)" }}>
            <p className="text-[11px] font-medium uppercase tracking-wider mb-2" style={{ color: "var(--muted)" }}>来源文档</p>
            <div className="flex flex-wrap gap-1.5">
              {rule.source_docs.map((doc: string, i: number) => (
                <span key={i} className="apple-badge bg-[#0071e310] text-[#0071e3]">{doc}</span>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] pt-3" style={{ borderTop: "1px solid var(--border)" }}>
          <div><span style={{ color: "var(--muted)" }}>调用次数：</span>{rule.hit_count}</div>
          <div><span style={{ color: "var(--muted)" }}>最后调用：</span>{formatTime(rule.last_hit_at)}</div>
          <div><span style={{ color: "var(--muted)" }}>提取时间：</span>{formatTime(rule.created_at)}</div>
          <div><span style={{ color: "var(--muted)" }}>更新时间：</span>{formatTime(rule.updated_at)}</div>
        </div>

        {rule.params && (
          <div className="pt-3" style={{ borderTop: "1px solid var(--border)" }}>
            <p className="text-[11px] font-medium uppercase tracking-wider mb-2" style={{ color: "var(--muted)" }}>关键参数</p>
            <pre className="text-[12px] p-3 rounded-lg bg-[var(--background)] font-mono overflow-auto">{JSON.stringify(rule.params, null, 2)}</pre>
          </div>
        )}
      </div>

      {msg && <div className="mt-4 px-4 py-3 rounded-xl text-[13px] bg-[#0071e310] text-[#0071e3]">{msg}</div>}

      <div className="mt-8">
        <h3 className="text-[15px] font-semibold mb-3 flex items-center gap-2">
          <svg className="w-4 h-4 text-[#c93400]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" /></svg>
          提交质疑</h3>
        <div className="apple-card p-4 space-y-3">
          <input placeholder="你的名字" value={challengeForm.challenger} onChange={(e) => setChallengeForm({ ...challengeForm, challenger: e.target.value })}
            className="apple-input w-full" />
          <textarea placeholder="质疑内容..." value={challengeForm.content} onChange={(e) => setChallengeForm({ ...challengeForm, content: e.target.value })}
            className="apple-input w-full resize-none" rows={3} />
          <button onClick={submitChallenge} className="inline-flex items-center px-4 py-2 rounded-full text-[13px] font-medium transition-colors" style={{ background: "rgba(255,159,10,0.12)", color: "#c93400" }}>提交质疑</button>
        </div>
      </div>

      {challenges.length > 0 && (
        <div className="mt-8">
          <h3 className="text-[15px] font-semibold mb-3">质疑记录</h3>
          <div className="space-y-2">
            {challenges.map((c) => (
              <div key={c.id} className="apple-card p-4 text-[13px]">
                <div className="flex justify-between items-center">
                  <span className="font-medium">{c.challenger || "匿名"}</span>
                  <span className={`apple-badge ${c.status === "open" ? "bg-[#ff9f0a20] text-[#c93400]" : "bg-[#34c75920] text-[#248a3d]"}`}>{c.status === "open" ? "待处理" : "已解决"}</span>
                </div>
                <p className="mt-2" style={{ color: "var(--foreground)" }}>{c.content}</p>
                {c.resolution && <p className="mt-1" style={{ color: "var(--muted)" }}>处理结果：{c.resolution}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {logs.length > 0 && (
        <div className="mt-8">
          <h3 className="text-[15px] font-semibold mb-3">操作日志</h3>
          <div className="apple-card overflow-hidden">
            {logs.map((l, i) => (
              <div key={l.id} className="flex justify-between items-center px-4 py-2.5 text-[13px]" style={{ borderBottom: i < logs.length - 1 ? "1px solid var(--border)" : "none" }}>
                <span><span style={{ color: "var(--muted)" }}>{l.actor || "系统"}</span> {l.action}</span>
                <span className="text-[11px]" style={{ color: "var(--muted)" }}>{formatTime(l.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
