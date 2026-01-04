"""
Standard Recipe models for Epic 3: Recipe Intelligence.

StandardRecipe: Global library of recipes (shared across restaurants)
StandardRecipeIngredient: Join table for recipe ingredients
MenuItemRecipe: Maps restaurant menu items to standard recipes
IngredientCostHistory: Tracks ingredient price changes over time
"""
import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, Numeric, DateTime, Date, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.db.base import Base


class StandardRecipe(Base):
    """
    A standard recipe from Flux's global library.

    These recipes are shared across all restaurants and contain
    detailed ingredient lists, prep times, and cuisine classification.
    """
    __tablename__ = "standard_recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    cuisine_type = Column(String(100))  # Italian, American, Mexican, Asian, French
    category = Column(String(100))  # Appetizer, Entree, Dessert, Beverage
    servings = Column(Integer, default=1)
    prep_time_minutes = Column(Integer)
    skill_level = Column(Integer)  # 1-5 scale
    description = Column(Text)

    # Dietary info
    dietary_tags = Column(JSONB, default=list)  # ["vegan", "gluten-free", "dairy-free"]

    # AI matching
    embedding = Column(JSONB)  # 384-dim vector for semantic search (will migrate to pgvector)

    # Provenance
    is_system = Column(Boolean, default=True)  # True for Flux-seeded recipes
    source = Column(String(100))  # "flux_database", "user_created", "imported"

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    ingredients = relationship("StandardRecipeIngredient", back_populates="recipe", cascade="all, delete-orphan")
    menu_item_links = relationship("MenuItemRecipe", back_populates="standard_recipe", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_standard_recipes_name', 'name'),
        Index('idx_standard_recipes_cuisine', 'cuisine_type'),
    )


class StandardRecipeIngredient(Base):
    """
    Join table linking StandardRecipe to Ingredient with quantities.

    This defines what ingredients and how much are needed for a standard recipe.
    """
    __tablename__ = "standard_recipe_ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    standard_recipe_id = Column(UUID(as_uuid=True), ForeignKey("standard_recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Numeric(10, 4), nullable=False)
    unit = Column(String(50), nullable=False)
    preparation = Column(String(100))  # "diced", "julienned", "whole", "minced"
    is_optional = Column(Boolean, default=False)  # For garnishes, sides
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    recipe = relationship("StandardRecipe", back_populates="ingredients")
    ingredient = relationship("Ingredient")


class MenuItemRecipe(Base):
    """
    Maps a restaurant's menu item to a standard recipe.

    This is the result of AI matching or user confirmation that links
    what the restaurant sells to how it's made.
    """
    __tablename__ = "menu_item_recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    standard_recipe_id = Column(UUID(as_uuid=True), ForeignKey("standard_recipes.id", ondelete="CASCADE"), nullable=False)

    # Portion adjustment
    yield_multiplier = Column(Numeric(4, 2), default=1.0)  # 1.0 = standard, 1.5 = XL portion

    # Confirmation tracking
    confirmed_by_user = Column(Boolean, default=False)
    confidence_score = Column(Numeric(3, 2))  # 0.00-1.00 for AI-suggested matches

    # Audit
    matched_at = Column(DateTime, server_default=func.now())
    confirmed_at = Column(DateTime)

    # Relationships
    menu_item = relationship("MenuItem")
    standard_recipe = relationship("StandardRecipe", back_populates="menu_item_links")

    __table_args__ = (
        Index('idx_menu_item_recipes_menu_item', 'menu_item_id'),
        Index('idx_menu_item_recipes_confirmed', 'confirmed_by_user'),
    )


class IngredientCostHistory(Base):
    """
    Tracks ingredient price changes over time.

    Used for accurate COGS calculation using the cost at time of sale,
    and for detecting price trends/seasonal variations.
    """
    __tablename__ = "ingredient_cost_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)

    cost_per_unit = Column(Numeric(10, 4), nullable=False)
    effective_date = Column(Date, nullable=False)
    source = Column(String(50))  # "manual", "invoice_ocr", "supplier_api"
    notes = Column(Text)

    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    ingredient = relationship("Ingredient", back_populates="cost_history")
    restaurant = relationship("Restaurant")

    __table_args__ = (
        Index('idx_cost_history_ingredient_date', 'ingredient_id', 'effective_date'),
    )
