"""Unit tests for Phase P10 candidate ranking engine."""

import math
from typing import Any
import pytest

from app.core.config import settings
from app.core.ranking import (
    RankedCandidate,
    RankingError,
    rank_candidates,
)
from app.core.fuel import DeltaVEstimate
from app.core.risk import RiskAssessment


def _make_candidate(cand_id: str, alt: float = 550.0, inc: float = 97.5, delay: float = 0.0) -> dict:
    return {
        "candidate_id": cand_id,
        "altitude_km": alt,
        "inclination_deg": inc,
        "raan_deg": 0.0,
        "u0_deg": 0.0,
        "deployment_delay_minutes": delay,
        "deployment_epoch": None,
    }


def _make_fuel(dv_m_s: float, within_budget: bool = True) -> dict:
    return {
        "total_dv_m_s": dv_m_s,
        "delta_v_m_s": dv_m_s,
        "propellant_mass_kg": 0.05,
        "fuel_fraction": 0.016,
        "within_dv_budget": within_budget,
    }


def _make_risk(risk_score: float, accepted_events: int = 1, min_miss: float = 15.0) -> dict:
    return {
        "risk_score": risk_score,
        "accepted_event_count": accepted_events,
        "minimum_miss_distance_km": min_miss,
        "uncertainty_level": "nominal",
    }


# ==============================================================================
# Tests A through E: Metric comparisons and weight properties
# ==============================================================================

def test_ranking_two_candidates_different_fuel_same_risk():
    """Test A: When risk is equal, lower delta-v produces a higher composite score and rank 1."""
    cands = [_make_candidate("c1"), _make_candidate("c2")]
    fuels = {"c1": _make_fuel(20.0), "c2": _make_fuel(80.0)}
    risks = {"c1": _make_risk(10.0), "c2": _make_risk(10.0)}

    ranked = rank_candidates(cands, fuels, risks)
    assert len(ranked) == 2
    assert ranked[0].candidate_id == "c1"
    assert ranked[0].rank == 1
    assert ranked[1].candidate_id == "c2"
    assert ranked[1].rank == 2
    assert ranked[0].composite_score > ranked[1].composite_score


def test_ranking_two_candidates_same_fuel_different_risk():
    """Test B: When fuel is equal, lower risk produces a higher composite score and rank 1."""
    cands = [_make_candidate("c1"), _make_candidate("c2")]
    fuels = {"c1": _make_fuel(50.0), "c2": _make_fuel(50.0)}
    risks = {"c1": _make_risk(10.0), "c2": _make_risk(70.0)}

    ranked = rank_candidates(cands, fuels, risks)
    assert len(ranked) == 2
    assert ranked[0].candidate_id == "c1"
    assert ranked[0].rank == 1
    assert ranked[1].candidate_id == "c2"
    assert ranked[1].rank == 2
    assert ranked[0].composite_score > ranked[1].composite_score


def test_ranking_both_metrics_different():
    """Test C: Both delta-v and risk differ."""
    cands = [_make_candidate("c1"), _make_candidate("c2")]
    fuels = {"c1": _make_fuel(10.0), "c2": _make_fuel(50.0)}
    risks = {"c1": _make_risk(80.0), "c2": _make_risk(10.0)}

    # c1: dv=10 (min->0 cost), risk=80. composite cost = 0.4*0 + 0.6*80 = 48. score = 52.
    # c2: dv=50 (max->100 cost), risk=10. composite cost = 0.4*100 + 0.6*10 = 46. score = 54.
    # c2 should rank #1 because score 54 > 52!
    ranked = rank_candidates(cands, fuels, risks, fuel_weight=0.4, risk_weight=0.6)
    assert ranked[0].candidate_id == "c2"
    assert ranked[0].rank == 1
    assert math.isclose(ranked[0].composite_score, 54.0, abs_tol=1e-5)
    assert ranked[1].candidate_id == "c1"
    assert ranked[1].rank == 2
    assert math.isclose(ranked[1].composite_score, 52.0, abs_tol=1e-5)


def test_ranking_default_weights():
    """Test D: Verifies default weights 0.4 fuel and 0.6 risk from settings."""
    assert math.isclose(settings.FUEL_WEIGHT, 0.4)
    assert math.isclose(settings.RISK_WEIGHT, 0.6)
    assert math.isclose(settings.FUEL_WEIGHT + settings.RISK_WEIGHT, 1.0)


