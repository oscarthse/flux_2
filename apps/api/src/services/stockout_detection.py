"""
Velocity-based stockout detection service.

Infers likely stockout events based on item velocity patterns,
avoiding false positives for naturally low-velocity items.
"""
from typing import Dict, List, Optional, Tuple
from datetime import date, timedelta
from uuid import UUID
from decimal import Decimal
import statistics

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.models.transaction import Transaction, TransactionItem
from src.models.inventory import InventorySnapshot
from src.models.menu import MenuItem


class StockoutDetectionResult:
    """Result of stockout detection analysis for an item."""
    def __init__(
        self,
        menu_item_id: UUID,
        item_name: str,
        detected_date: date,
        confidence: float,
        reason: str
    ):
        self.menu_item_id = menu_item_id
        self.item_name = item_name
        self.detected_date = detected_date
        self.confidence = confidence  # 0.0 - 1.0
        self.reason = reason


class StockoutDetectionService:
    """
    Service for detecting likely stockout events based on velocity anomalies.

    Velocity-based detection avoids false positives by:
    1. Only flagging zero-sale days for HIGH velocity items (>= 3.0 units/day)
    2. For medium velocity items, requiring gap > 3x average gap
    3. Ignoring low velocity items (< 1.0 units/day) entirely

    This addresses the audit finding about the naive "gap > 2x avg" heuristic.
    """

    # Velocity thresholds
    HIGH_VELOCITY_THRESHOLD = 3.0  # units/day
    LOW_VELOCITY_THRESHOLD = 1.0   # units/day

    # Gap multiplier for medium-velocity detection
    GAP_MULTIPLIER = 3.0

    # Minimum days of history required
    MIN_HISTORY_DAYS = 14

    def __init__(self, db: Session):
        self.db = db

    def calculate_item_velocity(
        self,
        restaurant_id: UUID,
        item_name: str,
        days_lookback: int = 14
    ) -> Tuple[float, int]:
        """
        Calculate rolling velocity (avg daily sales) for an item.

        Args:
            restaurant_id: Restaurant UUID
            item_name: Name of the menu item
            days_lookback: Number of days to calculate velocity over

        Returns:
            Tuple of (velocity, active_days)
        """
        cutoff_date = date.today() - timedelta(days=days_lookback)

        stmt = (
            select(
                func.count(func.distinct(Transaction.transaction_date)).label("active_days"),
                func.sum(TransactionItem.quantity).label("total_qty")
            )
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.restaurant_id == restaurant_id,
                Transaction.transaction_date >= cutoff_date,
                TransactionItem.menu_item_name == item_name
            )
        )

        result = self.db.execute(stmt).first()

        if not result or not result.total_qty:
            return 0.0, 0

        active_days = result.active_days or 0
        total_qty = float(result.total_qty or 0)

        # Velocity = total sales / active days (not calendar days)
        # This gives true "sales per selling day" metric
        # For items sold sporadically, active_days < days_lookback
        if active_days > 0:
            velocity = total_qty / active_days
        else:
            velocity = 0.0

        return velocity, active_days

    def detect_likely_stockouts(
        self,
        restaurant_id: UUID,
        days_to_analyze: int = 30
    ) -> List[StockoutDetectionResult]:
        """
        Analyze recent history and detect likely stockout events.

        Args:
            restaurant_id: Restaurant UUID
            days_to_analyze: Number of days to scan for stockouts

        Returns:
            List of detected stockout events with confidence scores
        """
        results: List[StockoutDetectionResult] = []

        # Get all distinct items sold in the lookback period
        lookback_date = date.today() - timedelta(days=days_to_analyze + self.MIN_HISTORY_DAYS)

        item_stmt = (
            select(TransactionItem.menu_item_name)
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.restaurant_id == restaurant_id,
                Transaction.transaction_date >= lookback_date
            )
            .distinct()
        )

        items = self.db.execute(item_stmt).scalars().all()

        for item_name in items:
            item_results = self._analyze_item_for_stockouts(
                restaurant_id, item_name, days_to_analyze
            )
            results.extend(item_results)

        return results

    def _analyze_item_for_stockouts(
        self,
        restaurant_id: UUID,
        item_name: str,
        days_to_analyze: int
    ) -> List[StockoutDetectionResult]:
        """
        Analyze a single item for stockout patterns.
        """
        results = []

        # Calculate velocity
        velocity, active_days = self.calculate_item_velocity(
            restaurant_id, item_name, self.MIN_HISTORY_DAYS
        )

        if active_days < 7:
            # Not enough history
            return results

        # Skip low-velocity items
        if velocity < self.LOW_VELOCITY_THRESHOLD:
            return results

        # Get daily sales for analysis period
        analysis_start = date.today() - timedelta(days=days_to_analyze)

        daily_sales = self._get_daily_sales(restaurant_id, item_name, analysis_start)

        # Check for already-flagged stockouts in inventory snapshots
        existing_stockouts = self._get_existing_stockouts(restaurant_id, item_name, analysis_start)

        # Find gaps in sales
        all_dates = set(
            analysis_start + timedelta(days=i)
            for i in range(days_to_analyze + 1)
        )
        sale_dates = set(daily_sales.keys())
        zero_days = all_dates - sale_dates

        for zero_date in zero_days:
            # Skip if already flagged
            if zero_date in existing_stockouts:
                continue

            # Skip future dates
            if zero_date > date.today():
                continue

            # Get MenuItem ID if available
            menu_item_id = self._get_menu_item_id(restaurant_id, item_name)

            if velocity >= self.HIGH_VELOCITY_THRESHOLD:
                # High velocity item with zero sales = likely stockout
                results.append(StockoutDetectionResult(
                    menu_item_id=menu_item_id,
                    item_name=item_name,
                    detected_date=zero_date,
                    confidence=0.85,
                    reason=f"Zero sales for high-velocity item (velocity: {velocity:.1f}/day)"
                ))
            else:
                # Medium velocity: check gap length
                gap_length = self._calculate_gap_length(zero_date, sale_dates)
                avg_gap = self._calculate_average_gap(sale_dates)

                if avg_gap > 0 and gap_length > avg_gap * self.GAP_MULTIPLIER:
                    results.append(StockoutDetectionResult(
                        menu_item_id=menu_item_id,
                        item_name=item_name,
                        detected_date=zero_date,
                        confidence=0.65,
                        reason=f"Gap ({gap_length}d) exceeds {self.GAP_MULTIPLIER}x avg ({avg_gap:.1f}d)"
                    ))

        return results

    def _get_daily_sales(
        self,
        restaurant_id: UUID,
        item_name: str,
        start_date: date
    ) -> Dict[date, float]:
        """Get daily sales quantities for an item."""
        stmt = (
            select(
                Transaction.transaction_date,
                func.sum(TransactionItem.quantity).label("qty")
            )
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.restaurant_id == restaurant_id,
                Transaction.transaction_date >= start_date,
                TransactionItem.menu_item_name == item_name
            )
            .group_by(Transaction.transaction_date)
        )

        results = self.db.execute(stmt).all()
        return {row.transaction_date: float(row.qty) for row in results}

    def _get_existing_stockouts(
        self,
        restaurant_id: UUID,
        item_name: str,
        start_date: date
    ) -> set:
        """Get dates where stockouts are already recorded."""
        # Try to find by menu item
        menu_item_id = self._get_menu_item_id(restaurant_id, item_name)

        if not menu_item_id:
            return set()

        stmt = (
            select(InventorySnapshot.date)
            .where(
                InventorySnapshot.restaurant_id == restaurant_id,
                InventorySnapshot.menu_item_id == menu_item_id,
                InventorySnapshot.stockout_flag == 'Y',
                InventorySnapshot.date >= start_date
            )
        )

        return set(self.db.execute(stmt).scalars().all())

    def _get_menu_item_id(self, restaurant_id: UUID, item_name: str) -> Optional[UUID]:
        """Look up menu item ID by name."""
        stmt = select(MenuItem.id).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.name == item_name
        ).limit(1)

        return self.db.execute(stmt).scalar_one_or_none()

    def _calculate_gap_length(self, target_date: date, sale_dates: set) -> int:
        """Calculate how long the gap is around a target date."""
        if not sale_dates:
            return 0

        sorted_dates = sorted(sale_dates)

        # Find surrounding sale dates
        prev_sale = None
        next_sale = None

        for d in sorted_dates:
            if d < target_date:
                prev_sale = d
            elif d > target_date and next_sale is None:
                next_sale = d
                break

        if prev_sale and next_sale:
            return (next_sale - prev_sale).days - 1
        elif prev_sale:
            return (date.today() - prev_sale).days
        else:
            return 0

    def _calculate_average_gap(self, sale_dates: set) -> float:
        """Calculate average gap between sale days."""
        if len(sale_dates) < 2:
            return 0.0

        sorted_dates = sorted(sale_dates)
        gaps = [
            (sorted_dates[i+1] - sorted_dates[i]).days - 1
            for i in range(len(sorted_dates) - 1)
        ]

        # Only consider gaps (days between sales, not consecutive)
        gaps = [g for g in gaps if g > 0]

        if not gaps:
            return 0.0

        return statistics.mean(gaps)
