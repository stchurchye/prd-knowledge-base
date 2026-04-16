"""
comparator.py — 跨版本/跨PRD规则对比，检测数值冲突和逻辑矛盾
支持三种检测方法:
  1. keyword  — 关键词反义词匹配（快，覆盖面有限）
  2. embedding — 向量相似度筛选高相似规则对（中速，语义层面）
  3. llm — Claude 逐对分析语义冲突（慢，最准确，消耗 API 额度）
"""
from __future__ import annotations

import json
import re
import logging

logger = logging.getLogger(__name__)


# ==================== 方法 1: 关键词检测 ====================

def compare_rules_keyword(rules) -> dict:
    """关键词/反义词匹配检测冲突。"""
    conflicts = []

    by_category: dict[str, list] = {}
    for r in rules:
        cat = r.category or "未分类"
        by_category.setdefault(cat, []).append(r)

    for cat, cat_rules in by_category.items():
        if len(cat_rules) < 2:
            continue
        for i, r1 in enumerate(cat_rules):
            for r2 in cat_rules[i + 1:]:
                nc = _check_numerical_conflict(r1, r2)
                if nc:
                    conflicts.append(nc)
                lc = _check_logic_conflict(r1, r2)
                if lc:
                    conflicts.append(lc)

    return {
        "conflicts": conflicts,
        "total_compared": len(rules),
        "categories_checked": len(by_category),
        "method": "keyword",
    }


# ==================== 方法 2: Embedding 相似度检测 ====================

async def compare_rules_embedding(rules, db) -> dict:
    """用向量相似度找出高度相似但可能矛盾的规则对，再做关键词分析。"""
    from sqlalchemy import text

    # 只取有 embedding 的规则
    rule_ids = [r.id for r in rules if r.embedding is not None]
    if len(rule_ids) < 2:
        return {
            "conflicts": [],
            "total_compared": len(rule_ids),
            "method": "embedding",
            "message": "embedding 不足，请先执行「生成向量」",
        }

    # 用 pgvector 找出相似度 > 0.85 的规则对
    placeholders = ", ".join(str(rid) for rid in rule_ids)
    sql = text(f"""
        SELECT a.id AS id_a, b.id AS id_b,
               a.rule_text AS text_a, b.rule_text AS text_b,
               a.category AS cat_a, b.category AS cat_b,
               a.domain AS domain_a, b.domain AS domain_b,
               a.params AS params_a, b.params AS params_b,
               1 - (a.embedding <=> b.embedding) AS similarity
        FROM rules a, rules b
        WHERE a.id < b.id
          AND a.id IN ({placeholders})
          AND b.id IN ({placeholders})
          AND a.embedding IS NOT NULL
          AND b.embedding IS NOT NULL
          AND 1 - (a.embedding <=> b.embedding) > 0.80
        ORDER BY similarity DESC
        LIMIT 50
    """)

    rows = db.execute(sql).fetchall()
    conflicts = []

    for row in rows:
        sim = round(row.similarity, 4)
        t1 = (row.text_a or "").lower()
        t2 = (row.text_b or "").lower()

        # 检查是否存在语义对立
        conflict_type = _detect_semantic_opposition(t1, t2)
        if conflict_type:
            conflicts.append({
                "type": conflict_type,
                "description": f"语义相似度 {sim}，规则内容存在对立表述。\n规则A: {(row.text_a or '')[:80]}\n规则B: {(row.text_b or '')[:80]}",
                "rule_ids": [row.id_a, row.id_b],
                "severity": "high" if sim > 0.9 else "medium",
                "method": "embedding",
            })
        elif sim > 0.92:
            # 高度相似但没有明显对立 → 可能重复
            # 检查参数冲突
            p1 = row.params_a if isinstance(row.params_a, dict) else (json.loads(row.params_a) if isinstance(row.params_a, str) else {})
            p2 = row.params_b if isinstance(row.params_b, dict) else (json.loads(row.params_b) if isinstance(row.params_b, str) else {})
            param_diff = _check_param_diff(p1, p2)
            if param_diff:
                conflicts.append({
                    "type": "数值冲突",
                    "description": f"语义相似度 {sim}，{param_diff}。\n规则A: {(row.text_a or '')[:80]}\n规则B: {(row.text_b or '')[:80]}",
                    "rule_ids": [row.id_a, row.id_b],
                    "severity": "high",
                    "method": "embedding",
                })
            else:
                conflicts.append({
                    "type": "疑似重复",
                    "description": f"语义相似度 {sim}，可能为重复规则。\n规则A: {(row.text_a or '')[:80]}\n规则B: {(row.text_b or '')[:80]}",
                    "rule_ids": [row.id_a, row.id_b],
                    "severity": "low",
                    "method": "embedding",
                })

    return {
        "conflicts": conflicts,
        "total_compared": len(rule_ids),
        "pairs_checked": len(rows),
        "method": "embedding",
    }