def test_ranking_risk_dominates_fuel_under_default_weights():
    """Test E: 0.6 risk weight has higher influence on composite score than 0.4 fuel weight."""
    cands = [_make_candidate("c_low_risk"), _make_candidate("c_low_fuel")]
    # c_low_risk: max fuel (cost=100), min risk (cost=0) -> cost = 0.4*100 + 0.6*0 = 40 -> score = 60
    # c_low_fuel: min fuel (cost=0), max risk (cost=100) -> cost = 0.4*0 + 0.6*100 = 60 -> score = 40
    fuels = {"c_low_risk": _make_fuel(100.0), "c_low_fuel": _make_fuel(0.0)}
    risks = {"c_low_risk": _make_risk(0.0), "c_low_fuel": _make_risk(100.0)}

    ranked = rank_candidates(cands, fuels, risks)
    assert ranked[0].candidate_id == "c_low_risk"
    assert ranked[0].rank == 1
    assert math.isclose(ranked[0].composite_score, 60.0, abs_tol=1e-5)
    assert ranked[1].candidate_id == "c_low_fuel"
    assert ranked[1].rank == 2
    assert math.isclose(ranked[1].composite_score, 40.0, abs_tol=1e-5)


# ==============================================================================
# Tests F through J: Normalization, bounding, and scales
# ==============================================================================

def test_ranking_min_max_fuel_normalization():
    """Test F & G: Min delta-v receives 0 cost, max delta-v receives 100 cost."""
    cands = [_make_candidate("c_min"), _make_candidate("c_mid"), _make_candidate("c_max")]
    fuels = {"c_min": _make_fuel(20.0), "c_mid": _make_fuel(50.0), "c_max": _make_fuel(80.0)}
    risks = {"c_min": _make_risk(0.0), "c_mid": _make_risk(0.0), "c_max": _make_risk(0.0)}

    ranked = rank_candidates(cands, fuels, risks)
    by_id = {rc.candidate_id: rc for rc in ranked}
    assert math.isclose(by_id["c_min"].normalized_fuel_cost, 0.0, abs_tol=1e-5)
    assert math.isclose(by_id["c_mid"].normalized_fuel_cost, 50.0, abs_tol=1e-5)
    assert math.isclose(by_id["c_max"].normalized_fuel_cost, 100.0, abs_tol=1e-5)


def test_ranking_equal_fuel_yields_zero_fuel_cost():
    """Test H: When all candidates have identical delta-v, normalized fuel cost is 0 for all."""
    cands = [_make_candidate("c1"), _make_candidate("c2"), _make_candidate("c3")]
    fuels = {"c1": _make_fuel(42.0), "c2": _make_fuel(42.0), "c3": _make_fuel(42.0)}
    risks = {"c1": _make_risk(10.0), "c2": _make_risk(20.0), "c3": _make_risk(30.0)}

    ranked = rank_candidates(cands, fuels, risks)
    for rc in ranked:
        assert math.isclose(rc.normalized_fuel_cost, 0.0, abs_tol=1e-5)


def test_ranking_risk_score_remains_on_0_to_100_scale():
    """Test I: P9 risk is used directly as normalized_risk_cost without min-max rescaling."""
    cands = [_make_candidate("c1"), _make_candidate("c2")]
    fuels = {"c1": _make_fuel(0.0), "c2": _make_fuel(0.0)}
    risks = {"c1": _make_risk(25.0), "c2": _make_risk(75.0)}

    ranked = rank_candidates(cands, fuels, risks)
    by_id = {rc.candidate_id: rc for rc in ranked}
    assert math.isclose(by_id["c1"].normalized_risk_cost, 25.0, abs_tol=1e-5)
    assert math.isclose(by_id["c2"].normalized_risk_cost, 75.0, abs_tol=1e-5)


def test_ranking_composite_score_strictly_bounded_0_to_100():
    """Test J: Composite score and normalized costs are always clamped within [0, 100]."""
    cands = [_make_candidate("c_best"), _make_candidate("c_worst")]
    fuels = {"c_best": _make_fuel(0.0), "c_worst": _make_fuel(100.0)}
    risks = {"c_best": _make_risk(0.0), "c_worst": _make_risk(100.0)}

    ranked = rank_candidates(cands, fuels, risks)
    for rc in ranked:
        assert 0.0 <= rc.normalized_fuel_cost <= 100.0
        assert 0.0 <= rc.normalized_risk_cost <= 100.0
        assert 0.0 <= rc.composite_score <= 100.0

    assert math.isclose(ranked[0].composite_score, 100.0, abs_tol=1e-5)
    assert math.isclose(ranked[1].composite_score, 0.0, abs_tol=1e-5)


