"""Screening risk score modeling for D-DATO candidate deployment orbits.

Phase P9: Physical Close-Approach Risk Screening.

IMPORTANT POSITIONING:
- D-DATO risk is a bounded [0, 100] early-stage screening index.
- It is NOT probability of collision (Pc).
- It is NOT probability of impact.
- It is NOT an operational flight-safety determination.
- The score is transparent and explainable through a component breakdown.

AUTHORITATIVE SPECIFICATION NOTE:
As verified by inspecting SPEC.md and codebase records, the original D-DATO
specification specifies multi-attribute evaluation but defines no exact mathematical formula.
Therefore, the transparent fallback screening heuristic specified in Phase P9 is implemented.
"""

from dataclasses import dataclass, asdict
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.config import settings


class RiskScoringError(ValueError):
    """Raised when risk scoring inputs violate domain contracts or mathematical bounds."""
    pass


@dataclass(frozen=True)
class RiskAssessment:
    """Immutable domain representation of an explainable candidate risk screening score."""
    candidate_id: str
    risk_score: float
    proximity_score: float
    event_count_score: float
    accepted_event_count: int
    minimum_miss_distance_km: Optional[float]
    minimum_relative_velocity_km_s: Optional[float]
    maximum_relative_velocity_km_s: Optional[float]
    data_age_seconds: Optional[float]
    uncertainty_level: str  # "nominal", "elevated", "unknown"
    uncertainty_notes: str
    scoring_method: str = "fallback_heuristic_v1"

    def to_dict(self) -> Dict[str, Any]:
        """Convert assessment to dictionary representation."""
        return asdict(self)


def calculate_proximity_score(
    min_miss_distance_km: float,
    event_threshold_km: float = settings.SCREENING_EVENT_THRESHOLD_KM,
) -> float:
    """Calculate proximity component score [0, 100] from minimum miss distance.

    Formula:
        proximity_score = clamp(100.0 * (1.0 - d_min / D_EVENT), 0.0, 100.0)

    Properties:
        d_min = 25.0 km -> 0.0
        d_min = 12.5 km -> 50.0
        d_min = 0.0 km  -> 100.0
        Smaller miss distance strictly never decreases proximity score.
    """
    if not math.isfinite(min_miss_distance_km):
        raise RiskScoringError(f"Minimum miss distance must be finite (got {min_miss_distance_km}).")
    if min_miss_distance_km < 0.0:
        raise RiskScoringError(f"Minimum miss distance cannot be negative (got {min_miss_distance_km}).")
    if event_threshold_km <= 0.0:
        raise RiskScoringError(f"Event threshold must be positive (got {event_threshold_km}).")
    if min_miss_distance_km > event_threshold_km:
        raise RiskScoringError(
            f"Miss distance ({min_miss_distance_km:.4f} km) exceeds event acceptance threshold "
            f"({event_threshold_km:.4f} km)."
        )

    score = 100.0 * (1.0 - (min_miss_distance_km / event_threshold_km))
    return float(max(0.0, min(100.0, score)))


def calculate_event_count_score(
    event_count: int,
    saturation_count: int = settings.RISK_EVENT_SATURATION_COUNT,
) -> float:
    """Calculate encounter-count component score [0, 100].

    Formula:
        count_score = min(100.0 * N / RISK_EVENT_SATURATION_COUNT, 100.0)

    Properties:
        N = 1  -> 20.0
        N = 2  -> 40.0
        N = 3  -> 60.0
        N = 4  -> 80.0
        N >= 5 -> 100.0
        More accepted events strictly never decrease count score.
    """
    if event_count < 0:
        raise RiskScoringError(f"Event count cannot be negative (got {event_count}).")
    if saturation_count <= 0:
        raise RiskScoringError(f"Event saturation count must be > 0 (got {saturation_count}).")

    score = min(100.0 * float(event_count) / float(saturation_count), 100.0)
    return float(max(0.0, score))


