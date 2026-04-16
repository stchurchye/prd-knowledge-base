from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("rules.id", ondelete="CASCADE"))
    actor = Column(String(100))
    action = Column(String(50))
    diff = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())

    rule = relationship("Rule", back_populates="audit_logs")
