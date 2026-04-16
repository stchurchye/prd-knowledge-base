"""
embedder.py — 生成文本 embedding 用于语义检索
优先级: 1) 本地 sentence-transformers (BAAI/bge-base-zh-v1.5)
        2) Voyage AI API (需 VOYAGE_API_KEY)
        3) hash 伪向量 (仅兜底)
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Any

import httpx
from config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768  # bge-base-zh-v1.5 输出维度
LOCAL_MODEL_NAME = "BAAI/bge-base-zh-v1.5"
VOYAGE_MODEL = "voyage-3-lite"
VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_BATCH_SIZE = 50

# Lazy-loaded singletons
_local_model: Any = None
_local_model_failed = False
_http_client: httpx.AsyncClient | None = None


def _load_local_model():
    """Load sentence-transformers model (lazy, first call only)."""
    global _local_model, _local_model_failed
    if _local_model is not None or _local_model_failed:
        return _local_model
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading local embedding model: %s ...", LOCAL_MODEL_NAME)
        _local_model = SentenceTransformer(LOCAL_MODEL_NAME)
        logger.info("Local embedding model loaded successfully.")
        return _local_model
    except Exception as e:
        _local_model_failed = True
        logger.warning("Failed to load local model: %s — will try Voyage AI or hash fallback", e)
        return None


def _local_embedding(text: str) -> list[float]:
    """Generate embedding using local sentence-transformers model."""
    model = _load_local_model()
    if model is None:
        raise RuntimeError("Local model not available")
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def _local_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch using local model."""
    model = _load_local_model()
    if model is None:
        raise RuntimeError("Local model not available")
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=64)
    return vecs.tolist()


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30)
    return _http_client


async def get_embedding(text: str) -> list[float]:
    """Generate embedding for text. Tries local model → Voyage AI → hash fallback."""
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIM

    # 1) Local model (best quality for Chinese, no API key needed)
    try:
        return _local_embedding(text)
    except RuntimeError:
        pass

    # 2) Voyage AI
    if settings.voyage_api_key:
        results = await _voyage_embedding_batch([text])
        return results[0]

    # 3) Hash fallback (not semantically meaningful)
    logger.warning("Using hash fallback — semantic search quality will be poor")
    return _hash_embedding(text)


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    if not texts:
        return []

    # 1) Local model
    try:
        return _local_embeddings_batch(texts)
    except RuntimeError:
        pass

    # 2) Voyage AI
    if settings.voyage_api_key:
        results: list[list[float]] = []
        for i in range(0, len(texts), VOYAGE_BATCH_SIZE):
            batch = texts[i:i + VOYAGE_BATCH_SIZE]
            batch_results = await _voyage_embedding_batch(batch)
            results.extend(batch_results)
        return results

    # 3) Hash fallback
    return [_hash_embedding(t) if t and t.strip() else [0.0] * EMBEDDING_DIM for t in texts]


async def _voyage_embedding_batch(texts: list[str]) -> list[list[float]]:
    """Call Voyage AI embedding API for a batch of texts."""
    client = await _get_client()
    resp = await client.post(
        VOYAGE_API_URL,
        headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
        json={"input": texts, "model": VOYAGE_MODEL},
    )
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def _hash_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic pseudo-embedding — last resort fallback only."""
    vector = []
    for i in range(dim):
        seed = f"{text}:{i}".encode("utf-8")
        h = hashlib.md5(seed).hexdigest()
        val = (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1
        vector.append(val)
    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector


def _build_rule_text(rule) -> str:
    """Build embedding text from rule fields."""
    parts = [rule.rule_text or ""]
    if rule.domain:
        parts.append(f"领域:{rule.domain}")
    if rule.category:
        parts.append(f"分类:{rule.category}")
    if rule.source_section:
        parts.append(f"来源:{rule.source_section}")
    return " ".join(parts)


async def embed_rule_text(rule) -> list[float]:
    """Build embedding text from rule fields and generate embedding."""
    return await get_embedding(_build_rule_text(rule))
