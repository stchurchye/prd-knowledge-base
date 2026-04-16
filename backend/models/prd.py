from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.database import Base


class PRD(Base):
    __tablename__ = "prds"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    filename = Column(String(300), nullable=False)
    file_hash = Column(String(32), unique=True, index=True)
    version = Column(String(20))
    author = Column(String(100))
    publish_date = Column(Date)
    domain = Column(String(50))
    doc_type = Column(String(20), default="prd")  # "prd" or "tech"
    status = Column(String(20), default="uploaded")
    raw_text = Column(Text)
    parsed_sections = Column(JSONB)
    sections_count = Column(Integer)
    rules_count = Column(Integer)
    process_elapsed = Column(Float)  # 总处理耗时（秒）
    total_tokens = Column(Integer)   # 总 token 消耗
    vision_provider = Column(String(20))  # off / claude / qwen
    llm_model = Column(String(50))   # 使用的文字提取模型
    error_message = Column(String(500))  # 处理失败时的错误信息
    created_at = Column(DateTime, server_default=func.now())

    rules = relationship("Rule", back_populates="prd", cascade="all, delete-orphan")
