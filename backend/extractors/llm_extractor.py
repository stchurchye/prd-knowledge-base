"""
llm_extractor.py — 使用百炼/通义千问 API 从 PRD 章节中提取结构化业务规则
v3: OpenAI 兼容格式 + function calling + 置信度
"""
from __future__ import annotations

import json
import logging
from config import settings
from extractors.llm_client import get_llm_client, get_model_name

logger = logging.getLogger(__name__)

# ==================== Tool Schema (OpenAI 格式) ====================

RULE_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "save_extracted_rules",
        "description": "保存从文档章节中提取的业务规则",
        "parameters": {
            "type": "object",
            "properties": {
                "rules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule_text": {
                                "type": "string",
                                "description": "规则的完整自然语言描述，必须可独立理解",
                            },
                            "category": {
                                "type": "string",
                                "enum": ["资金流转规则", "角色权限模型", "状态机流程", "数值参数阈值", "合规约束", "业务逻辑"],
                                "description": "规则分类",
                            },
                            "domain": {
                                "type": "string",
                                "description": "业务领域，如：支付接入/结账分账/营销资金/门店管理",
                            },
                            "structured_logic": {
                                "type": "object",
                                "description": "半结构化逻辑：条件(if)、动作(then)、否则(else)、约束(constraints)",
                            },
                            "params": {
                                "type": "object",
                                "description": "提取的数值参数，如金额限制、比例、时间阈值等",
                            },
                            "involves_roles": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "涉及的角色列表",
                            },
                            "compliance_notes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "合规相关备注",
                            },
                            "source_section": {
                                "type": "string",
                                "description": "来源章节名称",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "提取置信度 0-1，1 表示非常确定这是一条明确的业务规则",
                            },
                        },
                        "required": ["rule_text", "category", "source_section", "confidence"],
                    },
                },
            },
            "required": ["rules"],
        },
    },
}

# ==================== System Prompt ====================

SYSTEM_PROMPT = """你是一个专业的业务规则提取专家。你的任务是从 PRD 文档章节中提取可复用的业务规则。

## 提取原则
1. 只提取明确的业务规则，不要提取 UI 描述、产品运营内容或模糊的需求描述
2. 每条规则必须可独立理解，包含完整的条件和结论
3. 数值参数（金额、比例、时间等）必须提取到 params 字段
4. 涉及条件判断的规则，必须填写 structured_logic
5. 对提取置信度诚实评分：明确的业务规则给 0.8-1.0，推断出的规则给 0.5-0.7，不确定的给 0.3-0.5

## 示例

输入章节「退款规则」：
"整单部分退款时，退款金额需按照原始分账比例反向分摊至各角色，计算误差调整至最后一个分账方以确保总和精确。单笔退款金额不得超过原订单金额的100%。"

提取结果：
- rule_text: "整单部分退款时，退款金额按原始分账比例反向分摊至各角色，计算误差调整至最后一个分账方以确保总和精确"
  category: "资金流转规则"
  domain: "结账分账"
  structured_logic: {"if": "整单部分退款", "then": "按原始分账比例反向分摊", "constraint": "误差调整至最后一个分账方"}
  params: {}
  involves_roles: ["分账方"]
  source_section: "退款规则"
  confidence: 0.95

- rule_text: "单笔退款金额不得超过原订单金额的100%"
  category: "数值参数阈值"
  domain: "结账分账"
  params: {"退款金额上限比例": 1.0}
  source_section: "退款规则"
  confidence: 0.9

输入章节「权限管理」：
"总部管理员可以查看所有门店的交易数据，门店管理员只能查看本门店数据。操作员不具备退款权限，需由门店管理员审批。"

提取结果：
- rule_text: "总部管理员可查看所有门店交易数据，门店管理员只能查看本门店数据"
  category: "角色权限模型"
  involves_roles: ["总部管理员", "门店管理员"]
  confidence: 0.9

- rule_text: "操作员不具备退款权限，退款需由门店管理员审批"
  category: "角色权限模型"
  structured_logic: {"if": "操作员发起退款", "then": "需门店管理员审批", "constraint": "操作员无直接退款权限"}
  involves_roles: ["操作员", "门店管理员"]
  confidence: 0.85"""

# ==================== 分段提取 ====================


def _build_section_text(section: dict) -> str:
    """将一个章节构建为提取用的文本。"""
    heading = section.get("heading", "")
    content = section.get("content", "")
    if isinstance(content, list):
        content = "\n".join(content)

    tables_text = ""
    for t in section.get("tables", []):
        entries = t.get("entries", [])
        if entries:
            tables_text += "\n" + "\n".join(f"  - {e}" for e in entries)

    return f"## {heading}\n{content}\n{tables_text}".strip()


def _extract_from_section(section_text: str, doc_title: str, section_heading: str, prev_summary: str = "") -> tuple[list[dict], dict]:
    """对单个章节调用 LLM 提取规则。返回 (rules, stats)。"""
    import time

    client = get_llm_client()
    model = get_model_name()

    context_hint = ""
    if prev_summary:
        context_hint = f"\n\n【上文摘要】前一章节的关键信息：{prev_summary}\n\n"

    user_prompt = (
        f"以下是文档「{doc_title}」中「{section_heading}」章节的内容。"
        f"请提取其中的业务规则，使用 save_extracted_rules 工具输出。"
        f"如果该章节没有可提取的业务规则，调用工具传入空数组。"
        f"{context_hint}\n"
        f"{section_text}"
    )

    stats = {"section": section_heading, "chars": len(section_text), "rules": 0, "elapsed": 0, "input_tokens": 0, "output_tokens": 0, "error": None}
    start = time.time()

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            tools=[RULE_EXTRACTION_TOOL],
            tool_choice={"type": "function", "function": {"name": "save_extracted_rules"}},
        )

        stats["elapsed"] = round(time.time() - start, 2)
        usage = response.usage
        stats["input_tokens"] = usage.prompt_tokens if usage else 0
        stats["output_tokens"] = usage.completion_tokens if usage else 0

        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            args = tool_call.function.arguments
            # 处理 arguments 可能是 dict 或 str
            if isinstance(args, str):
                args = json.loads(args)
            rules = args.get("rules", [])
            for r in rules:
                if not r.get("source_section"):
                    r["source_section"] = section_heading
            stats["rules"] = len(rules)
            return rules, stats

        return [], stats

    except Exception as e:
        stats["elapsed"] = round(time.time() - start, 2)
        stats["error"] = str(e)[:500]
        logger.warning("章节「%s」提取失败: %s", section_heading, e)
        return [], stats


