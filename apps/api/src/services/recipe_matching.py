"""
Recipe Matching Service for Epic 3: Recipe Intelligence.

Matches restaurant menu items to standard recipes using a 3-stage pipeline:
1. Exact name match (case-insensitive)
2. Fuzzy string match (Levenshtein distance)
3. Category-based filtering

Note: Semantic embedding matching (Stage 4) is prepared but requires
sentence-transformers library for production use.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from rapidfuzz import fuzz, process

from src.models.menu import MenuItem
from src.models.recipe import StandardRecipe, MenuItemRecipe


@dataclass
class RecipeMatch:
    """A potential recipe match for a menu item."""
    recipe_id: UUID
    recipe_name: str
    cuisine_type: Optional[str]
    category: Optional[str]
    prep_time_minutes: Optional[int]
    confidence_score: Decimal
    match_method: str  # "exact", "fuzzy", "category", "semantic"


@dataclass
class MatchResult:
    """Result of matching a menu item to recipes."""
    menu_item_id: UUID
    menu_item_name: str
    matches: list[RecipeMatch]
    auto_confirmed: bool  # True if top match confidence > 0.9
    needs_review: bool  # True if top match confidence < 0.7


class RecipeMatchingService:
    """
    Matches menu items to standard recipes.

    Pipeline:
    1. Exact name match (confidence 1.0)
    2. Fuzzy string match (confidence based on similarity)
    3. Category filtering (if category known)

    Auto-accepts if confidence > 0.9
    Flags for review if confidence < 0.7
    """

    # Thresholds
    AUTO_ACCEPT_THRESHOLD = Decimal("0.90")
    REVIEW_THRESHOLD = Decimal("0.70")
    FUZZY_MIN_SCORE = 60  # Minimum fuzzy match score (0-100)

    def __init__(self, db: Session):
        self.db = db
        self._recipe_cache: Optional[list[tuple[UUID, str, str, str]]] = None

    def match_menu_item(
        self,
        menu_item: MenuItem,
        top_k: int = 3
    ) -> MatchResult:
        """
        Find the best matching recipes for a menu item.

        Returns top_k matches sorted by confidence.
        """
        matches: list[RecipeMatch] = []

        # Stage 1: Exact match
        exact = self._exact_match(menu_item.name)
        if exact:
            matches.append(exact)

        # Stage 2: Fuzzy match
        fuzzy_matches = self._fuzzy_match(menu_item.name, limit=top_k * 2)
        matches.extend(fuzzy_matches)

        # Stage 3: Category filtering (if category known)
        if menu_item.category_path:
            category_matches = self._category_match(menu_item.category_path, menu_item.name)
            matches.extend(category_matches)

        # Deduplicate and sort by confidence
        seen_ids = set()
        unique_matches = []
        for m in sorted(matches, key=lambda x: x.confidence_score, reverse=True):
            if m.recipe_id not in seen_ids:
                seen_ids.add(m.recipe_id)
                unique_matches.append(m)

        top_matches = unique_matches[:top_k]

        # Determine if auto-confirm or needs review
        auto_confirmed = False
        needs_review = True

        if top_matches:
            top_confidence = top_matches[0].confidence_score
            if top_confidence >= self.AUTO_ACCEPT_THRESHOLD:
                auto_confirmed = True
                needs_review = False
            elif top_confidence >= self.REVIEW_THRESHOLD:
                needs_review = False

        return MatchResult(
            menu_item_id=menu_item.id,
            menu_item_name=menu_item.name,
            matches=top_matches,
            auto_confirmed=auto_confirmed,
            needs_review=needs_review
        )

    def match_all_unconfirmed(
        self,
        restaurant_id: UUID,
        top_k: int = 3
    ) -> list[MatchResult]:
        """
        Match all menu items that don't have confirmed recipes.
        """
        # Find menu items without confirmed mappings
        subq = (
            select(MenuItemRecipe.menu_item_id)
            .where(MenuItemRecipe.confirmed_by_user == True)
        )

        menu_items = self.db.execute(
            select(MenuItem)
            .where(
                MenuItem.restaurant_id == restaurant_id,
                MenuItem.is_active == True,
                MenuItem.id.not_in(subq)
            )
        ).scalars().all()

        results = []
        for item in menu_items:
            result = self.match_menu_item(item, top_k=top_k)
            results.append(result)

        return results

    def confirm_match(
        self,
        menu_item_id: UUID,
        recipe_id: UUID,
        confidence: Decimal = Decimal("1.0")
    ) -> MenuItemRecipe:
        """
        Confirm a recipe match for a menu item.
        """
        from datetime import datetime

        # Check for existing mapping
        existing = self.db.execute(
            select(MenuItemRecipe)
            .where(MenuItemRecipe.menu_item_id == menu_item_id)
        ).scalar_one_or_none()

        if existing:
            existing.standard_recipe_id = recipe_id
            existing.confirmed_by_user = True
            existing.confidence_score = confidence
            existing.confirmed_at = datetime.utcnow()
            self.db.commit()
            return existing

        # Create new mapping
        mapping = MenuItemRecipe(
            menu_item_id=menu_item_id,
            standard_recipe_id=recipe_id,
            confirmed_by_user=True,
            confidence_score=confidence,
            confirmed_at=datetime.utcnow()
        )
        self.db.add(mapping)
        self.db.commit()
        return mapping

    def auto_confirm_high_confidence(
        self,
        restaurant_id: UUID
    ) -> int:
        """
        Auto-confirm all matches with confidence > AUTO_ACCEPT_THRESHOLD.

        Returns number of items confirmed.
        """
        results = self.match_all_unconfirmed(restaurant_id)
        confirmed = 0

        for result in results:
            if result.auto_confirmed and result.matches:
                top_match = result.matches[0]
                self.confirm_match(
                    result.menu_item_id,
                    top_match.recipe_id,
                    top_match.confidence_score
                )
                confirmed += 1

        return confirmed

    def _get_recipe_cache(self) -> list[tuple[UUID, str, str, str]]:
        """Get cached list of (id, name, cuisine, category) for all recipes."""
        if self._recipe_cache is None:
            recipes = self.db.execute(
                select(
                    StandardRecipe.id,
                    StandardRecipe.name,
                    StandardRecipe.cuisine_type,
                    StandardRecipe.category
                )
            ).all()
            self._recipe_cache = recipes
        return self._recipe_cache

    def _exact_match(self, name: str) -> Optional[RecipeMatch]:
        """Find exact case-insensitive name match."""
        recipe = self.db.execute(
            select(StandardRecipe)
            .where(func.lower(StandardRecipe.name) == name.lower())
        ).scalar_one_or_none()

        if recipe:
            return RecipeMatch(
                recipe_id=recipe.id,
                recipe_name=recipe.name,
                cuisine_type=recipe.cuisine_type,
                category=recipe.category,
                prep_time_minutes=recipe.prep_time_minutes,
                confidence_score=Decimal("1.0"),
                match_method="exact"
            )
        return None

    def _fuzzy_match(self, name: str, limit: int = 5) -> list[RecipeMatch]:
        """Find fuzzy string matches using rapidfuzz."""
        recipes = self._get_recipe_cache()
        if not recipes:
            return []

        # Create name -> recipe mapping
        name_to_recipe = {r[1]: r for r in recipes}
        recipe_names = list(name_to_recipe.keys())

        # Find best matches
        results = process.extract(
            name,
            recipe_names,
            scorer=fuzz.token_sort_ratio,
            limit=limit
        )

        matches = []
        for match_name, score, _ in results:
            if score >= self.FUZZY_MIN_SCORE:
                r = name_to_recipe[match_name]
                # Convert 0-100 score to 0-1 confidence
                confidence = Decimal(str(score / 100))
                matches.append(RecipeMatch(
                    recipe_id=r[0],
                    recipe_name=r[1],
                    cuisine_type=r[2],
                    category=r[3],
                    prep_time_minutes=None,
                    confidence_score=confidence,
                    match_method="fuzzy"
                ))

        return matches

    def _category_match(
        self,
        category_path: str,
        menu_name: str
    ) -> list[RecipeMatch]:
        """Find recipes in the same category."""
        # Extract category from path (e.g., "Entrees > Beef > Steaks" -> "Entrees")
        main_category = category_path.split(">")[0].strip().lower()

        # Map common categories
        category_map = {
            "appetizers": ["Appetizer", "Starter"],
            "entrees": ["Entree", "Main Course", "Main"],
            "desserts": ["Dessert"],
            "beverages": ["Beverage", "Drink"],
            "sides": ["Side", "Side Dish"],
            "salads": ["Salad"],
            "soups": ["Soup"],
        }

        target_categories = category_map.get(main_category, [main_category])

        recipes = self._get_recipe_cache()
        matches = []

        for r in recipes:
            if r[3] and any(cat.lower() in r[3].lower() for cat in target_categories):
                # Also check name similarity
                name_score = fuzz.token_sort_ratio(menu_name, r[1])
                if name_score >= 50:  # Minimum threshold
                    confidence = Decimal(str(name_score / 100 * 0.8))  # Reduce confidence for category matches
                    matches.append(RecipeMatch(
                        recipe_id=r[0],
                        recipe_name=r[1],
                        cuisine_type=r[2],
                        category=r[3],
                        prep_time_minutes=None,
                        confidence_score=confidence,
                        match_method="category"
                    ))

        return sorted(matches, key=lambda x: x.confidence_score, reverse=True)[:3]
