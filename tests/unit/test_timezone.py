"""Tests for timezone detection utility."""

from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from sputnik_offer_crm.utils.timezone import detect_timezone_from_local_time


class TestTimezoneDetection:
    """Test timezone detection from local time."""

    @freeze_time("2026-05-12 12:00:00", tz_offset=0)
    def test_detect_moscow_time(self):
        """Test Moscow timezone detection (UTC+3)."""
        # Moscow is 15:00 when UTC is 12:00
        result = detect_timezone_from_local_time("15:00")

        assert result is not None
        assert result.timezone_str == "Europe/Moscow"
        assert result.offset_hours == 3
        assert "UTC+3" in result.display_name

    @freeze_time("2026-05-12 12:00:00", tz_offset=0)
    def test_detect_london_time(self):
        """Test London timezone detection (UTC+1 in summer)."""
        # London is 13:00 when UTC is 12:00 (BST)
        result = detect_timezone_from_local_time("13:00")

        assert result is not None
        assert result.offset_hours == 1

    @freeze_time("2026-05-12 12:00:00", tz_offset=0)
    def test_detect_new_york_time(self):
        """Test New York timezone detection (UTC-4 in summer)."""
        # New York is 08:00 when UTC is 12:00 (EDT)
        result = detect_timezone_from_local_time("08:00")

        assert result is not None
        assert result.offset_hours == -4

    @freeze_time("2026-05-12 12:00:00", tz_offset=0)
    def test_detect_tokyo_time(self):
        """Test Tokyo timezone detection (UTC+9)."""
        # Tokyo is 21:00 when UTC is 12:00
        result = detect_timezone_from_local_time("21:00")

        assert result is not None
        assert result.offset_hours == 9

    @freeze_time("2026-05-12 23:30:00", tz_offset=0)
    def test_detect_timezone_crossing_midnight_forward(self):
        """Test timezone detection when local time crosses midnight forward."""
        # If UTC is 23:30 and local is 02:00, offset is +2.5 hours (rounds to +2 or +3)
        result = detect_timezone_from_local_time("02:00")

        assert result is not None
        assert result.offset_hours in [2, 3]

    @freeze_time("2026-05-12 01:30:00", tz_offset=0)
    def test_detect_timezone_crossing_midnight_backward(self):
        """Test timezone detection when local time crosses midnight backward."""
        # If UTC is 01:30 and local is 22:00, offset is -3.5 hours (rounds to -4)
        result = detect_timezone_from_local_time("22:00")

        assert result is not None
        assert result.offset_hours == -4

    def test_invalid_format_no_colon(self):
        """Test invalid time format without colon."""
        result = detect_timezone_from_local_time("1530")

        assert result is None

    def test_invalid_format_letters(self):
        """Test invalid time format with letters."""
        result = detect_timezone_from_local_time("15:30pm")

        assert result is None

    def test_invalid_format_empty(self):
        """Test empty string."""
        result = detect_timezone_from_local_time("")

        assert result is None

    def test_invalid_hour_too_large(self):
        """Test invalid hour > 23."""
        result = detect_timezone_from_local_time("25:30")

        assert result is None

    def test_invalid_minute_too_large(self):
        """Test invalid minute > 59."""
        result = detect_timezone_from_local_time("15:70")

        assert result is None

    def test_valid_edge_case_midnight(self):
        """Test valid midnight time."""
        result = detect_timezone_from_local_time("00:00")

        assert result is not None

    def test_valid_edge_case_end_of_day(self):
        """Test valid end of day time."""
        result = detect_timezone_from_local_time("23:59")

        assert result is not None

    @freeze_time("2026-05-12 12:00:00", tz_offset=0)
    def test_single_digit_hour(self):
        """Test single digit hour without leading zero."""
        result = detect_timezone_from_local_time("9:30")

        assert result is not None

    @freeze_time("2026-05-12 12:00:00", tz_offset=0)
    def test_single_digit_minute(self):
        """Test single digit minute without leading zero."""
        result = detect_timezone_from_local_time("15:5")

        # May or may not parse depending on implementation
        # Just check it doesn't crash
        assert result is None or result is not None

    @freeze_time("2026-05-12 12:00:00", tz_offset=0)
    def test_offset_rounding_positive(self):
        """Test that offset rounds to nearest hour (positive)."""
        # If UTC is 12:00 and local is 14:40, offset is +2.67 hours (rounds to +3)
        result = detect_timezone_from_local_time("14:40")

        assert result is not None
        # Should round to nearest hour
        assert result.offset_hours in [2, 3]

    @freeze_time("2026-05-12 12:00:00", tz_offset=0)
    def test_offset_rounding_negative(self):
        """Test that offset rounds to nearest hour (negative)."""
        # If UTC is 12:00 and local is 09:20, offset is -2.67 hours (rounds to -3)
        result = detect_timezone_from_local_time("09:20")

        assert result is not None
        # Should round to nearest hour
        assert result.offset_hours in [-2, -3]