def _detect_semantic_opposition(t1: str, t2: str) -> str | None:
    """检测两段文本是否存在语义对立。"""
    opposites = [
        ("允许", "禁止"), ("可以", "不可以"), ("支持", "不支持"),
        ("开启", "关闭"), ("启用", "禁用"), ("必须", "不得"),
        ("需要", "不需要"), ("强制", "可选"), ("包含", "不包含"),
        ("上限", "下限"),
    ]
    for pos, neg in opposites:
        if (pos in t1 and neg in t2) or (neg in t1 and pos in t2):
            return "逻辑矛盾"
    return None


def _check_param_diff(p1: dict, p2: dict) -> str | None:
    """检查两组参数的数值差异。"""
    for key in set(p1.keys()) & set(p2.keys()):
        v1, v2 = p1[key], p2[key]
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)) and v1 != v2:
            return f"参数 '{key}' 不一致: {v1} vs {v2}"
    return None


# ==================== 方法 3: LLM 语义分析 ====================

async def compare_rules_llm(rules) -> dict:
    """使用百炼/通义千问对同分类规则做语义冲突分析。"""
    from extractors.llm_client import get_llm_client, get_model_name
    from config import settings

    if not settings.qwen_api_key and not settings.anthropic_api_key:
        return {
            "conflicts": [],
            "total_compared": len(rules),
            "method": "llm",
            "message": "未配置 API Key",
        }

    # 按 category 分组
    by_category: dict[str, list] = {}
    for r in rules:
        cat = r.category or "未分类"
        by_category.setdefault(cat, []).append(r)

    # 准备需要分析的规则对（同分类、限制数量避免费用过高）
    pairs_to_check = []
    for cat, cat_rules in by_category.items():
        if len(cat_rules) < 2:
            continue
        for i, r1 in enumerate(cat_rules):
            for r2 in cat_rules[i + 1:]:
                pairs_to_check.append((r1, r2, cat))
                if len(pairs_to_check) >= 30:  # 最多分析 30 对
                    break
            if len(pairs_to_check) >= 30:
                break
        if len(pairs_to_check) >= 30:
            break

    if not pairs_to_check:
        return {
            "conflicts": [],
            "total_compared": len(rules),
            "pairs_analyzed": 0,
            "method": "llm",
        }

    # 构造 prompt，批量分析所有对
    pair_texts = []
    for idx, (r1, r2, cat) in enumerate(pairs_to_check):
        pair_texts.append(
            f"对 {idx + 1} (分类: {cat}):\n"
            f"  规则 A (ID={r1.id}): {r1.rule_text}\n"
            f"  规则 B (ID={r2.id}): {r2.rule_text}"
        )

    prompt = (
        "你是业务规则冲突检测专家。以下是从 PRD 文档中提取的规则对，请分析每对规则是否存在冲突。\n\n"
        "冲突类型包括：\n"
        "- 逻辑矛盾：两条规则对同一事物给出相反的要求\n"
        "- 数值冲突：同一参数的数值不一致\n"
        "- 条件覆盖：两条规则的适用条件重叠但结论不同\n"
        "- 范围矛盾：一条规则的范围与另一条矛盾\n\n"
        "注意：如果两条规则适用于不同场景或不同条件，即使措辞相反也不算冲突。\n\n"
        f"{'=' * 40}\n"
        + "\n\n".join(pair_texts)
        + f"\n{'=' * 40}\n\n"
        "请以 JSON 数组输出有冲突的规则对，每项包含：\n"
        '{"pair_index": 序号, "type": "冲突类型", "description": "冲突说明", '
        '"severity": "high/medium/low", "rule_id_a": ID, "rule_id_b": ID}\n\n'
        "如果没有冲突输出空数组 []。只输出 JSON，不要其他内容。"
    )

    client = get_llm_client()
    model = get_model_name()

    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]

    try:
        result_list = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            result_list = json.loads(text[start:end])
        else:
            result_list = []

    conflicts = []
    for item in result_list:
        conflicts.append({
            "type": item.get("type", "语义冲突"),
            "description": item.get("description", ""),
            "rule_ids": [item.get("rule_id_a"), item.get("rule_id_b")],
            "severity": item.get("severity", "medium"),
            "method": "llm",
        })

    return {
        "conflicts": conflicts,
        "total_compared": len(rules),
        "pairs_analyzed": len(pairs_to_check),
        "method": "llm",
    }


