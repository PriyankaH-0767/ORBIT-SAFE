"""Unit tests for conjunction screening geometry, relative states, prefiltering, and deduplication."""

from datetime import datetime, timezone, timedelta
import math
import numpy as np
import pytest

from app.core.candidate_generator import CandidateOrbit
from app.core.conjunction import (
    calculate_relative_distance,
    calculate_relative_velocity,
    calculate_relative_state,
    candidate_to_screening_orbit,
    prefilter_debris,
    deduplicate_conjunction_events,
    ConjunctionEventResult,
)
from app.data.parser import CanonicalElementRecord


def test_zero_relative_position():
    """Verify zero relative position yields distance 0.0."""
    r1 = np.array([7000.0, 0.0, 0.0])
    r2 = np.array([7000.0, 0.0, 0.0])
    dist = calculate_relative_distance(r1, r2)
    assert dist == 0.0


def test_known_vector_separation():
    """Verify 3-4-5 Pythagorean vector separation."""
    r1 = np.array([100.0, 200.0, 300.0])
    r2 = np.array([130.0, 240.0, 300.0])
    dist = calculate_relative_distance(r1, r2)
    assert math.isclose(dist, 50.0, abs_tol=1e-9)


def test_known_relative_velocity():
    """Verify relative velocity magnitude."""
    v1 = np.array([7.0, 1.0, 0.0])
    v2 = np.array([4.0, 5.0, 0.0])
    speed = calculate_relative_velocity(v1, v2)
    assert math.isclose(speed, 5.0, abs_tol=1e-9)


def test_calculate_relative_state():
    """Verify joint relative state calculation."""
    r1 = np.array([7000.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.5, 0.0])
    r2 = np.array([7010.0, 0.0, 0.0])
    v2 = np.array([0.0, 0.0, 0.0])

    dist, speed = calculate_relative_state(r1, v1, r2, v2)
    assert math.isclose(dist, 10.0, abs_tol=1e-9)
    assert math.isclose(speed, 7.5, abs_tol=1e-9)


def test_distance_rejects_non_finite_and_invalid_shapes():
    """Verify validation rejects NaN, Inf, and incorrect shapes."""
    with pytest.raises(ValueError, match="Position vectors must be 3-D"):
        calculate_relative_distance(np.array([1.0, 2.0]), np.array([1.0, 2.0, 3.0]))

    with pytest.raises(ValueError, match="Position vectors must contain finite numerical values"):
        calculate_relative_distance(np.array([np.nan, 0.0, 0.0]), np.array([0.0, 0.0, 0.0]))

    with pytest.raises(ValueError, match="Velocity vectors must contain finite numerical values"):
        calculate_relative_velocity(np.array([np.inf, 0.0, 0.0]), np.array([0.0, 0.0, 0.0]))


def test_candidate_to_screening_orbit_semantic_rule():
    """Verify Section 0 Critical Semantic Rule:

    candidate_to_screening_orbit constructs CircularJ2Orbit anchored at:
    epoch = candidate.deployment_epoch
    raan = candidate.raan_deg
    u0 = candidate.u0_deg
    Does NOT re-apply delay or propagate from epoch_start.
    """
    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    deployment_epoch = datetime(2026, 10, 2, 1, 0, 0, tzinfo=timezone.utc)  # 60 min delay

    cand = CandidateOrbit(
        candidate_id="TEST_CAND_01",
        altitude_km=550.0,
        inclination_deg=97.5,
        raan_deg=15.0408,  # Derived RAAN associated with delay
        u0_deg=45.0,
        deployment_delay_minutes=60.0,
        base_raan_deg=0.0,
        raan_delay_coupling_deg_per_min=0.25068,
        epoch_start=epoch_start,
        deployment_epoch=deployment_epoch,
        generated_index=1,
    )

    screening_orbit = candidate_to_screening_orbit(cand)

    assert screening_orbit.epoch == deployment_epoch
    assert screening_orbit.raan_deg == 15.0408
    assert screening_orbit.u0_deg == 45.0
    assert screening_orbit.altitude_km == 550.0
    assert screening_orbit.inclination_deg == 97.5


