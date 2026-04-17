"use client";

import { useState, useCallback, useEffect } from "react";
import { api } from "@/lib/api";
import { ImageUploadSection } from "./ImageUploadSection";

interface PRDItem {
  id: number;
  title: string;
  filename: string;
  status: string;
  domain?: string;
  version?: string;
  author?: string;
  sections_count?: number;
  rules_count?: number;
  process_elapsed?: number;
  total_tokens?: number;
  vision_provider?: string;
  llm_model?: string;
  error_message?: string;
}

export default function UploadPage() {
  const [prds, setPrds] = useState<PRDItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [docType, setDocType] = useState<"prd" | "tech">("prd");
  const [visionProvider, setVisionProvider] = useState<"off" | "claude" | "qwen">("off");
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" | "info" }>({ text: "", type: "info" });
  const [urlInput, setUrlInput] = useState("");
  const [importing, setImporting] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailData, setDetailData] = useState<any>(null);

  const refresh = useCallback(async () => {
    const data = await api.listPrds(docType);
    setPrds(data);
  }, [docType]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleUpload = async (files: FileList | null) => {
    if (!files) return;
    setLoading(true);
    setMsg({ text: "", type: "info" });
    try {
      for (const file of Array.from(files)) { await api.uploadPrd(file, docType); }
      setMsg({ text: `成功上传 ${files.length} 个文件`, type: "success" });
      await refresh();
    } catch (e: any) { setMsg({ text: e.message, type: "error" }); }
    finally { setLoading(false); }
  };

  const handleProcess = async (id: number) => {
    setMsg({ text: "", type: "info" });
    setProcessingId(id);
    try {
      const res = await api.processPrd(id, visionProvider);
      const parts = [`处理完成：${res.sections_count} 个章节，${res.rules_count} 条规则`];
      if (res.vision_rules_count) parts.push(`图片识别 ${res.vision_rules_count} 条`);
      if (res.dedup_count) parts.push(`去重 ${res.dedup_count} 条`);
      if (res.merged_count) parts.push(`跨文档合并 ${res.merged_count} 条`);
      if (res.verification_issues) parts.push(`${res.verification_issues} 条校验问题`);
      if (res.missed_rules_added) parts.push(`补充 ${res.missed_rules_added} 条`);
      parts.push(`耗时 ${res.process_elapsed}s`);
      if (res.total_tokens) parts.push(`${res.total_tokens} tokens`);
      setMsg({ text: parts.join("，"), type: "success" });
      await refresh();
    } catch (e: any) { setMsg({ text: e.message, type: "error" }); }
    finally { setProcessingId(null); }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确认删除？")) return;
    await api.deletePrd(id);
    await refresh();
  };

  const handleImportUrl = async () => {
    if (!urlInput.trim()) return;
    setImporting(true);
    setMsg({ text: "", type: "info" });
    try {
      const prd = await api.importUrl(urlInput.trim(), docType);
      setMsg({ text: `成功导入「${prd.title}」`, type: "success" });
      setUrlInput("");
      await refresh();
    } catch (e: any) { setMsg({ text: e.message, type: "error" }); }
    finally { setImporting(false); }
  };

  const toggleDetail = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); setDetailData(null); return; }
    setExpandedId(id);
    try {
      const data = await api.extractionLogs(id);
      setDetailData(data);
    } catch { setDetailData(null); }
  };

  const statusLabel: Record<string, string> = {
    uploaded: "待处理", parsing: "解析中", parsed: "已解析", extracting: "提取中", extracted: "已完成", embedded: "已完成", failed: "处理失败",
  };
  const statusStyle = (s: string) => {
    if (s === "extracted" || s === "embedded") return "bg-[#34c75920] text-[#248a3d]";
    if (s === "parsing" || s === "extracting") return "bg-[#0071e320] text-[#0071e3]";
    if (s === "parsed") return "bg-[#af52de20] text-[#8944ab]";
    if (s === "failed") return "bg-[#ff3b3020] text-[#d70015]";
    return "bg-[#ff9f0a20] text-[#c93400]";
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-[22px] font-semibold tracking-tight">材料库</h2>
        <p className="text-[13px] mt-0.5" style={{ color: "var(--muted)" }}>管理文档与图片，系统自动提取业务规则</p>
      </div>

      {msg.text && (
        <div className={`mb-4 px-4 py-3 rounded-xl text-[13px] font-medium ${
          msg.type === "success" ? "bg-[#34c75910] text-[#248a3d]" :
          msg.type === "error" ? "bg-[#ff3b3010] text-[#d70015]" : "bg-[#0071e310] text-[#0071e3]"
        }`}>{msg.text}</div>
      )}

      <div className="flex gap-1 mb-4 bg-black/[0.04] rounded-lg p-1 w-fit">
        <button onClick={() => setDocType("prd")} className={`px-4 py-1.5 rounded-md text-[13px] font-medium transition-all ${docType === "prd" ? "bg-white shadow-sm text-[#0071e3]" : "text-[#86868b] hover:text-[#1d1d1f]"}`}>PRD</button>
        <button onClick={() => setDocType("tech")} className={`px-4 py-1.5 rounded-md text-[13px] font-medium transition-all ${docType === "tech" ? "bg-white shadow-sm text-[#0071e3]" : "text-[#86868b] hover:text-[#1d1d1f]"}`}>技术文档</button>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <span className="text-[13px] font-medium">图片识别：</span>
        <div className="flex gap-1 bg-black/[0.04] rounded-lg p-1">
          {([["off", "关闭"], ["claude", "Claude Vision"], ["qwen", "Qwen-VL"]] as const).map(([val, label]) => (
            <button key={val} onClick={() => setVisionProvider(val as any)}
              className={`px-3 py-1 rounded-md text-[12px] font-medium transition-all ${visionProvider === val ? "bg-white shadow-sm text-[#0071e3]" : "text-[#86868b] hover:text-[#1d1d1f]"}`}>{label}</button>
          ))}
        </div>
      </div>

      {/* 图片上传区域 */}
      <ImageUploadSection docType={docType} onUploadComplete={refresh} />

      <div onDragOver={(e) => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files); }}
        className={`apple-card p-10 text-center mb-6 transition-all duration-200 ${dragOver ? "!border-[var(--accent)] !bg-[#0071e308]" : ""}`}
        style={{ borderStyle: "dashed", borderWidth: 2 }}>
        <div className="mb-3">
          <svg className="w-10 h-10 mx-auto" style={{ color: "var(--muted)" }} fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
        </div>
        <p className="text-[14px] font-medium mb-1">拖拽文件到此处</p>
        <p className="text-[12px] mb-4" style={{ color: "var(--muted)" }}>支持 .docx、.doc、.md 格式</p>
        <label className="inline-flex items-center px-5 py-2 rounded-full bg-[#0071e3] text-white text-[13px] font-medium hover:bg-[#0077ed] transition-colors cursor-pointer">
          选择文件<input type="file" accept=".docx,.doc,.md,.markdown" multiple className="hidden" onChange={(e) => handleUpload(e.target.files)} />
        </label>
        {loading && <p className="mt-3 text-[12px]" style={{ color: "var(--muted)" }}>上传中...</p>}
      </div>

      <div className="apple-card p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <svg className="w-4 h-4" style={{ color: "var(--muted)" }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m9.86-5.027a4.5 4.5 0 0 0-1.242-7.244l4.5-4.5a4.5 4.5 0 0 1 6.364 6.364l-1.757 1.757" /></svg>
          <h3 className="text-[14px] font-semibold">从链接导入</h3>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#0071e310] text-[#0071e3] font-medium">飞书文档</span>
        </div>
        <div className="flex gap-2">
          <input placeholder="粘贴飞书文档链接..." value={urlInput} onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleImportUrl()} className="apple-input flex-1" />
          <button onClick={handleImportUrl} disabled={importing || !urlInput.trim()}
            className={`inline-flex items-center px-5 py-2 rounded-full text-[13px] font-medium transition-colors ${importing ? "opacity-50 cursor-wait" : "hover:bg-[#0077ed]"}`}
            style={{ background: "#0071e3", color: "#fff" }}>{importing ? "导入中..." : "导入"}</button>
        </div>
      </div>
      {/* 文档列表 */}
      <div className="apple-card overflow-hidden" style={{ borderRadius: 16 }}>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] font-medium uppercase tracking-wider" style={{ color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
              <th className="py-3 px-4">ID</th>
              <th className="py-3 px-4">标题</th>
              <th className="py-3 px-4">功能模块</th>
              <th className="py-3 px-4">状态</th>
              <th className="py-3 px-4">处理信息</th>
              <th className="py-3 px-4 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {prds.map((p) => (<>
              <tr key={p.id} className="transition-colors hover:bg-black/[0.02]" style={{ borderBottom: expandedId === p.id ? "none" : "1px solid var(--border)" }}>
                <td className="py-3 px-4 font-mono text-[12px]" style={{ color: "var(--muted)" }}>{p.id}</td>
                <td className="py-3 px-4 font-medium">{p.title}</td>
                <td className="py-3 px-4" style={{ color: "var(--muted)" }}>{p.domain || "-"}</td>
                <td className="py-3 px-4"><span className={`apple-badge ${statusStyle(p.status)}`}>{statusLabel[p.status] || p.status}</span></td>
                <td className="py-3 px-4 text-[11px]" style={{ color: "var(--muted)" }}>
                  {(p.status === "extracted" || p.status === "embedded") ? (
                    <span>{p.sections_count || 0} 章节 · {p.rules_count || 0} 规则 · {p.process_elapsed || 0}s · {p.total_tokens || 0} tokens</span>
                  ) : p.status === "failed" ? (
                    <span className="text-[#d70015]" title={p.error_message || ""}>{p.error_message?.slice(0, 60) || "处理失败"}{(p.error_message?.length || 0) > 60 ? "..." : ""}</span>
                  ) : (p.status === "parsing" || p.status === "extracting") ? (
                    <span className="animate-pulse">{statusLabel[p.status]}...</span>
                  ) : "-"}
                </td>
                <td className="py-3 px-4 text-right space-x-2">
                  {(p.status === "uploaded" || p.status === "failed") && (
                    <button onClick={() => handleProcess(p.id)} disabled={processingId !== null}
                      className={`apple-btn apple-btn-primary text-[12px] ${processingId !== null ? "opacity-50 cursor-wait" : ""}`}>
                      {processingId === p.id ? "处理中..." : processingId !== null ? "等待中" : p.status === "failed" ? "重试" : "处理"}
                    </button>
                  )}
                  {(p.status === "parsing" || p.status === "extracting") && processingId !== p.id && (
                    <span className="text-[12px] animate-pulse" style={{ color: "var(--accent)" }}>{statusLabel[p.status]}</span>
                  )}
                  {processingId === p.id && (
                    <span className="text-[12px] animate-pulse" style={{ color: "var(--accent)" }}>处理中...</span>
                  )}
                  {(p.status === "extracted" || p.status === "embedded") && (
                    <button onClick={() => toggleDetail(p.id)} className="apple-btn apple-btn-secondary text-[12px]">
                      {expandedId === p.id ? "收起" : "详情"}
                    </button>
                  )}
                  <button onClick={() => handleDelete(p.id)}
                  disabled={p.status === "parsing" || p.status === "extracting" || processingId === p.id}
                  className={`apple-btn apple-btn-danger text-[12px] ${(p.status === "parsing" || p.status === "extracting" || processingId === p.id) ? "opacity-30 cursor-not-allowed" : ""}`}>删除</button>
                </td>
              </tr>
              {expandedId === p.id && detailData && (
                <tr key={`${p.id}-detail`}>
                  <td colSpan={6} className="px-4 pb-4 pt-0" style={{ borderBottom: "1px solid var(--border)" }}>
                    <div className="flex items-center gap-2 py-3 text-[12px]">
                      <span className="text-[#248a3d]">解析 ✓</span><span style={{ color: "var(--muted)" }}>→</span>
                      <span className="text-[#248a3d]">提取规则 ✓</span><span style={{ color: "var(--muted)" }}>→</span>
                      <span className="text-[#248a3d]">二次校验 ✓</span><span style={{ color: "var(--muted)" }}>→</span>
                      <span className="text-[#248a3d]">向量化 ✓</span><span style={{ color: "var(--muted)" }}>→</span>
                      <span className="text-[#248a3d]">去重合并 ✓</span>
                    </div>
                    <div className="flex items-center gap-4 pb-3 text-[12px]" style={{ color: "var(--muted)" }}>
                      <span>文字提取模型：<span style={{ color: "var(--foreground)" }}>{p.llm_model || "-"}</span></span>
                      <span>图片识别：<span style={{ color: "var(--foreground)" }}>{
                        p.vision_provider === "claude" ? "Claude Vision" :
                        p.vision_provider === "qwen" ? "Qwen-VL" : "未启用"
                      }</span></span>
                    </div>
                    {detailData.summary && (
                      <div className="grid grid-cols-4 gap-3 mb-4">
                        {[["章节数", detailData.summary.total_sections], ["提取规则", detailData.summary.total_rules],
                          ["总耗时", `${detailData.summary.total_time}s`], ["总 Tokens", detailData.summary.total_tokens]].map(([label, val]) => (
                          <div key={label as string} className="p-3 rounded-xl bg-black/[0.02]">
                            <p className="text-[18px] font-semibold">{val}</p>
                            <p className="text-[11px]" style={{ color: "var(--muted)" }}>{label}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    {detailData.sections?.length > 0 && (
                      <table className="w-full text-[12px]">
                        <thead>
                          <tr className="text-left text-[10px] font-medium uppercase tracking-wider" style={{ color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
                            <th className="py-2 pr-3">章节</th><th className="py-2 pr-3">字符数</th><th className="py-2 pr-3">规则数</th>
                            <th className="py-2 pr-3">耗时</th><th className="py-2 pr-3">Input</th><th className="py-2 pr-3">Output</th><th className="py-2">状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detailData.sections.map((s: any, i: number) => (
                            <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                              <td className="py-2 pr-3 max-w-[200px] truncate">{s.heading}</td>
                              <td className="py-2 pr-3 font-mono" style={{ color: "var(--muted)" }}>{s.chars}</td>
                              <td className="py-2 pr-3 font-mono">{s.rules_extracted}</td>
                              <td className="py-2 pr-3 font-mono" style={{ color: "var(--muted)" }}>{s.elapsed_seconds}s</td>
                              <td className="py-2 pr-3 font-mono" style={{ color: "var(--muted)" }}>{s.input_tokens}</td>
                              <td className="py-2 pr-3 font-mono" style={{ color: "var(--muted)" }}>{s.output_tokens}</td>
                              <td className="py-2">{s.error ? <span className="text-[#d70015]">失败</span> : <span className="text-[#248a3d]">成功</span>}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    {(!detailData.sections || detailData.sections.length === 0) && (
                      <p className="text-[12px] py-3" style={{ color: "var(--muted)" }}>暂无提取日志</p>
                    )}
                  </td>
                </tr>
              )}
            </>))}
          </tbody>
        </table>
        {prds.length === 0 && <p className="text-center py-10 text-[13px]" style={{ color: "var(--muted)" }}>暂无文档，请上传文件</p>}
      </div>
    </div>
  );
}

