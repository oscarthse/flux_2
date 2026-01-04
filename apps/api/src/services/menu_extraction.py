"""
Menu item extraction and deduplication service.

Automatically creates MenuItem records from transaction data with fuzzy matching
to handle name variations.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.menu import MenuItem, MenuItemPriceHistory
from src.services.menu_categorization import MenuCategorizationService


class MenuItemExtractionService:
    """
    Service for extracting and managing menu items from transaction data.

    Features:
    - Fuzzy matching to detect name variations ("Burger" vs "Hamburger")
    - Auto-creation of MenuItem records
    - Price history tracking
    - LLM-based categorization
    """

    FUZZY_MATCH_THRESHOLD = 85  # Levenshtein distance threshold (0-100)

    def __init__(self, db: Session, categorization_service: Optional[MenuCategorizationService] = None):
        """
        Initialize menu extraction service.

        Args:
            db: SQLAlchemy database session
            categorization_service: Optional categorization service (creates one if not provided)
        """
        self.db = db
        self.categorization_service = categorization_service or MenuCategorizationService()

    def find_existing_item(
        self,
        restaurant_id: UUID,
        item_name: str,
        use_fuzzy: bool = True
    ) -> Optional[MenuItem]:
        """
        Find existing menu item by name with optional fuzzy matching.

        Args:
            restaurant_id: Restaurant UUID
            item_name: Item name to search for
            use_fuzzy: Whether to use fuzzy matching for similar names

        Returns:
            Matching MenuItem or None
        """
        # Try exact match first (case-insensitive)
        stmt = select(MenuItem).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.name.ilike(item_name)
        )
        exact_match = self.db.execute(stmt).scalar_one_or_none()

        if exact_match:
            return exact_match

        if not use_fuzzy:
            return None

        # Try fuzzy matching on all items for this restaurant
        stmt = select(MenuItem).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_active == True
        )
        all_items = self.db.execute(stmt).scalars().all()

        best_match = None
        best_score = 0

        for item in all_items:
            # Use token_sort_ratio for better matching of reordered words
            score = fuzz.token_sort_ratio(item_name.lower(), item.name.lower())

            if score >= self.FUZZY_MATCH_THRESHOLD and score > best_score:
                best_score = score
                best_match = item

        return best_match

    def get_or_create_item(
        self,
        restaurant_id: UUID,
        item_name: str,
        price: Decimal,
        transaction_date: datetime,
        use_categorization: bool = True
    ) -> Tuple[MenuItem, bool, Optional[str]]:
        """
        Get existing menu item or create new one with auto-categorization.

        Args:
            restaurant_id: Restaurant UUID
            item_name: Item name
            price: Item price
            transaction_date: Date from transaction
            use_categorization: Whether to use LLM categorization

        Returns:
            Tuple of (menu_item, created, reasoning)
            - created: True if item was newly created
            - reasoning: Categorization reasoning (if categorized)
        """
        # Check if item already exists
        existing_item = self.find_existing_item(restaurant_id, item_name, use_fuzzy=True)

        if existing_item:
            # Update last_seen date
            if not existing_item.last_seen or transaction_date > existing_item.last_seen:
                existing_item.last_seen = transaction_date
                self.db.flush()

            return existing_item, False, None

        # Create new menu item
        category_path = None
        confidence = None
        reasoning = None

        if use_categorization and self.categorization_service.client:
            category_path, confidence, reasoning = self.categorization_service.categorize_item(item_name)

        new_item = MenuItem(
            restaurant_id=restaurant_id,
            name=item_name,
            price=price,
            category_path=category_path,
            first_seen=transaction_date,
            last_seen=transaction_date,
            auto_created=True,
            confidence_score=Decimal(str(confidence)) if confidence is not None else None,
            is_active=True
        )

        self.db.add(new_item)
        self.db.flush()

        # Create initial price history entry
        price_history = MenuItemPriceHistory(
            menu_item_id=new_item.id,
            price=price,
            effective_date=transaction_date.date(),
            source='auto_detected'
        )
        self.db.add(price_history)
        self.db.flush()

        return new_item, True, reasoning

    def detect_price_change(
        self,
        menu_item: MenuItem,
        new_price: Decimal,
        transaction_date: datetime
    ) -> bool:
        """
        Detect if item price has changed and create price history record.

        Args:
            menu_item: MenuItem to check
            new_price: New price from transaction
            transaction_date: Date of transaction

        Returns:
            True if price changed, False otherwise
        """
        # Check if price is different from current price
        if menu_item.price == new_price:
            return False

        # Check if we already have a price history entry for this date
        stmt = select(MenuItemPriceHistory).where(
            MenuItemPriceHistory.menu_item_id == menu_item.id,
            MenuItemPriceHistory.effective_date == transaction_date.date()
        )
        existing_entry = self.db.execute(stmt).scalar_one_or_none()

        if existing_entry:
            # Update existing entry if price is different
            if existing_entry.price != new_price:
                existing_entry.price = new_price
                self.db.flush()
                return True
            return False

        # Create new price history entry
        price_history = MenuItemPriceHistory(
            menu_item_id=menu_item.id,
            price=new_price,
            effective_date=transaction_date.date(),
            source='auto_detected'
        )
        self.db.add(price_history)

        # Update menu item's current price
        menu_item.price = new_price
        self.db.flush()

        return True

    def extract_items_from_transaction_data(
        self,
        restaurant_id: UUID,
        items_data: List[Dict]
    ) -> Dict[str, MenuItem]:
        """
        Extract and create menu items from transaction data.

        Args:
            restaurant_id: Restaurant UUID
            items_data: List of dicts with keys: name, price, transaction_date

        Returns:
            Dict mapping item names to MenuItem objects
        """
        menu_items_map = {}

        for item_data in items_data:
            item_name = item_data['name']
            price = item_data['price']
            transaction_date = item_data['transaction_date']

            menu_item, created, reasoning = self.get_or_create_item(
                restaurant_id=restaurant_id,
                item_name=item_name,
                price=price,
                transaction_date=transaction_date
            )

            menu_items_map[item_name] = menu_item

            # Check for price changes on existing items
            if not created:
                self.detect_price_change(menu_item, price, transaction_date)

        return menu_items_map

    def get_items_needing_review(
        self,
        restaurant_id: UUID,
        confidence_threshold: float = 0.7
    ) -> List[MenuItem]:
        """
        Get auto-created items with low confidence scores that need manual review.

        Args:
            restaurant_id: Restaurant UUID
            confidence_threshold: Items below this confidence need review

        Returns:
            List of MenuItem objects needing review
        """
        stmt = select(MenuItem).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.auto_created == True,
            MenuItem.confidence_score < confidence_threshold
        ).order_by(MenuItem.confidence_score.asc())

        return list(self.db.execute(stmt).scalars().all())
