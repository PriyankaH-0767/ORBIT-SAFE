"""Unit tests for Circular J2 secular candidate orbit model and Keplerian representations (orbit.py)."""

from datetime import datetime, timedelta, timezone
import math
import pytest

from app.core.constants import DEG_TO_RAD, J2, MU, RE
from app.core.orbit import (
    CircularJ2Orbit,
    KeplerianElements,
    create_circular_j2_orbit,
    keplerian_to_cartesian,
)


def test_circular_j2_semi_major_axis_and_mean_motion():
    """Verify semi-major axis a = RE + altitude and n = sqrt(MU / a^3)."""
    alt = 550.0
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    orbit = create_circular_j2_orbit(altitude_km=alt, inclination_deg=97.5, epoch=epoch)

    expected_a = RE + 550.0
    assert orbit.semi_major_axis_km == pytest.approx(expected_a)

    expected_n = math.sqrt(MU / math.pow(expected_a, 3))
    assert orbit.mean_motion_rad_s == pytest.approx(expected_n)


def test_circular_j2_secular_rates_exact_formulas():
    """Verify analytical J2 secular RAAN and argument of latitude rates."""
    alt = 550.0
    inc_deg = 97.5
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    orbit = create_circular_j2_orbit(altitude_km=alt, inclination_deg=inc_deg, epoch=epoch)

    a = RE + alt
    n = math.sqrt(MU / math.pow(a, 3))
    inc_rad = inc_deg * DEG_TO_RAD

    # Exact RAAN rate formula
    expected_raan_rate = -1.5 * J2 * n * math.pow(RE / a, 2) * math.cos(inc_rad)
    assert orbit.raan_rate_rad_s == pytest.approx(expected_raan_rate)

    # For retrograde SSO (inc = 97.5 deg), cos(i) < 0 so raan_rate should be positive (eastward drift ~ 0.9856 deg/day)
    assert orbit.raan_rate_rad_s > 0.0

    # Exact argument of perigee rate
    expected_omega_rate = 0.75 * J2 * n * math.pow(RE / a, 2) * (5.0 * math.pow(math.cos(inc_rad), 2) - 1.0)
    expected_u_rate = n + expected_omega_rate
    assert orbit.argument_of_latitude_rate_rad_s == pytest.approx(expected_u_rate)


def test_circular_j2_initial_state():
    """Verify initial position at RAAN = 0 and u0 = 0 lies on the equatorial X axis."""
    alt = 500.0
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    orbit = create_circular_j2_orbit(
        altitude_km=alt,
        inclination_deg=98.0,
        raan_deg=0.0,
        u0_deg=0.0,
        epoch=epoch,
    )

    pos0 = orbit.position_at(0.0)
    a = RE + alt
    # At RAAN=0, u=0: x = a, y = 0, z = 0
    assert pos0[0] == pytest.approx(a, abs=1e-9)
    assert pos0[1] == pytest.approx(0.0, abs=1e-9)
    assert pos0[2] == pytest.approx(0.0, abs=1e-9)


def test_circular_j2_one_minute_propagation():
    """Verify deterministic state after 60 seconds of propagation."""
    alt = 550.0
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    orbit = create_circular_j2_orbit(
        altitude_km=alt,
        inclination_deg=97.5,
        raan_deg=45.0,
        u0_deg=30.0,
        epoch=epoch,
    )

    pos_60, vel_60 = orbit.state_at(60.0)
    for coord in pos_60 + vel_60:
        assert math.isfinite(coord)

    # Radius must remain exactly equal to semi-major axis a
    r_mag = math.sqrt(pos_60[0] ** 2 + pos_60[1] ** 2 + pos_60[2] ** 2)
    assert r_mag == pytest.approx(orbit.semi_major_axis_km, abs=1e-8)


def test_circular_j2_velocity_consistency_finite_difference():
    """Verify analytical velocity matches central finite-difference position derivative."""
    alt = 600.0
    inc_deg = 97.5
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    orbit = create_circular_j2_orbit(
        altitude_km=alt,
        inclination_deg=inc_deg,
        raan_deg=30.0,
        u0_deg=60.0,
        epoch=epoch,
    )

    # Test at dt = 1200 seconds (~20 minutes)
    dt = 1200.0
    h = 1e-4  # Step size for central difference

    pos_plus = orbit.position_at(dt + h)
    pos_minus = orbit.position_at(dt - h)

    vx_fd = (pos_plus[0] - pos_minus[0]) / (2.0 * h)
    vy_fd = (pos_plus[1] - pos_minus[1]) / (2.0 * h)
    vz_fd = (pos_plus[2] - pos_minus[2]) / (2.0 * h)

    vx_an, vy_an, vz_an = orbit.velocity_at(dt)

    assert math.isclose(vx_an, vx_fd, rel_tol=1e-7, abs_tol=1e-7)
    assert math.isclose(vy_an, vy_fd, rel_tol=1e-7, abs_tol=1e-7)
    assert math.isclose(vz_an, vz_fd, rel_tol=1e-7, abs_tol=1e-7)


def test_circular_j2_physical_sanity():
    """Verify physical properties: radius == a, altitude constant, LEO speed in [7.4, 7.8] km/s."""
    alt = 550.0
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    orbit = create_circular_j2_orbit(altitude_km=alt, inclination_deg=97.5, epoch=epoch)

    # Sample across half an orbit (~48 minutes)
    for t_sec in [0.0, 300.0, 900.0, 1800.0, 2700.0]:
        pos, vel = orbit.state_at(t_sec)
        r_mag = math.sqrt(pos[0] ** 2 + pos[1] ** 2 + pos[2] ** 2)
        v_mag = math.sqrt(vel[0] ** 2 + vel[1] ** 2 + vel[2] ** 2)

        # Radius constant
        assert r_mag == pytest.approx(orbit.semi_major_axis_km, abs=1e-8)
        # Geocentric altitude constant
        assert (r_mag - RE) == pytest.approx(alt, abs=1e-8)
        # Physical speed for 550 km LEO is approx 7.58 km/s
        assert 7.4 < v_mag < 7.8


def test_circular_j2_validation_rejections():
    """Verify input validation rejects invalid inputs."""
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Negative altitude
    with pytest.raises(ValueError, match="altitude_km must be > 0"):
        create_circular_j2_orbit(altitude_km=-100.0, inclination_deg=97.5, epoch=epoch)

    # Inclination > 180
    with pytest.raises(ValueError, match="inclination_deg"):
        create_circular_j2_orbit(altitude_km=550.0, inclination_deg=195.0, epoch=epoch)

    # Naive datetime
    naive_dt = datetime(2026, 10, 1, 12, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        create_circular_j2_orbit(altitude_km=550.0, inclination_deg=97.5, epoch=naive_dt)


def test_keplerian_to_cartesian_basic():
    """Verify keplerian_to_cartesian produces consistent circular orbit radius."""
    a = 7000.0
    kep = KeplerianElements(
        semi_major_axis_km=a,
        eccentricity=0.0,
        inclination_rad=0.0,
        raan_rad=0.0,
        arg_perigee_rad=0.0,
        true_anomaly_rad=0.0,
    )
    pos, vel = keplerian_to_cartesian(kep)
    assert pos[0] == pytest.approx(a)
    assert pos[1] == pytest.approx(0.0)
    assert pos[2] == pytest.approx(0.0)
    # Circular speed sqrt(mu / a)
    expected_v = math.sqrt(MU / a)
    assert vel[1] == pytest.approx(expected_v)
