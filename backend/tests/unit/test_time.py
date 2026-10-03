"""Unit tests for D-DATO time and UTC convention utilities."""

from datetime import datetime, timezone, timedelta
import pytest

from app.utils.time import (
    now_utc,
    is_aware,
    ensure_utc,
    to_utc,
    duration_seconds,
    parse_iso_utc,
    format_iso_utc,
)


def test_now_utc_returns_aware_utc():
    """Verify now_utc returns a timezone-aware datetime with UTC timezone."""
    dt = now_utc()
    assert isinstance(dt, datetime)
    assert is_aware(dt)
    assert dt.tzinfo == timezone.utc


def test_ensure_utc_rejects_naive_datetime():
    """Verify that naive datetimes are strictly rejected with ValueError."""
    naive_dt = datetime(2026, 10, 1, 12, 0, 0)
    assert not is_aware(naive_dt)

    with pytest.raises(ValueError, match="Naive datetime received"):
        ensure_utc(naive_dt)

    with pytest.raises(ValueError, match="Naive datetime received"):
        to_utc(naive_dt)


def test_timezone_conversion_to_utc():
    """Verify converting an aware datetime with non-UTC offset into UTC."""
    # Create aware datetime in UTC+2
    tz_plus_2 = timezone(timedelta(hours=2))
    dt_plus_2 = datetime(2026, 10, 1, 14, 0, 0, tzinfo=tz_plus_2)

    utc_dt = ensure_utc(dt_plus_2)
    assert utc_dt.tzinfo == timezone.utc
    assert utc_dt.year == 2026
    assert utc_dt.month == 10
    assert utc_dt.day == 1
    assert utc_dt.hour == 12  # 14:00+02:00 is 12:00 UTC
    assert utc_dt.minute == 0


def test_iso8601_parsing_aware_utc():
    """Verify parsing ISO 8601 strings into timezone-aware UTC datetimes."""
    # Case with trailing 'Z'
    dt_z = parse_iso_utc("2026-10-01T12:00:00Z")
    assert is_aware(dt_z)
    assert dt_z.tzinfo == timezone.utc
    assert dt_z.hour == 12

    # Case with offset +02:00
    dt_offset = parse_iso_utc("2026-10-01T14:30:00+02:00")
    assert is_aware(dt_offset)
    assert dt_offset.tzinfo == timezone.utc
    assert dt_offset.hour == 12
    assert dt_offset.minute == 30

    # Case with negative offset -05:00
    dt_neg = parse_iso_utc("2026-10-01T07:00:00-05:00")
    assert is_aware(dt_neg)
    assert dt_neg.tzinfo == timezone.utc
    assert dt_neg.hour == 12


def test_iso8601_parsing_rejects_naive_string():
    """Verify parsing ISO strings without explicit timezone offsets raises ValueError."""
    naive_str = "2026-10-01T12:00:00"
    with pytest.raises(ValueError, match="lacks timezone offset"):
        parse_iso_utc(naive_str)


def test_duration_seconds():
    """Verify duration_seconds calculation between aware datetimes."""
    t1 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 1, 13, 15, 30, tzinfo=timezone.utc)

    # 1 hour + 15 min + 30 sec = 3600 + 900 + 30 = 4530 seconds
    assert duration_seconds(t1, t2) == 4530.0

    # Negative duration if end < start
    assert duration_seconds(t2, t1) == -4530.0

    # Reject if either is naive
    naive_t = datetime(2026, 10, 1, 12, 0, 0)
    with pytest.raises(ValueError):
        duration_seconds(t1, naive_t)


def test_format_iso_utc():
    """Verify format_iso_utc outputs canonical ISO string ending in 'Z'."""
    dt = datetime(2026, 10, 1, 12, 34, 56, tzinfo=timezone.utc)
    formatted = format_iso_utc(dt)
    assert formatted == "2026-10-01T12:34:56Z"
