"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body: any = { username, password };
      if (mode === "register") body.display_name = displayName || username;

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "操作失败");
      }

      const data = await res.json();
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      router.push("/upload");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "#fbfbfd",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif",
    }}>
      <div style={{ width: "100%", maxWidth: 400, padding: "0 24px" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: "linear-gradient(135deg, #0071e3, #42a1ec)",
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            marginBottom: 20,
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <h1 style={{
            fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em",
            color: "#1d1d1f", margin: 0, lineHeight: 1.1,
          }}>
            知识库
          </h1>
          <p style={{
            fontSize: 17, color: "#86868b", marginTop: 8,
            fontWeight: 400, lineHeight: 1.4,
          }}>
            {mode === "login" ? "登录你的账户" : "创建新账户"}
          </p>
        </div>

        {/* Form Card */}
        <div style={{
          background: "#fff",
          borderRadius: 20,
          padding: "36px 32px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.06)",
          border: "1px solid rgba(0,0,0,0.04)",
        }}>
          <form onSubmit={handleSubmit}>
            {/* Username */}
            <div style={{ marginBottom: 16 }}>
              <label style={{
                display: "block", fontSize: 13, fontWeight: 600,
                color: "#1d1d1f", marginBottom: 6,
              }}>
                用户名
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="请输入用户名"
                required
                autoFocus
                style={{
                  width: "100%", padding: "12px 16px",
                  fontSize: 17, borderRadius: 12,
                  border: "1px solid #d2d2d7",
                  outline: "none", transition: "all 0.2s",
                  background: "#fbfbfd",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "#0071e3";
                  e.target.style.boxShadow = "0 0 0 4px rgba(0,113,227,0.1)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "#d2d2d7";
                  e.target.style.boxShadow = "none";
                }}
              />
            </div>

            {/* Display Name (register only) */}
            {mode === "register" && (
              <div style={{ marginBottom: 16 }}>
                <label style={{
                  display: "block", fontSize: 13, fontWeight: 600,
                  color: "#1d1d1f", marginBottom: 6,
                }}>
                  显示名称
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="你的名字"
                  style={{
                    width: "100%", padding: "12px 16px",
                    fontSize: 17, borderRadius: 12,
                    border: "1px solid #d2d2d7",
                    outline: "none", transition: "all 0.2s",
                    background: "#fbfbfd",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = "#0071e3";
                    e.target.style.boxShadow = "0 0 0 4px rgba(0,113,227,0.1)";
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = "#d2d2d7";
                    e.target.style.boxShadow = "none";
                  }}
                />
              </div>
            )}

            {/* Password */}
            <div style={{ marginBottom: 24 }}>
              <label style={{
                display: "block", fontSize: 13, fontWeight: 600,
                color: "#1d1d1f", marginBottom: 6,
              }}>
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                required
                style={{
                  width: "100%", padding: "12px 16px",
                  fontSize: 17, borderRadius: 12,
                  border: "1px solid #d2d2d7",
                  outline: "none", transition: "all 0.2s",
                  background: "#fbfbfd",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "#0071e3";
                  e.target.style.boxShadow = "0 0 0 4px rgba(0,113,227,0.1)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "#d2d2d7";
                  e.target.style.boxShadow = "none";
                }}
              />
            </div>

            {/* Error */}
            {error && (
              <div style={{
                padding: "10px 14px", borderRadius: 10, marginBottom: 16,
                background: "#fff0f0", color: "#d70015",
                fontSize: 13, fontWeight: 500,
              }}>
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%", padding: "14px 0",
                fontSize: 17, fontWeight: 600,
                borderRadius: 14, border: "none",
                background: loading ? "#86868b" : "#0071e3",
                color: "#fff", cursor: loading ? "wait" : "pointer",
                transition: "all 0.2s",
                letterSpacing: "-0.01em",
              }}
              onMouseEnter={(e) => { if (!loading) (e.target as HTMLButtonElement).style.background = "#0077ed"; }}
              onMouseLeave={(e) => { if (!loading) (e.target as HTMLButtonElement).style.background = "#0071e3"; }}
            >
              {loading ? "处理中..." : mode === "login" ? "登录" : "注册"}
            </button>
          </form>
        </div>

        {/* Switch Mode */}
        <div style={{ textAlign: "center", marginTop: 24 }}>
          <span style={{ fontSize: 14, color: "#86868b" }}>
            {mode === "login" ? "还没有账户？" : "已有账户？"}
          </span>
          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            style={{
              background: "none", border: "none",
              fontSize: 14, fontWeight: 500,
              color: "#0071e3", cursor: "pointer",
              marginLeft: 4,
            }}
          >
            {mode === "login" ? "创建账户" : "返回登录"}
          </button>
        </div>

        {/* Footer */}
        <p style={{
          textAlign: "center", fontSize: 12,
          color: "#86868b", marginTop: 40,
        }}>
          材料分析与规则管理平台
        </p>
      </div>
    </div>
  );
}