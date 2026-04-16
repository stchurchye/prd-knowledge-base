from sqlalchemy import Column, Integer, String, Float, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB

from db.database import Base


class ExtractionLog(Base):
    __tablename__ = "extraction_logs"

    id = Column(Integer, primary_key=True)
    prd_id = Column(Integer, nullable=False)
    section_heading = Column(String(200))
    section_chars = Column(Integer, default=0)
    rules_extracted = Column(Integer, default=0)
    elapsed_seconds = Column(Float)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    error = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
