"""
Operating hours and service period models.

OperatingHours: Regular weekly schedule (e.g., "Monday: 11:00-22:00")
ServicePeriod: Exceptions (holidays, closures, special hours)
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, Date, Time, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base


class OperatingHours(Base):
    """
    Regular weekly operating schedule for a restaurant.
    One row per day of week (0=Monday, 6=Sunday).
    """
    __tablename__ = "operating_hours"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    open_time = Column(Time, nullable=True)  # Null if closed
    close_time = Column(Time, nullable=True)  # Null if closed
    is_closed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")

    __table_args__ = (
        # Only one entry per restaurant-day combination
        Index('idx_operating_hours_restaurant_day', 'restaurant_id', 'day_of_week', unique=True),
    )


class ServicePeriod(Base):
    """
    Exceptions to regular operating hours.
    Used for holidays, special events, closures, etc.
    """
    __tablename__ = "service_periods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    open_time = Column(Time, nullable=True)  # Override open time (null = use regular)
    close_time = Column(Time, nullable=True)  # Override close time (null = use regular)
    is_closed = Column(Boolean, default=False, nullable=False)  # True = closed all day
    reason = Column(String(100), nullable=True)  # "Holiday", "Private Event", "Emergency"
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")

    __table_args__ = (
        # Only one entry per restaurant-date combination
        Index('idx_service_periods_restaurant_date', 'restaurant_id', 'date', unique=True),
    )
