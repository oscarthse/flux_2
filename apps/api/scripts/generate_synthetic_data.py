"""
Synthetic Restaurant Data Generator for Forecasting Validation

Generates realistic sales data with:
- Seasonality (weekday/weekend patterns)
- Promotions (known discount periods)
- Stockouts (random 5% of days)
- Trend (slight growth over time)
- Noise (realistic variance)

This provides **ground truth** data for validating forecast accuracy.
"""
import sys
import os
from datetime import date, timedelta, time
import random
import numpy as np
from decimal import Decimal
from uuid import uuid4

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.db.session import SessionLocal
from src.models.user import User
from src.models.restaurant import Restaurant
from src.models.menu import MenuItem
from src.models.transaction import Transaction, TransactionItem
from src.models.inventory import InventorySnapshot
from src.models.promotion import Promotion
from src.models.data_upload import DataUpload
from src.core.security import hash_password


class SyntheticDataGenerator:
    """Generate realistic restaurant sales data for testing."""

    def __init__(self, db, random_seed=42):
        self.db = db
        np.random.seed(random_seed)
        random.seed(random_seed)

    def generate_quantity(self, base_mean, dow, is_promo=False, is_stockout=False):
        """
        Generate realistic daily quantity with seasonality, promotions, stockouts.

        Args:
            base_mean: Base daily mean sales
            dow: Day of week (0=Monday, 6=Sunday)
            is_promo: Whether there's a promotion active
            is_stockout: Whether item is stocked out

        Returns:
            Integer quantity (0 if stocked out)
        """
        if is_stockout:
            # Partial stockout: sell 20-40% of normal demand
            return int(max(0, np.random.normal(base_mean * 0.3, base_mean * 0.1)))

        # Weekend multiplier
        weekend_mult = 1.8 if dow >= 5 else 1.0  # Sat/Sun
        friday_mult = 1.4 if dow == 4 else 1.0   # Friday bump

        # Promotion lift (15-25% boost)
        promo_lift = 1.2 if is_promo else 1.0

        # Calculate expected quantity
        mu = base_mean * weekend_mult * friday_mult * promo_lift

        # Add realistic variance (Negative Binomial overdispersion)
        # CV (coefficient of variation) ~0.3-0.4 is realistic for restaurant sales
        qty = int(max(0, np.random.normal(mu, mu * 0.35)))

        return qty

    def generate_restaurant_data(
        self,
        email="test@flux.com",
        restaurant_name="Synthetic Test Restaurant",
        days=90,
        stockout_probability=0.05,
        num_promotions=3,
        clear_existing=True
    ):
        """
        Generate complete synthetic restaurant dataset.

        Args:
            email: User email
            restaurant_name: Restaurant name
            days: Number of days of history
            stockout_probability: Probability of stockout per item per day
            num_promotions: Number of promotion periods to generate
            clear_existing: If True, delete existing data before generating

        Returns:
            dict with user, restaurant, items, transactions
        """
        # 1. Create User
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Creating user {email}...")
            user = User(email=email, hashed_password=hash_password("test123"))
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        else:
            print(f"Found existing user {email}")

        # 2. Create Restaurant
        restaurant = self.db.query(Restaurant).filter(
            Restaurant.owner_id == user.id,
            Restaurant.name == restaurant_name
        ).first()

        if not restaurant:
            print(f"Creating restaurant '{restaurant_name}'...")
            restaurant = Restaurant(
                name=restaurant_name,
                owner_id=user.id,
                timezone="America/Los_Angeles"
            )
            self.db.add(restaurant)
            self.db.commit()
            self.db.refresh(restaurant)
        else:
            print(f"Using existing restaurant '{restaurant_name}'")

            # Clear existing data if requested
            if clear_existing:
                print("Clearing existing synthetic data...")
                from src.models.forecast import DemandForecast

                # Delete in order to respect foreign keys
                self.db.query(DemandForecast).filter(
                    DemandForecast.restaurant_id == restaurant.id
                ).delete()
                self.db.query(TransactionItem).filter(
                    TransactionItem.transaction_id.in_(
                        self.db.query(Transaction.id).filter(
                            Transaction.restaurant_id == restaurant.id
                        )
                    )
                ).delete(synchronize_session=False)
                self.db.query(Transaction).filter(
                    Transaction.restaurant_id == restaurant.id
                ).delete()
                self.db.query(InventorySnapshot).filter(
                    InventorySnapshot.restaurant_id == restaurant.id
                ).delete()
                self.db.query(Promotion).filter(
                    Promotion.restaurant_id == restaurant.id
                ).delete()
                self.db.query(DataUpload).filter(
                    DataUpload.restaurant_id == restaurant.id
                ).delete()
                # Note: Keep menu items as they may be referenced elsewhere
                self.db.commit()
                print("✅ Existing data cleared")

        # 3. Define Menu Items with realistic patterns
        # (name, base_mean, price, category)
        item_configs = [
            ("Burger", 35, 14.99, "Entrees > Beef"),
            ("Caesar Salad", 25, 11.99, "Salads"),
            ("French Fries", 50, 5.99, "Sides"),
        ]

        items = {}
        for name, base_mean, price, category in item_configs:
            item = self.db.query(MenuItem).filter(
                MenuItem.restaurant_id == restaurant.id,
                MenuItem.name == name
            ).first()

            if not item:
                print(f"Creating menu item: {name}")
                item = MenuItem(
                    restaurant_id=restaurant.id,
                    name=name,
                    price=Decimal(str(price)),
                    category_path=category,
                    is_active=True
                )
                self.db.add(item)
                self.db.flush()

            items[name] = {
                "model": item,
                "base_mean": base_mean,
                "price": price
            }

        self.db.commit()

        # 4. Generate Promotion Periods
        promotions = self._generate_promotions(
            restaurant,
            items,
            days,
            num_promotions
        )

        # 5. Generate Daily Transactions
        start_date = date.today() - timedelta(days=days)
        print(f"\nGenerating {days} days of transaction history...")

        transactions_created = 0
        stockouts_created = 0

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            dow = current_date.weekday()  # 0=Mon, 6=Sun

            # Determine if promotions active
            active_promos = {
                name: any(
                    p["start_date"] <= current_date <= p["end_date"]
                    for p in promotions if p["item_name"] == name
                )
                for name in items.keys()
            }

            # Generate transaction for this day
            day_total = Decimal("0.00")
            day_items = []

            for name, item_data in items.items():
                # Random stockout
                is_stockout = random.random() < stockout_probability
                is_promo = active_promos[name]

                # Generate quantity
                qty = self.generate_quantity(
                    item_data["base_mean"],
                    dow,
                    is_promo=is_promo,
                    is_stockout=is_stockout
                )

                if qty > 0:
                    line_total = Decimal(str(qty * item_data["price"]))
                    day_items.append({
                        "name": name,
                        "qty": qty,
                        "price": item_data["price"],
                        "total": line_total,
                        "menu_item_id": item_data["model"].id
                    })
                    day_total += line_total

                # Record stockout
                if is_stockout:
                    snapshot = InventorySnapshot(
                        restaurant_id=restaurant.id,
                        menu_item_id=item_data["model"].id,
                        date=current_date,
                        stockout_flag='Y',
                        source='synthetic'
                    )
                    self.db.add(snapshot)
                    stockouts_created += 1

            # Create transaction if any items sold
            if day_items:
                # Random operating hours (11 AM - 10 PM typical)
                first_order = time(11, random.randint(0, 30))
                last_order = time(21 + random.randint(0, 1), random.randint(0, 59))

                tx = Transaction(
                    restaurant_id=restaurant.id,
                    transaction_date=current_date,
                    total_amount=day_total,
                    first_order_time=first_order,
                    last_order_time=last_order,
                    stockout_occurred=any(
                        random.random() < stockout_probability for _ in items
                    ),
                    is_promo=any(active_promos.values())
                )
                self.db.add(tx)
                self.db.flush()

                # Add line items
                for item in day_items:
                    ti = TransactionItem(
                        transaction_id=tx.id,
                        menu_item_name=item["name"],
                        quantity=item["qty"],
                        unit_price=Decimal(str(item["price"])),
                        total=item["total"]
                    )
                    self.db.add(ti)

                transactions_created += 1

        self.db.commit()

        # 6. Create Upload Record (so dashboard recognizes the data)
        print("\nCreating upload record...")
        upload = DataUpload(
            restaurant_id=restaurant.id,
            status='COMPLETED',
            file_hash='synthetic_data_v1',
            errors={
                'rows_processed': transactions_created,
                'rows_failed': 0,
                'errors': []
            }
        )
        self.db.add(upload)
        self.db.commit()

        print(f"\n✅ Synthetic data generation complete:")
        print(f"  - {len(items)} menu items")
        print(f"  - {transactions_created} transactions")
        print(f"  - {len(promotions)} promotions")
        print(f"  - {stockouts_created} stockouts")
        print(f"  - 1 upload record created")

        return {
            "user": user,
            "restaurant": restaurant,
            "items": items,
            "transactions": transactions_created,
            "promotions": promotions,
            "stockouts": stockouts_created,
            "upload_id": upload.id
        }

    def _generate_promotions(self, restaurant, items, days, num_promotions):
        """Generate promotion periods with known start/end dates."""
        promotions = []
        start_date = date.today() - timedelta(days=days)

        # Distribute promotions evenly across the period
        promo_spacing = days // (num_promotions + 1)

        for i in range(num_promotions):
            # Random item
            item_name = random.choice(list(items.keys()))

            # Random start date (avoid first/last week for testing)
            promo_start_offset = promo_spacing * (i + 1) + random.randint(-5, 5)
            promo_start = start_date + timedelta(days=promo_start_offset)

            # Duration: 7-14 days
            duration = random.randint(7, 14)
            promo_end = promo_start + timedelta(days=duration)

            # Discount: 15-25%
            discount_pct = random.randint(15, 25)

            print(f"  Promotion {i+1}: {item_name} {discount_pct}% off from {promo_start} to {promo_end}")

            # Create promotion record
            promo = Promotion(
                restaurant_id=restaurant.id,
                name=f"{discount_pct}% off {item_name}",
                discount_type='percentage',
                discount_value=Decimal(str(discount_pct)),
                start_date=promo_start,
                end_date=promo_end,
                status='completed' if promo_end < date.today() else 'active',
                is_exploration=False
            )
            self.db.add(promo)

            promotions.append({
                "item_name": item_name,
                "start_date": promo_start,
                "end_date": promo_end,
                "discount_pct": discount_pct
            })

        self.db.commit()
        return promotions


def main():
    """Generate synthetic data for testing."""
    db = SessionLocal()

    try:
        generator = SyntheticDataGenerator(db, random_seed=42)

        result = generator.generate_restaurant_data(
            email="synthetic@example.com",
            restaurant_name="Synthetic Test Cafe",
            days=90,
            stockout_probability=0.05,  # 5% stockout rate
            num_promotions=3
        )

        print("\n" + "="*50)
        print("Synthetic data ready for backtesting!")
        print("="*50)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