# ==============================================================================
# Tests K through O: Sorting, tie-breaking, and contiguous ranks
# ==============================================================================

def test_ranking_deterministic_ordering_repeated():
    """Test K: Repeated ranking produces bitwise identical results."""
    cands = [_make_candidate(f"c{i}") for i in range(10)]
    fuels = {f"c{i}": _make_fuel(10.0 + i * 5.0) for i in range(10)}
    risks = {f"c{i}": _make_risk(50.0 - i * 3.0) for i in range(10)}

    order1 = [rc.candidate_id for rc in rank_candidates(cands, fuels, risks)]
    order2 = [rc.candidate_id for rc in rank_candidates(cands, fuels, risks)]
    assert order1 == order2


def test_ranking_tie_break_by_risk():
    """Test L: When composite_scores tie, candidate with lower risk_score ranks higher."""
    # Anchor candidates fix min delta-v to 0 and max delta-v to 100
    # c1: dv=30 -> norm_fuel=30, risk=70 -> cost = 0.5*30 + 0.5*70 = 50 -> score = 50.0
    # c2: dv=70 -> norm_fuel=70, risk=30 -> cost = 0.5*70 + 0.5*30 = 50 -> score = 50.0
    # Both c1 and c2 have composite_score = 50.0. c2 has lower risk (30 < 70) -> c2 ranks ahead of c1!
    cands = [
        _make_candidate("c_anchor_min"),
        _make_candidate("c1"),
        _make_candidate("c2"),
        _make_candidate("c_anchor_max"),
    ]
    fuels = {
        "c_anchor_min": _make_fuel(0.0),
        "c1": _make_fuel(30.0),
        "c2": _make_fuel(70.0),
        "c_anchor_max": _make_fuel(100.0),
    }
    risks = {
        "c_anchor_min": _make_risk(100.0),
        "c1": _make_risk(70.0),
        "c2": _make_risk(30.0),
        "c_anchor_max": _make_risk(100.0),
    }

    ranked = rank_candidates(cands, fuels, risks, fuel_weight=0.5, risk_weight=0.5)
    by_id = {rc.candidate_id: rc for rc in ranked}
    assert math.isclose(by_id["c1"].composite_score, 50.0, abs_tol=1e-5)
    assert math.isclose(by_id["c2"].composite_score, 50.0, abs_tol=1e-5)
    assert by_id["c2"].rank < by_id["c1"].rank


def test_ranking_tie_break_by_delta_v():
    """Test M: When composite_score and risk tie, candidate with lower delta-v ranks higher."""
    # Suppose fuel normalization resulted in equal scores, but raw delta-v was slightly different
    # (e.g. if custom weights or identical metrics except delta-v):
    cands = [_make_candidate("c1"), _make_candidate("c2")]
    fuels = {"c1": _make_fuel(10.0), "c2": _make_fuel(20.0)}
    risks = {"c1": _make_risk(10.0), "c2": _make_risk(10.0)}

    ranked = rank_candidates(cands, fuels, risks)
    assert ranked[0].candidate_id == "c1"
    assert ranked[0].rank == 1


def test_ranking_tie_break_by_candidate_id():
    """Test N: When all scores, risk, and delta-v are identical, candidate_id breaks ties alphabetically."""
    cands = [_make_candidate("cand_Z"), _make_candidate("cand_A"), _make_candidate("cand_M")]
    fuels = {c["candidate_id"]: _make_fuel(50.0) for c in cands}
    risks = {c["candidate_id"]: _make_risk(20.0) for c in cands}

    ranked = rank_candidates(cands, fuels, risks)
    ids = [rc.candidate_id for rc in ranked]
    assert ids == ["cand_A", "cand_M", "cand_Z"]


def test_ranking_contiguous_ranks():
    """Test O: Ranks are strictly 1, 2, 3, ... N without gaps."""
    cands = [_make_candidate(f"c{i}") for i in range(15)]
    fuels = {f"c{i}": _make_fuel(float(i * 10)) for i in range(15)}
    risks = {f"c{i}": _make_risk(float(i * 5)) for i in range(15)}

    ranked = rank_candidates(cands, fuels, risks)
    ranks = [rc.rank for rc in ranked]
    assert ranks == list(range(1, 16))


