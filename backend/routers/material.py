import hashlib
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from models import Material

router = APIRouter(prefix="/api/materials", tags=["Materials"])

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(os.path.join(settings.upload_dir, "images"), exist_ok=True)


class MaterialOut(BaseModel):
    id: int
    title: str
    filename: str
    material_type: Optional[str] = "document"
    doc_type: Optional[str] = "prd"
    source_channel: Optional[str] = "upload"
    status: str
    rules_count: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[MaterialOut])
def list_materials(
    material_type: Optional[str] = None,
    doc_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Material)
    if material_type:
        query = query.filter(Material.material_type == material_type)
    if doc_type:
        query = query.filter(Material.doc_type == doc_type)
    return query.order_by(Material.created_at.desc()).all()


@router.get("/{material_id}", response_model=MaterialOut)
def get_material(material_id: int, db: Session = Depends(get_db)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


@router.post("/upload-image", response_model=MaterialOut)
async def upload_image(
    file: UploadFile = File(...),
    doc_type: str = "prd",
    db: Session = Depends(get_db)
):
    """直接上传图片"""
    if not any(file.filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
        raise HTTPException(status_code=400, detail="支持 PNG、JPG、GIF、WebP、BMP 格式图片")

    safe_name = os.path.basename(file.filename)
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()

    existing = db.query(Material).filter(Material.file_hash == file_hash).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"图片已存在：「{existing.title}」(ID: {existing.id})",
        )

    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    image_dir = os.path.join(settings.upload_dir, "images")
    filepath = os.path.join(image_dir, unique_name)
    with open(filepath, "wb") as f:
        f.write(content)

    title = os.path.splitext(safe_name)[0]
    material = Material(
        title=title,
        filename=unique_name,
        file_hash=file_hash,
        material_type="image",
        doc_type=doc_type,
        source_channel="upload",
        raw_image_path=filepath,
        status="uploaded"
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.post("/{material_id}/process-image")
async def process_image(material_id: int, db: Session = Depends(get_db)):
    """处理上传的图片，提取规则"""
    import time

    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if material.material_type != "image":
        raise HTTPException(status_code=400, detail="只支持图片类型")

    if not material.raw_image_path:
        raise HTTPException(status_code=400, detail="图片路径不存在")

    start_time = time.time()
    material.status = "extracting"
    material.error_message = None
    db.commit()

    try:
        from extractors.vision_extractor import extract_from_image
        from extractors.embedder import get_embedding
        from models import Rule
        from sqlalchemy import insert as sa_insert
        from models.rule_source import rule_sources

        rules_data = await extract_from_image(material.raw_image_path, material.title, "qwen")

        created = []
        for rd in rules_data:
            rule = Rule(
                material_id=material.id,
                domain=rd.get("domain"),
                category=rd.get("category"),
                rule_text=rd["rule_text"],
                source_section=rd.get("source_section", "图片识别"),
                status="draft",
                confidence=rd.get("confidence", 0.6)
            )
            db.add(rule)
            db.flush()
            db.execute(sa_insert(rule_sources).values(rule_id=rule.id, prd_id=None))
            created.append(rule)

        # 向量化
        if created:
            from extractors.embedder import get_embeddings_batch, _build_rule_text
            embeddings = await get_embeddings_batch([_build_rule_text(r) for r in created])
            for rule, emb in zip(created, embeddings):
                rule.embedding = emb

        elapsed = round(time.time() - start_time, 2)
        material.status = "extracted"
        material.rules_count = len(created)
        material.process_elapsed = elapsed
        material.vision_provider = "qwen"
        db.commit()

        return {
            "status": "extracted",
            "rules_count": len(created),
            "elapsed": elapsed,
            "material_id": material.id
        }

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        material.status = "failed"
        material.error_message = str(e)[:500]
        material.process_elapsed = elapsed
        db.commit()
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)[:200]}")


@router.delete("/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # 删除图片文件
    if material.raw_image_path and os.path.exists(material.raw_image_path):
        os.remove(material.raw_image_path)

    db.delete(material)
    db.commit()
    return {"status": "deleted"}