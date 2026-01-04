import pytest
from decimal import Decimal
from uuid import uuid4
from src.services.recipe_matching import RecipeMatchingService, MatchResult
from src.models.menu import MenuItem
from src.models.recipe import StandardRecipe

def test_exact_match(db, test_user_with_restaurant):
    _, restaurant = test_user_with_restaurant
    unique_name = f"Margherita Pizza {uuid4()}"

    # 1. Create Standard Recipe
    rec = StandardRecipe(name=unique_name, category="Entree")
    db.add(rec)
    db.flush()

    # 2. Create Menu Item (Same name)
    item = MenuItem(restaurant_id=restaurant.id, name=unique_name, price=Decimal("12"))
    db.add(item)
    db.commit()

    service = RecipeMatchingService(db)
    result = service.match_menu_item(item)

    assert result.matches
    assert result.matches[0].match_method == "exact"
    assert result.matches[0].confidence_score == Decimal("1.0")
    assert result.matches[0].recipe_id == rec.id
    assert result.auto_confirmed is True

def test_fuzzy_match(db, test_user_with_restaurant):
    _, restaurant = test_user_with_restaurant
    suffix = str(uuid4())
    base_name = f"Spaghetti Bolognese {suffix}"
    fuzzy_name = f"Spaghetti Bolo {suffix}" # Shared suffix ensures high similarity

    # 1. Create Standard Recipe
    rec = StandardRecipe(name=base_name, category="Entree")
    db.add(rec)
    db.flush()

    # 2. Create Menu Item (Slightly different name)
    item = MenuItem(restaurant_id=restaurant.id, name=fuzzy_name, price=Decimal("15"))
    db.add(item)
    db.commit()

    service = RecipeMatchingService(db)
    result = service.match_menu_item(item)

    # Fuzzy match should work
    assert result.matches
    assert result.matches[0].recipe_id == rec.id
    assert result.matches[0].match_method == "fuzzy"

def test_no_match(db, test_user_with_restaurant):
    _, restaurant = test_user_with_restaurant

    unique_rec = f"Sushi Roll {uuid4()}"
    unique_item = f"Chocolate Cake {uuid4()}"

    # 1. Create Standard Recipe
    rec = StandardRecipe(name=unique_rec, category="Entree")
    db.add(rec)
    db.flush()

    # 2. Create unrelated Menu Item
    item = MenuItem(restaurant_id=restaurant.id, name=unique_item, price=Decimal("8"))
    db.add(item)
    db.commit()

    service = RecipeMatchingService(db)
    result = service.match_menu_item(item)

    # Should be empty or very low score
    if result.matches:
        # Ensure we don't accidentally match the Sushi Roll
        if result.matches[0].recipe_id == rec.id:
             assert result.matches[0].confidence_score < Decimal("0.6")
        assert not result.auto_confirmed

def test_auto_confirm_logic(db, test_user_with_restaurant):
    _, restaurant = test_user_with_restaurant
    unique_name = f"Beef Burger {uuid4()}"

    # High confidence match
    rec = StandardRecipe(name=unique_name, category="Entree")
    db.add(rec)
    db.flush()

    item = MenuItem(restaurant_id=restaurant.id, name=unique_name, price=Decimal("10"))
    db.add(item)
    db.commit()

    service = RecipeMatchingService(db)
    result = service.match_menu_item(item)
    assert result.auto_confirmed is True

    # Low confidence match
    item2 = MenuItem(restaurant_id=restaurant.id, name=f"Beef Sandwich {uuid4()}", price=Decimal("10"))
    db.add(item2)
    db.commit()

    result2 = service.match_menu_item(item2)
    if result2.matches:
        if result2.matches[0].recipe_id == rec.id:
             assert result2.auto_confirmed is False
