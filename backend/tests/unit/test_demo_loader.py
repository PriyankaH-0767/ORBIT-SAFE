"""Unit tests for offline demo data loader (demo_loader.py)."""

from datetime import timezone
import pytest

from app.data.demo_loader import (
    get_demo_raw_payload,
    load_demo_plan,
    load_demo_records,
    load_demo_tles,
)
from app.data.filter import classify_object


def test_load_demo_records_source_tagging():
    """Verify that all demo records are explicitly marked with source='demo'."""
    records = load_demo_records()
    assert len(records) > 0
    for r in records:
        assert r.source == "demo"
        assert r.epoch.tzinfo == timezone.utc


def test_demo_catalog_object_categories():
    """Verify demo catalog includes payload, rocket body, debris, and modern 6-digit objects."""
    records = load_demo_records()
    categories = {classify_object(r).category for r in records}

    assert "payload" in categories
    assert "rocket_body" in categories
    assert "debris" in categories

    # Verify modern 6-digit catalog ID is present
    has_6digit = any(len(r.norad_id) >= 6 for r in records)
    assert has_6digit is True


def test_load_demo_tle_format():
    """Verify loading demo records specifically in TLE format."""
    tle_records = load_demo_records(preferred_format="tle")
    assert len(tle_records) >= 4
    for r in tle_records:
        assert r.source == "demo"
        assert r.element_format == "tle"
        assert r.raw_tle_line1 is not None
        assert r.raw_tle_line2 is not None


def test_load_demo_tles_string_list():
    """Verify load_demo_tles returns standard raw TLE strings."""
    lines = load_demo_tles()
    assert len(lines) >= 10
    # Must contain lines starting with 1 and 2
    assert any(line.startswith("1 ") for line in lines)
    assert any(line.startswith("2 ") for line in lines)


def test_load_demo_plan_structure():
    """Verify load_demo_plan returns valid mission planning configuration dictionary."""
    plan_dict = load_demo_plan()
    assert plan_dict["demo_mode"] is True
    assert plan_dict["data_source"] == "celestrak"
    assert 500.0 <= plan_dict["altitude_min_km"] < plan_dict["altitude_max_km"] <= 600.0
    assert 90.0 <= plan_dict["inclination_min_deg"] < plan_dict["inclination_max_deg"] <= 100.0
    assert plan_dict["fuel_weight"] + plan_dict["risk_weight"] == pytest.approx(1.0)
