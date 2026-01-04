"""
Settings and audit models.
"""
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.db.base import Base


class RestaurantSettings(Base):
    """Flexible key-value settings per restaurant."""
    __tablename__ = "restaurant_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(JSONB, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")


class AlgorithmRun(Base):
    """Audit log for algorithm executions."""
    __tablename__ = "algorithm_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    algorithm_name = Column(String(100), nullable=False)  # demand_forecast, labor_schedule, promotions
    run_started_at = Column(DateTime, server_default=func.now())
    run_completed_at = Column(DateTime)
    status = Column(String(20), default="running")  # running, completed, failed
    input_params = Column(JSONB)
    output_summary = Column(JSONB)
    error_message = Column(Text)

    restaurant = relationship("Restaurant")
