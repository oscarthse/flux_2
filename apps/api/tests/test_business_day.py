"""
Tests for business day logic and hours_open calculation.
Verifies correct handling of midnight-crossing scenarios.
"""
from datetime import time, date, datetime
import pytz
import pytest

from src.core.business_day import (
    get_business_date,
    time_to_offset_minutes,
    calculate_hours_open,
    BUSINESS_DAY_START_HOUR
)


class TestBusinessDate:
    """Test business date calculation with 4 AM cutoff."""

    def test_before_4am_previous_day(self):
        """Transaction at 2:00 AM belongs to previous business day."""
        dt = datetime(2024, 1, 2, 2, 0, 0, tzinfo=pytz.UTC)
        result = get_business_date(dt, "America/New_York")

        # 2 AM UTC on Jan 2 is either 9 PM Jan 1 EST (winter) or 10 PM EDT (summer)
        # Either way, it's before 4 AM local, so should map to previous day
        # Actually, let's use a timezone-naive example for clarity
        dt_local = datetime(2024, 1, 2, 2, 0, 0)
        result = get_business_date(dt_local)
        assert result == date(2024, 1, 1)

    def test_after_4am_same_day(self):
        """Transaction at 5:00 AM belongs to same business day."""
        dt = datetime(2024, 1, 2, 5, 0, 0)
        result = get_business_date(dt)
        assert result == date(2024, 1, 2)

    def test_exactly_4am_same_day(self):
        """Transaction at exactly 4:00 AM belongs to same business day."""
        dt = datetime(2024, 1, 2, 4, 0, 0)
        result = get_business_date(dt)
        assert result == date(2024, 1, 2)

    def test_3_59am_previous_day(self):
        """Transaction at 3:59 AM belongs to previous business day."""
        dt = datetime(2024, 1, 2, 3, 59, 0)
        result = get_business_date(dt)
        assert result == date(2024, 1, 1)


class TestTimeToOffsetMinutes:
    """Test conversion of time to offset minutes from 4 AM."""

    def test_4am_is_zero(self):
        """4:00 AM is 0 offset minutes (start of business day)."""
        assert time_to_offset_minutes(time(4, 0)) == 0

    def test_5am_is_60(self):
        """5:00 AM is 60 minutes into business day."""
        assert time_to_offset_minutes(time(5, 0)) == 60

    def test_noon_is_480(self):
        """12:00 PM is 480 minutes (8 hours) into business day."""
        assert time_to_offset_minutes(time(12, 0)) == 480

    def test_midnight_is_1200(self):
        """12:00 AM (midnight) is 1200 minutes (20 hours) into business day."""
        assert time_to_offset_minutes(time(0, 0)) == 1200

    def test_2am_is_1320(self):
        """2:00 AM (next day) is 1320 minutes (22 hours) into business day."""
        assert time_to_offset_minutes(time(2, 0)) == 1320

    def test_3_59am_is_almost_24h(self):
        """3:59 AM (last minute before cutoff) is 1439 minutes."""
        assert time_to_offset_minutes(time(3, 59)) == 1439


class TestCalculateHoursOpen:
    """Test hours_open calculation for various scenarios."""

    def test_normal_day_11am_to_10pm(self):
        """Standard restaurant hours: 11 AM to 10 PM = 11 hours."""
        first = time(11, 0)
        last = time(22, 0)
        hours = calculate_hours_open(first, last)
        assert hours == 11.0

    def test_midnight_crossing_8pm_to_2am(self):
        """Late night hours: 8 PM to 2 AM (crosses midnight) = 6 hours."""
        first = time(20, 0)
        last = time(2, 0)
        hours = calculate_hours_open(first, last)
        assert hours == 6.0

    def test_midnight_crossing_10pm_to_3am(self):
        """Very late hours: 10 PM to 3 AM = 5 hours."""
        first = time(22, 0)
        last = time(3, 0)
        hours = calculate_hours_open(first, last)
        assert hours == 5.0

    def test_all_day_service(self):
        """24/7 restaurant: 4 AM to 3:59 AM next day = 23.98 hours (clamped to 24)."""
        first = time(4, 0)
        last = time(3, 59)
        hours = calculate_hours_open(first, last)
        assert hours == pytest.approx(23.98, abs=0.1)

    def test_very_short_hours(self):
        """Only 30 minutes open (should clamp to minimum 1 hour)."""
        first = time(12, 0)
        last = time(12, 30)
        hours = calculate_hours_open(first, last)
        # 0.5 hours clamped to 1.0
        assert hours == 1.0

    def test_none_values_return_default(self):
        """Missing data returns default 12.0 hours."""
        assert calculate_hours_open(None, None) == 12.0
        assert calculate_hours_open(time(10, 0), None) == 12.0
        assert calculate_hours_open(None, time(22, 0)) == 12.0

    def test_lunch_only_11am_to_3pm(self):
        """Lunch-only restaurant: 11 AM to 3 PM = 4 hours."""
        first = time(11, 0)
        last = time(15, 0)
        hours = calculate_hours_open(first, last)
        assert hours == 4.0

    def test_late_night_bar_10pm_to_3_30am(self):
        """Late night bar: 10 PM to 3:30 AM = 5.5 hours."""
        first = time(22, 0)
        last = time(3, 30)
        hours = calculate_hours_open(first, last)
        assert hours == 5.5


class TestRealWorldScenarios:
    """Integration tests with realistic restaurant scenarios."""

    def test_typical_dinner_service(self):
        """Typical dinner restaurant: 5 PM to 11 PM."""
        first = time(17, 0)
        last = time(23, 0)
        hours = calculate_hours_open(first, last)
        assert hours == 6.0

    def test_breakfast_and_lunch(self):
        """Breakfast/lunch place: 7 AM to 3 PM."""
        first = time(7, 0)
        last = time(15, 0)
        hours = calculate_hours_open(first, last)
        assert hours == 8.0

    def test_24_hour_diner(self):
        """24-hour diner with first order at 4:05 AM, last at 3:55 AM next day."""
        first = time(4, 5)
        last = time(3, 55)
        hours = calculate_hours_open(first, last)
        # Should be close to 24 hours
        assert 23.5 <= hours <= 24.0

    def test_bar_with_late_close(self):
        """Bar: 6 PM to 2:30 AM (8.5 hours)."""
        first = time(18, 0)
        last = time(2, 30)
        hours = calculate_hours_open(first, last)
        assert hours == 8.5

    def test_early_morning_cafe(self):
        """Cafe: 6 AM to 2 PM."""
        first = time(6, 0)
        last = time(14, 0)
        hours = calculate_hours_open(first, last)
        assert hours == 8.0
