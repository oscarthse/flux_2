"""
Generate synthetic restaurant sales data with known stockouts for testing.

Creates realistic transaction data with:
- 3 menu items with different velocity profiles
- 90 days of sales history
- Weekday/weekend seasonality patterns
- Random stockouts (5-10% of days)
- Promotion periods

This allows us to validate stockout detection accuracy.
"""
import random
import sys
from datetime import date, datetime, timedelta, time
from pathlib import Path
from decimal import Decimal
from uuid import uuid4

# Add parent directory to path to import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.models.user import User
from src.models.restaurant import Restaurant
from src.models.transaction import Transaction, TransactionItem
from src.models.menu import MenuItem
from src.models.inventory import InventorySnapshot


# Seed for reproducibility
random.seed(42)


class SyntheticDataGenerator:
    """Generate realistic restaurant sales data with controlled stockouts."""

    def __init__(self, db: Session):
        self.db = db

    def generate_test_restaurant(
        self,
        email: str = "test@stockout.com",
        days_history: int = 90
    ) -> Restaurant:
        """
        Create test restaurant with synthetic transaction data.

        Args:
            email: Email for test user
            days_history: Number of days of history to generate

        Returns:
            Restaurant object with generated data
        """
        # Create test user
        from src.core.security import hash_password

        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                hashed_password=hash_password("testpassword123")
            )
            self.db.add(user)
            self.db.flush()

        # Create restaurant
        restaurant = Restaurant(
            owner_id=user.id,
            name="Test Stockout Restaurant",
            timezone="UTC"
        )
        self.db.add(restaurant)
        self.db.flush()

        # Define menu items with different velocity profiles
        menu_items = [
            {
                "name": "Burger",
                "price": Decimal("12.99"),
                "velocity": "high",  # 8-12 units/day on average
                "dow_pattern": [8, 7, 7, 9, 12, 15, 14],  # Weekend spike
            },
            {
                "name": "Salad",
                "price": Decimal("9.99"),
                "velocity": "medium",  # 3-5 units/day
                "dow_pattern": [4, 5, 5, 4, 3, 3, 4],  # Lunch item
            },
            {
                "name": "Special Pasta",
                "price": Decimal("18.99"),
                "velocity": "low",  # 1-2 units/day
                "dow_pattern": [1, 1, 1, 2, 2, 3, 2],  # Weekend dinner item
            },
        ]

        created_items = []
        for item_data in menu_items:
            menu_item = MenuItem(
                restaurant_id=restaurant.id,
                name=item_data["name"],
                price=item_data["price"],
                auto_created=False
            )
            self.db.add(menu_item)
            self.db.flush()

            created_items.append({
                "item": menu_item,
                "velocity": item_data["velocity"],
                "dow_pattern": item_data["dow_pattern"],
            })

        self.db.commit()

        # Generate transactions
        end_date = date.today()
        start_date = end_date - timedelta(days=days_history)

        # Track stockout dates for ground truth validation
        stockout_dates = {}

        current_date = start_date
        while current_date <= end_date:
            # Randomly induce stockouts (5-10% of days per item)
            day_stockouts = []

            for item_data in created_items:
                menu_item = item_data["item"]

                # Determine if stockout today (10% chance for high-velocity items)
                is_stockout = False
                if item_data["velocity"] == "high" and random.random() < 0.10:
                    is_stockout = True
                    day_stockouts.append(menu_item.id)

                    # Record stockout for validation
                    if menu_item.name not in stockout_dates:
                        stockout_dates[menu_item.name] = []
                    stockout_dates[menu_item.name].append(current_date)

            # Generate daily transactions for this date
            self._generate_day_transactions(
                restaurant=restaurant,
                transaction_date=current_date,
                menu_items_data=created_items,
                stockout_item_ids=day_stockouts
            )

            current_date += timedelta(days=1)

        # Create InventorySnapshot records for actual stockouts
        for item_data in created_items:
            menu_item = item_data["item"]
            if menu_item.name in stockout_dates:
                for stockout_date in stockout_dates[menu_item.name]:
                    snapshot = InventorySnapshot(
                        restaurant_id=restaurant.id,
                        menu_item_id=menu_item.id,
                        date=stockout_date,
                        stockout_flag='Y',
                        source='synthetic_ground_truth'
                    )
                    self.db.add(snapshot)

        self.db.commit()

        print(f"✅ Generated {days_history} days of data for '{restaurant.name}'")
        print(f"   Menu items: {len(created_items)}")
        print(f"   Ground truth stockouts:")
        for item_name, dates in stockout_dates.items():
            print(f"     - {item_name}: {len(dates)} stockouts")

        return restaurant

    def _generate_day_transactions(
        self,
        restaurant: Restaurant,
        transaction_date: date,
        menu_items_data: list,
        stockout_item_ids: list
    ):
        """Generate transactions for a single day."""
        dow = transaction_date.weekday()

        # Operating hours (10 AM to 10 PM)
        first_order_time = time(10, random.randint(0, 59))
        last_order_time = time(21, random.randint(0, 59))

        total_amount = Decimal("0.00")
        transaction_items = []

        for item_data in menu_items_data:
            menu_item = item_data["item"]

            # Get expected quantity for this day of week
            base_qty = item_data["dow_pattern"][dow]

            # If stockout, set to exactly 0 sales (complete stockout)
            if menu_item.id in stockout_item_ids:
                qty = 0  # Zero sales on stockout days
            else:
                # Add random variance (±20%)
                variance = random.uniform(0.8, 1.2)
                qty = max(0, int(base_qty * variance))

            if qty > 0:
                item_total = menu_item.price * qty
                total_amount += item_total

                transaction_items.append({
                    "menu_item_name": menu_item.name,
                    "quantity": qty,
                    "unit_price": menu_item.price,
                    "total": item_total
                })

        # Only create transaction if there were sales
        if transaction_items:
            # Check if any stockouts occurred
            stockout_occurred = len(stockout_item_ids) > 0

            transaction = Transaction(
                restaurant_id=restaurant.id,
                transaction_date=transaction_date,
                total_amount=total_amount,
                first_order_time=first_order_time,
                last_order_time=last_order_time,
                is_promo=False,
                stockout_occurred=stockout_occurred
            )
            self.db.add(transaction)
            self.db.flush()

            # Add transaction items
            for item_data in transaction_items:
                tx_item = TransactionItem(
                    transaction_id=transaction.id,
                    menu_item_name=item_data["menu_item_name"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"],
                    total=item_data["total"],
                )
                self.db.add(tx_item)


def main():
    """Run synthetic data generation."""
    db = SessionLocal()

    try:
        print("🔧 Generating synthetic stockout test data...\n")

        generator = SyntheticDataGenerator(db)
        restaurant = generator.generate_test_restaurant(
            email="stockout_test@flux.com",
            days_history=90
        )

        print(f"\n✅ Synthetic data generated successfully!")
        print(f"   Restaurant ID: {restaurant.id}")
        print(f"   Restaurant Name: {restaurant.name}")
        print(f"\n💡 Test this data by:")
        print(f"   1. POST /api/inventory/detect-stockouts (days_to_analyze=90)")
        print(f"   2. Compare detected stockouts with ground truth")
        print(f"   3. Validate velocity calculations")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
