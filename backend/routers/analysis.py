from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import insert

from db.database import get_db
from config import settings
from models import PRD, Rule, AuditLog, ConflictRecord, ExtractionLog, rule_sources

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


@router.post("/embed/{prd_id}")
async def embed_prd_rules(prd_id: int, db: Session = Depends(get_db)):
    """为指定 PRD 提取的规则生成 embedding 向量。"""
    prd = db.query(PRD).filter(PRD.id == prd_id).first()
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")

    from extractors.embedder import get_embeddings_batch, _build_rule_text

    rules = db.query(Rule).filter(Rule.prd_id == prd_id, Rule.embedding.is_(None)).all()
    if not rules:
        prd.status = "embedded"
        db.commit()
        return {"embedded": 0, "prd_id": prd_id, "message": "所有规则已有向量"}

    texts = [_build_rule_text(r) for r in rules]
    embeddings = await get_embeddings_batch(texts)

    for rule, emb in zip(rules, embeddings):
        rule.embedding = emb

    prd.status = "embedded"
    db.commit()
    return {"embedded": len(rules), "prd_id": prd_id, "status": "embedded"}


@router.post("/extract/{prd_id}")
async def extract_rules(prd_id: int, vision_provider: str = "off", db: Session = Depends(get_db)):
    prd = db.query(PRD).filter(PRD.id == prd_id).first()
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    if not prd.parsed_sections:
        raise HTTPException(status_code=400, detail="PRD not yet parsed")

    from extractors.llm_extractor import extract_rules_from_sections, verify_extracted_rules

    rules_data, extraction_stats = extract_rules_from_sections(prd.parsed_sections, prd.title)

    # 保存提取日志
    for st in extraction_stats:
        log = ExtractionLog(
            prd_id=prd.id,
            section_heading=st["section"],
            section_chars=st["chars"],
            rules_extracted=st["rules"],
            elapsed_seconds=st["elapsed"],
            input_tokens=st["input_tokens"],
            output_tokens=st["output_tokens"],
            error=st["error"],
        )
        db.add(log)

    # 图片识别提取
    vision_rules_count = 0
    if vision_provider in ("claude", "qwen") and prd.filename.lower().endswith((".docx", ".doc")):
        try:
            from extractors.vision_extractor import extract_images_from_docx, extract_from_image
            import os
            filepath = os.path.join(settings.upload_dir, prd.filename)
            image_paths = extract_images_from_docx(filepath, settings.upload_dir)
            for img_path in image_paths:
                img_rules = await extract_from_image(img_path, prd.title, vision_provider)
                rules_data.extend(img_rules)
                vision_rules_count += len(img_rules)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("图片识别失败: %s", e)

    # 二次校验
    verification = {"issues": [], "missed": []}
    try:
        verification = verify_extracted_rules(rules_data, prd.parsed_sections, prd.title)

        # 把遗漏的规则补进来
        for missed in verification.get("missed", []):
            if missed.get("rule_text"):
                missed.setdefault("confidence", 0.5)
                missed.setdefault("category", "业务逻辑")
                missed.setdefault("source_section", "二次校验补充")
                rules_data.append(missed)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("二次校验失败: %s", e)

    # 保存规则并向量化
    created = []
    low_confidence = 0
    for rd in rules_data:
        confidence = rd.get("confidence", 0.5)
        rule = Rule(
            prd_id=prd.id,
            domain=rd.get("domain", prd.domain),
            category=rd.get("category"),
            rule_text=rd["rule_text"],
            structured_logic=rd.get("structured_logic"),
            params=rd.get("params"),
            involves_roles=rd.get("involves_roles"),
            compliance_notes=rd.get("compliance_notes"),
            source_section=rd.get("source_section"),
            risk_score=0,
            status="draft" if confidence >= 0.6 else "draft",
        )
        db.add(rule)
        db.flush()
        db.execute(insert(rule_sources).values(rule_id=rule.id, prd_id=prd.id))
        created.append((rule, confidence))
        if confidence < 0.6:
            low_confidence += 1

    # 自动向量化
    embedded_count = 0
    dedup_count = 0
    merged_count = 0
    if created:
        try:
            from extractors.embedder import get_embeddings_batch, _build_rule_text
            rules_only = [r for r, _ in created]
            texts = [_build_rule_text(r) for r in rules_only]
            embeddings = await get_embeddings_batch(texts)
            for rule, emb in zip(rules_only, embeddings):
                rule.embedding = emb
            embedded_count = len(rules_only)

            # 去重：同一批次内相似度 > 0.95 的标记为 deprecated
            import numpy as np
            emb_matrix = np.array(embeddings)
            norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normalized = emb_matrix / norms
            seen_deprecated = set()
            for i in range(len(rules_only)):
                if i in seen_deprecated:
                    continue
                for j in range(i + 1, len(rules_only)):
                    if j in seen_deprecated:
                        continue
                    sim = float(np.dot(normalized[i], normalized[j]))
                    if sim > 0.95:
                        # 保留置信度高的，废弃低的
                        ci = created[i][1]
                        cj = created[j][1]
                        if ci >= cj:
                            rules_only[j].status = "deprecated"
                            seen_deprecated.add(j)
                        else:
                            rules_only[i].status = "deprecated"
                            seen_deprecated.add(i)
                            break
            dedup_count = len(seen_deprecated)

            # 跨文档合并：和已有规则比较
            existing_rules = db.query(Rule).filter(
                Rule.prd_id != prd.id,
                Rule.status != "deprecated",
                Rule.embedding.isnot(None),
            ).all()

            merged_count = 0
            if existing_rules:
                import numpy as np
                existing_embs = np.array([r.embedding for r in existing_rules])
                existing_norms = np.linalg.norm(existing_embs, axis=1, keepdims=True)
                existing_norms[existing_norms == 0] = 1
                existing_normalized = existing_embs / existing_norms

                for i, new_rule in enumerate(rules_only):
                    if i in seen_deprecated:
                        continue
                    new_emb = np.array(embeddings[i])
                    new_norm = np.linalg.norm(new_emb)
                    if new_norm == 0:
                        continue
                    new_normalized = new_emb / new_norm
                    sims = existing_normalized @ new_normalized
                    max_idx = int(np.argmax(sims))
                    max_sim = float(sims[max_idx])

                    if max_sim > 0.93:
                        # 高度相似 → 关联到同一规则的来源文档，标记新规则为 deprecated
                        existing_rule = existing_rules[max_idx]
                        # 把当前 PRD 加到已有规则的来源文档
                        try:
                            db.execute(insert(rule_sources).values(rule_id=existing_rule.id, prd_id=prd.id))
                        except Exception:
                            pass  # 可能已存在
                        new_rule.status = "deprecated"
                        merged_count += 1

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("自动向量化/去重失败: %s", e)

    prd.status = "extracted"
    db.commit()
    return {
        "status": "extracted",
        "rules_count": len(created),
        "embedded_count": embedded_count,
        "dedup_count": dedup_count,
        "merged_count": merged_count,
        "low_confidence_count": low_confidence,
        "verification_issues": len(verification.get("issues", [])),
        "missed_rules_added": len(verification.get("missed", [])),
        "vision_rules_count": vision_rules_count,
        "vision_provider": vision_provider,
        "prd_id": prd.id,
    }


