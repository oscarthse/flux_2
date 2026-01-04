"""
Menu item categorization service using OpenAI LLM.

Automatically categorizes menu items into a 3-level taxonomy for ML forecasting.
"""
import json
from typing import Dict, List, Optional, Tuple
from openai import OpenAI

from src.core.config import get_settings

settings = get_settings()


# Restaurant menu category taxonomy (3 levels)
CATEGORY_TAXONOMY = {
    "Appetizers": ["Salads", "Soups", "Fried", "Vegetarian", "Seafood", "Other"],
    "Entrees": ["Beef", "Pork", "Chicken", "Seafood", "Vegetarian", "Pasta", "Other"],
    "Sides": ["Vegetables", "Starches", "Salads", "Bread", "Other"],
    "Desserts": ["Cakes", "Ice Cream", "Pies", "Pastries", "Other"],
    "Beverages": ["Alcoholic", "Non-Alcoholic", "Coffee/Tea", "Juices", "Other"],
    "Other": ["Condiments", "Add-Ons", "Specials", "Other"]
}


class MenuCategorizationService:
    """
    Service for categorizing menu items using OpenAI LLM.

    Uses GPT-4 to infer category paths from item names, enabling hierarchical
    pooling for ML cold-start forecasting.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize categorization service.

        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def _build_prompt(self, item_name: str) -> str:
        """
        Build categorization prompt for OpenAI.

        Args:
            item_name: Menu item name to categorize

        Returns:
            Formatted prompt string
        """
        taxonomy_str = json.dumps(CATEGORY_TAXONOMY, indent=2)

        return f"""You are a restaurant menu categorization expert. Categorize the following menu item into our 3-level taxonomy.

Menu Item: "{item_name}"

Available Categories (Level 1 > Level 2 > Level 3):
{taxonomy_str}

Instructions:
1. Choose the most appropriate Level 1 category (Appetizers, Entrees, Sides, Desserts, Beverages, Other)
2. Choose the most appropriate Level 2 subcategory from that Level 1's options
3. For Level 3, use a specific descriptor (max 2-3 words) that describes the dish style/preparation
4. Return confidence score 0.0-1.0 based on how certain you are

Examples:
- "Ribeye Steak" → "Entrees > Beef > Grilled Steak" (confidence: 0.95)
- "Caesar Salad" → "Appetizers > Salads > Classic Caesar" (confidence: 0.90)
- "Loaded Baked Potato" → "Sides > Starches > Baked Potato" (confidence: 0.85)
- "Tiramisu" → "Desserts > Cakes > Italian Cake" (confidence: 0.90)
- "Craft IPA" → "Beverages > Alcoholic > Beer" (confidence: 0.95)

Return ONLY a JSON object with this exact format:
{{
  "category_path": "Level1 > Level2 > Level3",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""

    def categorize_item(self, item_name: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Categorize a menu item using OpenAI LLM.

        Args:
            item_name: Menu item name to categorize

        Returns:
            Tuple of (category_path, confidence_score, reasoning)
            Returns (None, None, None) if API key not configured
        """
        if not self.client:
            # No API key configured - return None for all fields
            return None, None, "OpenAI API key not configured"

        try:
            prompt = self._build_prompt(item_name)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=[
                    {"role": "system", "content": "You are a restaurant menu categorization expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent categorization
                max_tokens=150,
                response_format={"type": "json_object"}
            )

            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            category_path = result.get("category_path")
            confidence = float(result.get("confidence", 0.0))
            reasoning = result.get("reasoning", "")

            return category_path, confidence, reasoning

        except Exception as e:
            # Log error and return fallback
            return None, 0.0, f"Categorization failed: {str(e)}"

    def categorize_batch(self, item_names: List[str]) -> List[Tuple[str, Optional[str], Optional[float], Optional[str]]]:
        """
        Categorize multiple menu items.

        Args:
            item_names: List of menu item names

        Returns:
            List of tuples: (item_name, category_path, confidence, reasoning)
        """
        results = []
        for item_name in item_names:
            category_path, confidence, reasoning = self.categorize_item(item_name)
            results.append((item_name, category_path, confidence, reasoning))

        return results

    def validate_category_path(self, category_path: str) -> bool:
        """
        Validate that a category path follows the taxonomy structure.

        Args:
            category_path: Category path string (e.g., "Entrees > Beef > Steaks")

        Returns:
            True if valid, False otherwise
        """
        if not category_path:
            return False

        parts = [p.strip() for p in category_path.split(">")]
        if len(parts) != 3:
            return False

        level1, level2, level3 = parts

        # Check Level 1 exists
        if level1 not in CATEGORY_TAXONOMY:
            return False

        # Check Level 2 is in Level 1's allowed subcategories
        if level2 not in CATEGORY_TAXONOMY[level1]:
            return False

        # Level 3 is free-form but should not be empty
        if not level3 or len(level3) > 50:
            return False

        return True

    def get_taxonomy(self) -> Dict[str, List[str]]:
        """
        Get the full category taxonomy.

        Returns:
            Dictionary mapping Level 1 categories to Level 2 subcategories
        """
        return CATEGORY_TAXONOMY.copy()
