"""Unit tests for D-DATO screening risk score modeling (Phase P9)."""

from datetime import datetime, timezone, timedelta
import math
import pytest

from app.core.conjunction import ConjunctionEventResult
from app.core.risk import (
    RiskAssessment,
    RiskScoringError,
    assess_candidate_risk,
    calculate_event_count_score,
    calculate_proximity_score,
    calculate_risk_score,
    calculate_scalar_risk_score,
    determine_uncertainty_level,
)


def _make_event(
    miss_distance_km: float,
    relative_velocity_km_s: float = 7.5,
    candidate_id: str = "CAND_01",
    norad_id: str = "99001",
) -> ConjunctionEventResult:
    """Helper to construct valid ConjunctionEventResult test fixture."""
    tca = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    return ConjunctionEventResult(
        candidate_id=candidate_id,
        debris_object_id=None,
        debris_norad_id=norad_id,
        tca=tca,
        miss_distance_km=miss_distance_km,
        relative_velocity_km_s=relative_velocity_km_s,
        coarse_min_distance_km=miss_distance_km + 5.0,
        coarse_time=tca,
        screening_start=tca - timedelta(days=1),
        screening_end=tca + timedelta(days=2),
        coarse_step_seconds=30.0,
        coarse_threshold_km=260.0,
        acceptance_threshold_km=25.0,
    )


# =====================================================================
# Core Scoring Requirements (Sections 3, 6, 17)
# =====================================================================

def test_risk_no_events_yields_zero():
    """Requirement A: No accepted events must evaluate to risk_score 0.0."""
    res = assess_candidate_risk(candidate="CAND_01", conjunction_events=[])
    assert res.risk_score == 0.0
    assert res.proximity_score == 0.0
    assert res.event_count_score == 0.0
    assert res.accepted_event_count == 0
    assert res.minimum_miss_distance_km is None
    assert res.minimum_relative_velocity_km_s is None
    assert res.maximum_relative_velocity_km_s is None
    assert res.scoring_method == "fallback_heuristic_v1"


def test_risk_one_event_at_exact_threshold_25km():
    """Requirement B & Section 6E: Single event at exact threshold (25 km) yields proximity score 0.0."""
    ev = _make_event(25.0, relative_velocity_km_s=5.0)
    res = assess_candidate_risk(candidate="CAND_01", conjunction_events=[ev])

    assert res.proximity_score == 0.0
    assert res.event_count_score == 20.0
    # 0.8 * 0.0 + 0.2 * 20.0 = 4.0
    assert math.isclose(res.risk_score, 4.0, abs_tol=1e-9)
    assert res.accepted_event_count == 1
    assert res.minimum_miss_distance_km == 25.0
    assert res.minimum_relative_velocity_km_s == 5.0


def test_risk_one_event_at_midpoint_12_5km():
    """Requirement C: Single event at midpoint (12.5 km) yields proximity score 50.0."""
    ev = _make_event(12.5, relative_velocity_km_s=8.0)
    res = assess_candidate_risk(candidate="CAND_01", conjunction_events=[ev])

    assert res.proximity_score == 50.0
    assert res.event_count_score == 20.0
    # 0.8 * 50.0 + 0.2 * 20.0 = 44.0
    assert math.isclose(res.risk_score, 44.0, abs_tol=1e-9)


def test_risk_one_event_at_zero_distance():
    """Requirement D & Section 6F: Single event at 0 km yields proximity score 100.0."""
    ev = _make_event(0.0, relative_velocity_km_s=10.0)
    res = assess_candidate_risk(candidate="CAND_01", conjunction_events=[ev])

    assert res.proximity_score == 100.0
    assert res.event_count_score == 20.0
    # 0.8 * 100.0 + 0.2 * 20.0 = 84.0
    assert math.isclose(res.risk_score, 84.0, abs_tol=1e-9)


def test_risk_two_events_same_min_distance():
    """Requirement E: Two events (min 12.5 km) increases count score from 20 to 40."""
    ev1 = _make_event(12.5, relative_velocity_km_s=6.0, norad_id="99001")
    ev2 = _make_event(15.0, relative_velocity_km_s=9.0, norad_id="99002")
    res = assess_candidate_risk(candidate="CAND_01", conjunction_events=[ev1, ev2])

    assert res.proximity_score == 50.0
    assert res.event_count_score == 40.0
    # 0.8 * 50.0 + 0.2 * 40.0 = 48.0
    assert math.isclose(res.risk_score, 48.0, abs_tol=1e-9)
    assert res.accepted_event_count == 2
    assert res.minimum_miss_distance_km == 12.5
    assert res.minimum_relative_velocity_km_s == 6.0
    assert res.maximum_relative_velocity_km_s == 9.0


def test_risk_five_events_saturate_count_component():
    """Requirement H: 5 events saturates the count component at 100.0."""
    events = [_make_event(12.5, norad_id=f"9900{i}") for i in range(5)]
    res = assess_candidate_risk(candidate="CAND_01", conjunction_events=events)

    assert res.proximity_score == 50.0
    assert res.event_count_score == 100.0
    # 0.8 * 50.0 + 0.2 * 100.0 = 60.0
    assert math.isclose(res.risk_score, 60.0, abs_tol=1e-9)


