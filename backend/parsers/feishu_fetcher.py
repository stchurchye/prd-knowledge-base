"""
feishu_fetcher.py — 通过飞书开放 API 获取文档内容
支持飞书知识库 (wiki) 和云文档 (docx) 两种链接格式
"""
from __future__ import annotations

import re
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"
_tenant_token: str | None = None


async def _get_tenant_token() -> str:
    """获取 tenant_access_token（有效期 2 小时，这里简单每次获取）。"""
    global _tenant_token
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        raise RuntimeError("未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，请在 .env 中设置")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书认证失败: {data.get('msg')}")
        _tenant_token = data["tenant_access_token"]
        return _tenant_token


def _parse_feishu_url(url: str) -> dict:
    """从飞书 URL 中解析文档类型和 token。

    支持格式:
      - https://xxx.feishu.cn/wiki/{token}
      - https://xxx.feishu.cn/docx/{token}
      - https://xxx.feishu.cn/docs/{token}
    """
    patterns = [
        (r"feishu\.cn/wiki/(\w+)", "wiki"),
        (r"feishu\.cn/docx/(\w+)", "docx"),
        (r"feishu\.cn/docs/(\w+)", "docx"),
    ]
    for pattern, doc_type in patterns:
        m = re.search(pattern, url)
        if m:
            return {"token": m.group(1), "type": doc_type}
    raise ValueError(f"无法解析飞书链接: {url}")


async def _get_wiki_node(token: str, headers: dict) -> str:
    """wiki token → 实际 document obj_token。"""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/wiki/v2/spaces/get_node",
            params={"token": token},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取知识库节点失败: {data.get('msg')}")
        node = data["data"]["node"]
        return node["obj_token"]


async def _get_document_blocks(doc_token: str, headers: dict) -> list[dict]:
    """获取文档所有 block，自动翻页。"""
    blocks = []
    page_token = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict = {"document_id": doc_token, "page_size": 500}
            if page_token:
                params["page_token"] = page_token
            resp = await client.get(
                f"{FEISHU_BASE}/docx/v1/documents/{doc_token}/blocks",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"获取文档内容失败: {data.get('msg')}")
            items = data.get("data", {}).get("items", [])
            blocks.extend(items)
            if not data.get("data", {}).get("has_more"):
                break
            page_token = data["data"].get("page_token")
    return blocks


def _blocks_to_markdown(blocks: list[dict]) -> tuple[str, str]:
    """将飞书 block 列表转为 markdown 文本，返回 (title, content)。"""
    lines = []
    title = ""

    for block in blocks:
        block_type = block.get("block_type")

        # 提取文本内容
        def extract_text(elements: list[dict] | None) -> str:
            if not elements:
                return ""
            parts = []
            for el in elements:
                text_run = el.get("text_run")
                if text_run:
                    parts.append(text_run.get("content", ""))
            return "".join(parts)

        if block_type == 1:  # page title
            body = block.get("page", {})
            text_elements = body.get("elements", [])
            title = extract_text(text_elements) or "飞书文档"

        elif block_type == 2:  # text
            body = block.get("text", {})
            text = extract_text(body.get("elements", []))
            if text.strip():
                lines.append(text)

        elif block_type == 3:  # heading1
            body = block.get("heading1", {})
            text = extract_text(body.get("elements", []))
            if text.strip():
                lines.append(f"# {text}")

        elif block_type == 4:  # heading2
            body = block.get("heading2", {})
            text = extract_text(body.get("elements", []))
            if text.strip():
                lines.append(f"## {text}")

        elif block_type == 5:  # heading3
            body = block.get("heading3", {})
            text = extract_text(body.get("elements", []))
            if text.strip():
                lines.append(f"### {text}")

        elif block_type == 6:  # heading4-9
            body = block.get("heading4", {}) or block.get("heading5", {})
            text = extract_text(body.get("elements", []))
            if text.strip():
                lines.append(f"#### {text}")

        elif block_type == 12:  # bullet
            body = block.get("bullet", {})
            text = extract_text(body.get("elements", []))
            if text.strip():
                lines.append(f"- {text}")

        elif block_type == 13:  # ordered
            body = block.get("ordered", {})
            text = extract_text(body.get("elements", []))
            if text.strip():
                lines.append(f"1. {text}")

        elif block_type == 14:  # code
            body = block.get("code", {})
            text = extract_text(body.get("elements", []))
            if text.strip():
                lines.append(f"```\n{text}\n```")

        elif block_type == 22:  # todo
            body = block.get("todo", {})
            text = extract_text(body.get("elements", []))
            done = body.get("style", {}).get("done", False)
            prefix = "[x]" if done else "[ ]"
            if text.strip():
                lines.append(f"- {prefix} {text}")

    content = "\n\n".join(lines)
    return title or "飞书文档", content


async def fetch_feishu_document(url: str) -> dict:
    """主入口：从飞书 URL 获取文档内容，返回 {title, content, url}。"""
    parsed = _parse_feishu_url(url)
    token = await _get_tenant_token()
    headers = {"Authorization": f"Bearer {token}"}

    doc_token = parsed["token"]
    if parsed["type"] == "wiki":
        doc_token = await _get_wiki_node(parsed["token"], headers)

    blocks = await _get_document_blocks(doc_token, headers)
    title, content = _blocks_to_markdown(blocks)

    if not content.strip():
        raise RuntimeError("文档内容为空，可能需要在飞书应用权限中添加该文档的访问权限")

    return {"title": title, "content": content, "url": url}