def _create_test_record(norad_id: str, name: str, classification: str, mm: float, ecc: float = 0.001, inc: float = 97.5) -> CanonicalElementRecord:
    """Helper to create test CanonicalElementRecord."""
    epoch = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    return CanonicalElementRecord(
        object_name=name,
        norad_id=norad_id,
        epoch=epoch,
        inclination_deg=inc,
        eccentricity=ecc,
        raan_deg=0.0,
        arg_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
        mean_motion_rev_per_day=mm,
        classification=classification,
        fetched_at=epoch,
    )


def test_prefilter_debris_payload_exclusion_and_unknown_inclusion():
    """Verify conservative prefilter excludes 'payload' and includes 'debris', 'rocket_body', 'unknown'."""
    # Mean motion ~15.0 rev/day corresponds to ~550 km LEO altitude
    r_deb = _create_test_record("10001", "DEBRIS OBJECT A", "debris", 15.0)
    r_rb = _create_test_record("10002", "SL-16 R/B", "rocket_body", 15.0)
    r_unk = _create_test_record("10003", "UNKNOWN FRAGMENT", "unknown", 15.0)
    r_pay = _create_test_record("10004", "STARLINK-1000", "payload", 15.0)

    accepted, skipped = prefilter_debris(
        debris_records=[r_deb, r_rb, r_unk, r_pay],
        candidate_altitude_km=550.0,
        margin_km=300.0,
        include_unknown=True,
    )

    norads = [r.norad_id for r, _ in accepted]
    assert "10001" in norads
    assert "10002" in norads
    assert "10003" in norads
    assert "10004" not in norads
    assert skipped == 1


def test_prefilter_debris_altitude_envelope():
    """Verify prefilter rejects objects whose altitude range cannot overlap candidate altitude +/- 300 km."""
    # mm = 15.0 -> ~550 km
    r_overlap = _create_test_record("20001", "DEB 550", "debris", 15.0)  # ~550 km alt
    # mm = 13.0 -> ~1250 km (far above 550 + 300 = 850 km)
    r_distant_high = _create_test_record("20002", "DEB HIGH", "debris", 13.0)

    accepted, skipped = prefilter_debris(
        debris_records=[r_overlap, r_distant_high],
        candidate_altitude_km=550.0,
        margin_km=300.0,
    )

    norads = [r.norad_id for r, _ in accepted]
    assert "20001" in norads
    assert "20002" not in norads
    assert skipped == 1


def test_prefilter_debris_never_excludes_by_inclination():
    """Verify prefilter does NOT exclude objects simply due to inclination differences."""
    # r_equatorial is at 28.5 deg, candidate is at 97.5 deg, but altitude is ~550 km
    r_equatorial = _create_test_record("30001", "DEB EQUATORIAL", "debris", 15.0, inc=28.5)

    accepted, skipped = prefilter_debris(
        debris_records=[r_equatorial],
        candidate_altitude_km=550.0,
        margin_km=300.0,
    )

    assert len(accepted) == 1
    assert skipped == 0
    assert accepted[0][0].norad_id == "30001"


