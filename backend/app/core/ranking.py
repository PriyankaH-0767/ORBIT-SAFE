"""Multi-objective candidate ranking engine for D-DATO.

Phase P10: Evaluates candidate deployment options using normalized fuel cost
and close-approach screening risk cost.

IMPORTANT POSITIONING:
- D-DATO ranking is an early-stage multi-objective screening heuristic.
- It does NOT identify an "optimal orbit", "safest orbit", or "guaranteed collision-free" path.
- Candidates are designated "screening-ranked candidates".
- P10 consumes precomputed P7 delta-v estimates and P9 screening risk assessments.
- P10 does NOT rescreen candidates, propagate orbits, or call external networks.

SPECIFICATION NOTE:
As verified by inspecting SPEC.md and codebase records, the original D-DATO
specification specifies multi-objective evaluation balancing fuel and conjunction risk
without defining a closed-form formula. Therefore, the documented fallback
ranking heuristic (fallback_ranking_v1) is implemented.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from app.core.config import settings


class RankingError(ValueError):
    """Raised when ranking inputs violate domain contracts, bounds, or data consistency."""
    pass


@dataclass(frozen=True)
class RankedCandidate:
    """Immutable domain representation of a multi-objective ranked candidate orbit."""

    candidate_id: str
    altitude_km: float
    inclination_deg: float
    raan_deg: float
    u0_deg: float
    deployment_delay_minutes: float
    deployment_epoch: Optional[datetime]

    # P7 Fuel metrics
    delta_v_m_s: float
    propellant_mass_kg: float
    fuel_fraction: float
    within_dv_budget: bool

    # P9 Risk metrics
    risk_score: float
    accepted_event_count: int
    minimum_miss_distance_km: Optional[float]
    uncertainty_level: str

    # P10 Ranking metrics
    normalized_fuel_cost: float
    normalized_risk_cost: float
    composite_score: float
    rank: int

    ranking_method: str = "fallback_ranking_v1"

    @property
    def ranking_score(self) -> float:
        """Alias for composite_score for schema/interface compatibility."""
        return self.composite_score

    def to_dict(self) -> Dict[str, Any]:
        """Convert ranked candidate to dictionary representation."""
        res = asdict(self)
        if self.deployment_epoch is not None:
            res["deployment_epoch"] = self.deployment_epoch.isoformat()
        res["ranking_score"] = self.composite_score
        return res


def _extract_candidate_id(cand: Any) -> str:
    """Extract string candidate ID from domain model, ORM model, dict, or string."""
    if isinstance(cand, str):
        return cand
    if hasattr(cand, "candidate_id") and cand.candidate_id:
        return str(cand.candidate_id)
    if hasattr(cand, "id") and cand.id:
        return str(cand.id)
    if isinstance(cand, dict):
        if "candidate_id" in cand and cand["candidate_id"]:
            return str(cand["candidate_id"])
        if "id" in cand and cand["id"]:
            return str(cand["id"])
    raise RankingError(f"Could not extract candidate ID from candidate object: {cand!r}")


def _extract_delta_v(fuel_obj: Any) -> float:
    """Extract total delta-v in m/s from DeltaVEstimate domain model or dict."""
    raw = None
    if hasattr(fuel_obj, "total_dv_m_s"):
        raw = fuel_obj.total_dv_m_s
    elif hasattr(fuel_obj, "delta_v_m_s"):
        raw = fuel_obj.delta_v_m_s
    elif isinstance(fuel_obj, dict):
        raw = fuel_obj.get("total_dv_m_s")
        if raw is None:
            raw = fuel_obj.get("delta_v_m_s")

    if raw is None:
        raise RankingError(f"Fuel result missing total_dv_m_s / delta_v_m_s: {fuel_obj!r}")
    if not math.isfinite(raw):
        raise RankingError(f"Delta-V must be a finite number (got {raw}).")
    val = float(raw)
    if val < 0.0:
        raise RankingError(f"Delta-V cannot be negative (got {val} m/s).")
    return val


def _extract_risk_score(risk_obj: Any) -> float:
    """Extract scalar risk score in [0, 100] from RiskAssessment domain model or dict."""
    raw = None
    if hasattr(risk_obj, "risk_score"):
        raw = risk_obj.risk_score
    elif isinstance(risk_obj, dict):
        raw = risk_obj.get("risk_score")

    if raw is None:
        raise RankingError(f"Risk result missing risk_score: {risk_obj!r}")
    if not math.isfinite(raw):
        raise RankingError(f"Risk score must be a finite number (got {raw}).")
    val = float(raw)
    if val < 0.0 or val > 100.0:
        raise RankingError(f"Risk score must be within [0, 100] (got {val}).")
    return val


def rank_candidates(
    candidates: Sequence[Any],
    fuel_estimates: Union[Mapping[str, Any], Sequence[Any]],
    risk_assessments: Union[Mapping[str, Any], Sequence[Any]],
    fuel_weight: Optional[float] = None,
    risk_weight: Optional[float] = None,
) -> List[RankedCandidate]:
    """Rank candidate deployment options using normalized fuel cost and risk score.

    Pure deterministic post-processing function.
    Does NOT call propagation, screening, or external networks.

    Args:
        candidates: Sequence of CandidateOrbit, Candidate ORM, dicts, or candidate IDs.
        fuel_estimates: Mapping of candidate_id -> DeltaVEstimate (or sequence matching candidates).
        risk_assessments: Mapping of candidate_id -> RiskAssessment (or sequence matching candidates).
        fuel_weight: Weight for normalized fuel cost (default settings.FUEL_WEIGHT = 0.4).
        risk_weight: Weight for normalized risk cost (default settings.RISK_WEIGHT = 0.6).

    Returns:
        List of RankedCandidate domain objects ordered by contiguous rank (rank=1 first).

    Raises:
        RankingError: If inputs violate contracts, bounds, consistency, or weights.
    """
    # 1. Weight resolution and validation
    w_fuel = float(fuel_weight if fuel_weight is not None else settings.FUEL_WEIGHT)
    w_risk = float(risk_weight if risk_weight is not None else settings.RISK_WEIGHT)

    if not (math.isfinite(w_fuel) and math.isfinite(w_risk)):
        raise RankingError(f"Weights must be finite numbers (got fuel={w_fuel}, risk={w_risk}).")
    if w_fuel < 0.0 or w_risk < 0.0:
        raise RankingError(f"Weights must be non-negative (got fuel={w_fuel}, risk={w_risk}).")
    if not math.isclose(w_fuel + w_risk, 1.0, abs_tol=1e-6):
        raise RankingError(f"Weights must sum to 1.0 (got {w_fuel} + {w_risk} = {w_fuel + w_risk}).")

    # 2. Empty candidate set handling
    if len(candidates) == 0:
        return []

    # 3. Candidate ID uniqueness & extraction
    candidate_list: List[Any] = list(candidates)
    candidate_ids: List[str] = []
    seen_ids = set()

    for cand in candidate_list:
        c_id = _extract_candidate_id(cand)
        if c_id in seen_ids:
            raise RankingError(f"Duplicate candidate ID detected in candidate list: {c_id}")
        seen_ids.add(c_id)
        candidate_ids.append(c_id)

    # 4. Map fuel_estimates to candidate_ids
    fuel_map: Dict[str, Any] = {}
    if isinstance(fuel_estimates, Mapping):
        fuel_map = dict(fuel_estimates)
    else:
        # Sequence of fuel results
        fuel_seq = list(fuel_estimates)
        if len(fuel_seq) != len(candidate_list):
            raise RankingError(
                f"Fuel estimates sequence length ({len(fuel_seq)}) does not match "
                f"candidates count ({len(candidate_list)})."
            )
        # Check if fuel objects carry candidate_id
        has_embedded_ids = any(
            hasattr(f, "candidate_id") or (isinstance(f, dict) and "candidate_id" in f)
            for f in fuel_seq
        )
        if has_embedded_ids:
            for f in fuel_seq:
                f_id = _extract_candidate_id(f)
                if f_id in fuel_map:
                    raise RankingError(f"Duplicate candidate ID in fuel_estimates: {f_id}")
                fuel_map[f_id] = f
        else:
            # Pair 1-to-1 by index
            for c_id, f in zip(candidate_ids, fuel_seq):
                fuel_map[c_id] = f

    # 5. Map risk_assessments to candidate_ids
    risk_map: Dict[str, Any] = {}
    if isinstance(risk_assessments, Mapping):
        risk_map = dict(risk_assessments)
    else:
        # Sequence of risk results
        risk_seq = list(risk_assessments)
        if len(risk_seq) != len(candidate_list):
            raise RankingError(
                f"Risk assessments sequence length ({len(risk_seq)}) does not match "
                f"candidates count ({len(candidate_list)})."
            )
        has_embedded_ids = any(
            hasattr(r, "candidate_id") or (isinstance(r, dict) and "candidate_id" in r)
            for r in risk_seq
        )
        if has_embedded_ids:
            for r in risk_seq:
                r_id = _extract_candidate_id(r)
                if r_id in risk_map:
                    raise RankingError(f"Duplicate candidate ID in risk_assessments: {r_id}")
                risk_map[r_id] = r
        else:
            for c_id, r in zip(candidate_ids, risk_seq):
                risk_map[c_id] = r

    # Validate that every candidate has both fuel and risk records
    for c_id in candidate_ids:
        if c_id not in fuel_map:
            raise RankingError(f"Candidate {c_id} is missing a corresponding fuel estimate.")
        if c_id not in risk_map:
            raise RankingError(f"Candidate {c_id} is missing a corresponding risk assessment.")

    # Validate no spurious extra IDs when passed as dictionary mappings
    if isinstance(fuel_estimates, Mapping) and set(fuel_map.keys()) != set(candidate_ids):
        diff = set(fuel_map.keys()) ^ set(candidate_ids)
        raise RankingError(f"Candidate IDs mismatch between candidates and fuel_estimates: {diff}")
    if isinstance(risk_assessments, Mapping) and set(risk_map.keys()) != set(candidate_ids):
        diff = set(risk_map.keys()) ^ set(candidate_ids)
        raise RankingError(f"Candidate IDs mismatch between candidates and risk_assessments: {diff}")

    # 6. Extract raw metrics and validate bounds
    raw_delta_vs: Dict[str, float] = {}
    raw_risks: Dict[str, float] = {}

    for c_id in candidate_ids:
        raw_delta_vs[c_id] = _extract_delta_v(fuel_map[c_id])
        raw_risks[c_id] = _extract_risk_score(risk_map[c_id])

    # 7. Fuel normalization (Min-Max)
    dv_values = list(raw_delta_vs.values())
    dv_min = min(dv_values)
    dv_max = max(dv_values)

    normalized_fuel_costs: Dict[str, float] = {}
    if dv_max > dv_min:
        dv_span = dv_max - dv_min
        for c_id, dv in raw_delta_vs.items():
            norm_f = 100.0 * (dv - dv_min) / dv_span
            normalized_fuel_costs[c_id] = float(max(0.0, min(100.0, norm_f)))
    else:
        # All candidates have identical delta-v (or single candidate)
        for c_id in candidate_ids:
            normalized_fuel_costs[c_id] = 0.0

    # 8. Risk normalization (P9 risk is already [0, 100])
    normalized_risk_costs: Dict[str, float] = {}
    for c_id, r in raw_risks.items():
        normalized_risk_costs[c_id] = float(max(0.0, min(100.0, r)))

    # 9. Composite score calculation
    composite_scores: Dict[str, float] = {}
    for c_id in candidate_ids:
        cost = w_fuel * normalized_fuel_costs[c_id] + w_risk * normalized_risk_costs[c_id]
        score = 100.0 - cost
        composite_scores[c_id] = float(max(0.0, min(100.0, score)))

    # 10. Deterministic sorting
    # Primary: composite_score descending
    # Secondary: risk_score ascending (lower risk preferred)
    # Tertiary: delta_v_m_s ascending (lower delta-v preferred)
    # Quaternary: candidate_id ascending (lexicographical string tie-breaker)
    def sort_key(item: Any) -> Any:
        c_id = _extract_candidate_id(item)
        return (
            -composite_scores[c_id],
            raw_risks[c_id],
            raw_delta_vs[c_id],
            c_id,
        )

    sorted_candidates = sorted(candidate_list, key=sort_key)

    # 11. Build RankedCandidate domain objects
    ranked_results: List[RankedCandidate] = []
    for rank_idx, cand in enumerate(sorted_candidates, start=1):
        c_id = _extract_candidate_id(cand)
        fuel_obj = fuel_map[c_id]
        risk_obj = risk_map[c_id]

        # Extract orbital geometry
        alt = float(getattr(cand, "altitude_km", None) or (cand.get("altitude_km") if isinstance(cand, dict) else 0.0) or 0.0)
        inc = float(getattr(cand, "inclination_deg", None) or (cand.get("inclination_deg") if isinstance(cand, dict) else 0.0) or 0.0)
        raan = float(getattr(cand, "raan_deg", None) or (cand.get("raan_deg") if isinstance(cand, dict) else 0.0) or 0.0)
        u0 = float(getattr(cand, "u0_deg", None) or (cand.get("u0_deg") if isinstance(cand, dict) else 0.0) or 0.0)
        delay = float(getattr(cand, "deployment_delay_minutes", None) or (cand.get("deployment_delay_minutes") if isinstance(cand, dict) else 0.0) or 0.0)
        epoch = getattr(cand, "deployment_epoch", None) or (cand.get("deployment_epoch") if isinstance(cand, dict) else None)

        # Extract P7 detailed metrics
        prop_mass = float(getattr(fuel_obj, "propellant_mass_kg", None) or (fuel_obj.get("propellant_mass_kg") if isinstance(fuel_obj, dict) else 0.0) or 0.0)
        fuel_frac = float(getattr(fuel_obj, "fuel_fraction", None) or (fuel_obj.get("fuel_fraction") if isinstance(fuel_obj, dict) else 0.0) or 0.0)
        within_budget = getattr(fuel_obj, "within_dv_budget", None)
        if within_budget is None and isinstance(fuel_obj, dict):
            within_budget = fuel_obj.get("within_dv_budget", True)
        if within_budget is None:
            within_budget = True
        within_budget = bool(within_budget)

        # Extract P9 detailed metrics
        accepted_ev = getattr(risk_obj, "accepted_event_count", None)
        if accepted_ev is None and isinstance(risk_obj, dict):
            accepted_ev = risk_obj.get("accepted_event_count", 0)
        accepted_ev = int(accepted_ev or 0)

        min_miss = getattr(risk_obj, "minimum_miss_distance_km", None)
        if min_miss is None and isinstance(risk_obj, dict):
            min_miss = risk_obj.get("minimum_miss_distance_km")
        min_miss_val = float(min_miss) if min_miss is not None else None

        unc_level = str(getattr(risk_obj, "uncertainty_level", None) or (risk_obj.get("uncertainty_level") if isinstance(risk_obj, dict) else "nominal") or "nominal")

        ranked_results.append(
            RankedCandidate(
                candidate_id=c_id,
                altitude_km=alt,
                inclination_deg=inc,
                raan_deg=raan,
                u0_deg=u0,
                deployment_delay_minutes=delay,
                deployment_epoch=epoch,
                delta_v_m_s=raw_delta_vs[c_id],
                propellant_mass_kg=prop_mass,
                fuel_fraction=fuel_frac,
                within_dv_budget=within_budget,
                risk_score=raw_risks[c_id],
                accepted_event_count=accepted_ev,
                minimum_miss_distance_km=min_miss_val,
                uncertainty_level=unc_level,
                normalized_fuel_cost=normalized_fuel_costs[c_id],
                normalized_risk_cost=normalized_risk_costs[c_id],
                composite_score=composite_scores[c_id],
                rank=rank_idx,
                ranking_method="fallback_ranking_v1",
            )
        )

    return ranked_results
