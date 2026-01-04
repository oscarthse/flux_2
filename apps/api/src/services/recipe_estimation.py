"""
AI-powered recipe ingredient estimation service.

Generates estimated ingredient breakdowns for menu items to help restaurant
owners quickly set up COGS calculations.
"""
import json
from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass
from openai import OpenAI

from src.core.config import get_settings

settings = get_settings()


# Waste factor guidance for different ingredient categories
# Based on industry standards for restaurant waste (trimming, spoilage, prep errors)
WASTE_FACTOR_GUIDANCE = {
    "produce": {
        "leafy_greens": 0.15,  # lettuce, spinach, herbs (outer leaves, wilting)
        "root_vegetables": 0.10,  # potatoes, carrots, onions (peeling, trimming)
        "fruits": 0.12,  # tomatoes, avocados (bruising, ripeness)
        "delicate": 0.20,  # mushrooms, berries (very perishable)
    },
    "meat": {
        "beef": 0.20,  # trimming fat, gristle
        "chicken": 0.15,  # trimming, skin removal
        "fish": 0.25,  # filleting, bones, skin
        "processed": 0.05,  # bacon, sausage (minimal waste)
    },
    "dairy": {
        "cheese": 0.05,  # grating, trimming
        "milk": 0.02,  # spillage, expiration
        "cream": 0.03,  # minimal waste
    },
    "dry_goods": {
        "pasta": 0.01,  # minimal waste
        "rice": 0.02,  # rinsing loss
        "flour": 0.03,  # dust, spillage
        "bread": 0.08,  # trimming crusts, staling
    },
    "prepared": {
        "sauces": 0.05,  # portion control waste
        "dressings": 0.05,  # portion control waste
        "oils": 0.10,  # absorption, deep frying
    }
}


@dataclass
class EstimatedIngredient:
    """Estimated ingredient for a menu item"""
    name: str
    quantity: Decimal
    unit: str  # e.g., "g", "ml", "piece", "tbsp"
    base_cost: Decimal  # Cost before waste factor
    waste_factor: Decimal = Decimal("0")  # 0.00-0.60 (0-60% waste)
    estimated_cost: Optional[Decimal] = None  # Calculated: base_cost * (1 + waste_factor)
    perishability: Optional[str] = None  # "low", "medium", "high"
    category: Optional[str] = None  # "produce", "meat", "dairy", "dry_goods"
    notes: Optional[str] = None

    def __post_init__(self):
        """Calculate estimated_cost if not provided"""
        if self.estimated_cost is None:
            self.estimated_cost = self.base_cost * (1 + self.waste_factor)


@dataclass
class RecipeEstimate:
    """Complete recipe estimate for a menu item"""
    menu_item_name: str
    ingredients: List[EstimatedIngredient]
    total_estimated_cost: Decimal
    confidence: str  # "high", "medium", "low"
    notes: Optional[str] = None


