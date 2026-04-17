from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship

from db.database import Base


class Material(Base):
    """材料模型 - 支持文档和图片"""
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    filename = Column(String(300), nullable=False)
    file_hash = Column(String(32), unique=True, index=True)

    # 材料类型
    material_type = Column(String(30), default="document")  # document, image
    doc_type = Column(String(20), default="prd")  # prd, tech, meeting_notes, requirement

    # 来源渠道
    source_channel = Column(String(20), default="upload")  # upload, feishu, wechat_work
    external_url = Column(String(500))  # 飞书链接、企微消息链接

    # 文档元数据
    version = Column(String(20))
    author = Column(String(100))
    publish_date = Column(Date)
    domain = Column(String(50))

    # 原始内容
    raw_text = Column(Text)
    raw_image_path = Column(String(500))  # 图片路径
    parsed_sections = Column(JSONB)

    # 处理状态和统计
    status = Column(String(20), default="uploaded")
    sections_count = Column(Integer)
    rules_count = Column(Integer)
    process_elapsed = Column(Float)
    total_tokens = Column(Integer)
    vision_provider = Column(String(20))
    llm_model = Column(String(50))
    error_message = Column(String(500))

    # Wiki 输出
    wiki_pages = Column(JSONB)  # [{"title": "...", "path": "..."}]

    created_at = Column(DateTime, server_default=func.now())

    rules = relationship("Rule", back_populates="material", cascade="all, delete-orphan")
    wiki_pages_rel = relationship("WikiPage", back_populates="material", cascade="all, delete-orphan")