"""
Ingestion log model for tracking CSV upload parsing errors.
"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base


class IngestionLog(Base):
    """
    Tracks parsing errors during CSV upload ingestion.

    Each log entry represents a single error that occurred while processing
    a specific row in an uploaded CSV file.
    """
    __tablename__ = "ingestion_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("data_uploads.id", ondelete="CASCADE"), nullable=False)
    row_number = Column(Integer, nullable=False)
    field = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    raw_value = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="error")
    created_at = Column(DateTime, server_default=func.now())

    upload = relationship("DataUpload")