def determine_uncertainty_level(
    data_age_seconds: Optional[float],
    elevated_threshold_seconds: Optional[float] = None,
) -> Tuple[str, str]:
    """Determine categorical data freshness and ephemeris uncertainty level.

    Levels:
        - "nominal": Catalog data age <= elevated threshold.
        - "elevated": Catalog data age > elevated threshold.
        - "unknown": Catalog data age unavailable.
    """
    thresh = (
        float(elevated_threshold_seconds)
        if elevated_threshold_seconds is not None
        else settings.RISK_DATA_AGE_ELEVATED_SECONDS
    )

    if data_age_seconds is None:
        return "unknown", "Catalog data age is unknown; ephemeris uncertainty is unquantified."

    if not math.isfinite(data_age_seconds):
        raise RiskScoringError(f"data_age_seconds must be finite (got {data_age_seconds}).")
    if data_age_seconds < 0.0:
        raise RiskScoringError(f"data_age_seconds cannot be negative (got {data_age_seconds}).")

    hours = data_age_seconds / 3600.0
    thresh_hours = thresh / 3600.0

    if data_age_seconds > thresh:
        return (
            "elevated",
            f"Catalog data age ({hours:.1f}h) exceeds freshness threshold ({thresh_hours:.1f}h); "
            "ephemeris uncertainty is elevated due to atmospheric drag perturbations.",
        )
    return (
        "nominal",
        f"Catalog data age ({hours:.1f}h) is within nominal freshness threshold ({thresh_hours:.1f}h).",
    )