def extract_rules_from_sections(sections: list[dict], title: str) -> tuple[list[dict], list[dict]]:
    """主入口：分段提取 + 合并。返回 (rules, extraction_stats)。"""
    if not settings.qwen_api_key and not settings.anthropic_api_key:
        raise RuntimeError("未配置 API Key。请设置 QWEN_API_KEY 或 ANTHROPIC_API_KEY。")

    all_rules = []
    all_stats = []
    prev_summary = ""
    for section in sections:
        section_text = _build_section_text(section)
        heading = section.get("heading", "未知章节")

        if len(section_text) < 30:
            continue

        skip_keywords = ["修订记录", "目录", "版本历史", "变更记录", "文档信息"]
        if any(kw in heading for kw in skip_keywords):
            continue

        logger.info("提取章节: %s (%d chars)", heading, len(section_text))
        rules, stats = _extract_from_section(section_text, title, heading, prev_summary)
        all_rules.extend(rules)
        all_stats.append(stats)
        logger.info("  -> 提取 %d 条规则 (%.1fs, %d+%d tokens)", len(rules), stats["elapsed"], stats["input_tokens"], stats["output_tokens"])

        prev_summary = f"「{heading}」"
        if rules:
            rule_texts = [r.get("rule_text", "")[:60] for r in rules[:3]]
            prev_summary += f"提取了 {len(rules)} 条规则，包括：{'；'.join(rule_texts)}"
        else:
            content_preview = section_text[:100].replace("\n", " ")
            prev_summary += f"内容概要：{content_preview}"

    logger.info("总计提取 %d 条规则（去重前）", len(all_rules))
    return all_rules, all_stats


# ==================== 二次校验 ====================

VERIFY_TOOL = {
    "type": "function",
    "function": {
        "name": "save_verification",
        "description": "保存规则校验结果",
        "parameters": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer", "description": "规则序号（从0开始）"},
                            "valid": {"type": "boolean", "description": "该规则是否准确"},
                            "issue": {"type": "string", "description": "如果不准确，说明问题"},
                            "corrected_text": {"type": "string", "description": "如果需要修正，给出修正后的规则文本"},
                        },
                        "required": ["index", "valid"],
                    },
                },
                "missed_rules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule_text": {"type": "string"},
                            "category": {"type": "string"},
                            "source_section": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": ["rule_text"],
                    },
                    "description": "原文中存在但被遗漏的规则",
                },
            },
            "required": ["results"],
        },
    },
}


def verify_extracted_rules(rules: list[dict], sections: list[dict], title: str) -> dict:
    """二次校验：用 LLM 验证提取结果的准确性，发现遗漏。"""
    if not rules:
        return {"verified": [], "issues": [], "missed": []}

    client = get_llm_client()
    model = get_model_name()

    # 构建原文摘要（取前 8000 字符避免太长）
    raw_parts = []
    for sec in sections:
        text = _build_section_text(sec)
        if text and len(text) > 30:
            raw_parts.append(text)
    raw_text = "\n\n".join(raw_parts)[:8000]

    # 构建规则列表
    rules_text = "\n".join(
        f"[{i}] {r.get('rule_text', '')} (分类: {r.get('category', '?')}, 置信度: {r.get('confidence', '?')})"
        for i, r in enumerate(rules)
    )

    prompt = (
        f"你是业务规则校验专家。以下是从文档「{title}」中提取的规则列表，以及原文摘要。\n\n"
        f"请逐条校验：\n"
        f"1. 规则是否准确反映了原文含义（不是幻觉）\n"
        f"2. 规则是否完整（没有丢失关键条件或数值）\n"
        f"3. 原文中是否有被遗漏的重要业务规则\n\n"
        f"=== 提取的规则 ===\n{rules_text}\n\n"
        f"=== 原文摘要 ===\n{raw_text}\n\n"
        f"使用 save_verification 工具输出校验结果。"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            tools=[VERIFY_TOOL],
            tool_choice={"type": "function", "function": {"name": "save_verification"}},
        )

        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            args = tool_call.function.arguments
            if isinstance(args, str):
                args = json.loads(args)
            results = args.get("results", [])
            missed = args.get("missed_rules", [])

            issues = []
            for r in results:
                idx = r.get("index", -1)
                if not r.get("valid", True) and 0 <= idx < len(rules):
                    rules[idx]["_verification_issue"] = r.get("issue", "")
                    if r.get("corrected_text"):
                        rules[idx]["_corrected_text"] = r["corrected_text"]
                    issues.append({"index": idx, "issue": r.get("issue", ""), "corrected_text": r.get("corrected_text")})

            return {"verified": results, "issues": issues, "missed": missed}

        return {"verified": [], "issues": [], "missed": []}

    except Exception as e:
        logger.warning("二次校验失败: %s", e)
        return {"verified": [], "issues": [], "missed": []}