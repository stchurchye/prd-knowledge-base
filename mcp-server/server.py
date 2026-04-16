#!/usr/bin/env python3
"""
PRD Knowledge Base MCP Server
让 Claude 在对话中直接查询 PRD 知识库中的业务规则。
支持语义搜索、规则详情、领域/分类浏览。
"""
from __future__ import annotations

import json
import logging
import os
import sys

import psycopg2
import psycopg2.extras
from mcp.server.fastmcp import FastMCP

# ── Config ────────────────────────────────────────────────────
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://prd_user:prd_pass_2024@localhost:5432/prd_knowledge_base",
)

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("prd-kb-mcp")

# ── Embedding model (lazy load) ──────────────────────────────
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("BAAI/bge-base-zh-v1.5")
        logger.info("Embedding model loaded")
    return _model


def _embed(text: str) -> list[float]:
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


# ── DB helpers ────────────────────────────────────────────────
def _get_conn():
    return psycopg2.connect(DB_URL)


def _query(sql: str, params: dict | tuple = (), *, fetch: str = "all"):
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if fetch == "all":
                return cur.fetchall()
            elif fetch == "one":
                return cur.fetchone()
            return None


# ── MCP Server ────────────────────────────────────────────────
mcp = FastMCP(
    "prd-knowledge-base",
    version="1.0.0",
    description="PRD 知识库：查询从产品需求文档中提取的业务规则、资金流转逻辑、数值参数等",
)


@mcp.tool()
def search_rules(
    query: str,
    domain: str = "",
    category: str = "",
    limit: int = 10,
) -> str:
    """
    语义搜索业务规则。输入自然语言查询，返回最相关的规则。
    适用场景：写PRD时查询已有规则确保一致性、客服咨询业务逻辑。

    Args:
        query: 搜索内容，如"分账比例上限"、"红包退款规则"、"提现手续费"
        domain: 可选，过滤领域（结账分账/营销资金/支付接入）
        category: 可选，过滤分类（资金流转/角色权限/状态机/数值参数/合规约束）
        limit: 返回数量，默认10
    """
    try:
        query_vec = _embed(query)
    except Exception as e:
        # Fallback: 文本搜索
        logger.warning("Embedding failed (%s), falling back to text search", e)
        return _text_search(query, domain, category, limit)

    vec_str = "[" + ",".join(str(x) for x in query_vec) + "]"

    sql = """
        SELECT r.id, r.domain, r.category, r.rule_text, r.source_section,
               r.params, r.status, r.risk_score, r.hit_count,
               p.title AS prd_title,
               (r.embedding <=> %(vec)s::vector) AS distance
        FROM rules r
        LEFT JOIN prds p ON r.prd_id = p.id
        WHERE r.embedding IS NOT NULL
    """
    params: dict = {"vec": vec_str, "limit": limit}

    if domain:
        sql += " AND r.domain = %(domain)s"
        params["domain"] = domain
    if category:
        sql += " AND r.category = %(category)s"
        params["category"] = category

    sql += " ORDER BY distance ASC LIMIT %(limit)s"

    rows = _query(sql, params)
    if not rows:
        return "未找到相关规则。可尝试更换关键词或去掉领域/分类过滤。"

    # Update hit counts
    ids = [r["id"] for r in rows]
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE rules SET hit_count = hit_count + 1, last_hit_at = NOW() WHERE id = ANY(%s)",
                (ids,),
            )
        conn.commit()

    results = []
    for r in rows:
        relevance = round(1 - r["distance"], 4)
        entry = (
            f"【规则 #{r['id']}】(相关度: {relevance})\n"
            f"  来源PRD: {r['prd_title'] or '未知'}\n"
            f"  领域: {r['domain'] or '-'} | 分类: {r['category'] or '-'}\n"
            f"  章节: {r['source_section'] or '-'}\n"
            f"  状态: {r['status']} | 风险分: {r['risk_score'] or 0}\n"
            f"  规则内容: {r['rule_text']}\n"
        )
        if r["params"]:
            params_data = r["params"] if isinstance(r["params"], dict) else json.loads(r["params"])
            if params_data:
                entry += f"  关键参数: {json.dumps(params_data, ensure_ascii=False)}\n"
        results.append(entry)

    return f"找到 {len(results)} 条相关规则:\n\n" + "\n---\n".join(results)