def test_risk_ten_events_remain_bounded_at_count_saturation():
    """Requirement I: 10 events saturates at count score 100.0 without exceeding bounds."""
    events = [_make_event(12.5, norad_id=f"990{i:02d}") for i in range(10)]
    res = assess_candidate_risk(candidate="CAND_01", conjunction_events=events)

    assert res.event_count_score == 100.0
    assert math.isclose(res.risk_score, 60.0, abs_tol=1e-9)
    assert res.accepted_event_count == 10


def test_risk_zero_distance_and_saturated_events_gives_max_score_100():
    """Verify maximum possible score is 100.0 (miss=0 km, N >= 5)."""
    events = [_make_event(0.0, norad_id=f"9900{i}") for i in range(5)]
    res = assess_candidate_risk(candidate="CAND_01", conjunction_events=events)

    assert res.proximity_score == 100.0
    assert res.event_count_score == 100.0
    assert res.risk_score == 100.0


# =====================================================================
# Monotonicity Properties (Sections 6, 18)
# =====================================================================

def test_risk_monotonic_with_miss_distance_fixed_count():
    """Requirement G & Section 18: For fixed event count, smaller miss distance must NEVER decrease risk score."""
    distances = [0.0, 5.0, 10.0, 12.5, 15.0, 20.0, 25.0]
    scores = [
        assess_candidate_risk("C", [_make_event(d)]).risk_score
        for d in distances
    ]

    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], f"Monotonicity violated: risk({distances[i]}) < risk({distances[i+1]})"


def test_risk_monotonic_with_event_count_fixed_distance():
    """Requirement F & Section 18: For fixed miss distance, more accepted events must NEVER decrease risk score."""
    counts = [1, 2, 3, 4, 5, 6, 10]
    scores = [
        assess_candidate_risk("C", [_make_event(10.0, norad_id=str(i)) for i in range(n)]).risk_score
        for n in counts
    ]

    for i in range(len(scores) - 1):
        assert scores[i] <= scores[i + 1], f"Monotonicity violated: risk(N={counts[i]}) > risk(N={counts[i+1]})"


def test_risk_score_always_bounded_between_zero_and_100():
    """Requirement J & Section 6A: Score must strictly satisfy 0 <= score <= 100 across varied inputs."""
    test_cases = [
        (0.0, 1),
        (0.0, 10),
        (25.0, 1),
        (25.0, 20),
        (12.5, 3),
        (1.0, 100),
    ]
    for d, n in test_cases:
        events = [_make_event(d, norad_id=str(i)) for i in range(n)]
        res = assess_candidate_risk("C", events)
        assert 0.0 <= res.risk_score <= 100.0
        assert 0.0 <= res.proximity_score <= 100.0
        assert 0.0 <= res.event_count_score <= 100.0


# =====================================================================
# Breakdown & Consistency (Sections 7, 17Q, 17R)
# =====================================================================

def test_risk_breakdown_internal_consistency():
    """Requirement Q: Verify breakdown values satisfy 0.8 * proximity + 0.2 * count = risk."""
    ev = _make_event(5.0)
    res = assess_candidate_risk("CAND_01", [ev])

    expected_proximity = 100.0 * (1.0 - 5.0 / 25.0)  # 80.0
    expected_count = 20.0
    expected_risk = 0.8 * 80.0 + 0.2 * 20.0  # 64.0 + 4.0 = 68.0

    assert math.isclose(res.proximity_score, expected_proximity, abs_tol=1e-9)
    assert math.isclose(res.event_count_score, expected_count, abs_tol=1e-9)
    assert math.isclose(res.risk_score, expected_risk, abs_tol=1e-9)

    d = res.to_dict()
    assert d["risk_score"] == res.risk_score
    assert d["proximity_score"] == res.proximity_score
    assert d["event_count_score"] == res.event_count_score


def test_risk_relative_velocity_reported_not_scaled_into_risk():
    """Requirement R & Section 4: Relative velocity is reported (min/max) but not artificially scaled into risk score."""
    # Fast encounter (14.0 km/s) vs slow encounter (2.0 km/s) at identical miss distance
    ev_fast = _make_event(12.5, relative_velocity_km_s=14.0)
    ev_slow = _make_event(12.5, relative_velocity_km_s=2.0)

    res_fast = assess_candidate_risk("CAND_FAST", [ev_fast])
    res_slow = assess_candidate_risk("CAND_SLOW", [ev_slow])

    # Scores must be identical under fallback model
    assert res_fast.risk_score == res_slow.risk_score == 44.0
    # But physical velocities are correctly reported
    assert res_fast.minimum_relative_velocity_km_s == 14.0
    assert res_slow.minimum_relative_velocity_km_s == 2.0


