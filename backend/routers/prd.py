import hashlib
import os
import shutil
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from models import PRD

router = APIRouter(prefix="/api/prds", tags=["PRDs"])

os.makedirs(settings.upload_dir, exist_ok=True)


class PRDOut(BaseModel):
    id: int
    title: str
    filename: str
    version: Optional[str] = None
    author: Optional[str] = None
    publish_date: Optional[date] = None
    domain: Optional[str] = None
    doc_type: str = "prd"
    status: str
    sections_count: Optional[int] = None
    rules_count: Optional[int] = None
    process_elapsed: Optional[float] = None
    total_tokens: Optional[int] = None
    vision_provider: Optional[str] = None
    llm_model: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[PRDOut])
def list_prds(doc_type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(PRD)
    if doc_type:
        query = query.filter(PRD.doc_type == doc_type)
    return query.order_by(PRD.created_at.desc()).all()


@router.get("/{prd_id}", response_model=PRDOut)
def get_prd(prd_id: int, db: Session = Depends(get_db)):
    prd = db.query(PRD).filter(PRD.id == prd_id).first()
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    return prd


ALLOWED_EXTENSIONS = (".docx", ".doc", ".md", ".markdown")


@router.post("/upload", response_model=PRDOut)
async def upload_prd(file: UploadFile = File(...), doc_type: str = "prd", db: Session = Depends(get_db)):
    if not any(file.filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="支持 .docx、.doc、.md 格式文件")

    # Sanitize filename to prevent path traversal
    safe_name = os.path.basename(file.filename)
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Read file content and compute MD5 for dedup
    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()

    existing = db.query(PRD).filter(PRD.file_hash == file_hash).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"文件已存在：「{existing.title}」(ID: {existing.id})，请勿重复上传",
        )

    # Add unique prefix to avoid overwriting existing files
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    filepath = os.path.join(settings.upload_dir, unique_name)
    with open(filepath, "wb") as f:
        f.write(content)

    if doc_type not in ("prd", "tech"):
        doc_type = "prd"

    title = os.path.splitext(safe_name)[0]
    prd = PRD(title=title, filename=unique_name, file_hash=file_hash, doc_type=doc_type, status="uploaded")
    db.add(prd)
    db.commit()
    db.refresh(prd)
    return prd


