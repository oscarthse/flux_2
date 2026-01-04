import pytest
import numpy as np
from datetime import date, timedelta
from src.services.forecasting.bayesian import BayesianForecaster
from src.services.forecast import ForecastService
from src.models.menu import MenuItem
from src.models.restaurant import Restaurant
from src.models.user import User
from src.models.transaction import Transaction, TransactionItem
from src.core.security import hash_password

# 1. Pure Unit Tests for Bayesian Logic
def test_bayesian_update_math():
    forecaster = BayesianForecaster(global_alpha=2.0, global_beta=0.5)

    # 0 observations. Should match prior.
    # Prior Mean = 2.0 / 0.5 = 4.0
    dists = forecaster.predict_item(
        item_history=[],
        history_dows=[],
        future_dates=["2025-01-01"],
        future_dows=[0]
    )
    assert len(dists) == 1
    assert abs(dists[0].mean - 4.0) < 0.1
    # P10 < Mean < P90
    assert dists[0].p10 < dists[0].mean < dists[0].p90

    # Strong evidence of higher sales
    # 10 days of exactly 10.0 sales
    history = [10.0] * 10
    history_dows = [0] * 10 # Assuming all Mondays (unrealistic but fine for pure math)

    dists = forecaster.predict_item(
        item_history=history,
        history_dows=history_dows,
        future_dates=["2025-01-01"],
        future_dows=[0] # Predict a Monday
    )

    # Posterior should be close to 10.0
    # Alpha = 2 + 100 = 102
    # Beta = 0.5 + 10 = 10.5
    # Mean = 102 / 10.5 ~= 9.71
    assert abs(dists[0].mean - 9.71) < 0.2
    assert dists[0].mean > 9.0

def test_seasonality_multipliers():
    forecaster = BayesianForecaster()
    # History of 10 sales every day
    # DOWs 0..9 -> 0..6, 0..2
    history = [10.0] * 10
    history_dows = [i % 7 for i in range(10)]

    # Seasonality: Multiplier of 1.0 implies history IS 10.0 base.
    # If we pass multipliers, the logic de-seasonalizes first.
    # Let's assume Profile: Mon(0) = 2.0, Tue(1) = 0.5, others 1.0
    seasonality = {0: 2.0, 1: 0.5, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0}

    # If history was 10.0 on a Mon (mult=2.0), Deseasonalized = 5.0
    # If history was 10.0 on a Tue (mult=0.5), Deseasonalized = 20.0

    # Let's try simple case: history is empty (Prior=4.0).
    # We predict Mon and Tue.

    dists = forecaster.predict_item(
        item_history=[],
        history_dows=[],
        future_dates=["2025-01-01", "2025-01-02"],
        future_dows=[0, 1], # Mon, Tue
        seasonal_multipliers=seasonality
    )

    # Base prior mean = 4.0
    # Mon prediction = 4.0 * 2.0 = 8.0
    # Tue prediction = 4.0 * 0.5 = 2.0

    assert abs(dists[0].mean - 8.0) < 0.1
    assert abs(dists[1].mean - 2.0) < 0.1
    assert "Seasonality 2.00x" in dists[0].logic_trigger
    assert "Seasonality 0.50x" in dists[1].logic_trigger

    assert "Seasonality 0.50x" in dists[1].logic_trigger