# ==================== 旧接口兼容 ====================

def compare_rules_across_prds(rules) -> dict:
    """兼容旧调用，默认使用关键词检测。"""
    return compare_rules_keyword(rules)


# ==================== 内部工具函数 ====================

def _check_numerical_conflict(r1, r2) -> dict | None:
    """Detect conflicting numerical parameters between two rules."""
    p1 = r1.params or {}
    p2 = r2.params or {}

    for key in set(p1.keys()) & set(p2.keys()):
        v1, v2 = p1[key], p2[key]
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)) and v1 != v2:
            return {
                "type": "数值冲突",
                "description": f"参数 '{key}' 在规则间不一致: {v1} vs {v2}。\n规则A: {(r1.rule_text or '')[:80]}\n规则B: {(r2.rule_text or '')[:80]}",
                "rule_ids": [r1.id, r2.id],
                "severity": "high" if abs(v1 - v2) / max(abs(v1), abs(v2), 1) > 0.1 else "medium",
                "method": "keyword",
            }
    return None


def _check_logic_conflict(r1, r2) -> dict | None:
    """Detect potential logical contradictions between rules."""
    t1 = (r1.rule_text or "").lower()
    t2 = (r2.rule_text or "").lower()

    opposites = [
        ("允许", "禁止"), ("可以", "不可以"), ("支持", "不支持"),
        ("开启", "关闭"), ("启用", "禁用"),
    ]
    for pos, neg in opposites:
        if (pos in t1 and neg in t2) or (neg in t1 and pos in t2):
            common = _common_keywords(t1, t2)
            if common:
                return {
                    "type": "逻辑矛盾",
                    "description": f"规则对 '{'/'.join(common)}' 存在相反描述（{pos}/{neg}）。\n规则A: {(r1.rule_text or '')[:80]}\n规则B: {(r2.rule_text or '')[:80]}",
                    "rule_ids": [r1.id, r2.id],
                    "severity": "high",
                    "method": "keyword",
                }
    return None


def _common_keywords(t1: str, t2: str) -> set[str]:
    """Find meaningful common keywords between two rule texts."""
    stop = {"的", "了", "在", "是", "和", "或", "与", "对", "为", "不", "可", "有", "被", "将", "从", "到"}
    w1 = set(re.findall(r"[\u4e00-\u9fff]{2,}", t1)) - stop
    w2 = set(re.findall(r"[\u4e00-\u9fff]{2,}", t2)) - stop
    return w1 & w2
