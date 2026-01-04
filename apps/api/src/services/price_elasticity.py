"""
Price elasticity estimation using econometric methods.

Implements Two-Stage Least Squares (2SLS) with instrumental variables
to address endogeneity in promotion timing.

Mathematical foundation:
    Stage 1: P_t = γ₀ + γ₁·P_{t-7} + γ₂·P_{t-28} + controls + u_t
    Stage 2: log(Q_t) = β₀ + β₁·log(P̂_t) + controls + ε_t

    Where β₁ is the price elasticity of demand.
"""
from typing import Dict, Optional, Tuple
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
import numpy as np
import pandas as pd
from dataclasses import dataclass

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from src.models.transaction import Transaction, TransactionItem
from src.models.menu import MenuItem
from src.models.promotion import PriceElasticity, Promotion


@dataclass
class ElasticityEstimate:
    """Result of price elasticity estimation."""
    elasticity: float
    std_error: float
    ci_lower: float
    ci_upper: float
    sample_size: int
    r_squared: float
    f_stat: float
    is_weak_instrument: bool
    confidence: float
    method: str


class PriceElasticityService:
    """
    Service for estimating price elasticity of demand.

    Uses Two-Stage Least Squares (2SLS) with lagged prices as instruments
    to address the endogeneity problem where promotions are timed based on
    expected low demand.
    """

    # Minimum data requirements
    MIN_OBSERVATIONS = 60  # Need at least 60 days
    MIN_PRICE_POINTS = 3   # Need at least 3 distinct prices
    WEAK_INSTRUMENT_THRESHOLD = 10.0  # First-stage F-statistic threshold

    def __init__(self, db: Session):
        self.db = db

    def estimate_elasticity_2sls(
        self,
        restaurant_id: UUID,
        menu_item_id: UUID,
        lookback_days: int = 180
    ) -> Optional[ElasticityEstimate]:
        """
        Estimate price elasticity using Two-Stage Least Squares.

        Args:
            restaurant_id: Restaurant UUID
            menu_item_id: Menu item UUID
            lookback_days: Days of history to use

        Returns:
            ElasticityEstimate or None if insufficient data
        """
        # Get historical sales and price data
        data = self._get_sales_price_data(
            restaurant_id=restaurant_id,
            menu_item_id=menu_item_id,
            lookback_days=lookback_days
        )

        if data is None or len(data) < self.MIN_OBSERVATIONS:
            return None

        # Check price variation
        unique_prices = data['price'].nunique()
        if unique_prices < self.MIN_PRICE_POINTS:
            return None  # Insufficient price variation

        # Prepare variables
        df = self._prepare_regression_data(data)

        if df is None or len(df) < self.MIN_OBSERVATIONS:
            return None

        # Run 2SLS estimation
        try:
            result = self._run_2sls_regression(df)
            return result
        except Exception as e:
            # Regression failed (multicollinearity, etc.)
            import logging
            logging.warning(f"2SLS regression failed for item {menu_item_id}: {e}")
            return None

    def _get_sales_price_data(
        self,
        restaurant_id: UUID,
        menu_item_id: UUID,
        lookback_days: int
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical sales and price data for an item.

        Returns DataFrame with columns:
        - date, quantity, price, is_promotion, dow, month, hours_open
        """
        cutoff_date = date.today() - timedelta(days=lookback_days)

        # Get menu item name
        menu_item = self.db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
        if not menu_item:
            return None

        # Query daily sales with prices
        stmt = (
            select(
                Transaction.transaction_date,
                func.sum(TransactionItem.quantity).label('quantity'),
                func.avg(TransactionItem.unit_price).label('avg_price'),
                func.bool_or(Transaction.is_promo).label('is_promotion'),
                func.min(Transaction.first_order_time).label('first_order'),
                func.max(Transaction.last_order_time).label('last_order')
            )
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.restaurant_id == restaurant_id,
                Transaction.transaction_date >= cutoff_date,
                TransactionItem.menu_item_name == menu_item.name
            )
            .group_by(Transaction.transaction_date)
            .order_by(Transaction.transaction_date)
        )

        results = self.db.execute(stmt).all()

        if not results:
            return None

        # Convert to DataFrame
        data = pd.DataFrame([
            {
                'date': r.transaction_date,
                'quantity': float(r.quantity),
                'price': float(r.avg_price),
                'is_promotion': r.is_promotion,
                'first_order': r.first_order,
                'last_order': r.last_order
            }
            for r in results
        ])

        # Add time features
        data['dow'] = pd.to_datetime(data['date']).dt.dayofweek
        data['month'] = pd.to_datetime(data['date']).dt.month

        # Calculate hours open
        from src.core.business_day import calculate_hours_open
        data['hours_open'] = data.apply(
            lambda row: calculate_hours_open(row['first_order'], row['last_order']),
            axis=1
        )

        return data

    def _prepare_regression_data(self, data: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Prepare data for 2SLS regression.

        Creates:
        - Log-transformed variables
        - Lagged instruments
        - Dummy variables for controls
        """
        df = data.copy()

        # Sort by date
        df = df.sort_values('date').reset_index(drop=True)

        # Log transformations
        df['log_quantity'] = np.log(df['quantity'] + 1)  # +1 to handle zeros
        df['log_price'] = np.log(df['price'])

        # Lagged prices (instruments)
        df['log_price_lag7'] = df['log_price'].shift(7)
        df['log_price_lag28'] = df['log_price'].shift(28)

        # Day-of-week dummies
        dow_dummies = pd.get_dummies(df['dow'], prefix='dow', drop_first=True)
        df = pd.concat([df, dow_dummies], axis=1)

        # Month dummies
        month_dummies = pd.get_dummies(df['month'], prefix='month', drop_first=True)
        df = pd.concat([df, month_dummies], axis=1)

        # Promotion indicator
        df['promotion'] = df['is_promotion'].astype(int)

        # Drop rows with NaN (from lagging)
        df = df.dropna()

        if len(df) < self.MIN_OBSERVATIONS:
            return None

        return df

    def _run_2sls_regression(self, df: pd.DataFrame) -> ElasticityEstimate:
        """
        Run Two-Stage Least Squares regression.

        Uses scipy/numpy for lightweight implementation without statsmodels dependency.
        """
        # Dependent variable
        y = df['log_quantity'].values

        # Endogenous regressor (price)
        X_endog = df[['log_price']].values

        # Instruments (lagged prices)
        Z = df[['log_price_lag7', 'log_price_lag28']].values

        # Exogenous controls
        control_cols = [col for col in df.columns if col.startswith('dow_') or col.startswith('month_')]
        control_cols.extend(['promotion', 'hours_open'])
        X_exog = df[control_cols].values

        # Add constant
        X_exog = np.column_stack([np.ones(len(df)), X_exog])

        # === First Stage: Regress price on instruments + controls ===
        Z_with_exog = np.column_stack([Z, X_exog])

        # OLS: β̂ = (Z'Z)^{-1} Z'X_endog
        try:
            ZtZ_inv = np.linalg.inv(Z_with_exog.T @ Z_with_exog)
            beta_first_stage = ZtZ_inv @ Z_with_exog.T @ X_endog
            X_endog_hat = Z_with_exog @ beta_first_stage  # Fitted values

            # Calculate first-stage F-statistic
            # F = (R² / k) / ((1-R²) / (n-k-1))
            residuals_first = X_endog.flatten() - X_endog_hat.flatten()
            ss_total = np.sum((X_endog.flatten() - np.mean(X_endog)) ** 2)
            ss_residual = np.sum(residuals_first ** 2)
            r_squared_first = 1 - (ss_residual / ss_total)

            k_instruments = 2  # Number of instruments (log_price_lag7, log_price_lag28)
            n = len(df)
            f_stat = (r_squared_first / k_instruments) / ((1 - r_squared_first) / (n - k_instruments - 1))

        except np.linalg.LinAlgError:
            # Singular matrix - perfect multicollinearity
            raise ValueError("Multicollinearity in first stage regression")

        # === Second Stage: Regress quantity on fitted price + controls ===
        X_second = np.column_stack([X_endog_hat, X_exog])

        try:
            XtX_inv = np.linalg.inv(X_second.T @ X_second)
            beta_second_stage = XtX_inv @ X_second.T @ y

            # Elasticity is coefficient on log_price (first column after constant)
            elasticity = float(beta_second_stage[0])

            # Calculate robust standard errors (HC3)
            residuals_second = y - X_second @ beta_second_stage
            n = len(y)
            k = X_second.shape[1]

            # Leverage values for HC3
            H = X_second @ XtX_inv @ X_second.T
            h = np.diag(H)

            # HC3 variance-covariance matrix
            # V_HC3 = (X'X)^{-1} X' Ω X (X'X)^{-1}
            # where Ω_ii = e_i² / (1 - h_i)²
            omega = np.diag((residuals_second ** 2) / ((1 - h) ** 2))
            V_HC3 = XtX_inv @ X_second.T @ omega @ X_second @ XtX_inv

            # Standard error for elasticity
            std_error = float(np.sqrt(V_HC3[0, 0]))

            # 95% Confidence interval
            ci_lower = elasticity - 1.96 * std_error
            ci_upper = elasticity + 1.96 * std_error

            # R-squared
            ss_total_second = np.sum((y - np.mean(y)) ** 2)
            ss_residual_second = np.sum(residuals_second ** 2)
            r_squared = 1 - (ss_residual_second / ss_total_second)

        except np.linalg.LinAlgError:
            raise ValueError("Multicollinearity in second stage regression")

        # Check for weak instruments
        is_weak_instrument = f_stat < self.WEAK_INSTRUMENT_THRESHOLD

        # Calculate confidence score
        confidence = self._calculate_confidence(
            elasticity=elasticity,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            r_squared=r_squared,
            f_stat=f_stat,
            sample_size=len(df),
            is_weak_instrument=is_weak_instrument
        )

        return ElasticityEstimate(
            elasticity=elasticity,
            std_error=std_error,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            sample_size=len(df),
            r_squared=r_squared,
            f_stat=f_stat,
            is_weak_instrument=is_weak_instrument,
            confidence=confidence,
            method='2SLS'
        )

    def _calculate_confidence(
        self,
        elasticity: float,
        ci_lower: float,
        ci_upper: float,
        r_squared: float,
        f_stat: float,
        sample_size: int,
        is_weak_instrument: bool
    ) -> float:
        """
        Calculate confidence score (0-1) in elasticity estimate.

        Penalizes:
        - Small sample size
        - Weak instruments
        - Wide confidence intervals
        - Low R-squared
        - Implausible elasticity values
        """
        score = 1.0

        # Penalty 1: Small sample size
        if sample_size < 90:
            score *= 0.7
        elif sample_size < 60:
            score *= 0.4

        # Penalty 2: Weak instruments
        if is_weak_instrument:
            score *= 0.5
        elif f_stat < 20:
            score *= 0.8

        # Penalty 3: Wide confidence interval
        ci_width = ci_upper - ci_lower
        if ci_width > 2.0:
            score *= 0.6
        elif ci_width > 1.0:
            score *= 0.8

        # Penalty 4: Low R-squared
        if r_squared < 0.3:
            score *= 0.7
        elif r_squared < 0.5:
            score *= 0.85

        # Penalty 5: Implausible elasticity
        if elasticity > 0:
            # Wrong sign (demand should decrease with price)
            score *= 0.2
        elif abs(elasticity) > 5:
            # Too elastic (unrealistic for most goods)
            score *= 0.5
        elif abs(elasticity) < 0.1:
            # Too inelastic (suspicious - could be measurement error)
            score *= 0.6

        return max(0.0, min(1.0, score))

    def estimate_and_save_elasticity(
        self,
        restaurant_id: UUID,
        menu_item_id: UUID
    ) -> Optional[PriceElasticity]:
        """
        Estimate elasticity and save to database.

        Args:
            restaurant_id: Restaurant UUID
            menu_item_id: Menu item UUID

        Returns:
            PriceElasticity record or None if estimation failed
        """
        # Run estimation
        estimate = self.estimate_elasticity_2sls(
            restaurant_id=restaurant_id,
            menu_item_id=menu_item_id
        )

        if estimate is None:
            return None

        # Check if elasticity record already exists
        existing = self.db.query(PriceElasticity).filter(
            PriceElasticity.restaurant_id == restaurant_id,
            PriceElasticity.menu_item_id == menu_item_id
        ).first()

        if existing:
            # Update existing record
            existing.elasticity = Decimal(str(round(estimate.elasticity, 3)))
            existing.confidence = Decimal(str(round(estimate.confidence, 3)))
            existing.sample_size = estimate.sample_size
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new record
            new_elasticity = PriceElasticity(
                restaurant_id=restaurant_id,
                menu_item_id=menu_item_id,
                elasticity=Decimal(str(round(estimate.elasticity, 3))),
                confidence=Decimal(str(round(estimate.confidence, 3))),
                sample_size=estimate.sample_size
            )
            self.db.add(new_elasticity)
            self.db.commit()
            self.db.refresh(new_elasticity)
            return new_elasticity

    def estimate_all_items(self, restaurant_id: UUID) -> Dict[str, int]:
        """
        Estimate elasticity for all menu items with sufficient data.

        Args:
            restaurant_id: Restaurant UUID

        Returns:
            Dictionary with counts: {'estimated': X, 'failed': Y}
        """
        menu_items = self.db.query(MenuItem).filter(
            MenuItem.restaurant_id == restaurant_id
        ).all()

        estimated_count = 0
        failed_count = 0

        for menu_item in menu_items:
            result = self.estimate_and_save_elasticity(
                restaurant_id=restaurant_id,
                menu_item_id=menu_item.id
            )

            if result:
                estimated_count += 1
            else:
                failed_count += 1

        return {
            'estimated': estimated_count,
            'failed': failed_count
        }
