"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function WikiPage() {
  const [indexContent, setIndexContent] = useState("");
  const [logContent, setLogContent] = useState("");
  const [pages, setPages] = useState<any[]>([]);
  const [selectedContent, setSelectedContent] = useState("");
  const [selectedTitle, setSelectedTitle] = useState("");
  const [tab, setTab] = useState<"index" | "pages" | "log">("index");

  useEffect(() => {
    api.wikiIndex().then(setIndexContent);
    api.wikiLog().then(setLogContent);
    api.wikiPages().then(setPages);
  }, []);

  const loadPage = async (path: string, title: string) => {
    try {
      const data = await api.wikiPage(path);
      setSelectedContent(data.content);
      setSelectedTitle(title);
    } catch {
      setSelectedContent("页面加载失败");
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-[22px] font-semibold tracking-tight">Wiki 知识库</h2>
        <p className="text-[13px] mt-0.5" style={{ color: "var(--muted)" }}>
          基于 LLM Wiki 架构，知识编译后持久化存储
        </p>
      </div>

      <div className="flex gap-1 mb-4 bg-black/[0.04] rounded-lg p-1 w-fit">
        {(["index", "pages", "log"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-[13px] font-medium transition-all ${
              tab === t ? "bg-white shadow-sm text-[#0071e3]" : "text-[#86868b] hover:text-[#1d1d1f]"
            }`}>
            {t === "index" ? "索引" : t === "pages" ? "页面列表" : "操作日志"}
          </button>
        ))}
      </div>

      {tab === "index" && (
        <div className="apple-card p-6">
          <pre className="text-[13px] whitespace-pre-wrap leading-relaxed" style={{ fontFamily: "inherit" }}>
            {indexContent || "暂无索引内容，上传材料并处理后自动生成"}
          </pre>
        </div>
      )}

      {tab === "pages" && (
        <div className="flex gap-4" style={{ minHeight: 400 }}>
          <div className="w-[300px] apple-card p-4 overflow-auto" style={{ maxHeight: "70vh" }}>
            <h3 className="text-[14px] font-semibold mb-3">Wiki 页面 ({pages.length})</h3>
            {pages.length === 0 && (
              <p className="text-[12px]" style={{ color: "var(--muted)" }}>暂无页面</p>
            )}
            {pages.map((p) => (
              <button key={p.id} onClick={() => loadPage(p.page_path || "", p.title)}
                className={`w-full text-left p-3 rounded-xl mb-2 transition-all hover:bg-black/[0.04] ${
                  selectedTitle === p.title ? "bg-[#0071e310]" : ""
                }`}>
                <p className="text-[13px] font-medium">{p.title}</p>
                <p className="text-[11px] mt-0.5" style={{ color: "var(--muted)" }}>
                  {p.page_type} · {p.rules_count || 0} 条规则 · v{p.version}
                </p>
              </button>
            ))}
          </div>

          <div className="flex-1 apple-card p-6 overflow-auto" style={{ maxHeight: "70vh" }}>
            {selectedContent ? (
              <pre className="text-[13px] whitespace-pre-wrap leading-relaxed" style={{ fontFamily: "inherit" }}>
                {selectedContent}
              </pre>
            ) : (
              <p className="text-[13px]" style={{ color: "var(--muted)" }}>选择左侧页面查看内容</p>
            )}
          </div>
        </div>
      )}

      {tab === "log" && (
        <div className="apple-card p-6">
          <pre className="text-[13px] whitespace-pre-wrap leading-relaxed" style={{ fontFamily: "inherit" }}>
            {logContent || "暂无操作日志"}
          </pre>
        </div>
      )}
    </div>
  );
}