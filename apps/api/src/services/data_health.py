from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select, func, desc, distinct, case
from sqlalchemy.orm import Session

from src.models.data_health import DataHealthScore
from src.models.transaction import Transaction
from src.models.menu import MenuItem
from src.models.data_upload import DataUpload
from src.models.inventory import InventorySnapshot

class DataHealthService:
    """
    Calculates and manages data health scores for restaurants.

    Score breakdown:
    - Completeness (40%): History length, item coverage
    - Consistency (30%): Upload regularity, data gaps
    - Timeliness (20%): Recency of data
    - Accuracy (10%): Validation against business logic
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_score(self, restaurant_id: UUID) -> DataHealthScore:
        """
        Calculate comprehensive data health score for a restaurant.
        """
        # Get data stats helper
        stats = self._get_restaurant_stats(restaurant_id)

        # Calculate sub-scores
        completeness, c_breakdown = self._calculate_completeness(stats)
        consistency, con_breakdown = self._calculate_consistency(stats)
        timeliness, t_breakdown = self._calculate_timeliness(stats)
        accuracy, a_breakdown = self._calculate_accuracy(stats)

        # Calculate weighted overall score
        # Weights: Completeness 40%, Consistency 30%, Timeliness 20%, Accuracy 10%
        overall = (
            (completeness * Decimal("0.40")) +
            (consistency * Decimal("0.30")) +
            (timeliness * Decimal("0.20")) +
            (accuracy * Decimal("0.10"))
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            completeness, consistency, timeliness, accuracy,
            stats
        )

        # Create score record
        score = DataHealthScore(
            restaurant_id=restaurant_id,
            overall_score=overall,
            completeness_score=completeness,
            consistency_score=consistency,
            timeliness_score=timeliness,
            accuracy_score=accuracy,
            component_breakdown={
                "completeness": c_breakdown,
                "consistency": con_breakdown,
                "timeliness": t_breakdown,
                "accuracy": a_breakdown
            },
            recommendations=recommendations
        )

        self.db.add(score)
        self.db.commit()
        self.db.refresh(score)

        return score

    def get_latest_score(self, restaurant_id: UUID) -> Optional[DataHealthScore]:
        """Get the most recent health score for a restaurant."""
        stmt = select(DataHealthScore).where(
            DataHealthScore.restaurant_id == restaurant_id
        ).order_by(desc(DataHealthScore.calculated_at)).limit(1)

        return self.db.execute(stmt).scalar_one_or_none()

    def _get_restaurant_stats(self, restaurant_id: UUID) -> Dict:
        """Fetch all necessary statistics for scoring."""
        now = datetime.now()

        # Transaction dates
        date_range = self.db.execute(
            select(
                func.min(Transaction.transaction_date),
                func.max(Transaction.transaction_date),
                func.count(distinct(Transaction.transaction_date))
            ).where(Transaction.restaurant_id == restaurant_id)
        ).first()

        min_date, max_date, distinct_dates = date_range

        # Menu stats
        menu_stats = self.db.execute(
            select(
                func.count(MenuItem.id),
                func.sum(case((MenuItem.category_path.isnot(None), 1), else_=0)),
                func.sum(case((MenuItem.category_path.is_(None), 1), else_=0))
            ).where(MenuItem.restaurant_id == restaurant_id)
        ).first()

        total_items, categorized_items, uncategorized_items = menu_stats

        return {
            "min_date": min_date,
            "max_date": max_date,
            "days_of_data": (max_date - min_date).days if min_date and max_date else 0,
            "active_days": distinct_dates or 0,
            "total_items": total_items or 0,
            "categorized_items": categorized_items or 0,
            "uncategorized_items": uncategorized_items or 0,
            "last_upload_date": now,  # Placeholder, should fetch from DataUpload
            "has_snapshots": self._has_inventory_data(restaurant_id),
            "has_stockouts": self._has_stockout_data(restaurant_id)
        }

    def _has_inventory_data(self, restaurant_id: UUID) -> bool:
        stmt = select(InventorySnapshot).where(InventorySnapshot.restaurant_id == restaurant_id).limit(1)
        return self.db.execute(stmt).first() is not None

    def _has_stockout_data(self, restaurant_id: UUID) -> bool:
        stmt = select(InventorySnapshot).where(
            InventorySnapshot.restaurant_id == restaurant_id,
            InventorySnapshot.stockout_flag == 'Y'
        ).limit(1)
        return self.db.execute(stmt).first() is not None

    def _calculate_completeness(self, stats: Dict) -> Tuple[Decimal, Dict]:
        """
        Completeness Score (40% weight):
        - History length (0-30d=0%, 30-60d=50%, 60-90d=80%, 90+d=100%)
        - Item categorization coverage (percentage of items categorized)
        """
        days = stats["days_of_data"]

        # History score
        if days >= 90:
            history_score = 100
        elif days >= 60:
            history_score = 80
        elif days >= 30:
            history_score = 50
        else:
            history_score = max(0, int((days / 30) * 50))  # Pro-rated for first 30 days

        # Categorization score
        total = stats["total_items"]
        cat_score = 100
        if total > 0:
            cat_score = int((stats["categorized_items"] / total) * 100)

        # Weighted average: History (70%) + Categorization (30%)
        score = (history_score * 0.7) + (cat_score * 0.3)

        return Decimal(str(score)), {
            "days_of_history": days,
            "history_score": history_score,
            "categorization_score": cat_score
        }

    def _calculate_consistency(self, stats: Dict) -> Tuple[Decimal, Dict]:
        """
        Consistency Score (30% weight):
        - Data gaps (ratio of active days to calendar days in range)
        """
        days_range = stats["days_of_data"]
        active_days = stats["active_days"]

        consistency_score = 100
        gap_ratio = 0

        if days_range > 0:
            # We expect data every day (restaurant open).
            # Allow for some holidays/closures (e.g. 1 day/week closed = ~85% active)
            # If active_days / days_range < 0.85, penalize
            gap_ratio = active_days / days_range
            if gap_ratio >= 0.85:
                consistency_score = 100
            elif gap_ratio >= 0.7:  # Missing ~2 days/week
                consistency_score = 80
            elif gap_ratio >= 0.5:  # Missing half the days
                consistency_score = 50
            else:
                consistency_score = int(gap_ratio * 100)
        elif days_range == 0 and active_days == 0:
             consistency_score = 0 # No data

        return Decimal(str(consistency_score)), {
            "active_days_ratio": round(gap_ratio, 2) if days_range > 0 else 0,
            "consistency_score": consistency_score
        }

    def _calculate_timeliness(self, stats: Dict) -> Tuple[Decimal, Dict]:
        """
        Timeliness Score (20% weight):
        - Recency (days since last transaction)
        """
        if not stats["max_date"]:
            return Decimal("0"), {"days_lag": None}

        days_lag = (datetime.now().date() - stats["max_date"]).days

        if days_lag <= 2:
            score = 100
        elif days_lag <= 7:
            score = 80
        elif days_lag <= 14:
            score = 50
        elif days_lag <= 30:
            score = 20
        else:
            score = 0

        return Decimal(str(score)), {
            "days_lag": days_lag,
            "timeliness_score": score
        }

    def _calculate_accuracy(self, stats: Dict) -> Tuple[Decimal, Dict]:
        """
        Accuracy Score (10% weight):
        - Stockout data presence (do we know when items were unavailable?)
        """
        # Check if restaurant has any inventory snapshots
        # We need restaurant_id from somewhere - stats doesn't have it explicitly but we can pass it or query using context
        # Actually stats dict doesn't contain it. I should fetch it in _get_restaurant_stats or pass it to this method.
        # But this method signature is fixed: (self, stats: Dict)

        # Better approach: Fetch the inventory stats in _get_restaurant_stats

        has_stockouts = stats.get("has_stockouts", False)
        has_snapshots = stats.get("has_snapshots", False)

        score = 0
        if has_stockouts:
            score = 100
        elif has_snapshots:
            score = 50
        else:
            score = 0

        return Decimal(str(score)), {
            "accuracy_score": score,
            "has_stockout_data": has_stockouts,
            "has_inventory_tracking": has_snapshots
        }

    def _generate_recommendations(self, completeness, consistency, timeliness, accuracy, stats) -> List[Dict]:
        """Generate actionable recommendations based on lowest scores."""
        recs = []

        # History length priority
        if stats["days_of_data"] < 30:
            recs.append({
                "type": "completeness",
                "priority": "high",
                "title": "Upload More History",
                "description": f"You only have {stats['days_of_data']} days of data. Upload at least 30 days to enable basic forecasting.",
                "action": "upload_csv"
            })
        elif stats["days_of_data"] < 90:
            recs.append({
                "type": "completeness",
                "priority": "medium",
                "title": "Extend History",
                "description": "Upload 90 days of history to improve forecast accuracy.",
                "action": "upload_csv"
            })

        # Recency priority
        days_lag = (datetime.now().date() - stats["max_date"]).days if stats["max_date"] else 999
        if days_lag > 7:
            recs.append({
                "type": "timeliness",
                "priority": "high",
                "title": "Data is Stale",
                "description": f"Last transaction was {days_lag} days ago. Upload recent sales data.",
                "action": "upload_csv"
            })

        # Categorization priority
        uncat = stats["uncategorized_items"]
        if uncat > 0:
            recs.append({
                "type": "completeness",
                "priority": "medium",
                "title": "Categorize Items",
                "description": f"You have {uncat} items without categories. Review them to improve item pooling.",
                "action": "review_items"
            })

        return recs[:3]  # Return top 3
