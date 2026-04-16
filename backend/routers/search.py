"""
search.py — 语义搜索 API，基于 pgvector 的向量检索
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.database import get_db
from models.rule import Rule
from extractors.embedder import get_embedding

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/")
async def semantic_search(
    q: str = Query(..., min_length=1, description="搜索查询"),
    limit: int = Query(10, ge=1, le=50),
    domain: str = Query(None),
    db: Session = Depends(get_db),
):
    """语义搜索规则，返回最相关的 top-k 结果"""
    query_embedding = await get_embedding(q)

    # Build pgvector cosine distance query
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = """
        SELECT id, prd_id, domain, category, rule_text, source_section,
               risk_score, status, hit_count, params,
               (embedding <=> CAST(:embedding AS vector)) AS distance
        FROM rules
        WHERE embedding IS NOT NULL
    """
    params = {"embedding": embedding_str, "limit": limit}

    if domain:
        sql += " AND domain = :domain"
        params["domain"] = domain

    sql += " ORDER BY distance ASC LIMIT :limit"

    results = db.execute(text(sql), params).fetchall()

    # Increment hit_count for returned rules
    rule_ids = [r.id for r in results]
    if rule_ids:
        placeholders = ", ".join(f":id_{i}" for i in range(len(rule_ids)))
        id_params = {f"id_{i}": rid for i, rid in enumerate(rule_ids)}
        id_params["now"] = datetime.now(timezone.utc)
        db.execute(
            text(f"UPDATE rules SET hit_count = hit_count + 1, last_hit_at = :now WHERE id IN ({placeholders})"),
            id_params,
        )
        db.commit()

    return [
        {
            "id": r.id,
            "prd_id": r.prd_id,
            "domain": r.domain,
            "category": r.category,
            "rule_text": r.rule_text,
            "source_section": r.source_section,
            "risk_score": r.risk_score,
            "status": r.status,
            "hit_count": r.hit_count,
            "params": json.loads(r.params) if isinstance(r.params, str) else r.params,
            "relevance": round(1 - r.distance, 4),
        }
        for r in results
    ]


@router.post("/embed-all")
async def embed_all_rules(db: Session = Depends(get_db)):
    """为所有缺少 embedding 的规则生成向量（批量处理）"""
    from extractors.embedder import get_embeddings_batch, _build_rule_text

    rules = db.query(Rule).filter(Rule.embedding.is_(None)).all()
    if not rules:
        return {"embedded": 0, "total_without_embedding": 0}

    texts = [_build_rule_text(r) for r in rules]
    embeddings = await get_embeddings_batch(texts)

    for rule, emb in zip(rules, embeddings):
        rule.embedding = emb

    db.commit()
    return {"embedded": len(rules), "total_without_embedding": 0}
