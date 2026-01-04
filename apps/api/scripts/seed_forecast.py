import sys
import os
from datetime import date, timedelta
import random
import numpy as np

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.db.session import SessionLocal
from src.models.user import User
from src.models.restaurant import Restaurant
from src.models.menu import MenuItem
from src.models.transaction import Transaction, TransactionItem
from src.models.data_health import DataHealthScore
from src.services.forecast import ForecastService
from src.core.security import hash_password

def seed_forecast_data(email="chef@laboqueria.es"):
    db = SessionLocal()
    try:
        # 1. Get/Create User
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Creating user {email}...")
            user = User(email=email, hashed_password=hash_password("flux123"))
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            print(f"Found user {email}")

        # 2. Get/Create Restaurant
        restaurant = db.query(Restaurant).filter(Restaurant.owner_id == user.id).first()
        if not restaurant:
            print("Creating restaurant 'La Boqueria'...")
            restaurant = Restaurant(name="La Boqueria", owner_id=user.id)
            db.add(restaurant)
            db.commit()
            db.refresh(restaurant)
        else:
            print(f"Using restaurant '{restaurant.name}'")

        # 3. Define Items & Patterns
        # (Name, Base Mean, Weekend Multiplier, Price)
        item_configs = [
            ("Patatas Bravas", 40, 1.8, 8.50),     # High volume, strong weekend peak
            ("Seafood Paella", 12, 2.5, 24.00),    # Expensive, mostly weekends
            ("Sangria Pitcher", 15, 2.0, 18.00),   # Drinks
            ("Gazpacho", 20, 1.1, 7.50)            # Steady lunch item
        ]

        items = {}
        for name, mean, weekend_mult, price in item_configs:
            item = db.query(MenuItem).filter(
                MenuItem.restaurant_id == restaurant.id,
                MenuItem.name == name
            ).first()

            if not item:
                item = MenuItem(name=name, restaurant_id=restaurant.id, price=price)
                db.add(item)
                db.commit()
                db.refresh(item)
            items[name] = item

        # 4. Generate 90 Days of History
        start_date = date.today() - timedelta(days=90)
        print("Generating 90 days of transaction history...")

        # Pre-fetch existing transactions to avoid dupes?
        # Simpler: just Delete old transactions for these items?
        # Or checking if date exists. For seeding, let's just append.

        for i in range(90):
            current_date = start_date + timedelta(days=i)
            dow = current_date.weekday() # 0=Mon, 6=Sun
            is_weekend = dow >= 4 # Fri, Sat, Sun

            # Create one aggregated transaction per day per item (simplified)
            # Or one big transaction for the day containing all items

            day_total = 0.0

            # Determine quantities
            day_items = []

            for name, base_mean, weekend_mult, price in item_configs:
                # Calculate Lambda for Poisson/NegBin
                mu = base_mean * (weekend_mult if is_weekend else 1.0)

                # Add noise (Negative Binomial overdispersion)
                # p = 0.5 (bursty). n = mu.
                # Scipy nbinom: n is number of successes parameters, p is probability.
                # Here uses numpy.random.negative_binomial?
                # Simpler: Poisson * Gamma noise

                # Randomized quantity centered around mu
                # Use simple normal approximation clipped to 0 for demo
                qty = int(max(0, np.random.normal(mu, mu * 0.3)))

                if qty > 0:
                    line_total = float(qty) * price
                    day_items.append({
                        "name": name,
                        "qty": qty,
                        "unit": price,
                        "total": line_total
                    })
                    day_total += line_total

            if day_items:
                # Create Transaction
                txn = Transaction(
                    restaurant_id=restaurant.id,
                    transaction_date=current_date,
                    total_amount=day_total,
                    stockout_occurred=False,
                    is_promo=False
                )
                db.add(txn)
                db.flush() # Get ID

                for line in day_items:
                    ti = TransactionItem(
                        transaction_id=txn.id,
                        menu_item_name=line["name"],
                        quantity=line["qty"],
                        unit_price=line["unit"],
                        total=line["total"]
                    )
                    db.add(ti)

        db.commit()
        print("History seeded.")

        # 5. Generate Forecasts
        print("Generating Forecasts...")
        service = ForecastService(db)

        for name, _, _, _ in item_configs:
            print(f"Forecasting {name}...")
            service.generate_forecasts(
                restaurant_id=restaurant.id,
                menu_item_name=name,
                days_ahead=14
            )

        print("Done! Forecasts ready.")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_forecast_data()