def test_deduplication_same_pair_within_30s():
    """Verify events for the same pair within 30s are merged, retaining minimum miss distance."""
    base_tca = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)

    ev1 = ConjunctionEventResult(
        candidate_id="CAND_A",
        debris_object_id="DEB_1",
        debris_norad_id="11111",
        tca=base_tca,
        miss_distance_km=12.5,
        relative_velocity_km_s=10.2,
        coarse_min_distance_km=20.0,
        coarse_time=base_tca,
        screening_start=base_tca,
        screening_end=base_tca + timedelta(days=3),
        coarse_step_seconds=30.0,
        coarse_threshold_km=260.0,
        acceptance_threshold_km=25.0,
    )
    # Same pair 15 seconds later with a smaller miss distance
    ev2 = ConjunctionEventResult(
        candidate_id="CAND_A",
        debris_object_id="DEB_1",
        debris_norad_id="11111",
        tca=base_tca + timedelta(seconds=15),
        miss_distance_km=8.1,
        relative_velocity_km_s=10.2,
        coarse_min_distance_km=20.0,
        coarse_time=base_tca,
        screening_start=base_tca,
        screening_end=base_tca + timedelta(days=3),
        coarse_step_seconds=30.0,
        coarse_threshold_km=260.0,
        acceptance_threshold_km=25.0,
    )

    deduped = deduplicate_conjunction_events([ev1, ev2], merge_window_seconds=30.0)
    assert len(deduped) == 1
    assert deduped[0].miss_distance_km == 8.1
    assert deduped[0].tca == base_tca + timedelta(seconds=15)


def test_deduplication_preserves_separated_encounters():
    """Verify genuinely separated encounters (> 30s) are retained separately."""
    base_tca = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    orbit_tca = base_tca + timedelta(minutes=95)  # 1 orbit later

    ev1 = ConjunctionEventResult(
        candidate_id="CAND_A",
        debris_object_id="DEB_1",
        debris_norad_id="11111",
        tca=base_tca,
        miss_distance_km=10.0,
        relative_velocity_km_s=9.5,
        coarse_min_distance_km=15.0,
        coarse_time=base_tca,
        screening_start=base_tca,
        screening_end=base_tca + timedelta(days=3),
        coarse_step_seconds=30.0,
        coarse_threshold_km=260.0,
        acceptance_threshold_km=25.0,
    )
    ev2 = ConjunctionEventResult(
        candidate_id="CAND_A",
        debris_object_id="DEB_1",
        debris_norad_id="11111",
        tca=orbit_tca,
        miss_distance_km=14.0,
        relative_velocity_km_s=9.5,
        coarse_min_distance_km=22.0,
        coarse_time=orbit_tca,
        screening_start=base_tca,
        screening_end=base_tca + timedelta(days=3),
        coarse_step_seconds=30.0,
        coarse_threshold_km=260.0,
        acceptance_threshold_km=25.0,
    )

    deduped = deduplicate_conjunction_events([ev1, ev2], merge_window_seconds=30.0)
    assert len(deduped) == 2
    assert deduped[0].tca == base_tca
    assert deduped[1].tca == orbit_tca


def test_deterministic_event_ordering():
    """Verify event ordering per Section 20: 1. candidate_id, 2. tca, 3. miss_distance, 4. debris_norad_id."""
    t1 = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 2, 14, 0, 0, tzinfo=timezone.utc)

    e1 = ConjunctionEventResult("CAND_B", None, "20000", t1, 15.0, 5.0, 20.0, t1, t1, t2, 30.0, 260.0, 25.0)
    e2 = ConjunctionEventResult("CAND_A", None, "30000", t2, 10.0, 5.0, 20.0, t2, t1, t2, 30.0, 260.0, 25.0)
    e3 = ConjunctionEventResult("CAND_A", None, "10000", t1, 20.0, 5.0, 20.0, t1, t1, t2, 30.0, 260.0, 25.0)
    e4 = ConjunctionEventResult("CAND_A", None, "10001", t1, 10.0, 5.0, 20.0, t1, t1, t2, 30.0, 260.0, 25.0)

    deduped = deduplicate_conjunction_events([e1, e2, e3, e4])

    # Expect:
    # 1. CAND_A at t1, miss 10.0 (e4)
    # 2. CAND_A at t1, miss 20.0 (e3)
    # 3. CAND_A at t2, miss 10.0 (e2)
    # 4. CAND_B at t1, miss 15.0 (e1)
    assert deduped[0] == e4
    assert deduped[1] == e3
    assert deduped[2] == e2
    assert deduped[3] == e1
