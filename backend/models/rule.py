from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from db.database import Base
from models.rule_source import rule_sources


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True)
    prd_id = Column(Integer, ForeignKey("prds.id", ondelete="SET NULL"), nullable=True)  # 兼容旧数据
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="SET NULL"), nullable=True)  # 新关联
    domain = Column(String(50))
    category = Column(String(100))
    rule_text = Column(Text, nullable=False)
    structured_logic = Column(JSONB)
    params = Column(JSONB)
    involves_roles = Column(ARRAY(Text))
    compliance_notes = Column(ARRAY(Text))
    source_section = Column(String(200))
    risk_score = Column(Float, default=0)
    risk_flags = Column(ARRAY(Text))
    confidence = Column(Float)  # 提取置信度 0-1
    status = Column(String(20), default="draft")
    hit_count = Column(Integer, default=0)
    last_hit_at = Column(DateTime)
    embedding = Column(Vector(768))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    prd = relationship("PRD", back_populates="rules")
    material = relationship("Material", back_populates="rules")
    source_prds = relationship("PRD", secondary=rule_sources, backref="sourced_rules")
    challenges = relationship("Challenge", back_populates="rule", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="rule", cascade="all, delete-orphan")
