from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from db.database import Base


class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("rules.id", ondelete="CASCADE"))
    challenger = Column(String(100))
    content = Column(Text, nullable=False)
    resolution = Column(Text)
    status = Column(String(20), default="open")
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)

    rule = relationship("Rule", back_populates="challenges")
