const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// --- Types ---

export interface PRDItem {
  id: number;
  title: string;
  filename: string;
  version?: string;
  author?: string;
  publish_date?: string;
  domain?: string;
  doc_type: string;
  status: string;
  created_at?: string;
}

export interface RuleItem {
  id: number;
  prd_id?: number;
  domain?: string;
  category?: string;
  rule_text: string;
  structured_logic?: Record<string, unknown>;
  params?: Record<string, unknown>;
  involves_roles?: string[];
  compliance_notes?: string[];
  source_section?: string;
  risk_score: number;
  risk_flags?: string[];
  status: string;
  hit_count: number;
  last_hit_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ChallengeItem {
  id: number;
  rule_id: number;
  challenger?: string;
  content: string;
  resolution?: string;
  status: string;
  created_at?: string;
  resolved_at?: string;
}

export interface AuditLogItem {
  id: number;
  rule_id?: number;
  actor?: string;
  action?: string;
  diff?: Record<string, unknown>;
  created_at?: string;
}

export interface HealthOverview {
  total_rules: number;
  active_rules: number;
  challenged_rules: number;
  deprecated_rules: number;
  open_challenges: number;
  total_hits: number;
  cold_rules: number;
}

export interface RuleStats {
  total: number;
  by_domain: Record<string, number>;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
}

export interface PaginatedRules {
  items: RuleItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SearchResult {
  id: number;
  prd_id?: number;
  domain?: string;
  category?: string;
  rule_text: string;
  source_section?: string;
  risk_score: number;
  status: string;
  hit_count: number;
  params?: Record<string, unknown>;
  relevance: number;
}

export interface RiskOverview {
  summary: { total_rules: number; high_risk_count: number; avg_risk_score: number };
  high_risk_rules: Array<{ id: number; rule_text: string; risk_score: number; risk_flags: string[]; category?: string; domain?: string }>;
  distribution: { low: number; medium: number; high: number };
}

export interface ChallengeStats {
  total: number;
  open: number;
  resolved: number;
  rejected: number;
}

interface TopHitItem {
  id: number;
  rule_text: string;
  category?: string;
  hit_count: number;
  last_hit_at?: string;
}

interface ColdRuleItem {
  id: number;
  rule_text: string;
  category?: string;
  domain?: string;
  created_at?: string;
}

// --- API ---

export const api = {
  listPrds: (docType?: string) => {
    const qs = docType ? `?doc_type=${docType}` : "";
    return request<PRDItem[]>(`/api/prds/${qs}`);
  },
  getPrd: (id: number) => request<PRDItem>(`/api/prds/${id}`),
  uploadPrd: async (file: File, docType: string = "prd") => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/prds/upload?doc_type=${docType}`, { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail);
    return res.json() as Promise<PRDItem>;
  },
  parsePrd: (id: number) => request<{ status: string; sections_count: number; prd_id: number }>(`/api/prds/${id}/parse`, { method: "POST" }),
  deletePrd: (id: number) => request<{ status: string }>(`/api/prds/${id}`, { method: "DELETE" }),
  processPrd: (id: number, visionProvider: string = "off") =>
    request<any>(`/api/prds/${id}/process?vision_provider=${visionProvider}`, { method: "POST" }),
  importUrl: (url: string, docType: string = "prd") =>
    request<PRDItem>("/api/prds/import-url", { method: "POST", body: JSON.stringify({ url, doc_type: docType }) }),

  // Rules
  listRules: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<PaginatedRules>(`/api/rules/${qs}`);
  },
  getRule: (id: number) => request<RuleItem>(`/api/rules/${id}`),
  updateRule: (id: number, data: Partial<RuleItem>, actor = "anonymous") =>
    request<RuleItem>(`/api/rules/${id}?actor=${actor}`, { method: "PUT", body: JSON.stringify(data) }),
  pendingReview: () => request<any[]>("/api/rules/pending-review"),
  approveRule: (id: number) => request<any>(`/api/rules/${id}/approve`, { method: "POST" }),
  rejectRule: (id: number) => request<any>(`/api/rules/${id}/reject`, { method: "POST" }),
  extractionLogs: (prdId: number) => request<any>(`/api/analysis/extraction-logs/${prdId}`),
  ruleStats: () => request<RuleStats>("/api/rules/stats"),

  // Challenges
  listChallenges: (ruleId: number) => request<ChallengeItem[]>(`/api/rules/${ruleId}/challenges`),
  createChallenge: (ruleId: number, data: { challenger: string; content: string }) =>
    request<ChallengeItem>(`/api/rules/${ruleId}/challenges`, { method: "POST", body: JSON.stringify(data) }),
  resolveChallenge: (challengeId: number, data: { resolution: string; status: string }, actor = "anonymous") =>
    request<ChallengeItem>(`/api/rules/challenges/${challengeId}/resolve?actor=${actor}`, { method: "PUT", body: JSON.stringify(data) }),

  // Analysis
  extractRules: (prdId: number, visionProvider: string = "off") =>
    request<any>(`/api/analysis/extract/${prdId}?vision_provider=${visionProvider}`, { method: "POST" }),
  embedPrdRules: (prdId: number) => request<{ embedded: number; prd_id: number }>(`/api/analysis/embed/${prdId}`, { method: "POST" }),
  compareRules: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<{ conflicts: unknown[]; total_compared: number; categories_checked: number }>(`/api/analysis/compare${qs}`);
  },
  riskOverview: () => request<RiskOverview>("/api/analysis/risks"),
  detectConflicts: (domain?: string, method: string = "keyword") => {
    const params: Record<string, string> = { method };
    if (domain) params.domain = domain;
    const qs = "?" + new URLSearchParams(params).toString();
    return request<{ conflicts: any[]; total_compared: number; method: string; elapsed_seconds?: number; pairs_analyzed?: number; pairs_checked?: number; categories_checked?: number; message?: string }>(`/api/analysis/detect-conflicts${qs}`, { method: "POST" });
  },
  conflictRecords: (limit = 20) => request<any[]>(`/api/analysis/conflict-records?limit=${limit}`),

  // Health
  healthOverview: () => request<HealthOverview>("/api/health/overview"),
  topHits: (limit = 10) => request<TopHitItem[]>(`/api/health/top-hits?limit=${limit}`),
  coldRules: (limit = 20) => request<ColdRuleItem[]>(`/api/health/cold-rules?limit=${limit}`),
  recentActivity: (limit = 20) => request<AuditLogItem[]>(`/api/health/recent-activity?limit=${limit}`),
  challengeStats: () => request<ChallengeStats>("/api/health/challenge-stats"),

  // Audit
  ruleLogs: (ruleId: number) => request<AuditLogItem[]>(`/api/rules/${ruleId}/logs`),

  // Search
  semanticSearch: (q: string, limit = 10, domain?: string) => {
    const params: Record<string, string> = { q, limit: String(limit) };
    if (domain) params.domain = domain;
    return request<SearchResult[]>(`/api/search/?${new URLSearchParams(params).toString()}`);
  },
  embedAll: () => request<{ embedded: number; total_without_embedding: number }>("/api/search/embed-all", { method: "POST" }),

  // Materials
  listMaterials: (materialType?: string, docType?: string) => {
    const params = new URLSearchParams();
    if (materialType && materialType !== "all") params.set("material_type", materialType);
    if (docType) params.set("doc_type", docType);
    return request<any[]>(`/api/materials/?${params.toString()}`);
  },
  uploadImage: async (file: File, docType: string = "prd") => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/materials/upload-image?doc_type=${docType}`, { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail);
    return res.json();
  },
  processImage: (id: number) => request<any>(`/api/materials/${id}/process-image`, { method: "POST" }),
  deleteMaterial: (id: number) => request<{ status: string }>(`/api/materials/${id}`, { method: "DELETE" }),

  // Wiki
  wikiIndex: () => fetch(`${API_BASE}/api/wiki/index`).then(r => r.text()),
  wikiLog: () => fetch(`${API_BASE}/api/wiki/log`).then(r => r.text()),
  wikiPages: () => request<any[]>("/api/wiki/pages"),
  wikiPage: (path: string) => request<{ path: string; content: string }>(`/api/wiki/page?path=${encodeURIComponent(path)}`),
  regenerateWiki: (materialId: number) => request<any>(`/api/wiki/regenerate/${materialId}`, { method: "POST" }),

  // Wechat Work
  wechatMessages: (status?: string) => {
    const qs = status ? `?status=${status}` : "";
    return request<any[]>(`/api/wechat-work/messages${qs}`);
  },
};
