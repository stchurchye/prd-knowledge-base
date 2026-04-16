from sqlalchemy import Column, Integer, String, Float, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB

from db.database import Base


class ConflictRecord(Base):
    __tablename__ = "conflict_records"

    id = Column(Integer, primary_key=True)
    method = Column(String(20), nullable=False)  # keyword / embedding / llm
    total_compared = Column(Integer, default=0)
    conflicts_count = Column(Integer, default=0)
    conflicts = Column(JSONB, default=[])  # 冲突详情列表
    elapsed_seconds = Column(Float)
    actor = Column(String(100), default="系统")
    created_at = Column(DateTime, server_default=func.now())
