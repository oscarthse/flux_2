import uuid
from sqlalchemy import Column, String, DateTime, func, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.db.base import Base

class DataUpload(Base):
    __tablename__ = "data_uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    file_hash = Column(String(64), nullable=True)
    errors = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    restaurant = relationship("Restaurant")
