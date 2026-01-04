"""
Recipe Explosion Service for Epic 3: Recipe Intelligence.

Converts demand forecasts into ingredient requirements for procurement planning.
Aggregates ingredients across menu items and applies waste factors.
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
class IngredientRequirement:
    """Ingredient requirement from recipe explosion."""
    ingredient_id: UUID
    ingredient_name: str
    total_quantity: Decimal
    unit: str
    estimated_cost: Decimal  # total_quantity * unit_cost
    perishability_days: Optional[int]
    priority_score: Decimal  # Higher = more urgent (based on cost + perishability)


@dataclass
class ExplosionResult:
    """Result of recipe explosion for procurement."""
    requirements: list[IngredientRequirement]
    total_cost: Decimal
    items_processed: int
    items_skipped: int  # Menu items without recipes
    skipped_item_names: list[str]


class RecipeExplosionService:
    """
    Explodes demand forecasts into ingredient requirements.

    Mathematical Model:
    ingredient_demand_j = Σ_i (forecast_i × qty_ij × (1 + waste_factor_j))

    Where:
    - forecast_i = units of menu item i expected to sell
    - qty_ij = quantity of ingredient j in recipe for item i
    - waste_factor_j = trim/waste percentage for ingredient j
    """

    def __init__(self, db: Session):
        self.db = db

    def explode_forecasts(
        self,
        forecasts: list[tuple[UUID, int]],  # [(menu_item_id, quantity), ...]
    ) -> ExplosionResult:
        """
        Convert demand forecasts into ingredient requirements.

        Args:
            forecasts: List of (menu_item_id, forecasted_quantity) tuples

        Returns:
            ExplosionResult with aggregated ingredient requirements
        """
        # Aggregate ingredients across all forecasts
        ingredient_totals: dict[UUID, dict] = {}  # ingredient_id -> {qty, cost, ...}
        items_processed = 0
        items_skipped = 0
        skipped_names = []

        for menu_item_id, forecast_qty in forecasts:
            menu_item = self.db.get(MenuItem, menu_item_id)
            if not menu_item:
                items_skipped += 1
                continue

            # Get recipe ingredients (try custom first, then standard)
            ingredients = self._get_recipe_ingredients(menu_item)

            if not ingredients:
                items_skipped += 1
                skipped_names.append(menu_item.name)
                continue

            items_processed += 1

            # Aggregate each ingredient
            for ing_id, ing_name, qty, unit, unit_cost, waste_factor, perishability in ingredients:
                # Apply waste factor
                waste_adjusted_qty = qty * (1 + (waste_factor or Decimal(0)))
                total_qty_for_forecast = waste_adjusted_qty * forecast_qty

                if ing_id not in ingredient_totals:
                    ingredient_totals[ing_id] = {
                        'name': ing_name,
                        'unit': unit,
                        'unit_cost': unit_cost or Decimal(0),
                        'perishability': perishability,
                        'total_qty': Decimal(0)
                    }

                ingredient_totals[ing_id]['total_qty'] += total_qty_for_forecast

        # Build requirements list
        requirements = []
        for ing_id, data in ingredient_totals.items():
            estimated_cost = data['total_qty'] * data['unit_cost']

            # Priority score: higher for perishable + expensive items
            perishability_factor = 1.0 / (data['perishability'] or 30)  # Higher if more perishable
            cost_factor = float(estimated_cost) / 100  # Normalize cost impact
            priority_score = Decimal(str(perishability_factor * 100 + cost_factor))

            requirements.append(IngredientRequirement(
                ingredient_id=ing_id,
                ingredient_name=data['name'],
                total_quantity=data['total_qty'],
                unit=data['unit'],
                estimated_cost=estimated_cost,
                perishability_days=data['perishability'],
                priority_score=priority_score
            ))

        # Sort by priority (highest first)
        requirements.sort(key=lambda r: r.priority_score, reverse=True)

        total_cost = sum(r.estimated_cost for r in requirements)

        return ExplosionResult(
            requirements=requirements,
            total_cost=total_cost,
            items_processed=items_processed,
            items_skipped=items_skipped,
            skipped_item_names=skipped_names
        )

    def _get_recipe_ingredients(
        self,
        menu_item: MenuItem
    ) -> list[tuple[UUID, str, Decimal, str, Decimal, Decimal, int]]:
        """
        Get ingredients for a menu item from custom or standard recipe.

        Returns list of tuples:
        (ingredient_id, name, quantity, unit, unit_cost, waste_factor, perishability_days)
        """
        # Try custom recipe first
        custom = self.db.execute(
            select(
                Ingredient.id,
                Ingredient.name,
                Recipe.quantity,
                Recipe.unit,
                Ingredient.unit_cost,
                Ingredient.waste_factor,
                Ingredient.perishability_days
            )
            .join(Recipe, Recipe.ingredient_id == Ingredient.id)
            .where(Recipe.menu_item_id == menu_item.id)
        ).all()

        if custom:
            return custom

        # Try standard recipe
        mapping = self.db.execute(
            select(MenuItemRecipe)
            .where(MenuItemRecipe.menu_item_id == menu_item.id)
        ).scalar_one_or_none()

        if not mapping:
            return []

        yield_mult = mapping.yield_multiplier or Decimal(1)

        standard = self.db.execute(
            select(
                Ingredient.id,
                Ingredient.name,
                StandardRecipeIngredient.quantity,
                StandardRecipeIngredient.unit,
                Ingredient.unit_cost,
                Ingredient.waste_factor,
                Ingredient.perishability_days
            )
            .join(StandardRecipeIngredient, StandardRecipeIngredient.ingredient_id == Ingredient.id)
            .where(StandardRecipeIngredient.standard_recipe_id == mapping.standard_recipe_id)
        ).all()

        # Apply yield multiplier
        return [
            (row[0], row[1], row[2] * yield_mult, row[3], row[4], row[5], row[6])
            for row in standard
        ]