def _text_search(query: str, domain: str, category: str, limit: int) -> str:
    """Fallback text-based search when embedding is unavailable."""
    sql = """
        SELECT r.id, r.domain, r.category, r.rule_text, r.source_section,
               r.params, r.status, r.risk_score, p.title AS prd_title
        FROM rules r
        LEFT JOIN prds p ON r.prd_id = p.id
        WHERE r.rule_text ILIKE %(q)s
    """
    params: dict = {"q": f"%{query}%", "limit": limit}
    if domain:
        sql += " AND r.domain = %(domain)s"
        params["domain"] = domain
    if category:
        sql += " AND r.category = %(category)s"
        params["category"] = category
    sql += " ORDER BY r.hit_count DESC LIMIT %(limit)s"

    rows = _query(sql, params)
    if not rows:
        return "未找到相关规则。"

    results = []
    for r in rows:
        entry = (
            f"【规则 #{r['id']}】\n"
            f"  来源PRD: {r['prd_title'] or '未知'}\n"
            f"  领域: {r['domain'] or '-'} | 分类: {r['category'] or '-'}\n"
            f"  规则内容: {r['rule_text']}\n"
        )
        results.append(entry)
    return f"找到 {len(results)} 条规则 (文本匹配):\n\n" + "\n---\n".join(results)


@mcp.tool()
def get_rule_detail(rule_id: int) -> str:
    """
    获取单条规则的完整详情，包含结构化逻辑、参数、来源、质疑记录等。

    Args:
        rule_id: 规则ID
    """
    row = _query(
        """
        SELECT r.*, p.title AS prd_title, p.filename AS prd_filename
        FROM rules r
        LEFT JOIN prds p ON r.prd_id = p.id
        WHERE r.id = %(id)s
        """,
        {"id": rule_id},
        fetch="one",
    )
    if not row:
        return f"规则 #{rule_id} 不存在"

    # Get challenges
    challenges = _query(
        "SELECT * FROM challenges WHERE rule_id = %(id)s ORDER BY created_at DESC",
        {"id": rule_id},
    )

    result = (
        f"# 规则 #{row['id']} 详情\n\n"
        f"**来源PRD**: {row['prd_title'] or '未知'} ({row['prd_filename'] or '-'})\n"
        f"**领域**: {row['domain'] or '-'}\n"
        f"**分类**: {row['category'] or '-'}\n"
        f"**来源章节**: {row['source_section'] or '-'}\n"
        f"**状态**: {row['status']}\n"
        f"**风险评分**: {row['risk_score'] or 0}\n"
        f"**被引用次数**: {row['hit_count'] or 0}\n\n"
        f"## 规则内容\n{row['rule_text']}\n\n"
    )

    if row["structured_logic"]:
        logic = row["structured_logic"] if isinstance(row["structured_logic"], dict) else json.loads(row["structured_logic"])
        result += f"## 结构化逻辑\n```json\n{json.dumps(logic, ensure_ascii=False, indent=2)}\n```\n\n"

    if row["params"]:
        params_data = row["params"] if isinstance(row["params"], dict) else json.loads(row["params"])
        result += f"## 关键参数\n```json\n{json.dumps(params_data, ensure_ascii=False, indent=2)}\n```\n\n"

    if row["involves_roles"]:
        result += f"## 涉及角色\n{', '.join(row['involves_roles'])}\n\n"

    if row["compliance_notes"]:
        result += f"## 合规备注\n" + "\n".join(f"- {n}" for n in row["compliance_notes"]) + "\n\n"

    if challenges:
        result += "## 质疑记录\n"
        for c in challenges:
            status_label = "已解决" if c["status"] == "resolved" else "待处理"
            result += f"- [{status_label}] {c['challenger'] or '匿名'}: {c['content']}\n"
            if c["resolution"]:
                result += f"  → 处理结果: {c['resolution']}\n"

    return result


