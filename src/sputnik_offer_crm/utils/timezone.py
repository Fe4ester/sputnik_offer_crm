"""Timezone detection utilities."""

import re
from datetime import datetime, timezone
from typing import NamedTuple


class TimezoneDetectionResult(NamedTuple):
    """Result of timezone detection from local time."""

    timezone_str: str
    offset_hours: int
    display_name: str


# Canonical mapping: UTC offset -> preferred timezone
# Based on supported timezones in the project
OFFSET_TO_TIMEZONE = {
    0: ("UTC", "UTC"),
    1: ("Etc/GMT-1", "UTC+1"),
    2: ("Europe/Kaliningrad", "Калининград (UTC+2)"),
    3: ("Europe/Moscow", "Москва (UTC+3)"),
    4: ("Europe/Samara", "Самара (UTC+4)"),
    5: ("Asia/Yekaterinburg", "Екатеринбург (UTC+5)"),
    6: ("Asia/Omsk", "Омск (UTC+6)"),
    7: ("Asia/Krasnoyarsk", "Красноярск (UTC+7)"),
    8: ("Asia/Irkutsk", "Иркутск (UTC+8)"),
    9: ("Etc/GMT-9", "UTC+9"),
    10: ("Asia/Vladivostok", "Владивосток (UTC+10)"),
    11: ("Etc/GMT-11", "UTC+11"),
    12: ("Etc/GMT-12", "UTC+12"),
    -1: ("Etc/GMT+1", "UTC-1"),
    -2: ("Etc/GMT+2", "UTC-2"),
    -3: ("Etc/GMT+3", "UTC-3"),
    -4: ("Etc/GMT+4", "UTC-4"),
    -5: ("Etc/GMT+5", "UTC-5"),
    -6: ("Etc/GMT+6", "UTC-6"),
    -7: ("Etc/GMT+7", "UTC-7"),
    -8: ("Etc/GMT+8", "UTC-8"),
    -9: ("Etc/GMT+9", "UTC-9"),
    -10: ("Etc/GMT+10", "UTC-10"),
    -11: ("Etc/GMT+11", "UTC-11"),
    -12: ("Etc/GMT+12", "UTC-12"),
}


def parse_local_time(time_str: str) -> tuple[int, int] | None:
    """
    Parse local time string in HH:MM format.

    Returns:
        (hours, minutes) tuple or None if invalid
    """
    # Match HH:MM format
    match = re.match(r"^(\d{1,2}):(\d{2})$", time_str.strip())
    if not match:
        return None

    hours = int(match.group(1))
    minutes = int(match.group(2))

    # Validate ranges
    if hours < 0 or hours > 23:
        return None
    if minutes < 0 or minutes > 59:
        return None

    return (hours, minutes)


def detect_timezone_from_local_time(
    local_time_str: str,
) -> TimezoneDetectionResult | None:
    """
    Detect timezone from user's local time.

    Algorithm:
    1. Parse local time HH:MM
    2. Get current UTC time
    3. Calculate offset: local_time - utc_time
    4. Map offset to canonical timezone

    Returns:
        TimezoneDetectionResult or None if detection failed

    Limitations:
    - Assumes user enters time on the same day as UTC
    - Does not handle DST transitions
    - Maps to canonical timezone per offset (may not match exact location)
    """
    parsed = parse_local_time(local_time_str)
    if not parsed:
        return None

    local_hours, local_minutes = parsed

    # Get current UTC time
    now_utc = datetime.now(timezone.utc)
    utc_hours = now_utc.hour
    utc_minutes = now_utc.minute

    # Calculate offset in hours (simplified, assumes same day)
    # Convert to minutes for more accurate calculation
    local_total_minutes = local_hours * 60 + local_minutes
    utc_total_minutes = utc_hours * 60 + utc_minutes

    offset_minutes = local_total_minutes - utc_total_minutes

    # Handle day boundary crossing
    # If offset is too large, assume day boundary was crossed
    if offset_minutes > 12 * 60:
        offset_minutes -= 24 * 60
    elif offset_minutes < -12 * 60:
        offset_minutes += 24 * 60

    # Round to nearest hour
    offset_hours = round(offset_minutes / 60)

    # Clamp to valid range
    if offset_hours < -12 or offset_hours > 12:
        return None

    # Map to timezone
    if offset_hours not in OFFSET_TO_TIMEZONE:
        return None

    tz_str, display_name = OFFSET_TO_TIMEZONE[offset_hours]

    return TimezoneDetectionResult(
        timezone_str=tz_str,
        offset_hours=offset_hours,
        display_name=display_name,
    )