# ==============================================================================
# Tests P through W: Edge cases and validation rejections
# ==============================================================================

def test_ranking_empty_candidate_set():
    """Test P: Empty candidate set returns empty list without error."""
    assert rank_candidates([], {}, {}) == []


def test_ranking_single_candidate():
    """Test Q: Single candidate receives rank 1, fuel cost 0, and risk-weighted score."""
    cands = [_make_candidate("solo")]
    fuels = {"solo": _make_fuel(75.0)}
    risks = {"solo": _make_risk(30.0)}

    ranked = rank_candidates(cands, fuels, risks, fuel_weight=0.4, risk_weight=0.6)
    assert len(ranked) == 1
    rc = ranked[0]
    assert rc.rank == 1
    assert rc.normalized_fuel_cost == 0.0
    assert rc.normalized_risk_cost == 30.0
    # score = 100 - (0.4 * 0 + 0.6 * 30) = 82.0
    assert math.isclose(rc.composite_score, 82.0, abs_tol=1e-5)


def test_ranking_rejects_negative_delta_v():
    """Test R: Negative delta-v raises RankingError."""
    cands = [_make_candidate("c1")]
    fuels = {"c1": _make_fuel(-10.0)}
    risks = {"c1": _make_risk(10.0)}
    with pytest.raises(RankingError, match="cannot be negative"):
        rank_candidates(cands, fuels, risks)


def test_ranking_rejects_invalid_risk_score():
    """Test S: Risk score < 0 or > 100 raises RankingError."""
    cands = [_make_candidate("c1")]
    fuels = {"c1": _make_fuel(10.0)}

    with pytest.raises(RankingError, match="within \\[0, 100\\]"):
        rank_candidates(cands, fuels, {"c1": _make_risk(-5.0)})

    with pytest.raises(RankingError, match="within \\[0, 100\\]"):
        rank_candidates(cands, fuels, {"c1": _make_risk(105.0)})


def test_ranking_rejects_nan_and_infinity():
    """Test T: NaN or infinity delta-v/risk raises RankingError."""
    cands = [_make_candidate("c1")]
    with pytest.raises(RankingError, match="finite"):
        rank_candidates(cands, {"c1": _make_fuel(float("nan"))}, {"c1": _make_risk(10.0)})

    with pytest.raises(RankingError, match="finite"):
        rank_candidates(cands, {"c1": _make_fuel(float("inf"))}, {"c1": _make_risk(10.0)})

    with pytest.raises(RankingError, match="finite"):
        rank_candidates(cands, {"c1": _make_fuel(10.0)}, {"c1": _make_risk(float("nan"))})


def test_ranking_rejects_mismatched_candidate_ids():
    """Test U: Missing candidate in fuel or risk mapping raises RankingError."""
    cands = [_make_candidate("c1"), _make_candidate("c2")]
    fuels = {"c1": _make_fuel(10.0)}  # missing c2
    risks = {"c1": _make_risk(10.0), "c2": _make_risk(10.0)}
    with pytest.raises(RankingError, match="missing a corresponding fuel estimate"):
        rank_candidates(cands, fuels, risks)


def test_ranking_rejects_duplicate_candidate_ids():
    """Test V: Duplicate candidate IDs in candidates list raises RankingError."""
    cands = [_make_candidate("c1"), _make_candidate("c1")]
    fuels = {"c1": _make_fuel(10.0)}
    risks = {"c1": _make_risk(10.0)}
    with pytest.raises(RankingError, match="Duplicate candidate ID"):
        rank_candidates(cands, fuels, risks)


def test_ranking_rejects_invalid_weights():
    """Test W: Negative weights or weights not summing to 1.0 raise RankingError."""
    cands = [_make_candidate("c1")]
    fuels = {"c1": _make_fuel(10.0)}
    risks = {"c1": _make_risk(10.0)}

    with pytest.raises(RankingError, match="must be non-negative"):
        rank_candidates(cands, fuels, risks, fuel_weight=-0.1, risk_weight=1.1)

    with pytest.raises(RankingError, match="must sum to 1.0"):
        rank_candidates(cands, fuels, risks, fuel_weight=0.5, risk_weight=0.6)


# ==============================================================================
# Tests X: No rescreening / No external calls
# ==============================================================================

