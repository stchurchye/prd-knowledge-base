import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from db.database import get_db
from models import WikiPage, Material
from wiki import wiki_generator

router = APIRouter(prefix="/api/wiki", tags=["Wiki"])

WIKI_DIR = "./wiki_output"


@router.get("/index", response_class=PlainTextResponse)
def get_wiki_index():
    """获取知识库索引 index.md"""
    index_path = f"{WIKI_DIR}/index.md"
    if not os.path.exists(index_path):
        return "# 知识库索引\n\n暂无内容"
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


@router.get("/log", response_class=PlainTextResponse)
def get_wiki_log():
    """获取操作日志 log.md"""
    log_path = f"{WIKI_DIR}/log.md"
    if not os.path.exists(log_path):
        return "# Wiki 操作日志\n\n暂无记录"
    with open(log_path, "r", encoding="utf-8") as f:
        return f.read()


@router.get("/page")
def get_wiki_page(path: str):
    """获取指定 Wiki 页面内容"""
    if not path:
        raise HTTPException(status_code=400, detail="path 参数必填")

    # 安全检查，防止路径穿越
    safe_path = os.path.basename(path)
    full_path = os.path.join(WIKI_DIR, safe_path)

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="页面不存在")

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {"path": safe_path, "content": content}


@router.get("/pages")
def list_wiki_pages(db: Session = Depends(get_db)):
    """列出所有 Wiki 页面"""
    pages = db.query(WikiPage).order_by(WikiPage.created_at.desc()).limit(100).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "page_type": p.page_type,
            "material_id": p.material_id,
            "rules_count": len(p.related_rules or []),
            "version": p.version,
            "is_dirty": p.is_dirty,
            "last_generated_at": p.last_generated_at.isoformat() if p.last_generated_at else None,
        }
        for p in pages
    ]


@router.post("/regenerate/{material_id}")
async def regenerate_wiki(material_id: int, db: Session = Depends(get_db)):
    """重新生成指定材料的 Wiki"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    from models import Rule
    rules = db.query(Rule).filter(Rule.material_id == material_id).all()

    if not rules:
        raise HTTPException(status_code=400, detail="该材料暂无规则")

    result = await wiki_generator.generate_for_material(material, rules, db)

    return {"status": "regenerated", **result}