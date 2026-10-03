"""Unit tests for D-DATO unit conversion utilities."""

import math
import pytest

from app.utils.units import (
    deg_to_rad,
    rad_to_deg,
    m_s_to_km_s,
    km_s_to_m_s,
    minutes_to_seconds,
    seconds_to_minutes,
    km_to_m,
    m_to_km,
)


def test_angle_conversions():
    """Verify degrees to radians and radians to degrees conversions."""
    # Representative values
    assert math.isclose(deg_to_rad(180.0), math.pi, rel_tol=1e-12)
    assert math.isclose(deg_to_rad(0.0), 0.0, abs_tol=1e-12)
    assert math.isclose(deg_to_rad(90.0), math.pi / 2.0, rel_tol=1e-12)
    assert math.isclose(deg_to_rad(360.0), 2.0 * math.pi, rel_tol=1e-12)

    assert math.isclose(rad_to_deg(math.pi), 180.0, rel_tol=1e-12)
    assert math.isclose(rad_to_deg(math.pi / 2.0), 90.0, rel_tol=1e-12)

    # Round trip test across arbitrary angles
    test_angles = [0.0, 45.0, 97.5, 180.0, 270.0, 359.99]
    for angle in test_angles:
        rad = deg_to_rad(angle)
        deg_back = rad_to_deg(rad)
        assert math.isclose(angle, deg_back, rel_tol=1e-12)


def test_velocity_conversions():
    """Verify m/s to km/s and km/s to m/s conversions."""
    # Representative values
    assert math.isclose(m_s_to_km_s(1.0), 0.001, rel_tol=1e-12)
    assert math.isclose(m_s_to_km_s(100.0), 0.1, rel_tol=1e-12)
    assert math.isclose(km_s_to_m_s(7.5), 7500.0, rel_tol=1e-12)

    # Round trip
    velocities_m_s = [0.0, 1.0, 100.0, 7500.0, 11200.0]
    for v in velocities_m_s:
        v_km = m_s_to_km_s(v)
        v_back = km_s_to_m_s(v_km)
        assert math.isclose(v, v_back, rel_tol=1e-12)


def test_time_conversions():
    """Verify minutes to seconds and seconds to minutes conversions."""
    # Representative values
    assert math.isclose(minutes_to_seconds(60.0), 3600.0, rel_tol=1e-12)
    assert math.isclose(minutes_to_seconds(1.0), 60.0, rel_tol=1e-12)
    assert math.isclose(seconds_to_minutes(3600.0), 60.0, rel_tol=1e-12)

    # Round trip
    durations_min = [0.0, 0.5, 15.0, 60.0, 720.0]
    for m in durations_min:
        s = minutes_to_seconds(m)
        m_back = seconds_to_minutes(s)
        assert math.isclose(m, m_back, rel_tol=1e-12)


def test_distance_conversions():
    """Verify km to m and m to km conversions."""
    assert math.isclose(km_to_m(1.0), 1000.0, rel_tol=1e-12)
    assert math.isclose(m_to_km(1000.0), 1.0, rel_tol=1e-12)
    assert math.isclose(km_to_m(550.0), 550000.0, rel_tol=1e-12)


def test_invalid_input_rejection():
    """Verify conversion functions reject non-finite inputs and wrong types."""
    # Non-finite values (NaN, Inf) must raise ValueError
    for bad_val in [float("nan"), float("inf"), float("-inf")]:
        with pytest.raises(ValueError):
            deg_to_rad(bad_val)
        with pytest.raises(ValueError):
            rad_to_deg(bad_val)
        with pytest.raises(ValueError):
            m_s_to_km_s(bad_val)
        with pytest.raises(ValueError):
            minutes_to_seconds(bad_val)

    # Non-numeric types (strings, None, bool) must raise TypeError
    for bad_type in ["180", None, True, False, [10]]:
        with pytest.raises(TypeError):
            deg_to_rad(bad_type)
        with pytest.raises(TypeError):
            m_s_to_km_s(bad_type)
        with pytest.raises(TypeError):
            minutes_to_seconds(bad_type)