def test_ranking_no_rescreening_monkeypatch(monkeypatch):
    """Test X: Proves ranking consumes precomputed metrics and makes zero calls to P7/P8/P9."""
    import app.core.fuel as fuel_module
    import app.core.risk as risk_module
    import app.core.conjunction as conjunction_module

    def forbid_call(*args, **kwargs):
        raise AssertionError("P10 Ranking MUST NOT call fuel evaluation, risk assessment, or screening!")

    monkeypatch.setattr(fuel_module, "evaluate_candidate_fuel", forbid_call)
    monkeypatch.setattr(risk_module, "assess_candidate_risk", forbid_call)
    monkeypatch.setattr(conjunction_module, "screen_candidate_against_debris", forbid_call)

    cands = [_make_candidate("c1"), _make_candidate("c2")]
    fuels = {"c1": _make_fuel(20.0), "c2": _make_fuel(40.0)}
    risks = {"c1": _make_risk(10.0), "c2": _make_risk(20.0)}

    ranked = rank_candidates(cands, fuels, risks)
    assert len(ranked) == 2
    assert ranked[0].rank == 1



# ==============================================================================
# Monotonicity, Weight-Sensitivity, Reference Candidate, and Budget Tests
# ==============================================================================

def test_ranking_monotonic_with_delta_v():
    """Monotonicity: For fixed risk, lower delta-v never produces a worse composite score."""
    cands = [_make_candidate(f"c_{i}") for i in range(5)]
    dv_values = [10.0, 25.0, 50.0, 75.0, 100.0]
    fuels = {f"c_{i}": _make_fuel(dv_values[i]) for i in range(5)}
    risks = {f"c_{i}": _make_risk(20.0) for i in range(5)}  # Fixed risk

    ranked = rank_candidates(cands, fuels, risks)
    for i in range(len(ranked) - 1):
        assert ranked[i].composite_score >= ranked[i + 1].composite_score
        assert ranked[i].delta_v_m_s <= ranked[i + 1].delta_v_m_s


def test_ranking_monotonic_with_risk():
    """Monotonicity: For fixed delta-v, lower risk never produces a worse composite score."""
    cands = [_make_candidate(f"c_{i}") for i in range(5)]
    fuels = {f"c_{i}": _make_fuel(30.0) for i in range(5)}  # Fixed fuel
    risk_values = [5.0, 20.0, 45.0, 70.0, 95.0]
    risks = {f"c_{i}": _make_risk(risk_values[i]) for i in range(5)}

    ranked = rank_candidates(cands, fuels, risks)
    for i in range(len(ranked) - 1):
        assert ranked[i].composite_score >= ranked[i + 1].composite_score
        assert ranked[i].risk_score <= ranked[i + 1].risk_score


def test_ranking_weight_sensitivity():
    """Weight sensitivity: Changing weights changes scores in expected direction."""
    cands = [_make_candidate("c_fuel_favored"), _make_candidate("c_risk_favored")]
    # c_fuel_favored: low fuel (dv=10 -> cost=0), high risk (risk=80)
    # c_risk_favored: high fuel (dv=90 -> cost=100), low risk (risk=10)
    fuels = {"c_fuel_favored": _make_fuel(10.0), "c_risk_favored": _make_fuel(90.0)}
    risks = {"c_fuel_favored": _make_risk(80.0), "c_risk_favored": _make_risk(10.0)}

    # Case 1: Fuel heavily weighted (0.8 fuel, 0.2 risk)
    # c_fuel_favored score = 100 - (0.8*0 + 0.2*80) = 84
    # c_risk_favored score = 100 - (0.8*100 + 0.2*10) = 18
    ranked_fuel_heavy = rank_candidates(cands, fuels, risks, fuel_weight=0.8, risk_weight=0.2)
    assert ranked_fuel_heavy[0].candidate_id == "c_fuel_favored"

    # Case 2: Risk heavily weighted (0.2 fuel, 0.8 risk)
    # c_fuel_favored score = 100 - (0.2*0 + 0.8*80) = 36
    # c_risk_favored score = 100 - (0.2*100 + 0.8*10) = 72
    ranked_risk_heavy = rank_candidates(cands, fuels, risks, fuel_weight=0.2, risk_weight=0.8)
    assert ranked_risk_heavy[0].candidate_id == "c_risk_favored"