def test_risk_deterministic_repeated_calculation():
    """Requirement K: Same inputs must yield exactly the same risk score and breakdown."""
    events = [_make_event(10.0, norad_id="1"), _make_event(15.0, norad_id="2")]
    res1 = assess_candidate_risk("CAND_01", events, data_age_seconds=3600.0)
    res2 = assess_candidate_risk("CAND_01", events, data_age_seconds=3600.0)

    assert res1 == res2
    assert res1.risk_score == res2.risk_score


# =====================================================================
# Error Handling & Validation (Sections 10, 12, 17)
# =====================================================================

def test_risk_rejects_negative_miss_distance():
    """Requirement L: Negative miss distance raises RiskScoringError."""
    ev = _make_event(-1.0)
    with pytest.raises(RiskScoringError, match="cannot be negative"):
        assess_candidate_risk("CAND_01", [ev])


def test_risk_rejects_miss_distance_over_threshold():
    """Requirement L & Section 10: Event exceeding 25 km raises RiskScoringError."""
    ev = _make_event(25.1)
    with pytest.raises(RiskScoringError, match="violates P8 acceptance threshold"):
        assess_candidate_risk("CAND_01", [ev])


def test_risk_rejects_nan_and_infinity():
    """Requirement N: NaN or Inf in miss distance or velocity raises RiskScoringError."""
    with pytest.raises(RiskScoringError, match="must be finite"):
        assess_candidate_risk("CAND_01", [_make_event(float("nan"))])

    with pytest.raises(RiskScoringError, match="must be finite"):
        assess_candidate_risk("CAND_01", [_make_event(float("inf"))])

    with pytest.raises(RiskScoringError, match="must be finite"):
        assess_candidate_risk("CAND_01", [_make_event(10.0, relative_velocity_km_s=float("nan"))])


def test_risk_rejects_negative_velocity():
    """Requirement M: Negative velocity raises RiskScoringError."""
    ev = _make_event(10.0, relative_velocity_km_s=-2.5)
    with pytest.raises(RiskScoringError, match="cannot be negative"):
        assess_candidate_risk("CAND_01", [ev])


def test_risk_rejects_invalid_weights():
    """Requirement O: Negative weights or sum != 1.0 raises RiskScoringError."""
    ev = _make_event(10.0)
    with pytest.raises(RiskScoringError, match="must sum to 1.0"):
        assess_candidate_risk("CAND_01", [ev], proximity_weight=0.7, count_weight=0.2)

    with pytest.raises(RiskScoringError, match="must be non-negative"):
        assess_candidate_risk("CAND_01", [ev], proximity_weight=-0.1, count_weight=1.1)


def test_risk_rejects_invalid_saturation_count():
    """Requirement P: Saturation count <= 0 raises RiskScoringError."""
    ev = _make_event(10.0)
    with pytest.raises(RiskScoringError, match="must be > 0"):
        assess_candidate_risk("CAND_01", [ev], saturation_count=0)


def test_risk_rejects_negative_data_age():
    """Verify negative data age raises RiskScoringError."""
    ev = _make_event(10.0)
    with pytest.raises(RiskScoringError, match="cannot be negative"):
        assess_candidate_risk("CAND_01", [ev], data_age_seconds=-100.0)


# =====================================================================
# Data Age & Uncertainty (Sections 5, 22)
# =====================================================================

def test_risk_uncertainty_levels():
    """Verify uncertainty level classification: nominal, elevated, unknown."""
    # Unknown when data_age_seconds is None
    level_none, notes_none = determine_uncertainty_level(None)
    assert level_none == "unknown"
    assert "unknown" in notes_none

    # Nominal when data age <= 3 days (259200s)
    level_nom, notes_nom = determine_uncertainty_level(3600.0)
    assert level_nom == "nominal"
    assert "within nominal freshness" in notes_nom

    # Elevated when data age > 3 days
    level_elev, notes_elev = determine_uncertainty_level(400000.0)
    assert level_elev == "elevated"
    assert "exceeds freshness threshold" in notes_elev


# =====================================================================
# Edge Cases & Aliases (Section 19)
# =====================================================================

def test_risk_edge_cases_micro_distance():
    """Section 19: Extremely close distance (1e-9 km) handled cleanly without NaN."""
    ev = _make_event(1e-9)
    res = assess_candidate_risk("CAND_01", [ev])
    assert math.isclose(res.proximity_score, 100.0, abs_tol=1e-5)
    assert math.isfinite(res.risk_score)


def test_risk_calculate_scalar_convenience():
    """Verify calculate_scalar_risk_score convenience helper."""
    ev = _make_event(12.5)
    scalar_score = calculate_scalar_risk_score("CAND_01", [ev])
    assert math.isclose(scalar_score, 44.0, abs_tol=1e-9)


def test_risk_accepts_dict_records():
    """Verify assess_candidate_risk accepts plain dictionaries as events."""
    dict_events = [
        {"miss_distance_km": 12.5, "relative_velocity_km_s": 5.0},
        {"miss_distance_km": 20.0, "relative_velocity_km_s": 7.0},
    ]
    res = assess_candidate_risk("CAND_DICT", dict_events)
    assert res.accepted_event_count == 2
    assert res.minimum_miss_distance_km == 12.5
    assert math.isclose(res.risk_score, 48.0, abs_tol=1e-9)
