from sqlalchemy import Column, Integer, String, Float, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB

from db.database import Base


class WikiLog(Base):
    """Wiki 操作日志 - 类似 Karpathy 的 log.md"""
    __tablename__ = "wiki_logs"

    id = Column(Integer, primary_key=True)
    operation = Column(String(50))  # create_page, update_page, merge_rules, detect_conflict
    actor = Column(String(100))  # system, user_x, wechat_bot
    target_type = Column(String(30))  # material, rule, wiki_page
    target_id = Column(Integer)

    details = Column(JSONB)
    elapsed_seconds = Column(Float)

    created_at = Column(DateTime, server_default=func.now())