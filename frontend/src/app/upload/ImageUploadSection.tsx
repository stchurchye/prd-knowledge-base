"use client";

import { useState } from "react";

interface ImageUploadSectionProps {
  docType: "prd" | "tech";
  onUploadComplete: () => void;
}

export function ImageUploadSection({ docType, onUploadComplete }: ImageUploadSectionProps) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" }>({ text: "", type: "success" });

  const handleImageUpload = async (files: FileList | null) => {
    if (!files) return;
    setUploading(true);
    setMsg({ text: "", type: "success" });

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

    try {
      let successCount = 0;
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) {
          setMsg({ text: `${file.name} 不是图片格式`, type: "error" });
          continue;
        }

        const form = new FormData();
        form.append("file", file);

        const res = await fetch(`${API_BASE}/api/materials/upload-image?doc_type=${docType}`, {
          method: "POST",
          body: form,
        });

        if (!res.ok) {
          const err = await res.json();
          setMsg({ text: err.detail || "上传失败", type: "error" });
          continue;
        }
        successCount++;
      }

      if (successCount > 0) {
        setMsg({ text: `成功上传 ${successCount} 张图片`, type: "success" });
        onUploadComplete();
      }
    } catch (e: any) {
      setMsg({ text: e.message || "上传失败", type: "error" });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="apple-card p-5 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-4 h-4" style={{ color: "var(--muted)" }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
        </svg>
        <h3 className="text-[14px] font-semibold">直接上传图片</h3>
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#ff9f0a10] text-[#c93400] font-medium">Qwen-VL 提取规则</span>
      </div>

      {msg.text && (
        <div className={`mb-3 px-3 py-2 rounded-lg text-[12px] font-medium ${
          msg.type === "success" ? "bg-[#34c75910] text-[#248a3d]" : "bg-[#ff3b3010] text-[#d70015]"
        }`}>{msg.text}</div>
      )}

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleImageUpload(e.dataTransfer.files); }}
        className={`p-6 text-center rounded-xl border-2 transition-all ${
          dragOver ? "border-[var(--accent)] bg-[#0071e308]" : "border-dashed border-[var(--border)]"
        }`}
      >
        <p className="text-[13px] mb-2" style={{ color: "var(--muted)" }}>拖拽图片到此处，或点击选择</p>
        <label className="inline-flex items-center px-4 py-2 rounded-full bg-[#ff9f0a] text-white text-[12px] font-medium hover:bg-[#ffb340] transition-colors cursor-pointer">
          选择图片
          <input
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => handleImageUpload(e.target.files)}
          />
        </label>
        {uploading && <p className="mt-2 text-[12px]" style={{ color: "var(--muted)" }}>处理中...</p>}
      </div>
    </div>
  );
}