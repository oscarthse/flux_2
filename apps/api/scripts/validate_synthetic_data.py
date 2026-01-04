"""
Validate the quality of synthetic data for forecasting.

Checks:
- Seasonality patterns (weekday vs weekend)
- Promotion lift effects
- Stockout impact
- Data completeness
"""
import sys
import os
from datetime import timedelta
import pandas as pd
import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.db.session import SessionLocal
from src.models.restaurant import Restaurant
from src.models.transaction import Transaction, TransactionItem
from src.models.promotion import Promotion
from sqlalchemy import select, func


def validate_synthetic_data(restaurant_name="Synthetic Test Cafe"):
    """Validate synthetic data patterns."""
    db = SessionLocal()

    try:
        # Find restaurant
        restaurant = db.query(Restaurant).filter(
            Restaurant.name == restaurant_name
        ).first()

        if not restaurant:
            print(f"❌ Restaurant '{restaurant_name}' not found!")
            return

        print(f"✅ Found restaurant: {restaurant.name}")
        print("="*60)

        # 1. Check data completeness
        print("\n📊 DATA COMPLETENESS:")
        tx_count = db.query(Transaction).filter(
            Transaction.restaurant_id == restaurant.id
        ).count()

        date_range = db.execute(
            select(
                func.min(Transaction.transaction_date),
                func.max(Transaction.transaction_date)
            ).where(Transaction.restaurant_id == restaurant.id)
        ).first()

        min_date, max_date = date_range
        days_span = (max_date - min_date).days if max_date and min_date else 0

        print(f"  Transactions: {tx_count}")
        print(f"  Date range: {min_date} to {max_date} ({days_span} days)")
        print(f"  Coverage: {tx_count / (days_span + 1) * 100:.1f}%")

        # 2. Analyze seasonality
        print("\n📈 SEASONALITY PATTERNS:")

        # Query all transactions with items
        stmt = (
            select(
                Transaction.transaction_date,
                TransactionItem.menu_item_name,
                TransactionItem.quantity
            )
            .join(TransactionItem, TransactionItem.transaction_id == Transaction.id)
            .where(Transaction.restaurant_id == restaurant.id)
        )

        results = db.execute(stmt).all()
        df = pd.DataFrame(results, columns=["date", "item", "quantity"])
        df["date"] = pd.to_datetime(df["date"])  # Convert to datetime
        df["dow"] = df["date"].dt.dayofweek
        df["is_weekend"] = df["dow"] >= 5

        # Group by item and weekend
        seasonality = df.groupby(["item", "is_weekend"])["quantity"].agg([
            ("mean", "mean"),
            ("std", "std"),
            ("count", "count")
        ]).reset_index()

        for item in df["item"].unique():
            item_data = seasonality[seasonality["item"] == item]
            weekday_mean = item_data[item_data["is_weekend"] == False]["mean"].values[0]
            weekend_mean = item_data[item_data["is_weekend"] == True]["mean"].values[0]
            weekend_mult = weekend_mean / weekday_mean if weekday_mean > 0 else 0

            print(f"\n  {item}:")
            print(f"    Weekday avg: {weekday_mean:.1f} units")
            print(f"    Weekend avg: {weekend_mean:.1f} units")
            print(f"    Weekend multiplier: {weekend_mult:.2f}x")
            print(f"    ✅ Seasonality detected!" if weekend_mult > 1.2 else f"    ⚠️  Weak seasonality")

        # 3. Analyze promotion effects
        print("\n🏷️  PROMOTION EFFECTS:")

        promos = db.query(Promotion).filter(
            Promotion.restaurant_id == restaurant.id
        ).all()

        for promo in promos:
            # Get sales during promotion
            promo_sales = df[
                (df["date"] >= promo.start_date) &
                (df["date"] <= promo.end_date)
            ]

            # Get baseline sales (30 days before promo)
            baseline_start = promo.start_date - timedelta(days=30)
            baseline_end = promo.start_date - timedelta(days=1)

            baseline_sales = df[
                (df["date"] >= baseline_start) &
                (df["date"] <= baseline_end)
            ]

            if len(promo_sales) > 0 and len(baseline_sales) > 0:
                promo_mean = promo_sales["quantity"].mean()
                baseline_mean = baseline_sales["quantity"].mean()
                lift = ((promo_mean - baseline_mean) / baseline_mean * 100) if baseline_mean > 0 else 0

                print(f"\n  {promo.name} ({promo.start_date} to {promo.end_date}):")
                print(f"    Baseline avg: {baseline_mean:.1f} units/day")
                print(f"    Promo avg: {promo_mean:.1f} units/day")
                print(f"    Lift: {lift:+.1f}%")
                print(f"    ✅ Promotion impact detected!" if abs(lift) > 5 else f"    ⚠️  No clear impact")

        # 4. Check stockouts
        print("\n📦 STOCKOUT TRACKING:")

        from src.models.inventory import InventorySnapshot

        stockouts = db.query(InventorySnapshot).filter(
            InventorySnapshot.restaurant_id == restaurant.id,
            InventorySnapshot.stockout_flag == 'Y'
        ).count()

        print(f"  Stockout events recorded: {stockouts}")
        print(f"  Rate: {stockouts / (days_span * 3) * 100:.1f}% (target: ~5%)")

        # 5. Data quality summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY:")
        print("="*60)

        checks = []

        # Check 1: Adequate history
        if days_span >= 85:
            checks.append("✅ 90 days of history")
        else:
            checks.append(f"⚠️  Only {days_span} days (target: 90)")

        # Check 2: Seasonality
        has_seasonality = weekend_mult > 1.2
        if has_seasonality:
            checks.append("✅ Weekend seasonality detected")
        else:
            checks.append("⚠️  Weak seasonality")

        # Check 3: Promotions
        if len(promos) >= 3:
            checks.append(f"✅ {len(promos)} promotions included")
        else:
            checks.append(f"⚠️  Only {len(promos)} promotions (target: 3)")

        # Check 4: Stockouts
        if 3 <= stockouts <= 20:
            checks.append(f"✅ {stockouts} stockouts (~5% rate)")
        else:
            checks.append(f"⚠️  {stockouts} stockouts (unusual rate)")

        for check in checks:
            print(f"  {check}")

        print("\n✅ Synthetic data validation complete!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    validate_synthetic_data()