@router.post("/{prd_id}/parse")
def parse_prd(prd_id: int, db: Session = Depends(get_db)):
    prd = db.query(PRD).filter(PRD.id == prd_id).first()
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")

    filepath = os.path.join(settings.upload_dir, prd.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found on disk")

    if prd.filename.lower().endswith((".md", ".markdown")):
        from parsers.md_parser import parse_markdown
        result = parse_markdown(filepath)
    else:
        from parsers.docx_parser import parse_docx
        result = parse_docx(filepath)
    prd.parsed_sections = result["sections"]
    prd.raw_text = result["raw_text"]
    prd.title = result.get("title", prd.title)
    prd.version = result.get("version")
    prd.author = result.get("author")
    prd.domain = result.get("domain")
    if result.get("publish_date"):
        try:
            # Parser returns strings like "2025-3-17" or "2025/3/17"
            date_str = result["publish_date"].replace("/", "-")
            parts = date_str.split("-")
            prd.publish_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            pass
    prd.status = "parsed"
    db.commit()
    db.refresh(prd)
    return {"status": "parsed", "sections_count": len(result["sections"]), "prd_id": prd.id}


@router.delete("/{prd_id}")
def delete_prd(prd_id: int, db: Session = Depends(get_db)):
    prd = db.query(PRD).filter(PRD.id == prd_id).first()
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    if prd.status in ("parsing", "extracting"):
        raise HTTPException(status_code=400, detail="文档正在处理中，无法删除")
    filepath = os.path.join(settings.upload_dir, prd.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.delete(prd)
    db.commit()
    return {"status": "deleted"}


class ImportURLRequest(BaseModel):
    url: str
    doc_type: str = "prd"


@router.post("/import-url", response_model=PRDOut)
async def import_from_url(req: ImportURLRequest, db: Session = Depends(get_db)):
    """从飞书链接导入文档，自动获取内容并保存为 markdown。"""
    from parsers.feishu_fetcher import fetch_feishu_document

    try:
        doc = await fetch_feishu_document(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # 保存为 md 文件
    content = doc["content"]
    file_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

    existing = db.query(PRD).filter(PRD.file_hash == file_hash).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"文档已存在：「{existing.title}」(ID: {existing.id})",
        )

    safe_title = doc["title"].replace("/", "_").replace("\\", "_")[:80]
    filename = f"{uuid.uuid4().hex[:8]}_{safe_title}.md"
    filepath = os.path.join(settings.upload_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {doc['title']}\n\n{content}")

    if req.doc_type not in ("prd", "tech"):
        req.doc_type = "prd"

    prd = PRD(
        title=doc["title"],
        filename=filename,
        file_hash=file_hash,
        doc_type=req.doc_type,
        status="uploaded",
    )
    db.add(prd)
    db.commit()
    db.refresh(prd)
    return prd


@router.post("/{prd_id}/process")
async def process_prd(prd_id: int, vision_provider: str = "off", db: Session = Depends(get_db)):
    """一键处理：解析 → 提取规则 → 向量化。"""
    import time
    from sqlalchemy import insert as sa_insert
    from models import Rule, ExtractionLog
    from models.rule_source import rule_sources

    prd = db.query(PRD).filter(PRD.id == prd_id).first()
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    if prd.status in ("parsing", "extracting"):
        raise HTTPException(status_code=400, detail="文档正在处理中")

    start_time = time.time()
    result = {"prd_id": prd.id, "sections_count": 0, "rules_count": 0, "embedded_count": 0,
              "dedup_count": 0, "merged_count": 0, "vision_rules_count": 0, "verification_issues": 0,
              "missed_rules_added": 0, "low_confidence_count": 0, "total_tokens": 0}

    prd.error_message = None

    try:
        return await _do_process(prd, vision_provider, db, result, start_time)
    except HTTPException:
        raise
    except Exception as e:
        import logging, traceback
        logging.getLogger(__name__).error("处理文档 %d 失败: %s", prd_id, traceback.format_exc())
        elapsed = round(time.time() - start_time, 2)
        prd.status = "failed"
        prd.error_message = str(e)[:500]
        prd.process_elapsed = elapsed
        db.commit()
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)[:200]}")


async def _do_process(prd, vision_provider, db, result, start_time):
    """实际处理逻辑，抛异常由上层捕获。"""
    import time
    from sqlalchemy import insert as sa_insert
    from models import Rule, ExtractionLog
    from models.rule_source import rule_sources

    # === Step 1: 解析 ===
    prd.status = "parsing"
    db.commit()

    filepath = os.path.join(settings.upload_dir, prd.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found on disk")

    if prd.filename.lower().endswith((".md", ".markdown")):
        from parsers.md_parser import parse_markdown
        parse_result = parse_markdown(filepath)
    else:
        from parsers.docx_parser import parse_docx
        parse_result = parse_docx(filepath)

    prd.parsed_sections = parse_result["sections"]
    prd.raw_text = parse_result["raw_text"]
    prd.title = parse_result.get("title", prd.title)
    prd.version = parse_result.get("version")
    prd.author = parse_result.get("author")
    prd.domain = parse_result.get("domain")
    prd.sections_count = len(parse_result["sections"])
    result["sections_count"] = prd.sections_count

    if parse_result.get("publish_date"):
        try:
            date_str = parse_result["publish_date"].replace("/", "-")
            parts = date_str.split("-")
            prd.publish_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            pass

    prd.status = "parsed"
    db.commit()

    # === Step 2: 提取规则 ===
    prd.status = "extracting"
    db.commit()

    from extractors.llm_extractor import extract_rules_from_sections, verify_extracted_rules

    rules_data, extraction_stats = extract_rules_from_sections(prd.parsed_sections, prd.title)

    for st in extraction_stats:
        db.add(ExtractionLog(
            prd_id=prd.id, section_heading=st["section"], section_chars=st["chars"],
            rules_extracted=st["rules"], elapsed_seconds=st["elapsed"],
            input_tokens=st["input_tokens"], output_tokens=st["output_tokens"], error=st["error"],
        ))
    result["total_tokens"] = sum((s["input_tokens"] or 0) + (s["output_tokens"] or 0) for s in extraction_stats)

    if vision_provider in ("claude", "qwen") and prd.filename.lower().endswith((".docx", ".doc")):
        try:
            from extractors.vision_extractor import extract_images_from_docx, extract_from_image
            for img_path in extract_images_from_docx(filepath, settings.upload_dir):
                img_rules = await extract_from_image(img_path, prd.title, vision_provider)
                rules_data.extend(img_rules)
                result["vision_rules_count"] += len(img_rules)
        except Exception:
            pass

    verification = {"issues": [], "missed": []}
    try:
        import anthropic
        ck = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            ck["base_url"] = settings.anthropic_base_url
        client = anthropic.Anthropic(**ck)
        verification = verify_extracted_rules(client, rules_data, prd.parsed_sections, prd.title)
        for missed in verification.get("missed", []):
            if missed.get("rule_text"):
                missed.setdefault("confidence", 0.5)
                missed.setdefault("category", "业务逻辑")
                missed.setdefault("source_section", "二次校验补充")
                rules_data.append(missed)
    except Exception:
        pass

    result["verification_issues"] = len(verification.get("issues", []))
    result["missed_rules_added"] = len(verification.get("missed", []))

    created = []
    for rd in rules_data:
        confidence = rd.get("confidence", 0.5)
        rule = Rule(
            prd_id=prd.id, domain=rd.get("domain", prd.domain), category=rd.get("category"),
            rule_text=rd["rule_text"], structured_logic=rd.get("structured_logic"),
            params=rd.get("params"), involves_roles=rd.get("involves_roles"),
            compliance_notes=rd.get("compliance_notes"), source_section=rd.get("source_section"),
            risk_score=0, status="draft",
        )
        db.add(rule)
        db.flush()
        db.execute(sa_insert(rule_sources).values(rule_id=rule.id, prd_id=prd.id))
        created.append((rule, confidence))
        if confidence < 0.6:
            result["low_confidence_count"] += 1
    result["rules_count"] = len(created)

    # === Step 3: 向量化 + 去重 + 跨文档合并 ===
    if created:
        try:
            from extractors.embedder import get_embeddings_batch, _build_rule_text
            import numpy as np
            rules_only = [r for r, _ in created]
            embeddings = await get_embeddings_batch([_build_rule_text(r) for r in rules_only])
            for rule, emb in zip(rules_only, embeddings):
                rule.embedding = emb
            result["embedded_count"] = len(rules_only)

            emb_matrix = np.array(embeddings)
            norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True); norms[norms == 0] = 1
            normalized = emb_matrix / norms
            seen = set()
            for i in range(len(rules_only)):
                if i in seen: continue
                for j in range(i + 1, len(rules_only)):
                    if j in seen: continue
                    if float(np.dot(normalized[i], normalized[j])) > 0.95:
                        if created[i][1] >= created[j][1]: rules_only[j].status = "deprecated"; seen.add(j)
                        else: rules_only[i].status = "deprecated"; seen.add(i); break
            result["dedup_count"] = len(seen)

            existing = db.query(Rule).filter(Rule.prd_id != prd.id, Rule.status != "deprecated", Rule.embedding.isnot(None)).all()
            if existing:
                ex_embs = np.array([r.embedding for r in existing])
                ex_n = np.linalg.norm(ex_embs, axis=1, keepdims=True); ex_n[ex_n == 0] = 1
                ex_norm = ex_embs / ex_n
                for i, nr in enumerate(rules_only):
                    if i in seen: continue
                    ne = np.array(embeddings[i]); nn = np.linalg.norm(ne)
                    if nn == 0: continue
                    sims = ex_norm @ (ne / nn)
                    if float(np.max(sims)) > 0.93:
                        try: db.execute(sa_insert(rule_sources).values(rule_id=existing[int(np.argmax(sims))].id, prd_id=prd.id))
                        except: pass
                        nr.status = "deprecated"; result["merged_count"] += 1
        except Exception:
            pass

    elapsed = round(time.time() - start_time, 2)
    prd.status = "extracted"
    prd.rules_count = result["rules_count"]
    prd.process_elapsed = elapsed
    prd.total_tokens = result["total_tokens"]
    prd.vision_provider = vision_provider
    prd.llm_model = settings.claude_model
    db.commit()
    result["process_elapsed"] = elapsed
    result["status"] = "extracted"
    return result
