"""
External data models: weather and events.
"""
import uuid
from sqlalchemy import Column, String, Text, Date, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base


class WeatherData(Base):
    """Historical and forecast weather data."""
    __tablename__ = "weather_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location = Column(String(100), nullable=False)  # City or zip code
    date = Column(Date, nullable=False)
    temp_high = Column(Numeric(5, 2))
    temp_low = Column(Numeric(5, 2))
    precipitation_mm = Column(Numeric(5, 2))
    conditions = Column(String(50))  # sunny, cloudy, rainy, snowy
    created_at = Column(DateTime, server_default=func.now())


class LocalEvent(Base):
    """Local events that may affect demand."""
    __tablename__ = "local_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    event_date = Column(Date, nullable=False)
    event_type = Column(String(50))  # sports, concert, holiday, festival
    expected_impact = Column(Numeric(5, 2))  # Multiplier: 1.2 = +20% demand
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")
