
import pytest
from datetime import date, timedelta
from uuid import uuid4
from decimal import Decimal
import pandas as pd
import numpy as np

from src.models.transaction import Transaction, TransactionItem
from src.services.features import FeatureEngineeringService

def test_create_training_dataset(db, test_user_with_restaurant):
    """Verify feature generation and unconstraining logic."""
    _, test_restaurant = test_user_with_restaurant

    # Create 35 days of data (enough for lag_28)
    start_date = date.today() - timedelta(days=35)
    item_name = "Test Burger"

    # Stockout on day 30 (index relative to start)
    # We want stockout to be visible in final DF.
    # DF will have rows from index 28 to 35 (approx).
    stockout_offset = 30
    stockout_date_val = start_date + timedelta(days=stockout_offset)

    for i in range(35):
        current_date = start_date + timedelta(days=i)
        is_stockout = (i == stockout_offset)
        qty = 2 if is_stockout else 10

        tx = Transaction(
            restaurant_id=test_restaurant.id,
            transaction_date=current_date,
            total_amount=Decimal(str(qty * 10)),
            stockout_occurred=is_stockout,
            is_promo=False
        )
        db.add(tx)
        db.flush()

        item = TransactionItem(
            transaction_id=tx.id,
            menu_item_name=item_name,
            quantity=qty,
            unit_price=Decimal("10.00"),
            total=Decimal(str(qty * 10))
        )
        db.add(item)

    db.commit()

    # Execute
    service = FeatureEngineeringService(db)
    df = service.create_training_dataset(
        restaurant_id=test_restaurant.id,
        days_history=60 # Request robust history
    )

    assert not df.empty, f"DataFrame is empty. Columns: {df.columns.tolist()}"

    # Verify Columns
    expected_cols = ["quantity", "adjusted_quantity", "lag_1", "lag_7", "roll_7_mean", "dow", "hours_open"]
    for col in expected_cols:
        assert col in df.columns, f"Missing column: {col}"

    # Verify Unconstraining
    # Find row for stockout date
    stockout_ts = pd.Timestamp(stockout_date_val)
    if stockout_ts in df.index:
        row = df.loc[stockout_ts]
        # actual=2, but adjusted=10.0 (median of recent same-DOW non-stockout sales)
        # All previous same-DOW days had qty=10, so median=10
        assert row["quantity"] == 2.0
        assert row["adjusted_quantity"] == 10.0
        assert row["stockout"] == True
    else:
        pytest.fail(f"Stockout date {stockout_ts} not in dataframe index: {df.index}")

    # Verify Lag 7
    # For day 30 (stockout), lag_7 is day 23's adjusted qty (10)
    assert df.loc[stockout_ts, "lag_7"] == 10.0

def test_create_training_dataset_long_history(db, test_user_with_restaurant):
    """Verify with sufficient history - kept for compatibility/extra coverage."""
    # Logic merged into above test mostly, but keeping simplified version
    _, test_restaurant = test_user_with_restaurant

    start_date = date.today() - timedelta(days=40)
    item_name = "Long Burger"

    for i in range(40):
        current_date = start_date + timedelta(days=i)
        qty = 10
        tx = Transaction(
            restaurant_id=test_restaurant.id,
            transaction_date=current_date,
            total_amount=Decimal("100"),
            stockout_occurred=False,
            is_promo=False
        )
        db.add(tx)
        db.flush()
        item = TransactionItem(
            transaction_id=tx.id,
            menu_item_name=item_name,
            quantity=qty,
            unit_price=Decimal("10"),
            total=Decimal("10")
        )
        db.add(item)
    db.commit()

    service = FeatureEngineeringService(db)
    df = service.create_training_dataset(
        restaurant_id=test_restaurant.id,
        days_history=60
    )
    assert not df.empty
    assert len(df) >= 10
