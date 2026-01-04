
import uuid
from sqlalchemy import Column, String, Date, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base

class DemandForecast(Base):
    """Stores predicted demand for menu items."""
    __tablename__ = "demand_forecasts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    menu_item_name = Column(String, nullable=False)  # Using name for simplicity
    forecast_date = Column(Date, nullable=False)
    predicted_quantity = Column(Numeric(10, 2), nullable=False)
    p10_quantity = Column(Numeric(10, 2))
    p50_quantity = Column(Numeric(10, 2))
    p90_quantity = Column(Numeric(10, 2))
    model_name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")


class StaffingForecast(Base):
    """Placeholder for future staffing forecasts."""
    __tablename__ = "staffing_forecasts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False)
    forecast_date = Column(Date, nullable=False)
    predicted_hours = Column(Numeric(10, 2), nullable=False)
    model_name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")
