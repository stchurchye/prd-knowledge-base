"""
vision_extractor.py — 从文档图片中提取业务规则
支持 Claude Vision 和 Qwen-VL 两种模型
"""
from __future__ import annotations

import base64
import logging
import os
from config import settings

logger = logging.getLogger(__name__)

VISION_PROMPT = """你是业务规则提取专家。这张图片来自 PRD 文档「{title}」。
请分析图片内容（可能是流程图、状态机、表格截图、架构图等），提取其中的业务规则。

每条规则输出为 JSON 对象，包含：
- rule_text: 规则的完整自然语言描述
- category: 分类（资金流转规则/角色权限模型/状态机流程/数值参数阈值/合规约束/业务逻辑）
- source_section: "图片识别"
- confidence: 置信度 0-1

如果图片中没有可提取的业务规则（如纯 UI 截图、装饰图），返回空数组 []。
只输出 JSON 数组，不要其他内容。"""


def _read_image_base64(filepath: str) -> tuple[str, str]:
    """读取图片并返回 (base64_data, media_type)。"""
    ext = os.path.splitext(filepath)[1].lower()
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_types.get(ext, "image/png")
    with open(filepath, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


async def extract_from_image_claude(filepath: str, title: str) -> list[dict]:
    """用 Claude Vision 分析图片。"""
    import anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("未配置 ANTHROPIC_API_KEY")

    data, media_type = _read_image_base64(filepath)

    client_kwargs = {"api_key": settings.anthropic_api_key}
    if settings.anthropic_base_url:
        client_kwargs["base_url"] = settings.anthropic_base_url

    client = anthropic.Anthropic(**client_kwargs)
    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                {"type": "text", "text": VISION_PROMPT.format(title=title)},
            ],
        }],
    )

    return _parse_json_response(message.content[0].text, "claude", filepath)


async def extract_from_image_qwen(filepath: str, title: str) -> list[dict]:
    """用 Qwen-VL 分析图片。"""
    import httpx

    if not settings.qwen_api_key:
        raise RuntimeError("未配置 QWEN_API_KEY")

    data, media_type = _read_image_base64(filepath)
    data_url = f"data:{media_type};base64,{data}"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.qwen_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
            json={
                "model": settings.qwen_vl_model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": VISION_PROMPT.format(title=title)},
                    ],
                }],
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        result = resp.json()
        text = result["choices"][0]["message"]["content"]

    return _parse_json_response(text, "qwen", filepath)


def _parse_json_response(text: str, provider: str, filepath: str) -> list[dict]:
    """解析 LLM 返回的 JSON 数组。"""
    import json

    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]

    try:
        rules = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            rules = json.loads(text[start:end])
        else:
            logger.warning("图片 %s (%s) 返回无法解析: %s", filepath, provider, text[:200])
            rules = []

    for r in rules:
        r.setdefault("source_section", "图片识别")
        r.setdefault("confidence", 0.6)
        r["_vision_provider"] = provider

    return rules


async def extract_from_image(filepath: str, title: str, provider: str = "claude") -> list[dict]:
    """统一入口。"""
    if provider == "qwen":
        return await extract_from_image_qwen(filepath, title)
    return await extract_from_image_claude(filepath, title)


def extract_images_from_docx(filepath: str, upload_dir: str) -> list[str]:
    """从 docx 文件中提取所有图片，保存到 upload_dir，返回路径列表。"""
    from docx import Document

    doc = Document(filepath)
    image_paths = []
    img_dir = os.path.join(upload_dir, "_images")
    os.makedirs(img_dir, exist_ok=True)

    for i, rel in enumerate(doc.part.rels.values()):
        if "image" in rel.reltype:
            try:
                img_data = rel.target_part.blob
                ext = os.path.splitext(rel.target_ref)[1] or ".png"
                basename = os.path.splitext(os.path.basename(filepath))[0]
                img_path = os.path.join(img_dir, f"{basename}_img{i}{ext}")
                with open(img_path, "wb") as f:
                    f.write(img_data)
                image_paths.append(img_path)
            except Exception as e:
                logger.warning("提取图片失败: %s", e)

    return image_paths
