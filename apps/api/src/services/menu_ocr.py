"""
Menu OCR service for extracting menu items from photos.

Uses OpenAI GPT-4o Vision API to extract menu item names, prices, and descriptions
from uploaded menu photos.
"""
import base64
from typing import List, Optional
from dataclasses import dataclass
from openai import OpenAI
import json

from src.core.config import get_settings

settings = get_settings()


@dataclass
class MenuItemExtraction:
    """Extracted menu item from photo."""
    name: str
    category: Optional[str]
    description: Optional[str]
    price: Optional[float]
    confidence: float  # 0.0-1.0


@dataclass
class MenuExtractionResult:
    """Result of menu photo OCR."""
    items: List[MenuItemExtraction]
    total_items: int
    raw_text: Optional[str]  # Raw OCR output for debugging


class MenuOCRService:
    """Service for extracting menu items from photos using GPT-4o Vision."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    def extract_menu_items(self, image_data: bytes) -> MenuExtractionResult:
        """
        Extract menu items from a photo using GPT-4o Vision.

        Args:
            image_data: Raw image bytes (JPEG, PNG, etc.)

        Returns:
            MenuExtractionResult with extracted items
        """
        if not self.client:
            # Return fallback if API key not configured
            return self._fallback_extraction()

        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # Prepare the prompt
            prompt = """
You are a restaurant menu parser. Analyze this menu photo and extract ALL menu items.

For each menu item, extract:
1. **name**: The dish name (required)
2. **category**: Category if visible (Appetizers, Entrees, Desserts, Beverages, etc.)
3. **description**: Brief description if provided
4. **price**: Price in dollars (just the number, e.g., 12.99)

Return ONLY a valid JSON array with this exact structure:
[
  {
    "name": "Caesar Salad",
    "category": "Appetizers",
    "description": "Romaine lettuce with parmesan and croutons",
    "price": 8.99,
    "confidence": 0.95
  },
  ...
]

Rules:
- Set confidence to 1.0 if you're certain, 0.7-0.9 if somewhat certain, <0.7 if unsure
- If category is not visible, use null
- If description is not visible, use null
- If price is not visible, use null
- Extract ONLY actual menu items, not headers, footers, or restaurant info
- Return ONLY the JSON array, no other text
"""

            # Call GPT-4o Vision API
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using mini for cost efficiency
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1  # Low temperature for consistent extraction
            )

            # Parse response
            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            # Parse JSON
            items_data = json.loads(content)

            # Convert to dataclass
            items = [
                MenuItemExtraction(
                    name=item["name"],
                    category=item.get("category"),
                    description=item.get("description"),
                    price=item.get("price"),
                    confidence=item.get("confidence", 0.8)
                )
                for item in items_data
            ]

            return MenuExtractionResult(
                items=items,
                total_items=len(items),
                raw_text=content
            )

        except Exception as e:
            print(f"Error extracting menu items: {e}")
            # Return fallback on error
            return self._fallback_extraction()

    def _fallback_extraction(self) -> MenuExtractionResult:
        """
        Fallback extraction when API is unavailable.
        Returns empty result.
        """
        return MenuExtractionResult(
            items=[],
            total_items=0,
            raw_text="API unavailable or error occurred"
        )
