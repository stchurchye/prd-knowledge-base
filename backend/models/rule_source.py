from sqlalchemy import Column, Integer, ForeignKey, DateTime, func, Table
from db.database import Base

# 多对多关联表：一条规则可来自多个PRD
rule_sources = Table(
    "rule_sources",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("rule_id", Integer, ForeignKey("rules.id", ondelete="CASCADE"), nullable=False),
    Column("prd_id", Integer, ForeignKey("prds.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime, server_default=func.now()),
)
