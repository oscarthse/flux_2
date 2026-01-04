"""
Promotion and pricing models.
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base


class Promotion(Base):
    """Discounts and promotions for menu items."""
    __tablename__ = "promotions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"))
    name = Column(String(255))
    discount_type = Column(String(20), nullable=False)  # percentage, fixed_amount
    discount_value = Column(Numeric(10, 2), nullable=False)
    min_margin = Column(Numeric(5, 2))  # Floor margin to protect
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(String(20), default="draft")  # draft, active, completed, cancelled
    trigger_reason = Column(String(100))  # expiring_stock, low_demand, manual
    is_exploration = Column(Boolean, default=False, nullable=False)  # 5% random promos for unbiased elasticity
    expected_lift = Column(Numeric(5, 2))  # Predicted % increase
    actual_lift = Column(Numeric(5, 2))  # Observed % increase
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")
    menu_item = relationship("MenuItem", back_populates="promotions")
    transaction_items = relationship("TransactionItem", back_populates="promotion")


class PriceElasticity(Base):
    """Learned price elasticity for items or categories."""
    __tablename__ = "price_elasticity"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("menu_categories.id", ondelete="CASCADE"))
    elasticity = Column(Numeric(5, 3), nullable=False)  # Typical range: 0.5 - 4.0
    confidence = Column(Numeric(5, 3))  # 0-1
    sample_size = Column(Integer)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")
