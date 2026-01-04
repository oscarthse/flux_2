"""
Centralized business day logic for Flux.

Handles the restaurant industry standard of "4 AM day start" to properly
attribute late-night sales to the correct business day.

Example: A transaction at 2:00 AM on Jan 2nd belongs to Jan 1st business day
         (assuming the restaurant opened Jan 1st evening and stayed open past midnight).
"""
from datetime import datetime, date, time, timedelta
from typing import Optional
import pytz


# Restaurant business day starts at 4:00 AM
BUSINESS_DAY_START_HOUR = 4


def get_business_date(dt: datetime, restaurant_timezone: Optional[str] = None) -> date:
    """
    Convert a datetime to its business date, respecting the 4 AM cutoff.

    Args:
        dt: The datetime to convert (should be timezone-aware)
        restaurant_timezone: IANA timezone string (e.g., "America/Los_Angeles")
                            If None, assumes dt is already in restaurant local time

    Returns:
        The business date this transaction belongs to

    Examples:
        # Transaction at 2:00 AM on Jan 2 -> Business day Jan 1
        >>> dt = datetime(2024, 1, 2, 2, 0, 0, tzinfo=pytz.UTC)
        >>> get_business_date(dt, "America/New_York")
        date(2024, 1, 1)

        # Transaction at 5:00 AM on Jan 2 -> Business day Jan 2
        >>> dt = datetime(2024, 1, 2, 5, 0, 0, tzinfo=pytz.UTC)
        >>> get_business_date(dt, "America/New_York")
        date(2024, 1, 2)
    """
    # Convert to restaurant local time if timezone provided
    if restaurant_timezone:
        if dt.tzinfo is None:
            # Assume UTC if no timezone
            dt = pytz.UTC.localize(dt)
        tz = pytz.timezone(restaurant_timezone)
        dt_local = dt.astimezone(tz)
    else:
        # Already in local time (or timezone-naive)
        dt_local = dt

    # If before 4 AM, attribute to previous day
    if dt_local.hour < BUSINESS_DAY_START_HOUR:
        return (dt_local.date() - timedelta(days=1))
    else:
        return dt_local.date()


def time_to_offset_minutes(t: time) -> int:
    """
    Convert a time to "offset minutes" where 4:00 AM = 0.

    This normalizes times around the business day boundary:
    - 4:00 AM = 0 minutes (start of business day)
    - 5:00 AM = 60 minutes
    - 2:00 AM (next day) = 1380 minutes (22 hours after 4 AM)

    Used for calculating operating hours that span midnight.

    Args:
        t: A time object

    Returns:
        Integer minutes offset from 4:00 AM

    Examples:
        >>> time_to_offset_minutes(time(4, 0))   # 4:00 AM
        0
        >>> time_to_offset_minutes(time(16, 30))  # 4:30 PM
        750
        >>> time_to_offset_minutes(time(2, 0))   # 2:00 AM (next day)
        1380
    """
    minutes = t.hour * 60 + t.minute

    # If before 4 AM, it's "tomorrow" relative to business day start
    if t.hour < BUSINESS_DAY_START_HOUR:
        minutes += 24 * 60

    # Subtract the 4 AM offset to get minutes since business day start
    offset = minutes - (BUSINESS_DAY_START_HOUR * 60)

    return offset


def calculate_hours_open(first_order: Optional[time], last_order: Optional[time]) -> float:
    """
    Calculate hours open given first and last order times.

    Correctly handles midnight crossing using offset minutes.

    Args:
        first_order: Time of first order (None if no orders)
        last_order: Time of last order (None if no orders)

    Returns:
        Hours open as a float (minimum 1.0, default 12.0 if data missing)

    Examples:
        >>> calculate_hours_open(time(11, 0), time(22, 0))  # 11 AM to 10 PM
        11.0
        >>> calculate_hours_open(time(20, 0), time(2, 0))   # 8 PM to 2 AM (crosses midnight)
        6.0
        >>> calculate_hours_open(None, None)  # No data
        12.0
    """
    if first_order is None or last_order is None:
        return 12.0  # Default assumption

    first_mins = time_to_offset_minutes(first_order)
    last_mins = time_to_offset_minutes(last_order)

    # last_mins will always be >= first_mins due to offset calculation
    # (midnight crossing is handled by adding 24*60 to times before 4 AM)
    hours = (last_mins - first_mins) / 60.0

    # Sanity check: at least 1 hour, at most 24 hours
    return max(1.0, min(hours, 24.0))
