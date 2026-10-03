"""Unit tests for bounded 1-D TCA numerical refinement."""

from datetime import datetime, timezone, timedelta
import math
import numpy as np
import pytest

from app.core.orbit import CircularJ2Orbit, create_circular_j2_orbit
from app.core.propagation import Sgp4Propagator
from app.core.tca import refine_tca, refine_tca_scalar, TCARefinementResult
from app.data.parser import parse_tle_pair


def test_tca_synthetic_quadratic_minimum():
    """Verify optimizer finds known synthetic minimum within sub-second tolerance."""
    bracket_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    total_seconds = 60.0
    known_tca_offset = 18.734  # seconds
    known_miss_distance = 4.25  # km

    # Distance function: sqrt((s - s0)^2 + d0^2)
    def distance_fn(s: float) -> float:
        return math.sqrt((s - known_tca_offset) ** 2 + known_miss_distance ** 2)

    tca, min_dist, success, iters, msg = refine_tca_scalar(
        distance_fn=distance_fn,
        bracket_start=bracket_start,
        total_seconds=total_seconds,
        xtol_seconds=0.01,
    )

    assert success is True
    expected_tca = bracket_start + timedelta(seconds=known_tca_offset)
    assert abs((tca - expected_tca).total_seconds()) < 0.01
    assert math.isclose(min_dist, known_miss_distance, abs_tol=1e-4)


def test_tca_bounded_interval_clamping():
    """Verify TCA never leaves the bracket even if unconstrained minimum lies outside."""
    bracket_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    total_seconds = 30.0

    # Minimum is at s = -15.0 (before bracket)
    def before_fn(s: float) -> float:
        return math.sqrt((s - (-15.0)) ** 2 + 10.0 ** 2)

    tca_before, dist_before, _, _, _ = refine_tca_scalar(
        distance_fn=before_fn,
        bracket_start=bracket_start,
        total_seconds=total_seconds,
    )
    # Must clamp to bracket_start
    assert tca_before == bracket_start
    assert math.isclose(dist_before, before_fn(0.0), abs_tol=1e-4)

    # Minimum is at s = 50.0 (after bracket)
    def after_fn(s: float) -> float:
        return math.sqrt((s - 50.0) ** 2 + 10.0 ** 2)

    tca_after, dist_after, _, _, _ = refine_tca_scalar(
        distance_fn=after_fn,
        bracket_start=bracket_start,
        total_seconds=total_seconds,
    )
    # Must clamp to bracket_end
    bracket_end = bracket_start + timedelta(seconds=total_seconds)
    assert tca_after == bracket_end
    assert math.isclose(dist_after, after_fn(total_seconds), abs_tol=1e-4)


def test_tca_refinement_exact_distance_and_velocity_recomputation():
    """Verify refine_tca recomputes exact distance and relative velocity with actual propagators."""
    epoch = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    # Candidate: 550 km circular J2 orbit
    candidate = create_circular_j2_orbit(
        altitude_km=550.0,
        inclination_deg=97.5,
        raan_deg=0.0,
        u0_deg=0.0,
        epoch=epoch,
    )

    # Debris: TLE near the candidate orbit
    # ISS or typical LEO TLE adapted to epoch 2026-10-02
    tle1 = "1 25544U 98067A   26275.00000000  .00016717  00000-0  10270-3 0  9001"
    tle2 = "2 25544  97.5000 000.0000 0004500   0.0000   0.0000 15.00000000000015"
    record = parse_tle_pair(tle1, tle2, object_name="LEO-DEBRIS-TEST", verify_checksum=False)
    record.epoch = epoch
    propagator = Sgp4Propagator(record)

    bracket_start = epoch + timedelta(seconds=100)
    bracket_end = epoch + timedelta(seconds=200)

    result = refine_tca(
        candidate_orbit=candidate,
        debris_propagator=propagator,
        bracket_start=bracket_start,
        bracket_end=bracket_end,
    )

    assert result.success is True
    assert bracket_start <= result.tca <= bracket_end

    # Verify returned miss distance matches direct manual state evaluation at result.tca
    dt_cand = (result.tca - candidate.epoch).total_seconds()
    r_cand, v_cand = candidate.state_at(dt_cand)
    deb_state = propagator.propagate(result.tca)
    r_deb = deb_state.position_km
    v_deb = deb_state.velocity_km_s

    direct_dist = float(np.linalg.norm(np.asarray(r_cand) - np.asarray(r_deb)))
    direct_vel = float(np.linalg.norm(np.asarray(v_cand) - np.asarray(v_deb)))

    assert math.isclose(result.miss_distance_km, direct_dist, abs_tol=1e-6)
    assert math.isclose(result.relative_velocity_km_s, direct_vel, abs_tol=1e-6)
    assert result.miss_distance_km >= 0.0
    assert result.relative_velocity_km_s >= 0.0


def test_tca_optimizer_failure_path_no_fabricated_event():
    """Verify optimizer failure or invalid bounds does not fabricate a valid event."""
    bracket_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    bracket_end = bracket_start - timedelta(seconds=10)  # Invalid: end < start

    epoch = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    candidate = create_circular_j2_orbit(550.0, 97.5, 0.0, 0.0, epoch)
    tle1 = "1 25544U 98067A   26275.00000000  .00016717  00000-0  10270-3 0  9001"
    tle2 = "2 25544  97.5000 000.0000 0004500   0.0000   0.0000 15.00000000000015"
    record = parse_tle_pair(tle1, tle2, object_name="DEB", verify_checksum=False)
    record.epoch = epoch
    propagator = Sgp4Propagator(record)

    with pytest.raises(ValueError, match="must be >="):
        refine_tca(candidate, propagator, bracket_start, bracket_end)
