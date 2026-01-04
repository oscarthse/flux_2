"""
COGS Calculator Service for Epic 3: Recipe Intelligence.

Calculates Cost of Goods Sold for menu items based on recipe ingredients,
waste factors, and current ingredient costs.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from src.models.menu import MenuItem
from src.models.ingredient import Ingredient, Recipe
from src.models.recipe import StandardRecipe, StandardRecipeIngredient, MenuItemRecipe


@dataclass
class IngredientCost:
    """Cost breakdown for a single ingredient in a recipe."""
    ingredient_id: UUID
    ingredient_name: str
    quantity: Decimal
    unit: str
    unit_cost: Decimal
    waste_factor: Decimal
    base_cost: Decimal  # quantity * unit_cost
    waste_adjusted_cost: Decimal  # base_cost * (1 + waste_factor)


@dataclass
class COGSResult:
    """Full COGS breakdown for a menu item."""
    menu_item_id: UUID
    menu_item_name: str
    menu_item_price: Decimal
    total_cogs: Decimal
    ingredient_breakdown: list[IngredientCost]
    contribution_margin: Decimal  # price - COGS
    margin_percentage: Decimal  # (contribution_margin / price) * 100
    recipe_source: str  # "custom", "standard", "none"


class COGSCalculator:
    """
    Calculates COGS for menu items.

    COGS Formula:
    COGS = Σ (ingredient_qty × unit_cost × (1 + waste_factor))

    The calculator checks for:
    1. Custom recipe ingredients (Recipe table)
    2. Standard recipe mappings (MenuItemRecipe → StandardRecipe)
    3. Falls back to cost_override on MenuItem if no recipe
    """

    def __init__(self, db: Session, waste_factors_enabled: bool = True):
        self.db = db
        self.waste_factors_enabled = waste_factors_enabled

    def calculate_cogs(self, menu_item_id: UUID) -> Optional[COGSResult]:
        """
        Calculate COGS for a single menu item.

        Returns None if menu item not found.
        """
        # Fetch menu item
        menu_item = self.db.get(MenuItem, menu_item_id)
        if not menu_item:
            return None

        # Try confirmed cached recipe first (AI-generated + user confirmed)
        cached_breakdown = self._calculate_from_cached_estimate(menu_item)
        if cached_breakdown:
            return self._build_result(menu_item, cached_breakdown, "confirmed_estimate")

        # Try custom recipe (existing Recipe join table)
        custom_breakdown = self._calculate_from_custom_recipe(menu_item)
        if custom_breakdown:
            return self._build_result(menu_item, custom_breakdown, "custom")

        # Try standard recipe mapping
        standard_breakdown = self._calculate_from_standard_recipe(menu_item)
        if standard_breakdown:
            return self._build_result(menu_item, standard_breakdown, "standard")

        # Fallback to cost_override
        if menu_item.cost_override:
            return COGSResult(
                menu_item_id=menu_item.id,
                menu_item_name=menu_item.name,
                menu_item_price=menu_item.price,
                total_cogs=menu_item.cost_override,
                ingredient_breakdown=[],
                contribution_margin=menu_item.price - menu_item.cost_override,
                margin_percentage=((menu_item.price - menu_item.cost_override) / menu_item.price * 100) if menu_item.price else Decimal(0),
                recipe_source="override"
            )

        # No recipe or override - return with zero COGS
        return COGSResult(
            menu_item_id=menu_item.id,
            menu_item_name=menu_item.name,
            menu_item_price=menu_item.price,
            total_cogs=Decimal(0),
            ingredient_breakdown=[],
            contribution_margin=menu_item.price,
            margin_percentage=Decimal(100),
            recipe_source="none"
        )

    def _calculate_from_cached_estimate(self, menu_item: MenuItem) -> Optional[list[IngredientCost]]:
        """Calculate COGS from confirmed cached recipe estimates."""
        from sqlalchemy import text
        from uuid import UUID as UUID_TYPE

        # Query for confirmed cached estimate
        query = text("""
            SELECT ingredients, total_estimated_cost
            FROM cached_recipe_estimates
            WHERE menu_item_id = :menu_item_id AND is_confirmed = true
        """)

        result = self.db.execute(query, {"menu_item_id": str(menu_item.id)}).fetchone()

        if not result:
            return None

        ingredients_data = result.ingredients

        if not ingredients_data:
            return None

        breakdown = []
        for ing_data in ingredients_data:
            # Get base cost and waste factor from cached data
            base_cost = Decimal(str(ing_data.get('base_cost', ing_data.get('estimated_cost', 0))))
            waste_factor = Decimal(str(ing_data.get('waste_factor', 0))) if self.waste_factors_enabled else Decimal(0)
            quantity = Decimal(str(ing_data['quantity']))

            # Calculate waste-adjusted cost
            waste_adjusted_cost = base_cost * (1 + waste_factor)

            breakdown.append(IngredientCost(
                ingredient_id=UUID_TYPE('00000000-0000-0000-0000-000000000000'),  # Dummy UUID for cached ingredients
                ingredient_name=ing_data['name'],
                quantity=quantity,
                unit=ing_data['unit'],
                unit_cost=base_cost / quantity if quantity > 0 else Decimal(0),
                waste_factor=waste_factor,
                base_cost=base_cost,
                waste_adjusted_cost=waste_adjusted_cost
            ))

        return breakdown

    def _calculate_from_custom_recipe(self, menu_item: MenuItem) -> Optional[list[IngredientCost]]:
        """Calculate COGS from custom Recipe entries."""
        recipes = self.db.execute(
            select(Recipe, Ingredient)
            .join(Ingredient, Recipe.ingredient_id == Ingredient.id)
            .where(Recipe.menu_item_id == menu_item.id)
        ).all()

        if not recipes:
            return None

        breakdown = []
        for recipe, ingredient in recipes:
            unit_cost = ingredient.unit_cost or Decimal(0)
            waste_factor = (ingredient.waste_factor or Decimal(0)) if self.waste_factors_enabled else Decimal(0)
            base_cost = recipe.quantity * unit_cost
            waste_adjusted_cost = base_cost * (1 + waste_factor)

            breakdown.append(IngredientCost(
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                quantity=recipe.quantity,
                unit=recipe.unit,
                unit_cost=unit_cost,
                waste_factor=waste_factor,
                base_cost=base_cost,
                waste_adjusted_cost=waste_adjusted_cost
            ))

        return breakdown

    def _calculate_from_standard_recipe(self, menu_item: MenuItem) -> Optional[list[IngredientCost]]:
        """Calculate COGS from StandardRecipe mapping."""
        # Find the mapping
        mapping = self.db.execute(
            select(MenuItemRecipe)
            .where(MenuItemRecipe.menu_item_id == menu_item.id)
        ).scalar_one_or_none()

        if not mapping:
            return None

        # Get standard recipe ingredients
        recipe_ingredients = self.db.execute(
            select(StandardRecipeIngredient, Ingredient)
            .join(Ingredient, StandardRecipeIngredient.ingredient_id == Ingredient.id)
            .where(StandardRecipeIngredient.standard_recipe_id == mapping.standard_recipe_id)
        ).all()

        if not recipe_ingredients:
            return None

        breakdown = []
        yield_multiplier = mapping.yield_multiplier or Decimal(1)

        for sri, ingredient in recipe_ingredients:
            unit_cost = ingredient.unit_cost or Decimal(0)
            waste_factor = (ingredient.waste_factor or Decimal(0)) if self.waste_factors_enabled else Decimal(0)
            adjusted_qty = sri.quantity * yield_multiplier
            base_cost = adjusted_qty * unit_cost
            waste_adjusted_cost = base_cost * (1 + waste_factor)

            breakdown.append(IngredientCost(
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                quantity=adjusted_qty,
                unit=sri.unit,
                unit_cost=unit_cost,
                waste_factor=waste_factor,
                base_cost=base_cost,
                waste_adjusted_cost=waste_adjusted_cost
            ))

        return breakdown

    def _build_result(
        self,
        menu_item: MenuItem,
        breakdown: list[IngredientCost],
        source: str
    ) -> COGSResult:
        """Build COGSResult from ingredient breakdown."""
        total_cogs = sum(ic.waste_adjusted_cost for ic in breakdown)
        contribution_margin = menu_item.price - total_cogs
        margin_pct = (contribution_margin / menu_item.price * 100) if menu_item.price else Decimal(0)

        return COGSResult(
            menu_item_id=menu_item.id,
            menu_item_name=menu_item.name,
            menu_item_price=menu_item.price,
            total_cogs=total_cogs,
            ingredient_breakdown=breakdown,
            contribution_margin=contribution_margin,
            margin_percentage=margin_pct,
            recipe_source=source
        )

    def calculate_menu_profitability(
        self,
        restaurant_id: UUID,
        limit: int = 100
    ) -> list[COGSResult]:
        """
        Calculate COGS for all active menu items in a restaurant.

        Returns list sorted by margin percentage (lowest first).
        """
        menu_items = self.db.execute(
            select(MenuItem)
            .where(
                MenuItem.restaurant_id == restaurant_id,
                MenuItem.is_active == True
            )
            .limit(limit)
        ).scalars().all()

        results = []
        for item in menu_items:
            result = self.calculate_cogs(item.id)
            if result:
                results.append(result)

        # Sort by margin (lowest first to highlight problems)
        results.sort(key=lambda r: r.margin_percentage)
        return results

    def categorize_bcg(self, result: COGSResult, median_margin: Decimal, is_high_volume: bool) -> str:
        """
        Categorize menu item into BCG matrix quadrant.

        - Stars: High volume, high margin
        - Puzzles: Low volume, high margin
        - Plow Horses: High volume, low margin
        - Dogs: Low volume, low margin

        High margin threshold: > median margin
        Volume determined by caller (based on sales data)
        """
        is_high_margin = result.margin_percentage > median_margin

        if is_high_volume and is_high_margin:
            return "star"
        elif not is_high_volume and is_high_margin:
            return "puzzle"
        elif is_high_volume and not is_high_margin:
            return "plow_horse"
        else:
            return "dog"