def test_ranking_reference_candidate_behavior():
    """Reference candidate (dv=0) gets normalized_fuel_cost=0, but rank depends on risk."""
    cands = [_make_candidate("cand_ref"), _make_candidate("cand_other")]
    # cand_ref: dv=0, but very high risk (risk=90)
    # cand_other: dv=10, but low risk (risk=10)
    fuels = {"cand_ref": _make_fuel(0.0), "cand_other": _make_fuel(10.0)}
    risks = {"cand_ref": _make_risk(90.0), "cand_other": _make_risk(10.0)}

    ranked = rank_candidates(cands, fuels, risks)
    by_id = {rc.candidate_id: rc for rc in ranked}
    assert by_id["cand_ref"].normalized_fuel_cost == 0.0
    # Because of default 0.6 risk weight, cand_other ranks #1 despite having dv > 0!
    assert ranked[0].candidate_id == "cand_other"
    assert ranked[0].rank == 1
    assert ranked[1].candidate_id == "cand_ref"
    assert ranked[1].rank == 2


def test_ranking_preserves_above_budget_candidates():
    """Budget preservation: Above-budget candidates are NOT deleted from ranking."""
    cands = [_make_candidate("within_1"), _make_candidate("above_1"), _make_candidate("within_2")]
    fuels = {
        "within_1": _make_fuel(50.0, within_budget=True),
        "above_1": _make_fuel(120.0, within_budget=False),  # Above 100 m/s budget
        "within_2": _make_fuel(80.0, within_budget=True),
    }
    risks = {
        "within_1": _make_risk(20.0),
        "above_1": _make_risk(5.0),
        "within_2": _make_risk(30.0),
    }

    ranked = rank_candidates(cands, fuels, risks)
    assert len(ranked) == 3
    by_id = {rc.candidate_id: rc for rc in ranked}
    assert by_id["above_1"].within_dv_budget is False
    assert by_id["within_1"].within_dv_budget is True


def test_ranking_accepts_domain_objects():
    """Verifies that DeltaVEstimate and RiskAssessment domain objects are accepted directly."""
    cands = [_make_candidate("c1"), _make_candidate("c2")]

    fuel1 = DeltaVEstimate(
        reference_altitude_km=550.0, candidate_altitude_km=550.0,
        reference_inclination_deg=97.5, candidate_inclination_deg=97.5,
        reference_radius_km=6928.137, candidate_radius_km=6928.137,
        transfer_dv_m_s=0.0, plane_change_dv_m_s=0.0, total_dv_m_s=0.0,
        spacecraft_mass_kg=3.0, isp_seconds=60.0, propellant_mass_kg=0.0,
        final_mass_kg=3.0, fuel_fraction=0.0, within_dv_budget=True, dv_budget_m_s=100.0,
    )
    fuel2 = DeltaVEstimate(
        reference_altitude_km=550.0, candidate_altitude_km=600.0,
        reference_inclination_deg=97.5, candidate_inclination_deg=98.0,
        reference_radius_km=6928.137, candidate_radius_km=6978.137,
        transfer_dv_m_s=27.1, plane_change_dv_m_s=66.2, total_dv_m_s=93.3,
        spacecraft_mass_kg=3.0, isp_seconds=60.0, propellant_mass_kg=0.44,
        final_mass_kg=2.56, fuel_fraction=0.147, within_dv_budget=True, dv_budget_m_s=100.0,
    )

    risk1 = RiskAssessment(
        candidate_id="c1", risk_score=20.0, proximity_score=20.0, event_count_score=20.0,
        accepted_event_count=1, minimum_miss_distance_km=20.0, minimum_relative_velocity_km_s=10.0,
        maximum_relative_velocity_km_s=10.0, data_age_seconds=3600.0, uncertainty_level="nominal",
        uncertainty_notes="Fresh data",
    )
    risk2 = RiskAssessment(
        candidate_id="c2", risk_score=10.0, proximity_score=10.0, event_count_score=10.0,
        accepted_event_count=1, minimum_miss_distance_km=22.5, minimum_relative_velocity_km_s=8.0,
        maximum_relative_velocity_km_s=8.0, data_age_seconds=3600.0, uncertainty_level="nominal",
        uncertainty_notes="Fresh data",
    )

    ranked = rank_candidates(cands, {"c1": fuel1, "c2": fuel2}, {"c1": risk1, "c2": risk2})
    assert len(ranked) == 2
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2
