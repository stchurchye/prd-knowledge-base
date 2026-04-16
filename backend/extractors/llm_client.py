"""
llm_client.py — 统一 LLM 调用客户端
支持: 1) 百炼 Qwen (OpenAI 兼容格式)  2) Anthropic Claude (备用)
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_llm_client() -> OpenAI:
    """获取 LLM 客户端（优先百炼 Qwen）。"""
    global _client
    if _client is not None:
        return _client

    if settings.qwen_api_key:
        logger.info("使用百炼 API (模型: %s)", settings.qwen_model)
        _client = OpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
        )
        return _client

    if settings.anthropic_api_key:
        logger.info("使用 Anthropic API (备用)")
        import anthropic
        kwargs = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        # 返回一个包装器，让 Anthropic 客户端也能用 OpenAI 风格调用
        _client = AnthropicWrapper(anthropic.Anthropic(**kwargs))
        return _client

    raise RuntimeError("未配置 LLM API Key。请设置 QWEN_API_KEY 或 ANTHROPIC_API_KEY")


def get_model_name() -> str:
    """获取当前使用的模型名称。"""
    if settings.qwen_api_key:
        return settings.qwen_model
    return "claude-sonnet-4-20250514"


class AnthropicWrapper:
    """Anthropic 客户端包装器，模拟 OpenAI 接口风格（备用）。"""

    def __init__(self, anthropic_client):
        self._client = anthropic_client

    def chat.completions.create(self, **kwargs):
        """模拟 OpenAI 的 chat.completions.create 接口。"""
        # 这里需要转换 OpenAI 格式到 Anthropic 格式
        # 简化实现：只处理基本场景
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "claude-sonnet-4-20250514")
        max_tokens = kwargs.get("max_tokens", 4096)
        tools = kwargs.get("tools", [])

        # 分离 system 消息
        system = ""
        user_messages = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content", "")
            else:
                user_messages.append(m)

        # 转换 tools 格式
        anthropic_tools = []
        for t in tools:
            anthropic_tools.append({
                "name": t.get("function", {}).get("name", ""),
                "description": t.get("function", {}).get("description", ""),
                "input_schema": t.get("function", {}).get("parameters", {}),
            })

        # 调用 Anthropic
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=anthropic_tools,
            messages=user_messages,
        )

        # 转换响应格式
        return AnthropicResponseWrapper(response)


class AnthropicResponseWrapper:
    """Anthropic 响应包装器。"""

    def __init__(self, anthropic_response):
        self._response = anthropic_response
        self.choices = [AnthropicChoiceWrapper(anthropic_response)]
        self.usage = anthropic_response.usage


class AnthropicChoiceWrapper:
    """Anthropic 选择项包装器。"""

    def __init__(self, response):
        self._response = response
        self.message = AnthropicMessageWrapper(response)


class AnthropicMessageWrapper:
    """Anthropic 消息包装器。"""

    def __init__(self, response):
        self._response = response
        self.content = response.content
        self.tool_calls = []

        # 转换 tool_use 到 tool_calls
        for block in response.content:
            if hasattr(block, "type") and block.type == "tool_use":
                self.tool_calls.append({
                    "id": block.id,
                    "function": {
                        "name": block.name,
                        "arguments": block.input,
                    },
                })