"""
Ingredient and recipe models for costing.
"""
import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.db.base import Base


class IngredientCategory(Base):
    """Category for ingredients (produce, dairy, meat, dry goods, etc.)."""
    __tablename__ = "ingredient_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")
    ingredients = relationship("Ingredient", back_populates="category")


class Ingredient(Base):
    """An ingredient used in recipes."""
    __tablename__ = "ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("ingredient_categories.id", ondelete="SET NULL"))
    name = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=False)  # kg, liters, units
    unit_cost = Column(Numeric(10, 4))
    shelf_life_days = Column(Integer)
    min_stock_level = Column(Numeric(10, 3))

    # Recipe Intelligence (Epic 3)
    waste_factor = Column(Numeric(3, 2), default=0.0)  # 0.00-0.60, e.g., 0.10 = 10% waste after trim
    allergens = Column(JSONB, default=list)  # ["dairy", "gluten", "nuts", etc.]
    perishability_days = Column(Integer)  # Days until spoilage (1-7 = highly perishable)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")
    category = relationship("IngredientCategory", back_populates="ingredients")
    recipes = relationship("Recipe", back_populates="ingredient")
    inventory_items = relationship("Inventory", back_populates="ingredient")
    cost_history = relationship("IngredientCostHistory", back_populates="ingredient")


class Recipe(Base):
    """Link between menu items and ingredients with quantities."""
    __tablename__ = "recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Numeric(10, 4), nullable=False)
    unit = Column(String(50), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    menu_item = relationship("MenuItem", back_populates="recipes")
    ingredient = relationship("Ingredient", back_populates="recipes")
