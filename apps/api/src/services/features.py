
from typing import List, Optional, Dict
from datetime import date, timedelta
from uuid import UUID

import pandas as pd
import numpy as np
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from src.models.transaction import Transaction, TransactionItem
from src.models.menu import MenuItem

class FeatureEngineeringService:
    """
    Service for transforming raw transaction data into feature sets for forecasting.
    Handles demand unconstraining (imputation) and feature generation.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_training_dataset(
        self,
        restaurant_id: UUID,
        menu_item_id: Optional[UUID] = None,
        days_history: int = 365
    ) -> pd.DataFrame:
        """
        Create a DataFrame suitable for training ML models.

        Args:
            restaurant_id: Restaurant UUID
            menu_item_id: Specific item to get data for (optional)
            days_history: How many days of history to retrieve

        Returns:
            DataFrame with index 'date' and columns:
            [quantity, imputed_quantity, lag_1, lag_7, roll_7_mean, dow, is_weekend, etc.]
        """
        # 1. Fetch raw daily sales data with hours open
        cutoff_date = date.today() - timedelta(days=days_history)

        # Base query joining TransactionItem -> Transaction
        # Include first/last order times to calculate hours_open
        stmt = (
            select(
                Transaction.transaction_date,
                TransactionItem.menu_item_name,  # Fallback if menu_item_id linkage is weak
                func.sum(TransactionItem.quantity).label("daily_qty"),
                func.bool_or(Transaction.stockout_occurred).label("stockout_flag"),
                func.bool_or(Transaction.is_promo).label("is_promo"),
                func.min(Transaction.first_order_time).label("first_order"),
                func.max(Transaction.last_order_time).label("last_order")
            )
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.restaurant_id == restaurant_id,
                Transaction.transaction_date >= cutoff_date
            )
            .group_by(Transaction.transaction_date, TransactionItem.menu_item_name)
        )


        # Get manually flagged stockouts from InventorySnapshot table
        # This supplements the transaction-level stockout_occurred flag
        from src.models.inventory import InventorySnapshot
        stockout_dates_by_item: Dict[str, set] = {}

        if menu_item_id:
            # Get stockouts for specific item
            stockout_stmt = (
                select(InventorySnapshot.date)
                .where(
                    InventorySnapshot.restaurant_id == restaurant_id,
                    InventorySnapshot.menu_item_id == menu_item_id,
                    InventorySnapshot.stockout_flag == 'Y',
                    InventorySnapshot.date >= cutoff_date
                )
            )
            stockout_results = self.db.execute(stockout_stmt).scalars().all()

            # Get item name to map stockouts
            item = self.db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
            if item:
                stockout_dates_by_item[item.name] = set(stockout_results)
        else:
            # Get all stockouts for restaurant to merge later
            stockout_stmt = (
                select(
                    MenuItem.name,
                    InventorySnapshot.date
                )
                .join(MenuItem, InventorySnapshot.menu_item_id == MenuItem.id)
                .where(
                    InventorySnapshot.restaurant_id == restaurant_id,
                    InventorySnapshot.stockout_flag == 'Y',
                    InventorySnapshot.date >= cutoff_date
                )
            )
            stockout_results = self.db.execute(stockout_stmt).all()
            for item_name, stockout_date in stockout_results:
                if item_name not in stockout_dates_by_item:
                    stockout_dates_by_item[item_name] = set()
                stockout_dates_by_item[item_name].add(stockout_date)


        # Filter by menu item if provided
        # Note: TransactionItems currently store 'menu_item_name'.
        # Ideally we join with MenuItem table, but mapping might be via name.
        # Epic 2.3 Auto-creation maps items. Let's assume we can filter by name if ID passed.

        target_name = None
        if menu_item_id:
            # Get name from ID
            item = self.db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
            if item:
                target_name = item.name
                stmt = stmt.where(TransactionItem.menu_item_name == target_name)
            else:
                return pd.DataFrame() # Item not found

        results = self.db.execute(stmt).all()

        if not results:
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(results, columns=["date", "item_name", "quantity", "stockout", "is_promo", "first_order", "last_order"])

        # Convert date to datetime first, then merge stockouts
        df["date"] = pd.to_datetime(df["date"])

        # Merge in manually flagged stockouts from InventorySnapshot
        # If a date is flagged in InventorySnapshot, mark stockout=True
        if target_name and target_name in stockout_dates_by_item:
            manual_stockout_dates = stockout_dates_by_item[target_name]
            df["stockout"] = df.apply(
                lambda row: row["stockout"] or (row["date"].date() in manual_stockout_dates),
                axis=1
            )
        df.sort_values("date", inplace=True)

        # Calculate hours_open from first/last order times
        # Import centralized business day utility
        from src.core.business_day import calculate_hours_open

        df["hours_open"] = df.apply(
            lambda row: calculate_hours_open(row["first_order"], row["last_order"]),
            axis=1
        )

        # Handle multiple items (if no ID provided, we'd loop, but for now assuming single target flow)
        # If multiple items returned (no ID filter), we should pivot or group.
        # For MVP, let's enforce single item context or aggregate total.
        # Let's pivot if we want to forecast all?
        # Implementation Plan says "Train per-category or top-item".
        # Let's keep it simple: This service returns data for ONE series (filtered).

        # Reindex to ensure full date range (fill missing days with 0)
        full_idx = pd.date_range(start=df["date"].min(), end=df["date"].max(), freq='D')
        df.set_index("date", inplace=True)
        df = df.reindex(full_idx)

        # Fill missing values after reindex
        df["quantity"] = df["quantity"].fillna(0).astype(float)
        df["stockout"] = df["stockout"].fillna(False).infer_objects(copy=False).astype(bool)
        df["is_promo"] = df["is_promo"].fillna(False).infer_objects(copy=False).astype(bool)
        df["hours_open"] = df["hours_open"].fillna(12.0)  # Default 12 hours for missing days

        # 2. Demand Unconstraining (Imputation)
        # If stockout=True, quantity is likely lower than demand.
        # Impute with: max(current, rolling 7d median of NON-stockout days)
        # We need a rolling window that skips stockouts? Hard in pandas rolling.
        # Simpler heuristic: Replace with Rolling 7D Max (including stockouts) or just ignore stockouts for mean calc?

        # Let's try: Replace stockout days with NaN, interpolate, then take max of (interpolated, actual).
        # Better: Standard method => Impute = Average of t-1, t-7, t+7? (Future not avail in training?)
        # Training data has "future" relative to past.
        # Simple for MVP: If stockout, set quantity = quantity * 1.5 (boost 50%).

        # Improved stockout imputation using recent non-stockout history
        # Instead of arbitrary 1.5x multiplier, use statistical approach
        df["adjusted_quantity"] = df["quantity"].copy()

        # For each stockout day, impute using median of recent non-stockout days
        # with same day-of-week (to preserve seasonality)
        for idx in df[df["stockout"] == True].index:
            dow = idx.dayofweek
            # Look back 4-8 weeks for same DOW, excluding stockouts
            lookback_start = idx - timedelta(days=56)  # 8 weeks
            lookback_end = idx - timedelta(days=1)

            # Get same-DOW historical values (non-stockout only)
            historical_mask = (
                (df.index >= lookback_start) &
                (df.index < lookback_end) &
                (df.index.dayofweek == dow) &
                (df["stockout"] == False)
            )
            historical_values = df.loc[historical_mask, "quantity"]

            if len(historical_values) >= 2:
                # Use median of recent same-DOW non-stockout sales
                imputed_value = historical_values.median()
                # Take max of observed and imputed (could have partial stockout)
                df.loc[idx, "adjusted_quantity"] = max(
                    df.loc[idx, "quantity"],
                    imputed_value
                )
            else:
                # Fallback: if insufficient history, use conservative 1.3x multiplier
                # (less aggressive than old 1.5x)
                df.loc[idx, "adjusted_quantity"] = df.loc[idx, "quantity"] * 1.3

        # 3. Feature Generation
        target = "adjusted_quantity"

        # Lags
        df["lag_1"] = df[target].shift(1)
        df["lag_7"] = df[target].shift(7)
        df["lag_28"] = df[target].shift(28)

        # Rolling Means
        df["roll_7_mean"] = df[target].shift(1).rolling(window=7).mean()
        df["roll_28_mean"] = df[target].shift(1).rolling(window=28).mean()

        # Calendar
        df["dow"] = df.index.dayofweek
        df["month"] = df.index.month
        df["is_weekend"] = df["dow"].isin([5, 6]).astype(int)

        # Clean NaNs (only for essential columns - keep rows even if lag_28 is NaN)
        essential_cols = ["lag_1", "lag_7", "roll_7_mean"]
        df.dropna(subset=essential_cols, inplace=True)

        return df