class RecipeEstimationService:
    """
    Service for estimating recipe ingredients and costs using AI.

    Helps restaurant owners quickly set up recipes by providing intelligent
    estimates that they can review and adjust.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the service with OpenAI client"""
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def estimate_recipe(
        self,
        menu_item_name: str,
        menu_item_price: Optional[Decimal] = None,
        cuisine_type: Optional[str] = None
    ) -> RecipeEstimate:
        """
        Estimate ingredients and costs for a menu item.

        Args:
            menu_item_name: Name of the menu item
            menu_item_price: Optional selling price (helps estimate portion size)
            cuisine_type: Optional cuisine type for better estimates

        Returns:
            RecipeEstimate with ingredient breakdown
        """
        if not self.client:
            # Fallback if no API key
            return self._fallback_estimate(menu_item_name)

        prompt = self._build_prompt(menu_item_name, menu_item_price, cuisine_type)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional chef and restaurant cost analyst. "
                                   "Provide realistic ingredient estimates for menu items."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return self._parse_response(menu_item_name, result)

        except Exception as e:
            print(f"AI estimation failed: {e}, using fallback")
            return self._fallback_estimate(menu_item_name)

    def _build_prompt(
        self,
        menu_item_name: str,
        price: Optional[Decimal],
        cuisine_type: Optional[str]
    ) -> str:
        """Build the AI prompt for recipe estimation"""
        price_context = f"\nMenu price: ${price}" if price else ""
        cuisine_context = f"\nCuisine type: {cuisine_type}" if cuisine_type else ""

        return f"""Estimate the ingredients, quantities, and costs for this menu item, INCLUDING WASTE FACTORS:

Menu Item: {menu_item_name}{price_context}{cuisine_context}

Provide a JSON response with this structure:
{{
  "ingredients": [
    {{
      "name": "ingredient name",
      "quantity": 100,
      "unit": "g" (use: g, ml, piece, tbsp, tsp, cup, oz),
      "base_cost": 1.50,
      "waste_factor": 0.15,
      "category": "produce|meat|dairy|dry_goods|prepared",
      "perishability": "low|medium|high",
      "notes": "optional note"
    }}
  ],
  "confidence": "high|medium|low",
  "notes": "any assumptions or recommendations"
}}

WASTE FACTOR GUIDELINES (fraction, not percentage):
Produce:
- Leafy greens (lettuce, spinach, herbs): 0.15 (15% waste from outer leaves, wilting)
- Root vegetables (potatoes, carrots, onions): 0.10 (10% peeling/trimming)
- Fruits (tomatoes, avocados): 0.12 (12% bruising/ripeness)
- Delicate (mushrooms, berries): 0.20 (20% very perishable)

Meat/Protein:
- Beef: 0.20 (20% trimming fat/gristle)
- Chicken: 0.15 (15% trimming/skin)
- Fish: 0.25 (25% filleting/bones)
- Processed (bacon, sausage): 0.05 (5% minimal)

Dairy:
- Cheese: 0.05 (5% grating/trimming)
- Milk/cream: 0.02-0.03 (2-3% spillage)

Dry Goods:
- Pasta/rice: 0.01-0.02 (1-2% minimal)
- Flour: 0.03 (3% dust/spillage)
- Bread: 0.08 (8% trimming/staling)

Prepared:
- Sauces/dressings: 0.05 (5% portion control)
- Cooking oils: 0.10 (10% absorption/deep frying)

OTHER GUIDELINES:
- Use realistic portion sizes for restaurant servings
- base_cost = raw ingredient purchase price (before waste)
- Total cost will be calculated as: base_cost * (1 + waste_factor)
- Include main ingredients only (not garnishes unless significant)
- Use metric units (g, ml) for precision
- Target COGS of 25-35% of menu price if provided (INCLUDING waste costs)
- perishability affects waste factor (high = more waste risk)
"""

    def _parse_response(self, menu_item_name: str, response: dict) -> RecipeEstimate:
        """Parse AI response into RecipeEstimate with waste factors"""
        ingredients = []
        total_cost = Decimal("0")

        for ing in response.get("ingredients", []):
            # Handle both new format (base_cost + waste_factor) and old format (estimated_cost)
            base_cost = Decimal(str(ing.get("base_cost", ing.get("estimated_cost", 0))))
            waste_factor = Decimal(str(ing.get("waste_factor", 0)))

            # Ensure waste_factor is within valid range (0-0.60)
            waste_factor = min(max(waste_factor, Decimal("0")), Decimal("0.60"))

            ingredient = EstimatedIngredient(
                name=ing["name"],
                quantity=Decimal(str(ing["quantity"])),
                unit=ing["unit"],
                base_cost=base_cost,
                waste_factor=waste_factor,
                category=ing.get("category"),
                perishability=ing.get("perishability"),
                notes=ing.get("notes")
            )
            # estimated_cost is auto-calculated in __post_init__
            ingredients.append(ingredient)
            total_cost += ingredient.estimated_cost

        return RecipeEstimate(
            menu_item_name=menu_item_name,
            ingredients=ingredients,
            total_estimated_cost=total_cost,
            confidence=response.get("confidence", "medium"),
            notes=response.get("notes")
        )

    def _fallback_estimate(self, menu_item_name: str) -> RecipeEstimate:
        """
        Provide basic fallback estimate when AI is unavailable.

        Creates a simple placeholder that prompts user to fill in details.
        """
        # Very basic heuristics based on common items
        name_lower = menu_item_name.lower()

        if "burger" in name_lower:
            ingredients = [
                EstimatedIngredient("Beef patty", Decimal("150"), "g", base_cost=Decimal("2.50"), waste_factor=Decimal("0.20"), category="meat", perishability="medium"),
                EstimatedIngredient("Bun", Decimal("1"), "piece", base_cost=Decimal("0.40"), waste_factor=Decimal("0.08"), category="dry_goods", perishability="low"),
                EstimatedIngredient("Cheese", Decimal("30"), "g", base_cost=Decimal("0.30"), waste_factor=Decimal("0.05"), category="dairy", perishability="medium"),
                EstimatedIngredient("Lettuce", Decimal("20"), "g", base_cost=Decimal("0.10"), waste_factor=Decimal("0.15"), category="produce", perishability="high"),
                EstimatedIngredient("Tomato", Decimal("30"), "g", base_cost=Decimal("0.15"), waste_factor=Decimal("0.12"), category="produce", perishability="high"),
            ]
        elif "salad" in name_lower:
            ingredients = [
                EstimatedIngredient("Mixed greens", Decimal("100"), "g", base_cost=Decimal("0.80"), waste_factor=Decimal("0.15"), category="produce", perishability="high"),
                EstimatedIngredient("Vegetables", Decimal("50"), "g", base_cost=Decimal("0.50"), waste_factor=Decimal("0.12"), category="produce", perishability="medium"),
                EstimatedIngredient("Dressing", Decimal("30"), "ml", base_cost=Decimal("0.30"), waste_factor=Decimal("0.05"), category="prepared", perishability="low"),
            ]
        elif "fries" in name_lower or "fry" in name_lower:
            ingredients = [
                EstimatedIngredient("Potatoes", Decimal("200"), "g", base_cost=Decimal("0.50"), waste_factor=Decimal("0.10"), category="produce", perishability="low"),
                EstimatedIngredient("Oil", Decimal("20"), "ml", base_cost=Decimal("0.15"), waste_factor=Decimal("0.10"), category="prepared", perishability="low"),
                EstimatedIngredient("Salt", Decimal("2"), "g", base_cost=Decimal("0.01"), waste_factor=Decimal("0.01"), category="dry_goods", perishability="low"),
            ]
        else:
            # Generic fallback
            ingredients = [
                EstimatedIngredient(
                    "Main ingredient",
                    Decimal("100"),
                    "g",
                    base_cost=Decimal("1.00"),
                    waste_factor=Decimal("0.10"),
                    category="produce",
                    perishability="medium",
                    notes="Please update with actual ingredient"
                ),
            ]

        total_cost = sum(ing.estimated_cost for ing in ingredients)

        return RecipeEstimate(
            menu_item_name=menu_item_name,
            ingredients=ingredients,
            total_estimated_cost=total_cost,
            confidence="low",
            notes="Fallback estimate - please review and update all values"
        )
