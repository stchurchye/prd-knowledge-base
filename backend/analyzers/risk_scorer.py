"""
risk_scorer.py — 四维度风险评分
维度：数值一致性(0-25) / 逻辑完整性(0-25) / 跨项目一致性(0-25) / 定义清晰度(0-25)
"""
from __future__ import annotations


def calculate_risk_overview(rules) -> dict:
    """Calculate risk scores for all rules and return overview."""
    scored = []
    for r in rules:
        score, flags = score_rule(r)
        scored.append({
            "id": r.id,
            "rule_text": r.rule_text[:100] if r.rule_text else "",
            "risk_score": score,
            "risk_flags": flags,
            "category": r.category,
            "domain": r.domain,
        })

    scored.sort(key=lambda x: x["risk_score"], reverse=True)
    high_risk = [s for s in scored if s["risk_score"] >= 60]

    return {
        "summary": {
            "total_rules": len(rules),
            "high_risk_count": len(high_risk),
            "avg_risk_score": round(sum(s["risk_score"] for s in scored) / max(len(scored), 1), 1),
        },
        "high_risk_rules": high_risk[:20],
        "distribution": _risk_distribution(scored),
    }


def score_rule(rule) -> tuple[float, list[str]]:
    """Score a single rule across 4 dimensions. Returns (score, flags)."""
    flags = []
    score = 0.0

    # Dimension 1: 数值一致性 (0-25) — missing or vague params
    params = rule.params or {}
    if not params:
        score += 15
        flags.append("缺少数值参数")
    else:
        for k, v in params.items():
            if isinstance(v, str) and any(w in v for w in ["约", "大概", "左右", "待定"]):
                score += 8
                flags.append(f"参数'{k}'定义模糊")
                break

    # Dimension 2: 逻辑完整性 (0-25) — missing conditions or edge cases
    text = rule.rule_text or ""
    logic = rule.structured_logic or {}
    if not logic:
        score += 10
        flags.append("缺少结构化逻辑")
    if "如果" in text and "否则" not in text and "else" not in str(logic):
        score += 10
        flags.append("条件分支不完整")
    if len(text) < 20:
        score += 5
        flags.append("规则描述过短")

    # Dimension 3: 跨项目一致性 (0-25) — checked at overview level
    if rule.status == "challenged":
        score += 15
        flags.append("规则被质疑")
    elif rule.status == "deprecated":
        score += 20
        flags.append("规则已废弃")

    # Dimension 4: 定义清晰度 (0-25)
    vague_words = ["可能", "大概", "一般", "通常", "视情况", "待确认", "TBD"]
    for w in vague_words:
        if w in text:
            score += 5
            flags.append(f"含模糊表述'{w}'")
            break

    compliance = rule.compliance_notes or []
    if not compliance and rule.category in ("资金流转规则", "合规约束"):
        score += 10
        flags.append("资金/合规规则缺少合规备注")

    return min(score, 100), flags


def _risk_distribution(scored: list[dict]) -> dict:
    low = sum(1 for s in scored if s["risk_score"] < 30)
    medium = sum(1 for s in scored if 30 <= s["risk_score"] < 60)
    high = sum(1 for s in scored if s["risk_score"] >= 60)
    return {"low": low, "medium": medium, "high": high}
