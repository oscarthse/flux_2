"""
Menu-related models: categories, menu items, and price history.
"""
import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, Numeric, DateTime, Date, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.base import Base


class MenuCategory(Base):
    """Category grouping for menu items (appetizers, mains, desserts, etc.)."""
    __tablename__ = "menu_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")
    menu_items = relationship("MenuItem", back_populates="category")


class MenuItem(Base):
    """A dish or product sold by the restaurant."""
    __tablename__ = "menu_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("menu_categories.id", ondelete="SET NULL"))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    cost_override = Column(Numeric(10, 2))  # Manual cost if no recipe
    prep_time_minutes = Column(Integer)
    is_active = Column(Boolean, default=True)

    # Auto-creation and categorization fields (Story 2.3)
    category_path = Column(String(255), nullable=True)  # e.g., "Entrees > Beef > Steaks"
    first_seen = Column(DateTime, nullable=True)  # First appearance in transaction data
    last_seen = Column(DateTime, nullable=True)  # Most recent appearance in transaction data
    auto_created = Column(Boolean, default=False)  # True if auto-created from transaction data
    confidence_score = Column(Numeric(3, 2), nullable=True)  # LLM categorization confidence (0.00-1.00)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", back_populates="menu_items")
    category = relationship("MenuCategory", back_populates="menu_items")
    recipes = relationship("Recipe", back_populates="menu_item", cascade="all, delete-orphan")
    promotions = relationship("Promotion", back_populates="menu_item")
    price_history = relationship("MenuItemPriceHistory", back_populates="menu_item", cascade="all, delete-orphan")


class MenuItemPriceHistory(Base):
    """
    Historical record of menu item price changes.

    Tracks price changes over time to enable demand elasticity analysis
    and detect price-driven demand shifts for ML forecasting.
    """
    __tablename__ = "menu_item_price_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    effective_date = Column(Date, nullable=False)
    source = Column(String(50), nullable=False)  # 'manual', 'auto_detected', 'import'
    created_at = Column(DateTime, server_default=func.now())

    menu_item = relationship("MenuItem", back_populates="price_history")