@mcp.tool()
def list_domains() -> str:
    """
    列出知识库中所有业务领域及其规则数量。
    用于了解知识库覆盖范围。
    """
    rows = _query("""
        SELECT domain, category, COUNT(*) as cnt,
               COUNT(*) FILTER (WHERE status = 'active') as active_cnt
        FROM rules
        WHERE domain IS NOT NULL
        GROUP BY domain, category
        ORDER BY domain, cnt DESC
    """)
    if not rows:
        return "知识库中暂无规则数据。"

    domains: dict[str, list] = {}
    for r in rows:
        d = r["domain"]
        if d not in domains:
            domains[d] = []
        domains[d].append(f"  - {r['category'] or '未分类'}: {r['cnt']}条 (活跃{r['active_cnt']}条)")

    result = "# 知识库领域概览\n\n"
    for domain, categories in domains.items():
        total = sum(int(c.split(":")[1].split("条")[0].strip()) for c in categories)
        result += f"## {domain} ({total}条规则)\n" + "\n".join(categories) + "\n\n"

    return result


@mcp.tool()
def list_prds() -> str:
    """
    列出所有已导入的PRD文档及其状态。
    """
    rows = _query("""
        SELECT p.id, p.title, p.filename, p.domain, p.status, p.created_at,
               COUNT(r.id) as rule_count
        FROM prds p
        LEFT JOIN rules r ON r.prd_id = p.id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """)
    if not rows:
        return "暂无已导入的PRD文档。"

    result = "# 已导入PRD列表\n\n"
    for r in rows:
        result += (
            f"- **{r['title']}** (ID: {r['id']})\n"
            f"  文件: {r['filename']} | 领域: {r['domain'] or '-'} | "
            f"状态: {r['status']} | 提取规则: {r['rule_count']}条\n"
        )
    return result


@mcp.tool()
def get_rules_by_category(
    category: str,
    domain: str = "",
    status: str = "",
) -> str:
    """
    按分类获取规则列表。

    Args:
        category: 规则分类（资金流转/角色权限/状态机/数值参数/合规约束）
        domain: 可选，过滤领域
        status: 可选，过滤状态（draft/active/challenged/deprecated）
    """
    sql = """
        SELECT r.id, r.domain, r.rule_text, r.source_section, r.params,
               r.status, r.risk_score, p.title AS prd_title
        FROM rules r
        LEFT JOIN prds p ON r.prd_id = p.id
        WHERE r.category = %(category)s
    """
    params: dict = {"category": category}
    if domain:
        sql += " AND r.domain = %(domain)s"
        params["domain"] = domain
    if status:
        sql += " AND r.status = %(status)s"
        params["status"] = status
    sql += " ORDER BY r.risk_score DESC NULLS LAST LIMIT 50"

    rows = _query(sql, params)
    if not rows:
        return f"未找到分类为「{category}」的规则。"

    result = f"# {category} 类规则 ({len(rows)}条)\n\n"
    for r in rows:
        result += (
            f"**#{r['id']}** [{r['status']}] (风险: {r['risk_score'] or 0})\n"
            f"  来源: {r['prd_title'] or '-'} > {r['source_section'] or '-'}\n"
            f"  {r['rule_text'][:200]}{'...' if len(r['rule_text'] or '') > 200 else ''}\n\n"
        )
    return result


@mcp.tool()
def get_numeric_params(domain: str = "") -> str:
    """
    获取所有数值参数类规则，便于在写PRD时确保数值一致性。
    例如：费率、限额、比例、天数等关键数值。

    Args:
        domain: 可选，过滤领域
    """
    sql = """
        SELECT r.id, r.rule_text, r.params, r.source_section, r.status,
               p.title AS prd_title
        FROM rules r
        LEFT JOIN prds p ON r.prd_id = p.id
        WHERE r.category = '数值参数' AND r.params IS NOT NULL
    """
    params: dict = {}
    if domain:
        sql += " AND r.domain = %(domain)s"
        params["domain"] = domain
    sql += " ORDER BY r.hit_count DESC NULLS LAST"

    rows = _query(sql, params)
    if not rows:
        return "未找到数值参数类规则。"

    result = "# 数值参数汇总\n\n"
    for r in rows:
        params_data = r["params"] if isinstance(r["params"], dict) else json.loads(r["params"]) if r["params"] else {}
        result += (
            f"**#{r['id']}** [{r['status']}] 来源: {r['prd_title'] or '-'}\n"
            f"  {r['rule_text']}\n"
        )
        if params_data:
            for k, v in params_data.items():
                result += f"  · {k} = {v}\n"
        result += "\n"

    return result


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
