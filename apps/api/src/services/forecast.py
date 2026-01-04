from typing import List, Optional, Dict, Tuple
from datetime import timedelta, date
from uuid import UUID
from decimal import Decimal

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from src.models.forecast import DemandForecast
from src.models.menu import MenuItem
from src.models.transaction import Transaction, TransactionItem
from src.services.features import FeatureEngineeringService
from src.services.forecasting.bayesian import BayesianForecaster

class ForecastService:
    """
    Orchestrates demand forecasting using the Flux Probabilistic Engine (Bayesian).
    """

    def __init__(self, db: Session):
        self.db = db
        self.feature_service = FeatureEngineeringService(db)
        self.forecaster = BayesianForecaster()

    def _get_category_data(self, restaurant_id: UUID, category_name: str, days: int = 90) -> Tuple[pd.DataFrame, Dict[str, List[float]]]:
        """
        Fetch category data.
        Returns:
            - df: Aggregated daily sales (Sum of all items) for Seasonality.
            - priors_data: Dict[item_name -> list_of_daily_quantities] for Prior Learning.
        """
        start_date = date.today() - timedelta(days=days)

        # Pull raw daily sales for every item in category (or all items)
        stmt = (
            select(
                Transaction.transaction_date,
                TransactionItem.menu_item_name,
                TransactionItem.quantity
            )
            .join(TransactionItem, Transaction.id == TransactionItem.transaction_id)
            .join(MenuItem, and_(
                MenuItem.name == TransactionItem.menu_item_name,
                MenuItem.restaurant_id == restaurant_id
            ))
            .where(
                Transaction.restaurant_id == restaurant_id,
                Transaction.transaction_date >= start_date
            )
        )

        result = self.db.execute(stmt).all()

        if not result:
            return pd.DataFrame(columns=["date", "quantity"]), {}

        # 1. Process for Priors (Individual Items)
        priors_data = {}
        for r in result:
            name = r.menu_item_name
            qty = float(r.quantity)
            if name not in priors_data:
                priors_data[name] = []
            priors_data[name].append(qty)

        # 2. Process for Seasonality (Aggregated)
        # Sum all quantities per date
        agg_data = {}
        for r in result:
            d = r.transaction_date
            qty = float(r.quantity)
            agg_data[d] = agg_data.get(d, 0.0) + qty

        df = pd.DataFrame([{"date": k, "quantity": v} for k,v in agg_data.items()])
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

        return df, priors_data

    def _calculate_seasonality(self, df: pd.DataFrame) -> Dict[int, float]:
        """
        Calculate Day-of-Week multipliers with Normalization and Capping (Shrinkage).
        """
        if df.empty:
            return {i: 1.0 for i in range(7)}

        # 1. Add DOW
        df["dow"] = df.index.dayofweek

        # 2. Mean per DOW
        dow_means = df.groupby("dow")["quantity"].mean()
        global_mean = df["quantity"].mean()

        if global_mean == 0:
             return {i: 1.0 for i in range(7)}

        # 3. Calculate Raw Multipliers with Conservative Shrinkage
        multipliers = {}
        for i in range(7):
            # Raw multiplier = observed mean / global mean
            m = dow_means.get(i, global_mean) / global_mean
            if np.isnan(m): m = 1.0

            # Apply shrinkage toward 1.0 for days with limited data
            # This reduces overfitting while preserving true seasonal patterns
            day_count = len(df[df["dow"] == i])
            if day_count < 4:
                # Strong shrinkage for <4 observations
                m = 0.7 * m + 0.3 * 1.0
            elif day_count < 8:
                # Moderate shrinkage for <8 observations
                m = 0.85 * m + 0.15 * 1.0

            # Conservative capping to prevent extreme outliers
            # Allow wider range [0.3, 3.0] to capture real variation
            m = max(0.3, min(m, 3.0))

            multipliers[i] = float(m)

        # NOTE: We do NOT normalize to mean=1.0 because that introduces bias
        # If weekends truly have higher sales, forcing mean=1.0 will
        # underestimate weekend demand and overestimate weekday demand
        # The deseasonalization/reseasonalization process handles level correctly

        return multipliers

    def generate_forecasts(
        self,
        restaurant_id: UUID,
        menu_item_name: str,
        days_ahead: int = 7,
        category: Optional[str] = None
    ) -> List[DemandForecast]:
        """
        Generate probabilistic demand forecasts.
        """
        # Fix race condition: capture today once at start
        today = date.today()

        # 0. Lookup Item ID
        item = self.db.execute(
            select(MenuItem).where(MenuItem.name == menu_item_name, MenuItem.restaurant_id == restaurant_id)
        ).scalar_one_or_none()
        item_id = item.id if item else None

        # 1. Get Item History (Unconstrained)
        df_item = self.feature_service.create_training_dataset(
            restaurant_id=restaurant_id,
            menu_item_id=item_id,
            days_history=365
        )

        # 2. Get Context Data (Category/Global) for Seasonality & Priors
        # Usage strategy:
        # - If item has robust history (>28 days), use item's own seasonality?
        #   - No, individual item is noisy. Category is safer.
        # - Use Category for Seasonality.

        # Determine effective category name (or fallback to 'Global')
        cat_context = category or "Global"
        df_cat, priors_raw_data = self._get_category_data(restaurant_id, cat_context)

        # 3. Calculate Seasonality Profile
        # If Category data is sparse, maybe fallback to Global (Restaurant) is better.
        seasonality_profile = self._calculate_seasonality(df_cat)


        # 4. Learn Priors (Individual Item Data - Aggregated into one list of 'samples')
        # We treat every daily sale of every item in the category as a sample observation
        # from the "Platonic Ideal Item" of that category.
        # This gives us a strong prior for the *distribution* of sales.

        all_item_sales_samples = []
        for sales_list in priors_raw_data.values():
            all_item_sales_samples.extend(sales_list)

        if all_item_sales_samples:
            self.forecaster.learn_priors({cat_context: all_item_sales_samples})

        # 5. Prepare Prediction Inputs
        if df_item.empty:
            history = []
            history_dows = []
            last_date = today - timedelta(days=1)
        else:
            history = df_item["adjusted_quantity"].tolist()
            history_dows = df_item.index.dayofweek.tolist()
            last_date = df_item.index.max().date()

        # 6. Prepare Future DOWs
        future_dates_str = []
        future_dows = []
        curr = last_date + timedelta(days=1)
        for _ in range(days_ahead):
            future_dates_str.append(curr.isoformat())
            future_dows.append(curr.weekday())
            curr += timedelta(days=1)

        # 7. Predict
        forecast_dists = self.forecaster.predict_item(
            item_history=history,
            history_dows=history_dows,
            future_dates=future_dates_str,
            future_dows=future_dows,
            category=cat_context,
            seasonal_multipliers=seasonality_profile
        )

        # 8. Save
        saved = []
        for i, f in enumerate(forecast_dists):
            f_date = last_date + timedelta(days=i+1)

            rec = DemandForecast(
                restaurant_id=restaurant_id,
                menu_item_name=menu_item_name,
                forecast_date=f_date,
                predicted_quantity=Decimal(f"{f.mean:.2f}"),
                p10_quantity=Decimal(f"{f.p10:.2f}"),
                p50_quantity=Decimal(f"{f.p50:.2f}"),
                p90_quantity=Decimal(f"{f.p90:.2f}"),
                model_name=f"BayesianSeasonal_v1 ({f.logic_trigger})"
            )
            self.db.add(rec)
            saved.append(rec)

        self.db.commit()
        return saved