def assess_candidate_risk(
    candidate: Any,
    conjunction_events: Optional[List[Any]] = None,
    data_age_seconds: Optional[float] = None,
    proximity_weight: Optional[float] = None,
    count_weight: Optional[float] = None,
    saturation_count: Optional[int] = None,
    event_threshold_km: Optional[float] = None,
    elevated_threshold_seconds: Optional[float] = None,
) -> RiskAssessment:
    """Assess and score collision risk for a candidate deployment orbit.

    Computes a transparent, bounded [0, 100] screening score combining:
    1. Proximity component (80% default): closer miss distance increases score.
    2. Encounter-count component (20% default): more accepted encounters increase score.

    Args:
        candidate: CandidateOrbit domain model, Candidate ORM model, or string ID.
        conjunction_events: List of accepted P8 ConjunctionEventResult or ConjunctionEvent records.
        data_age_seconds: Elapsed seconds since debris catalog epoch.
        proximity_weight: Weight for proximity component (default 0.8).
        count_weight: Weight for count component (default 0.2).
        saturation_count: Event count at which count component saturates at 100 (default 5).
        event_threshold_km: Conjunction event acceptance threshold (default 25.0 km).
        elevated_threshold_seconds: Threshold for elevated uncertainty (default 3 days).

    Returns:
        RiskAssessment containing risk_score [0, 100], component breakdown, and uncertainty metadata.
    """
    candidate_id = str(getattr(candidate, "candidate_id", None) or getattr(candidate, "id", None) or candidate)

    # 1. Parameter resolution & validation
    w_prox = float(proximity_weight if proximity_weight is not None else settings.RISK_PROXIMITY_WEIGHT)
    w_cnt = float(count_weight if count_weight is not None else settings.RISK_EVENT_COUNT_WEIGHT)
    sat_cnt = int(saturation_count if saturation_count is not None else settings.RISK_EVENT_SATURATION_COUNT)
    d_event = float(event_threshold_km if event_threshold_km is not None else settings.SCREENING_EVENT_THRESHOLD_KM)

    if w_prox < 0.0 or w_cnt < 0.0:
        raise RiskScoringError(f"Risk weights must be non-negative (got proximity={w_prox}, count={w_cnt}).")
    if not math.isclose(w_prox + w_cnt, 1.0, abs_tol=1e-6):
        raise RiskScoringError(f"Risk weights must sum to 1.0 (got {w_prox} + {w_cnt} = {w_prox + w_cnt}).")
    if sat_cnt <= 0:
        raise RiskScoringError(f"Event saturation count must be > 0 (got {sat_cnt}).")
    if d_event <= 0.0:
        raise RiskScoringError(f"Event threshold must be positive (got {d_event}).")

    unc_level, unc_notes = determine_uncertainty_level(data_age_seconds, elevated_threshold_seconds)

    events = conjunction_events or []

    # 2. Case: No accepted conjunction events
    if len(events) == 0:
        return RiskAssessment(
            candidate_id=candidate_id,
            risk_score=0.0,
            proximity_score=0.0,
            event_count_score=0.0,
            accepted_event_count=0,
            minimum_miss_distance_km=None,
            minimum_relative_velocity_km_s=None,
            maximum_relative_velocity_km_s=None,
            data_age_seconds=data_age_seconds,
            uncertainty_level=unc_level,
            uncertainty_notes=unc_notes,
            scoring_method="fallback_heuristic_v1",
        )

    # 3. Case: One or more accepted conjunction events
    miss_distances: List[float] = []
    velocities: List[float] = []

    for ev in events:
        # Extract miss distance
        if hasattr(ev, "miss_distance_km"):
            raw_d = getattr(ev, "miss_distance_km")
        elif isinstance(ev, dict) and "miss_distance_km" in ev:
            raw_d = ev["miss_distance_km"]
        else:
            raise RiskScoringError(f"Conjunction event missing miss_distance_km: {ev}")

        if raw_d is None or not math.isfinite(raw_d):
            raise RiskScoringError(f"Event miss distance must be finite (got {raw_d}).")
        d_val = float(raw_d)
        if d_val < 0.0:
            raise RiskScoringError(f"Event miss distance cannot be negative (got {d_val}).")
        if d_val > d_event:
            raise RiskScoringError(
                f"Conjunction event miss distance ({d_val:.4f} km) violates P8 acceptance "
                f"threshold ({d_event:.4f} km)."
            )
        miss_distances.append(d_val)

        # Extract relative velocity
        raw_v = None
        if hasattr(ev, "relative_velocity_km_s"):
            raw_v = getattr(ev, "relative_velocity_km_s")
        elif isinstance(ev, dict) and "relative_velocity_km_s" in ev:
            raw_v = ev.get("relative_velocity_km_s")

        if raw_v is not None:
            if not math.isfinite(raw_v):
                raise RiskScoringError(f"Event relative velocity must be finite (got {raw_v}).")
            v_val = float(raw_v)
            if v_val < 0.0:
                raise RiskScoringError(f"Event relative velocity cannot be negative (got {v_val}).")
            velocities.append(v_val)

    d_min = min(miss_distances)
    v_min = min(velocities) if velocities else None
    v_max = max(velocities) if velocities else None
    n_events = len(events)

    proximity_score = calculate_proximity_score(d_min, d_event)
    count_score = calculate_event_count_score(n_events, sat_cnt)

    raw_score = w_prox * proximity_score + w_cnt * count_score
    risk_score = float(max(0.0, min(100.0, raw_score)))

    return RiskAssessment(
        candidate_id=candidate_id,
        risk_score=risk_score,
        proximity_score=proximity_score,
        event_count_score=count_score,
        accepted_event_count=n_events,
        minimum_miss_distance_km=d_min,
        minimum_relative_velocity_km_s=v_min,
        maximum_relative_velocity_km_s=v_max,
        data_age_seconds=data_age_seconds,
        uncertainty_level=unc_level,
        uncertainty_notes=unc_notes,
        scoring_method="fallback_heuristic_v1",
    )


def calculate_risk_score(
    candidate: Any,
    conjunction_events: Optional[List[Any]] = None,
    data_age_seconds: Optional[float] = None,
    proximity_weight: Optional[float] = None,
    count_weight: Optional[float] = None,
    saturation_count: Optional[int] = None,
    event_threshold_km: Optional[float] = None,
) -> RiskAssessment:
    """Alias for assess_candidate_risk, returning full RiskAssessment domain result."""
    return assess_candidate_risk(
        candidate=candidate,
        conjunction_events=conjunction_events,
        data_age_seconds=data_age_seconds,
        proximity_weight=proximity_weight,
        count_weight=count_weight,
        saturation_count=saturation_count,
        event_threshold_km=event_threshold_km,
    )


def calculate_scalar_risk_score(
    candidate: Any,
    conjunction_events: Optional[List[Any]] = None,
    **kwargs: Any,
) -> float:
    """Convenience helper returning purely the scalar float risk_score in [0, 100]."""
    assessment = assess_candidate_risk(candidate=candidate, conjunction_events=conjunction_events, **kwargs)
    return assessment.risk_score
