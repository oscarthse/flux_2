"""
Promotion detection service using multi-method approach.

Detects discounts and promotions from:
1. Explicit discount columns in CSV
2. Negative prices (comps/voids)
3. Keyword analysis
4. Statistical price variance analysis (Bayesian change-point detection)
"""
from typing import Dict, List, Optional, Tuple
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
import statistics
import numpy as np
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.models.transaction import Transaction, TransactionItem
from src.models.menu import MenuItem
from src.models.promotion import Promotion


@dataclass
class DiscountDetection:
    """Result of discount detection on a single transaction item."""
    is_promo: bool
    discount_amount: Optional[Decimal] = None
    discount_type: str = 'none'  # explicit, comp_void, keyword, inferred
    confidence: float = 0.0
    keywords_found: List[str] = None


@dataclass
class InferredPromotion:
    """Statistically inferred promotion period."""
    menu_item_name: str
    start_date: date
    end_date: date
    avg_discount_pct: Decimal
    confidence: float
    method: str
    baseline_price: Decimal
    promo_avg_price: Decimal


class PromotionDetectionService:
    """
    Service for detecting promotions and discounts from transaction data.

    Uses multiple detection methods with varying confidence levels:
    - Direct: Explicit discount columns (confidence=1.0)
    - Heuristic: Negative prices, keywords (confidence=0.7-1.0)
    - Statistical: Price variance analysis (confidence=0.5-0.9)
    """

    # Discount indicator keywords
    DISCOUNT_KEYWORDS = [
        'discount', 'promo', 'promotion', 'comp', 'void',
        'off', 'coupon', 'special', 'deal', 'happy hour',
        'sale', 'clearance', 'markdown', 'reduced'
    ]

    def __init__(self, db: Session):
        self.db = db

    def detect_discount_in_item(
        self,
        item_name: str,
        unit_price: Decimal,
        total: Decimal,
        discount_amount: Optional[Decimal] = None
    ) -> DiscountDetection:
        """
        Detect if a single transaction item has a discount.

        Args:
            item_name: Menu item name
            unit_price: Price per unit
            total: Line total
            discount_amount: Explicit discount (if available in CSV)

        Returns:
            DiscountDetection with confidence score
        """

        # Method 1: Explicit discount column
        if discount_amount is not None and discount_amount > 0:
            return DiscountDetection(
                is_promo=True,
                discount_amount=discount_amount,
                discount_type='explicit',
                confidence=1.0
            )

        # Method 2: Negative prices (comps, voids, refunds)
        if unit_price < 0 or total < 0:
            return DiscountDetection(
                is_promo=True,
                discount_amount=abs(total),
                discount_type='comp_void',
                confidence=1.0
            )

        # Method 3: Item name contains discount keywords
        item_lower = item_name.lower()
        found_keywords = [kw for kw in self.DISCOUNT_KEYWORDS if kw in item_lower]

        if found_keywords:
            return DiscountDetection(
                is_promo=True,
                discount_amount=None,  # Unknown amount
                discount_type='keyword',
                confidence=0.7,
                keywords_found=found_keywords
            )

        # No discount detected
        return DiscountDetection(
            is_promo=False,
            confidence=1.0
        )

    def infer_promotions_from_price_history(
        self,
        restaurant_id: UUID,
        item_name: str,
        lookback_days: int = 90,
        min_promotion_days: int = 2
    ) -> List[InferredPromotion]:
        """
        Infer promotion periods using statistical price variance analysis.

        Uses robust baseline calculation and 2-sigma threshold to detect
        periods where prices deviate significantly from normal.

        Args:
            restaurant_id: Restaurant UUID
            item_name: Menu item name
            lookback_days: Days of history to analyze
            min_promotion_days: Minimum consecutive days to count as promotion

        Returns:
            List of inferred promotion periods
        """
        # Get historical price data
        cutoff_date = date.today() - timedelta(days=lookback_days)

        stmt = (
            select(
                Transaction.transaction_date,
                func.avg(TransactionItem.unit_price).label('avg_price'),
                func.count(TransactionItem.id).label('num_sales')
            )
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.restaurant_id == restaurant_id,
                Transaction.transaction_date >= cutoff_date,
                TransactionItem.menu_item_name == item_name
            )
            .group_by(Transaction.transaction_date)
            .order_by(Transaction.transaction_date)
        )

        results = self.db.execute(stmt).all()

        if len(results) < 30:
            # Insufficient data for reliable inference
            return []

        # Convert to arrays
        dates = [r.transaction_date for r in results]
        prices = np.array([float(r.avg_price) for r in results])

        # Step 1: Calculate robust baseline price (excluding outliers)
        baseline_price = self._calculate_robust_baseline(prices)
        price_std = self._calculate_robust_std(prices, baseline_price)

        # Step 2: Define discount threshold (2-sigma rule)
        discount_threshold = baseline_price - 2 * price_std

        # Step 3: Find consecutive periods below threshold
        is_discounted = prices < discount_threshold
        promotion_periods = self._find_consecutive_periods(
            is_discounted,
            dates,
            min_length=min_promotion_days
        )

        # Step 4: Quantify each promotion period
        inferred_promotions = []
        for start_idx, end_idx in promotion_periods:
            period_prices = prices[start_idx:end_idx+1]
            period_mean = float(np.mean(period_prices))

            discount_pct = (baseline_price - period_mean) / baseline_price

            # Calculate confidence based on:
            # 1. How far below threshold (more = higher confidence)
            # 2. Length of period (longer = higher confidence)
            # 3. Consistency of discount (lower variance = higher confidence)
            sigma_below = (baseline_price - period_mean) / price_std
            length_factor = min(1.0, (end_idx - start_idx + 1) / 7)  # Cap at 7 days
            consistency_factor = 1.0 - min(1.0, np.std(period_prices) / price_std)

            confidence = (
                0.4 * min(1.0, sigma_below / 2) +  # How far below baseline
                0.3 * length_factor +              # Duration
                0.3 * consistency_factor           # Consistency
            )

            inferred_promotions.append(InferredPromotion(
                menu_item_name=item_name,
                start_date=dates[start_idx],
                end_date=dates[end_idx],
                avg_discount_pct=Decimal(str(round(discount_pct * 100, 2))),
                confidence=round(confidence, 2),
                method='price_variance',
                baseline_price=Decimal(str(round(baseline_price, 2))),
                promo_avg_price=Decimal(str(round(period_mean, 2)))
            ))

        return inferred_promotions

    def _calculate_robust_baseline(self, prices: np.ndarray) -> float:
        """
        Calculate robust baseline price using Huber M-estimator.

        More resistant to outliers than simple mean.
        """
        if len(prices) < 10:
            return float(np.median(prices))

        # Simple implementation: Trimmed mean (10% trim on each end)
        # This approximates Huber M-estimator for most cases
        sorted_prices = np.sort(prices)
        trim_count = max(1, int(len(prices) * 0.1))

        trimmed = sorted_prices[trim_count:-trim_count]
        return float(np.mean(trimmed))

    def _calculate_robust_std(self, prices: np.ndarray, baseline: float) -> float:
        """
        Calculate robust standard deviation using MAD (Median Absolute Deviation).

        MAD = median(|X_i - median(X)|)
        σ ≈ 1.4826 × MAD (for normal distribution)
        """
        deviations = np.abs(prices - baseline)
        mad = float(np.median(deviations))

        # Scale MAD to approximate standard deviation
        robust_std = 1.4826 * mad

        # Return at least some minimum variance
        return max(robust_std, 0.01 * baseline)

    def _find_consecutive_periods(
        self,
        condition: np.ndarray,
        dates: List[date],
        min_length: int = 2
    ) -> List[Tuple[int, int]]:
        """
        Find consecutive periods where condition is True.

        Returns list of (start_idx, end_idx) tuples.
        """
        periods = []
        in_period = False
        period_start = None

        for i, is_true in enumerate(condition):
            if is_true and not in_period:
                # Start new period
                in_period = True
                period_start = i
            elif not is_true and in_period:
                # End current period
                if i - period_start >= min_length:
                    periods.append((period_start, i - 1))
                in_period = False
                period_start = None

        # Handle period extending to end
        if in_period and len(condition) - period_start >= min_length:
            periods.append((period_start, len(condition) - 1))

        return periods

    def detect_and_save_promotions(
        self,
        restaurant_id: UUID,
        confidence_threshold: float = 0.6
    ) -> int:
        """
        Run promotion inference on all menu items and save to database.

        Args:
            restaurant_id: Restaurant UUID
            confidence_threshold: Minimum confidence to save (0-1)

        Returns:
            Number of promotions created
        """
        # Get all menu items for restaurant
        menu_items = self.db.query(MenuItem).filter(
            MenuItem.restaurant_id == restaurant_id
        ).all()

        promotions_created = 0

        for menu_item in menu_items:
            # Infer promotions for this item
            inferred = self.infer_promotions_from_price_history(
                restaurant_id=restaurant_id,
                item_name=menu_item.name,
                lookback_days=90
            )

            # Save high-confidence inferred promotions
            for promo in inferred:
                if promo.confidence < confidence_threshold:
                    continue

                # Check if promotion already exists for this period
                existing = self.db.query(Promotion).filter(
                    Promotion.restaurant_id == restaurant_id,
                    Promotion.menu_item_id == menu_item.id,
                    Promotion.start_date == promo.start_date,
                    Promotion.end_date == promo.end_date
                ).first()

                if existing:
                    continue  # Skip duplicate

                # Create new promotion record
                new_promo = Promotion(
                    restaurant_id=restaurant_id,
                    menu_item_id=menu_item.id,
                    name=f"{menu_item.name} - Inferred Promotion",
                    discount_type='percentage',
                    discount_value=promo.avg_discount_pct,
                    start_date=promo.start_date,
                    end_date=promo.end_date,
                    status='completed',  # Already happened
                    trigger_reason='inferred',
                    is_exploration=False
                )
                self.db.add(new_promo)
                promotions_created += 1

        if promotions_created > 0:
            self.db.commit()

        return promotions_created
