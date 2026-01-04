
from typing import Dict, List, Optional
from datetime import time, timedelta, datetime, date
from uuid import UUID
from collections import defaultdict
import statistics

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.models.transaction import Transaction

class OperatingHoursService:
    """
    Service for analyzing and inferring restaurant operating hours
    from historical transaction data.
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_standard_hours(self, restaurant_id: UUID, days_lookback: int = 90) -> Dict[str, Dict[str, str]]:
        """
        Infer standard operating hours (mon-sun) based on transaction history.

        Args:
            restaurant_id: Restaurant UUID
            days_lookback: Number of days of history to analyze

        Returns:
            Dictionary with day names and open/close times, e.g.:
            {
                "Monday": {"open": "11:00", "close": "22:00"},
                ...
            }
        """
        # Calculate cutoff date
        cutoff_date = date.today() - timedelta(days=days_lookback)

        # Query transaction times
        stmt = select(
            Transaction.transaction_date,
            Transaction.first_order_time,
            Transaction.last_order_time
        ).where(
            Transaction.restaurant_id == restaurant_id,
            Transaction.transaction_date >= cutoff_date,
            Transaction.first_order_time.is_not(None),
            Transaction.last_order_time.is_not(None)
        )

        results = self.db.execute(stmt).all()

        # Group by day of week
        # 0=Monday, 6=Sunday
        opening_times: Dict[int, List[time]] = defaultdict(list)
        closing_times: Dict[int, List[time]] = defaultdict(list)

        for row in results:
            tx_date: date = row.transaction_date
            day_idx = tx_date.weekday()

            opening_times[day_idx].append(row.first_order_time)
            closing_times[day_idx].append(row.last_order_time)

        # Calculate median times per day
        # We round to nearest 15 minutes for cleaner output?
        # For MVP, just median minute.

        schedule = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for i, day_name in enumerate(days):
            if i not in opening_times or not opening_times[i]:
                schedule[day_name] = None  # Closed
                continue

            median_open = self._get_median_time(opening_times[i])
            median_close = self._get_median_time(closing_times[i])

            # Round opening time DOWN to nearest 30 minutes (restaurant likely opened before first sale)
            # Round closing time UP to nearest 30 minutes (restaurant likely closed after last sale)
            rounded_open = self._round_time_down(median_open, minutes=30)
            rounded_close = self._round_time_up(median_close, minutes=30)

            schedule[day_name] = {
                "open": rounded_open.strftime("%H:%M"),
                "close": rounded_close.strftime("%H:%M")
            }

        return schedule

    def _get_median_time(self, times: List[time]) -> time:
        """
        Calculate median time from a list of time objects.
        Handles midnight crossing by normalizing to 4 AM start of day.
        """
        # Use centralized business day utility for consistent time offset calculation
        from src.core.business_day import time_to_offset_minutes

        # Convert all times to offset minutes
        offset_minutes_list = [time_to_offset_minutes(t) for t in times]

        # Calculate median
        median_offset = statistics.median(offset_minutes_list)

        # Convert back to time
        # Add back the 4 AM offset
        median_total_minutes = int(median_offset) + (4 * 60)

        # Handle wrap around 24 hours
        if median_total_minutes >= 24 * 60:
            median_total_minutes -= 24 * 60

        h, m = divmod(median_total_minutes, 60)
        return time(h, m)

    def _round_time_down(self, t: time, minutes: int = 30) -> time:
        """
        Round time DOWN to the nearest interval.
        E.g., 11:23 rounds down to 11:00 (if minutes=30)
        """
        total_minutes = t.hour * 60 + t.minute
        rounded_minutes = (total_minutes // minutes) * minutes
        h, m = divmod(rounded_minutes, 60)
        return time(h, m)

    def _round_time_up(self, t: time, minutes: int = 30) -> time:
        """
        Round time UP to the nearest interval.
        E.g., 21:47 rounds up to 22:00 (if minutes=30)
        """
        total_minutes = t.hour * 60 + t.minute
        rounded_minutes = ((total_minutes + minutes - 1) // minutes) * minutes
        h, m = divmod(rounded_minutes, 60)
        # Handle midnight overflow
        if h >= 24:
            h = 23
            m = 59
        return time(h, m)
