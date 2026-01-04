from sqlalchemy import Column, DateTime, ForeignKey, Numeric, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from src.db.base import Base

class DataHealthScore(Base):
    """
    Tracks the data quality health score for a restaurant's ingested data.

    Score is 0-100% and composed of weighted sub-scores:
    - Completeness (40%): History length, item coverage
    - Consistency (30%): Upload regularity, price stability
    - Timeliness (20%): Data recency
    - Accuracy (10%): Stockout/promotion tracking
    """
    __tablename__ = "data_health_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)

    # Overall score (0-100)
    overall_score = Column(Numeric(5, 2), nullable=False)

    # Component sub-scores (0-100)
    completeness_score = Column(Numeric(5, 2), nullable=False)
    consistency_score = Column(Numeric(5, 2), nullable=False)
    timeliness_score = Column(Numeric(5, 2), nullable=False)
    accuracy_score = Column(Numeric(5, 2), nullable=False)

    # JSON breakdowns
    component_breakdown = Column(JSON, nullable=False, default=dict)
    recommendations = Column(JSON, nullable=False, default=list)

    calculated_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    restaurant = relationship("Restaurant", back_populates="health_scores")
