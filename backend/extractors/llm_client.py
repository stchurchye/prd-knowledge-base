"""llm_client.py — 统一 LLM 调用客户端"""
from __future__ import annotations

import logging
from config import settings
from openai import OpenAI

logger = logging.getLogger(__name__)
_client: OpenAI | None = None

def get_llm_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    if not settings.qwen_api_key:
        raise RuntimeError("未配置 QWEN_API_KEY")
    logger.info("使用百炼 API")
    _client = OpenAI(api_key=settings.qwen_api_key, base_url=settings.qwen_base_url)
    return _client 
def get_model_name() -> str:
    return settings.qwen_model