def test_seasonality_capping_and_normalization():
    # We can test the math logic conceptually or if we had the method exposed.
    # Since the logic is inside ForecastService._calculate_seasonality, let's Verify
    # it via a "Whitebox" test where we call the method directly on the service.

    # Mock DB not needed for this specific method logic if we pass a DF
    service = ForecastService(None)

    # 1. Test Normalization
    # Input: 2 days. Day 0 has 10 sales, Day 1 has 10 sales.
    # Mean = 10. Multipliers = 1.0, 1.0. Correct.
    import pandas as pd
    df = pd.DataFrame([
        {"date": date(2025, 1, 1), "quantity": 10.0}, # Wed
        {"date": date(2025, 1, 2), "quantity": 10.0}  # Thu
    ])
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)

    multipliers = service._calculate_seasonality(df)
    # Wed(2) and Thu(3) should be 1.0
    assert abs(multipliers[2] - 1.0) < 0.01
    assert abs(multipliers[3] - 1.0) < 0.01

    # 2. Test Capping
    # Input: Day 0 has 100 sales (Extreme), Day 1 has 1 sales.
    # Mean = 50.5
    # Day 0 Raw Mult = 100 / 50.5 ~= 1.98 (Not capped yet)

    # Extreme Case for Capping > 2.5
    # Day 0: 1000, Day 1: 1.
    # Mean ~ 500.
    # Day 0 Raw = 1000/500 = 2.0. Still not hitting 2.5 cap easy with 2 days.
    # Let's force a DF that simulates aggregate data perfectly having one huge day.

    # Fake DOW means directly? No, method calculates from DF.
    # Let's construct DF.
    data = []
    # Mon(0): 1000, others 10.
    today = date(2025, 1, 6) # Mon
    data.append({"date": today, "quantity": 1000.0})
    for i in range(1, 7):
        data.append({"date": today + timedelta(days=i), "quantity": 10.0})

    df_extreme = pd.DataFrame(data)
    df_extreme["date"] = pd.to_datetime(df_extreme["date"])
    df_extreme.set_index("date", inplace=True)

    # Global Mean = (1000 + 60) / 7 = 151.4
    # Mon Raw Mult = 1000 / 151.4 = 6.6 -> Should Cap at 2.5
    # Others Raw = 10 / 151.4 = 0.06 -> Should Floor at 0.5

    # Then Normalization:
    # 1 day of 2.5, 6 days of 0.5.
    # Sum = 2.5 + 3.0 = 5.5
    # Mean = 5.5 / 7 = 0.785
    # Normalized Mon = 2.5 / 0.785 = 3.18 ??
    # Wait. If we cap THEN normalize, the huge spike might get boosted back up?
    # Yes, normalization forces mean to 1.0.
    # If we have [2.5, 0.5, 0.5...], sum=5.5.
    # To get mean 1.0 (sum 7.0), we multiply by 7/5.5 = 1.27
    # So capped 2.5 becomes 3.18.
    # This implies we might still exceed 2.5 *after* normalization, but it's "dampened" compared to 6.6.
    # The requirement was "Mean of Multipliers = 1.0".
    # And "Cap raw multipliers".

    mults = service._calculate_seasonality(df_extreme)

    # Mon(0)
    mon_m = mults[0]
    # It should be roughly 3.18 based on my desktop calculation?
    # Or did I code it to cap -> normalize? Yes.
    assert mon_m < 4.0 # Much less than 6.6
    assert mon_m > 2.0

    # Verify Sum is exactly 7.0 (Mean 1.0)
    total_m = sum(mults.values())
    assert abs(total_m - 7.0) < 0.01

# 2. Integration Tests with DB
def test_forecast_service_integration(db, test_user_with_restaurant):
    user, restaurant = test_user_with_restaurant

    # Setup Item
    item_name = "Burger"
    item = MenuItem(name=item_name, restaurant_id=restaurant.id, price=10.0)
    db.add(item)
    db.flush()

    # Add transactions
    today = date.today()
    for i in range(10):
        # 10 burgers per day
        txn_date = today - timedelta(days=i+1)
        txn = Transaction(
             restaurant_id=restaurant.id,
             transaction_date=txn_date,
             total_amount=100.0,
             stockout_occurred=False,
             is_promo=False,
             first_order_time=None,
             last_order_time=None
        )
        db.add(txn)
        db.flush()

        ti = TransactionItem(
            transaction_id=txn.id,
            menu_item_name=item_name,
            quantity=10,
            unit_price=10.0,
            total=100.0
        )
        db.add(ti)

    db.commit()

    # Test Generation
    service = ForecastService(db)
    forecasts = service.generate_forecasts(
        restaurant_id=restaurant.id,
        menu_item_name=item_name,
        days_ahead=3
    )

    assert len(forecasts) == 3
    assert forecasts[0].menu_item_name == item_name
    # Basic check - mean > 0
    assert forecasts[0].predicted_quantity > 0
    # Check p10/p90
    assert forecasts[0].p10_quantity < forecasts[0].predicted_quantity < forecasts[0].p90_quantity
    assert forecasts[0].model_name.startswith("BayesianSeasonal")
