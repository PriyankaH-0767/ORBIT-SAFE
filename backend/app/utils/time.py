"""Astrodynamics and UTC time conventions for D-DATO.

D-DATO architectural time policies:
- UTC for all timestamps across the system
- Timezone-aware Python datetimes only (`timezone.utc`)
- ISO 8601 representation at all API boundaries
- Never silently interpret naive datetimes as local time (raise ValueError)
- Deterministic and testable time arithmetic
"""

from datetime import datetime, timezone
from typing import Union


def now_utc() -> datetime:
    """Return the current system time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def is_aware(dt: datetime) -> bool:
    """Check if a datetime object has explicit timezone information."""
    if not isinstance(dt, datetime):
        raise TypeError(f"Expected datetime object, got {type(dt).__name__}.")
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def ensure_utc(dt: datetime) -> datetime:
    """Ensure that a datetime object is timezone-aware and represented in UTC.

    Raises:
        ValueError: If a naive datetime is provided (D-DATO never assumes local time).
        TypeError: If input is not a datetime object.
    """
    if not isinstance(dt, datetime):
        raise TypeError(f"Expected datetime object, got {type(dt).__name__}.")
    if not is_aware(dt):
        raise ValueError(
            "Naive datetime received. D-DATO strictly requires explicit timezone-aware UTC datetimes."
        )
    return dt.astimezone(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Convert an aware datetime from any timezone into UTC.

    Raises:
        ValueError: If a naive datetime is provided.
    """
    return ensure_utc(dt)


def duration_seconds(start: datetime, end: datetime) -> float:
    """Calculate the duration in seconds between two timestamps (end - start).

    Both timestamps must be timezone-aware.
    """
    start_utc = ensure_utc(start)
    end_utc = ensure_utc(end)
    return (end_utc - start_utc).total_seconds()


def parse_iso_utc(iso_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware UTC datetime.

    Accepts standard ISO 8601 strings such as:
    - "2026-10-01T12:00:00Z"
    - "2026-10-01T12:00:00+00:00"
    - "2026-10-01T14:00:00+02:00"

    Raises:
        ValueError: If the string is malformed or lacks an explicit timezone specification.
        TypeError: If input is not a string.
    """
    if not isinstance(iso_str, str):
        raise TypeError(f"Expected string for ISO timestamp, got {type(iso_str).__name__}.")

    clean_str = iso_str.strip()
    try:
        dt = datetime.fromisoformat(clean_str)
    except Exception as e:
        raise ValueError(f"Malformed ISO 8601 timestamp '{iso_str}': {e}") from e

    if not is_aware(dt):
        raise ValueError(
            f"ISO timestamp '{iso_str}' lacks timezone offset. D-DATO requires explicit timezone-aware ISO 8601 strings."
        )

    return dt.astimezone(timezone.utc)


def format_iso_utc(dt: datetime) -> str:
    """Format a timezone-aware datetime into a canonical ISO 8601 UTC string ending in 'Z'."""
    dt_utc = ensure_utc(dt)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def datetime_to_julian_date(dt: datetime) -> float:
    """Convert a timezone-aware UTC datetime to Julian Date (JD)."""
    from sgp4.api import jday
    dt_utc = ensure_utc(dt)
    sec_float = dt_utc.second + (dt_utc.microsecond / 1e6)
    jd, fr = jday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour, dt_utc.minute, sec_float)
    return float(jd + fr)


def julian_date_to_gmst(jd: float) -> float:
    """Calculate Greenwich Mean Sidereal Time (GMST) in radians for a given Julian Date."""
    import math
    # Julian centuries from J2000.0
    t = (jd - 2451545.0) / 36525.0
    # IAU-82 GMST polynomial in degrees
    gmst_deg = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * t * t - (t * t * t) / 38710000.0
    gmst_deg = gmst_deg % 360.0
    if gmst_deg < 0.0:
        gmst_deg += 360.0
    return math.radians(gmst_deg)
