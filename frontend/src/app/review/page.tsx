"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ReviewPage() {
  const [rules, setRules] = useState<any[]>([]);
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" | "info" }>({ text: "", type: "info" });

  const load = useCallback(async () => {
    try { setRules(await api.pendingReview()); } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleApprove = async (id: number) => {
    try {
      await api.approveRule(id);
      setMsg({ text: `规则 #${id} 已通过`, type: "success" });
      await load();
    } catch (e: any) { setMsg({ text: e.message, type: "error" }); }
  };

  const handleReject = async (id: number) => {
    if (!confirm("确认拒绝该规则？")) return;
    try {
      await api.rejectRule(id);
      setMsg({ text: `规则 #${id} 已拒绝`, type: "success" });
      await load();
    } catch (e: any) { setMsg({ text: e.message, type: "error" }); }
  };

  const handleApproveAll = async () => {
    if (!confirm(`确认批量通过 ${rules.length} 条规则？`)) return;
    for (const r of rules) { await api.approveRule(r.id); }
    setMsg({ text: `已批量通过 ${rules.length} 条规则`, type: "success" });
    await load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-[22px] font-semibold tracking-tight">规则审核</h2>
          <p className="text-[13px] mt-0.5" style={{ color: "var(--muted)" }}>
            {rules.length} 条规则待审核
          </p>
        </div>
        {rules.length > 0 && (
          <button onClick={handleApproveAll}
            className="inline-flex items-center px-5 py-2 rounded-full text-[13px] font-medium transition-colors hover:bg-[#2a9d3e]"
            style={{ background: "#34c759", color: "#fff" }}>
            全部通过
          </button>
        )}
      </div>

      {msg.text && (
        <div className={`mb-4 px-4 py-3 rounded-xl text-[13px] font-medium ${
          msg.type === "success" ? "bg-[#34c75910] text-[#248a3d]" :
          msg.type === "error" ? "bg-[#ff3b3010] text-[#d70015]" :
          "bg-[#0071e310] text-[#0071e3]"
        }`}>{msg.text}</div>
      )}
      <div className="space-y-3">
        {rules.map((r) => (
          <div key={r.id} className="apple-card p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-mono text-[12px]" style={{ color: "var(--muted)" }}>#{r.id}</span>
                  {r.category && <span className="apple-badge bg-[#0071e310] text-[#0071e3]">{r.category}</span>}
                  {r.domain && <span className="apple-badge bg-[#af52de15] text-[#8944ab]">{r.domain}</span>}
                  {r.source_section && <span className="text-[11px]" style={{ color: "var(--muted)" }}>来源: {r.source_section}</span>}
                </div>
                <p className="text-[14px] leading-relaxed mb-2">{r.rule_text}</p>
                {r.structured_logic && (
                  <pre className="text-[11px] p-2 rounded-lg bg-[var(--background)] font-mono overflow-auto mb-2">{JSON.stringify(r.structured_logic, null, 2)}</pre>
                )}
                {r.params && Object.keys(r.params).length > 0 && (
                  <div className="flex gap-2 flex-wrap">
                    {Object.entries(r.params).map(([k, v]) => (
                      <span key={k} className="text-[11px] px-2 py-0.5 rounded-full bg-[#ff9f0a15] text-[#c93400]">{k}: {String(v)}</span>
                    ))}
                  </div>
                )}
                {r.source_docs?.length > 0 && (
                  <div className="flex gap-1.5 mt-2">
                    {r.source_docs.map((doc: string, i: number) => (
                      <span key={i} className="text-[11px] px-2 py-0.5 rounded-full bg-[#86868b10]" style={{ color: "var(--muted)" }}>{doc}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                <button onClick={() => handleApprove(r.id)}
                  className="apple-btn text-[12px]" style={{ background: "rgba(52,199,89,0.12)", color: "#248a3d" }}>通过</button>
                <button onClick={() => handleReject(r.id)}
                  className="apple-btn apple-btn-danger text-[12px]">拒绝</button>
                <Link href={`/rules/${r.id}`} className="apple-btn apple-btn-secondary text-[12px]">详情</Link>
              </div>
            </div>
          </div>
        ))}
      </div>

      {rules.length === 0 && <p className="text-center py-10 text-[13px]" style={{ color: "var(--muted)" }}>所有规则已审核完毕</p>}
    </div>
  );
}