@router.get("/extraction-logs/{prd_id}")
def get_extraction_logs(prd_id: int, db: Session = Depends(get_db)):
    """查询某个 PRD 的提取过程日志。"""
    logs = db.query(ExtractionLog).filter(ExtractionLog.prd_id == prd_id).order_by(ExtractionLog.created_at).all()
    total_tokens = sum((l.input_tokens or 0) + (l.output_tokens or 0) for l in logs)
    total_time = sum(l.elapsed_seconds or 0 for l in logs)
    return {
        "prd_id": prd_id,
        "sections": [
            {
                "heading": l.section_heading,
                "chars": l.section_chars,
                "rules_extracted": l.rules_extracted,
                "elapsed_seconds": l.elapsed_seconds,
                "input_tokens": l.input_tokens,
                "output_tokens": l.output_tokens,
                "error": l.error,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
        "summary": {
            "total_sections": len(logs),
            "total_rules": sum(l.rules_extracted or 0 for l in logs),
            "total_tokens": total_tokens,
            "total_time": round(total_time, 2),
            "errors": sum(1 for l in logs if l.error),
        },
    }
def compare_rules(
    category: str = None,
    domain: str = None,
    db: Session = Depends(get_db),
):
    from analyzers.comparator import compare_rules_across_prds

    query = db.query(Rule)
    if category:
        query = query.filter(Rule.category == category)
    if domain:
        query = query.filter(Rule.domain == domain)

    rules = query.all()
    if len(rules) < 2:
        return {"conflicts": [], "message": "Need at least 2 rules to compare"}

    result = compare_rules_across_prds(rules)
    return result


@router.get("/risks")
def risk_overview(db: Session = Depends(get_db)):
    from analyzers.risk_scorer import calculate_risk_overview

    rules = db.query(Rule).all()
    return calculate_risk_overview(rules)


@router.post("/detect-conflicts")
async def detect_conflicts(
    domain: str = None,
    method: str = "keyword",
    db: Session = Depends(get_db),
):
    """主动检测规则冲突，支持三种检测方法：keyword / embedding / llm。"""
    import time

    if method not in ("keyword", "embedding", "llm"):
        raise HTTPException(status_code=400, detail="method 必须为 keyword / embedding / llm")

    query = db.query(Rule).filter(Rule.status != "deprecated")
    if domain:
        query = query.filter(Rule.domain == domain)

    rules = query.all()
    if len(rules) < 2:
        return {"conflicts": [], "total_compared": len(rules), "method": method, "message": "规则不足，无法检测冲突"}

    start = time.time()

    if method == "keyword":
        from analyzers.comparator import compare_rules_keyword
        result = compare_rules_keyword(rules)
    elif method == "embedding":
        from analyzers.comparator import compare_rules_embedding
        result = await compare_rules_embedding(rules, db)
    else:  # llm
        from analyzers.comparator import compare_rules_llm
        result = await compare_rules_llm(rules)

    elapsed = round(time.time() - start, 2)
    result["elapsed_seconds"] = elapsed

    # 保存检测记录
    record = ConflictRecord(
        method=method,
        total_compared=result.get("total_compared", len(rules)),
        conflicts_count=len(result.get("conflicts", [])),
        conflicts=result.get("conflicts", []),
        elapsed_seconds=elapsed,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    result["record_id"] = record.id

    return result


@router.get("/conflict-records")
def list_conflict_records(limit: int = 20, db: Session = Depends(get_db)):
    """查询历史冲突检测记录。"""
    records = db.query(ConflictRecord).order_by(ConflictRecord.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "method": r.method,
            "total_compared": r.total_compared,
            "conflicts_count": r.conflicts_count,
            "conflicts": r.conflicts,
            "elapsed_seconds": r.elapsed_seconds,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
