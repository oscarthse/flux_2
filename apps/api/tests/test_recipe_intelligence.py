import pytest
from decimal import Decimal
from uuid import uuid4

from src.models.ingredient import Ingredient, Recipe
from src.models.recipe import StandardRecipe, StandardRecipeIngredient, MenuItemRecipe
from src.models.menu import MenuItem
from src.services.cogs_calculator import COGSCalculator

def test_calculate_cogs_custom_recipe(db, test_user_with_restaurant):
    """Test COGS calculation using the custom Recipe table (Ad-hoc mapping)."""
    _, restaurant = test_user_with_restaurant

    # 1. Create Ingredients with waste factors
    beef = Ingredient(
        restaurant_id=restaurant.id,
        name="Ground Beef",
        unit="kg",
        unit_cost=Decimal("10.00"),
        waste_factor=Decimal("0.10")  # 10% waste
    )
    bun = Ingredient(
        restaurant_id=restaurant.id,
        name="Brioche Bun",
        unit="unit",
        unit_cost=Decimal("0.50"),
        waste_factor=Decimal("0.00")
    )
    db.add_all([beef, bun])
    db.flush()

    # 2. Create Menu Item
    burger = MenuItem(
        restaurant_id=restaurant.id,
        name="House Burger",
        price=Decimal("15.00")
    )
    db.add(burger)
    db.flush()

    # 3. Link via Recipe table (Custom)
    # Beef: 0.150 kg * 10.00 = 1.50 base. With waste 10% -> 1.50 * 1.1 = 1.65
    rec1 = Recipe(menu_item_id=burger.id, ingredient_id=beef.id, quantity=Decimal("0.150"), unit="kg")

    # Bun: 1 unit * 0.50 = 0.50 base. No waste -> 0.50
    rec2 = Recipe(menu_item_id=burger.id, ingredient_id=bun.id, quantity=Decimal("1.0"), unit="unit")

    db.add_all([rec1, rec2])
    db.commit()

    # 4. Calculate
    calculator = COGSCalculator(db)
    result = calculator.calculate_cogs(burger.id)

    assert result is not None
    assert result.menu_item_name == "House Burger"
    assert result.recipe_source == "custom"

    # Expected COGS: 1.65 + 0.50 = 2.15
    # Allow small rounding diffs
    assert abs(result.total_cogs - Decimal("2.15")) < Decimal("0.01")

    # Margin: 15.00 - 2.15 = 12.85
    assert abs(result.contribution_margin - Decimal("12.85")) < Decimal("0.01")


def test_calculate_cogs_standard_recipe(db, test_user_with_restaurant):
    """Test COGS calculation using the Standard Recipe mapping."""
    _, restaurant = test_user_with_restaurant

    # 1. Create Ingredients
    cheese = Ingredient(
        restaurant_id=restaurant.id,
        name="Cheddar Cheese",
        unit="kg",
        unit_cost=Decimal("20.00"),
        waste_factor=Decimal("0.05")
    )
    db.add(cheese)
    db.flush()

    # 2. Create Standard Recipe
    std_recipe = StandardRecipe(name="Standard Cheeseburger", is_system=True)
    db.add(std_recipe)
    db.flush()

    # 3. Add Ingredients to Standard Recipe
    # Cheese: 0.02 kg * 20.00 = 0.40 base. Waste 1.05 -> 0.42
    std_ing = StandardRecipeIngredient(
        standard_recipe_id=std_recipe.id,
        ingredient_id=cheese.id,
        quantity=Decimal("0.02"),
        unit="kg"
    )
    db.add(std_ing)
    db.flush()

    # 4. Create Menu Item
    menu_item = MenuItem(
        restaurant_id=restaurant.id,
        name="Classic Cheeseburger",
        price=Decimal("10.00")
    )
    db.add(menu_item)
    db.flush()

    # 5. Link Menu Item to Standard Recipe with Yield Multiplier
    # Multiplier 2.0 -> Double Cheese -> 0.04 kg -> 0.84 cost
    link = MenuItemRecipe(
        menu_item_id=menu_item.id,
        standard_recipe_id=std_recipe.id,
        yield_multiplier=Decimal("2.0")
    )
    db.add(link)
    db.commit()

    # 6. Calculate
    calculator = COGSCalculator(db)
    result = calculator.calculate_cogs(menu_item.id)

    assert result is not None
    assert result.recipe_source == "standard"

    # Expected: 0.42 * 2.0 = 0.84
    assert abs(result.total_cogs - Decimal("0.84")) < Decimal("0.01")

def test_calculate_profitability_sorting(db, test_user_with_restaurant):
    """Test that profitability calculation sorts items by margin."""
    _, restaurant = test_user_with_restaurant

    # Item A: Cost 5, Price 10 -> Margin 50%
    item_a = MenuItem(restaurant_id=restaurant.id, name="A", price=Decimal("10"), cost_override=Decimal("5"))

    # Item B: Cost 1, Price 10 -> Margin 90%
    item_b = MenuItem(restaurant_id=restaurant.id, name="B", price=Decimal("10"), cost_override=Decimal("1"))

    # Item C: Cost 9, Price 10 -> Margin 10%
    item_c = MenuItem(restaurant_id=restaurant.id, name="C", price=Decimal("10"), cost_override=Decimal("9"))

    db.add_all([item_a, item_b, item_c])
    db.commit()

    calculator = COGSCalculator(db)
    results = calculator.calculate_menu_profitability(restaurant.id)

    assert len(results) == 3
    # Should be sorted by margin percentage (ascending) -> C (10%), A (50%), B (90%)
    assert results[0].menu_item_name == "C"
    assert results[1].menu_item_name == "A"
    assert results[2].menu_item_name == "B"
