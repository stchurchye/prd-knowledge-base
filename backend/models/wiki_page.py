from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from db.database import Base


class WikiPage(Base):
    """Wiki 页面 - LLM 维护的结构化知识"""
    __tablename__ = "wiki_pages"

    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"))

    # 页面信息
    title = Column(String(200), nullable=False)
    page_type = Column(String(30))  # rule_summary, concept, entity, conflict_report
    page_path = Column(String(300))  # 生成的 markdown 文件路径

    # 内容
    markdown_content = Column(Text)
    structured_data = Column(JSONB)

    # 关联
    related_rules = Column(ARRAY(Integer))
    related_pages = Column(ARRAY(Integer))
    cross_references = Column(JSONB)  # {"page_id": ..., "relation": "..."}

    # 状态
    version = Column(Integer, default=1)
    is_dirty = Column(Boolean, default=False)
    last_generated_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    material = relationship("Material", back_populates="wiki_pages_rel")