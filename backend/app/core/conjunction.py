"""Conjunction screening, coarse spatial detection, and event filtering.

Implements Phase P8 of the D-DATO pipeline:
Two-pass screening (coarse scan + bounded TCA refinement)
between candidate deployment orbits (Circular J2) and space debris (SGP4)
in the TEME reference frame at common UTC timestamps.

NOTE: This is a physical screening filter for close approaches (miss distance <= 25 km).
It is NOT a collision probability or impact risk calculation.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from app.core.config import settings
from app.core.orbit import CircularJ2Orbit, create_circular_j2_orbit
from app.core.propagation import Sgp4Propagator, PropagationError
from app.core.tca import refine_tca, TCARefinementResult
from app.data.filter import classify_object
from app.data.parser import CanonicalElementRecord
from app.utils.time import now_utc, ensure_utc


class ScreeningError(Exception):
    """Raised when conjunction screening encounters an unrecoverable candidate failure."""
    pass


@dataclass(frozen=True)
class ConjunctionEventResult:
    """Immutable domain representation of a verified close-approach screening event."""
    candidate_id: str
    debris_object_id: Optional[str]
    debris_norad_id: str
    tca: datetime
    miss_distance_km: float
    relative_velocity_km_s: float
    coarse_min_distance_km: float
    coarse_time: datetime
    screening_start: datetime
    screening_end: datetime
    coarse_step_seconds: float
    coarse_threshold_km: float
    acceptance_threshold_km: float
    propagation_model_candidate: str = "CircularJ2"
    propagation_model_debris: str = "SGP4"
    created_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class CoarseApproach:
    """Internal intermediate representation of an approach identified during coarse screening."""
    candidate_id: str
    debris_record: CanonicalElementRecord
    debris_object_id: Optional[str]
    bracket_start: datetime
    bracket_end: datetime
    coarse_min_distance_km: float
    coarse_time: datetime


@dataclass(frozen=True)
class ScreeningReport:
    """Summary and audit metadata produced by a conjunction screening run."""
    candidate_id: str
    screening_start: datetime
    screening_end: datetime
    coarse_step_seconds: float
    coarse_threshold_km: float
    event_threshold_km: float
    debris_objects_considered: int
    debris_objects_skipped: int
    coarse_pair_hits: int
    refined_event_count: int
    events: List[ConjunctionEventResult]
    warnings: List[str] = field(default_factory=list)


# =====================================================================
# State Distance & Relative Velocity Calculations
# =====================================================================

def calculate_relative_distance(r1: np.ndarray, r2: np.ndarray) -> float:
    """Calculate Euclidean distance (km) between two 3-D Cartesian position vectors.

    Args:
        r1: 3-element position array in km.
        r2: 3-element position array in km.

    Returns:
        Separation distance in km.
    """
    v1 = np.asarray(r1, dtype=float)
    v2 = np.asarray(r2, dtype=float)
    if v1.shape != (3,) or v2.shape != (3,):
        raise ValueError(f"Position vectors must be 3-D, got shapes {v1.shape} and {v2.shape}")
    if not (np.all(np.isfinite(v1)) and np.all(np.isfinite(v2))):
        raise ValueError("Position vectors must contain finite numerical values")
    dr = v1 - v2
    dist = float(np.linalg.norm(dr))
    if not math.isfinite(dist):
        raise ValueError("Computed relative distance is non-finite")
    return dist


def calculate_relative_velocity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Calculate relative speed magnitude (km/s) between two 3-D velocity vectors.

    Args:
        v1: 3-element velocity array in km/s.
        v2: 3-element velocity array in km/s.

    Returns:
        Relative speed magnitude in km/s.
    """
    u1 = np.asarray(v1, dtype=float)
    u2 = np.asarray(v2, dtype=float)
    if u1.shape != (3,) or u2.shape != (3,):
        raise ValueError(f"Velocity vectors must be 3-D, got shapes {u1.shape} and {u2.shape}")
    if not (np.all(np.isfinite(u1)) and np.all(np.isfinite(u2))):
        raise ValueError("Velocity vectors must contain finite numerical values")
    dv = u1 - u2
    speed = float(np.linalg.norm(dv))
    if not math.isfinite(speed):
        raise ValueError("Computed relative speed is non-finite")
    return speed


def calculate_relative_state(
    cand_pos: np.ndarray,
    cand_vel: np.ndarray,
    deb_pos: np.ndarray,
    deb_vel: np.ndarray,
) -> Tuple[float, float]:
    """Calculate both miss distance (km) and relative speed (km/s)."""
    dist = calculate_relative_distance(cand_pos, deb_pos)
    speed = calculate_relative_velocity(cand_vel, deb_vel)
    return dist, speed


# =====================================================================
# Candidate Propagation Model Adapter (CRITICAL SEMANTIC RULE)
# =====================================================================

def candidate_to_screening_orbit(candidate: Any) -> CircularJ2Orbit:
    """Construct the Circular J2 propagation model anchored at candidate deployment_epoch.

    CRITICAL SEMANTIC RULE:
    candidate.raan_deg is the candidate's derived RAAN AT deployment_epoch.
    candidate.u0_deg is the candidate's argument of latitude AT deployment_epoch.
    candidate.deployment_epoch is the screening start epoch.

    DO NOT re-apply deployment delay / RAAN coupling here.
    DO NOT propagate candidate from epoch_start using coupled RAAN.
    DO NOT double-count deployment delay.
    """
    altitude_km = float(candidate.altitude_km)
    inclination_deg = float(candidate.inclination_deg)
    raan_deg = float(candidate.raan_deg)
    u0_deg = float(candidate.u0_deg)

    if hasattr(candidate, "deployment_epoch") and candidate.deployment_epoch is not None:
        epoch = ensure_utc(candidate.deployment_epoch)
    elif hasattr(candidate, "run") and getattr(candidate, "run", None) and getattr(candidate.run, "plan", None):
        delay_min = float(getattr(candidate, "deployment_delay_minutes", 0.0))
        epoch = ensure_utc(candidate.run.plan.epoch_start + timedelta(minutes=delay_min))
    elif hasattr(candidate, "epoch_start") and candidate.epoch_start is not None:
        delay_min = float(getattr(candidate, "deployment_delay_minutes", 0.0))
        epoch = ensure_utc(candidate.epoch_start + timedelta(minutes=delay_min))
    else:
        raise ValueError("Candidate must provide deployment_epoch, epoch_start, or plan linkage.")

    return create_circular_j2_orbit(
        altitude_km=altitude_km,
        inclination_deg=inclination_deg,
        raan_deg=raan_deg,
        u0_deg=u0_deg,
        epoch=epoch,
    )


# =====================================================================
# Conservative Pre-screening Filter
# =====================================================================

def prefilter_debris(
    debris_records: List[Union[CanonicalElementRecord, Tuple[CanonicalElementRecord, Optional[str]]]],
    candidate_altitude_km: float,
    margin_km: float = settings.SCREENING_PREFILTER_ALTITUDE_MARGIN_KM,
    include_unknown: bool = settings.SCREENING_INCLUDE_UNKNOWN_OBJECTS,
) -> Tuple[List[Tuple[CanonicalElementRecord, Optional[str]]], int]:
    """Conservative candidate/debris prefilter prior to expensive numerical propagation.

    Rules:
    1. Rejection of payload objects:
       Screening targets debris and rocket bodies. Records classified as 'payload'
       are excluded. 'unknown' is retained conservatively.
    2. Altitude envelope check:
       If perigee and apogee altitudes can be computed for the debris object,
       reject only if candidate altitude cannot overlap [hp - margin, ha + margin].
       Default margin is 300.0 km.
    3. Retain on missing metadata:
       If orbital altitude data cannot be reliably determined, the object is retained.
    4. NO inclination filtering:
       Inclination is never used to exclude objects because differently inclined orbits
       frequently intersect spatially.

    Returns:
        Tuple of (accepted_pairs, skipped_count), where each accepted pair is
        (CanonicalElementRecord, Optional[str] debris_object_id).
    """
    accepted: List[Tuple[CanonicalElementRecord, Optional[str]]] = []
    skipped_count = 0

    for item in debris_records:
        if isinstance(item, tuple):
            record, db_id = item
        else:
            record, db_id = item, getattr(item, "id", None)

        # 1. Classification check
        # Check explicit classification attribute or classify using conservative heuristics
        cls_name: Optional[str] = None
        if hasattr(record, "object_type") and record.object_type:
            cls_name = str(record.object_type).lower()
        elif record.classification and record.classification.lower() in ("payload", "debris", "rocket_body", "unknown"):
            cls_name = record.classification.lower()
        else:
            cls = classify_object(record)
            cls_name = cls.category.lower()

        if cls_name == "payload":
            skipped_count += 1
            continue

        if cls_name == "unknown" and not include_unknown:
            skipped_count += 1
            continue

        # 2. Orbital altitude envelope check
        try:
            hp = record.perigee_altitude_km
            ha = record.apogee_altitude_km
            if hp > 0 and ha > 0 and ha >= hp:
                min_allowed = hp - margin_km
                max_allowed = ha + margin_km
                if candidate_altitude_km < min_allowed or candidate_altitude_km > max_allowed:
                    skipped_count += 1
                    continue
        except Exception:
            # On any calculation failure, retain object conservatively
            pass

        accepted.append((record, db_id))

    return accepted, skipped_count


# =====================================================================
# Deduplication & Ordering
# =====================================================================

def deduplicate_conjunction_events(
    events: List[ConjunctionEventResult],
    merge_window_seconds: float = 30.0,
) -> List[ConjunctionEventResult]:
    """Deterministically deduplicate conjunction events for the same candidate/debris pair.

    Encounters for the same pair within merge_window_seconds (default 30s) are merged,
    retaining the event with the minimum refined miss distance. Distinct encounters
    separated by more than merge_window_seconds are preserved.

    Output ordering:
    1. candidate ID
    2. TCA (UTC)
    3. miss distance (km)
    4. debris NORAD catalog ID
    """
    if not events:
        return []

    # Group by (candidate_id, debris_key)
    grouped: Dict[Tuple[str, str], List[ConjunctionEventResult]] = defaultdict(list)
    for ev in events:
        debris_key = ev.debris_object_id if ev.debris_object_id is not None else ev.debris_norad_id
        grouped[(ev.candidate_id, debris_key)].append(ev)

    deduped: List[ConjunctionEventResult] = []
    for key, group in grouped.items():
        # Sort group by TCA
        group.sort(key=lambda e: e.tca)

        current_cluster: List[ConjunctionEventResult] = [group[0]]
        for next_ev in group[1:]:
            last_ev = current_cluster[-1]
            dt = abs((next_ev.tca - last_ev.tca).total_seconds())
            if dt <= merge_window_seconds:
                current_cluster.append(next_ev)
            else:
                best_ev = min(current_cluster, key=lambda e: (e.miss_distance_km, e.tca))
                deduped.append(best_ev)
                current_cluster = [next_ev]

        if current_cluster:
            best_ev = min(current_cluster, key=lambda e: (e.miss_distance_km, e.tca))
            deduped.append(best_ev)

    # Sort deterministically
    deduped.sort(key=lambda e: (e.candidate_id, e.tca, e.miss_distance_km, e.debris_norad_id))
    return deduped


# =====================================================================
# Two-Pass Screening Engine
# =====================================================================

def screen_candidate_against_debris(
    candidate: Any,
    debris_records: List[Union[CanonicalElementRecord, Tuple[CanonicalElementRecord, Optional[str]]]],
    screening_days: Optional[float] = None,
    coarse_step_seconds: Optional[float] = None,
    coarse_threshold_km: Optional[float] = None,
    event_threshold_km: Optional[float] = None,
    time_chunk_seconds: Optional[float] = None,
    max_events_per_candidate: Optional[int] = None,
) -> ScreeningReport:
    """Execute two-pass conjunction screening for a single candidate orbit against debris records.

    Pass 1: Coarse screening on regular time grid with time chunking.
    Pass 2: Bounded 1-D numerical TCA refinement for local minima <= coarse_threshold_km.
    Filtering: Only refined encounters with miss_distance_km <= event_threshold_km are kept.
    Deduplication: Merges detections within 30 seconds for the same pair.

    Args:
        candidate: CandidateOrbit domain object or Candidate ORM object.
        debris_records: List of CanonicalElementRecord or (record, debris_object_id) tuples.
        screening_days: Horizon in days (defaults to settings.SCREENING_DAYS = 3.0).
        coarse_step_seconds: Coarse step in seconds (defaults to settings.SCREENING_COARSE_STEP_SECONDS = 30.0).
        coarse_threshold_km: Coarse hit threshold in km (defaults to settings.SCREENING_COARSE_THRESHOLD_KM = 260.0).
        event_threshold_km: Final event acceptance threshold in km (defaults to settings.SCREENING_EVENT_THRESHOLD_KM = 25.0).
        time_chunk_seconds: Memory chunk size in seconds (defaults to settings.SCREENING_TIME_CHUNK_SECONDS = 3600).
        max_events_per_candidate: Max events safety cap (defaults to settings.SCREENING_MAX_EVENTS_PER_CANDIDATE = 1000).

    Returns:
        ScreeningReport containing verified ConjunctionEventResult list and audit metrics.
    """
    days = float(screening_days if screening_days is not None else settings.SCREENING_DAYS)
    step_sec = float(coarse_step_seconds if coarse_step_seconds is not None else settings.SCREENING_COARSE_STEP_SECONDS)
    coarse_thresh = float(coarse_threshold_km if coarse_threshold_km is not None else settings.SCREENING_COARSE_THRESHOLD_KM)
    event_thresh = float(event_threshold_km if event_threshold_km is not None else settings.SCREENING_EVENT_THRESHOLD_KM)
    chunk_sec = float(time_chunk_seconds if time_chunk_seconds is not None else settings.SCREENING_TIME_CHUNK_SECONDS)
    max_events = int(max_events_per_candidate if max_events_per_candidate is not None else settings.SCREENING_MAX_EVENTS_PER_CANDIDATE)

    warnings: List[str] = []
    candidate_id = str(getattr(candidate, "candidate_id", None) or getattr(candidate, "id", "candidate"))

    # 1. Construct candidate propagation model anchored at deployment_epoch
    try:
        candidate_orbit = candidate_to_screening_orbit(candidate)
    except Exception as e:
        raise ScreeningError(f"Failed to initialize screening orbit for candidate {candidate_id}: {e}") from e

    screening_start = candidate_orbit.epoch
    screening_end = ensure_utc(screening_start + timedelta(days=days))
    total_screening_sec = (screening_end - screening_start).total_seconds()

    # 2. Conservative prefiltering
    filtered_pairs, skipped_count = prefilter_debris(
        debris_records=debris_records,
        candidate_altitude_km=candidate.altitude_km,
    )

    considered_count = len(filtered_pairs)
    coarse_pair_hits = 0
    raw_events: List[ConjunctionEventResult] = []

    if considered_count == 0:
        return ScreeningReport(
            candidate_id=candidate_id,
            screening_start=screening_start,
            screening_end=screening_end,
            coarse_step_seconds=step_sec,
            coarse_threshold_km=coarse_thresh,
            event_threshold_km=event_thresh,
            debris_objects_considered=0,
            debris_objects_skipped=skipped_count,
            coarse_pair_hits=0,
            refined_event_count=0,
            events=[],
            warnings=warnings,
        )

    # 3. Initialize SGP4 propagators with error isolation
    valid_propagators: List[Tuple[CanonicalElementRecord, Optional[str], Sgp4Propagator]] = []
    for rec, db_id in filtered_pairs:
        try:
            prop = Sgp4Propagator(rec)
            valid_propagators.append((rec, db_id, prop))
        except Exception as e:
            warnings.append(f"Failed to initialize SGP4 for object '{rec.norad_id}': {e}")
            skipped_count += 1

    # 4. Time-chunked coarse scanning & refinement
    current_chunk_start_sec = 0.0
    limit_reached = False

    while current_chunk_start_sec < total_screening_sec and not limit_reached:
        current_chunk_end_sec = min(total_screening_sec, current_chunk_start_sec + chunk_sec)

        # To avoid missing local minima or crossings across chunk boundaries,
        # expand evaluation by one step on either side where possible.
        eval_start_sec = max(0.0, current_chunk_start_sec - step_sec)
        eval_end_sec = min(total_screening_sec, current_chunk_end_sec + step_sec)

        # Generate coarse grid offsets
        step_count = int(round((eval_end_sec - eval_start_sec) / step_sec)) + 1
        t_offsets = np.linspace(eval_start_sec, eval_end_sec, step_count)
        timestamps = [screening_start + timedelta(seconds=float(s)) for s in t_offsets]

        # Batch-compute candidate positions for this chunk
        cand_positions = np.zeros((step_count, 3), dtype=float)
        for idx, offset in enumerate(t_offsets):
            r_c, _ = candidate_orbit.state_at(float(offset))
            cand_positions[idx] = r_c

        # Screen each debris object across this chunk
        for rec, db_id, deb_prop in valid_propagators:
            if limit_reached:
                break

            # Propagate debris over chunk timestamps
            deb_positions = np.zeros((step_count, 3), dtype=float)
            deb_failed = False
            for idx, t_stamp in enumerate(timestamps):
                try:
                    deb_state = deb_prop.propagate(t_stamp)
                    deb_positions[idx] = deb_state.position_km
                except (PropagationError, ValueError, Exception) as pe:
                    warnings.append(
                        f"Debris propagation error for '{rec.norad_id}' at {t_stamp.isoformat()}: {pe}"
                    )
                    deb_failed = True
                    break

            if deb_failed:
                continue

            # Compute Euclidean distances array
            dr = cand_positions - deb_positions
            distances = np.linalg.norm(dr, axis=1)

            # Local minimum and threshold crossing detection
            coarse_approaches: List[CoarseApproach] = []

            for i in range(step_count):
                is_hit = False
                dist_i = float(distances[i])

                # Interior local minimum
                if 0 < i < step_count - 1:
                    if dist_i <= float(distances[i - 1]) and dist_i <= float(distances[i + 1]):
                        if dist_i <= coarse_thresh:
                            is_hit = True
                # Boundary local minimum
                elif i == 0 and step_count > 1:
                    if dist_i <= coarse_thresh and dist_i <= float(distances[1]):
                        is_hit = True
                elif i == step_count - 1 and step_count > 1:
                    if dist_i <= coarse_thresh and dist_i <= float(distances[step_count - 2]):
                        is_hit = True

                # Adjacent samples straddling threshold
                if not is_hit and i > 0:
                    d_prev = float(distances[i - 1])
                    if (d_prev > coarse_thresh >= dist_i) or (dist_i <= coarse_thresh < d_prev):
                        is_hit = True

                if is_hit:
                    # Construct bracket [t_i - step, t_i + step] clamped to screening window
                    t_i = timestamps[i]
                    b_start = max(screening_start, t_i - timedelta(seconds=step_sec))
                    b_end = min(screening_end, t_i + timedelta(seconds=step_sec))

                    coarse_approaches.append(
                        CoarseApproach(
                            candidate_id=candidate_id,
                            debris_record=rec,
                            debris_object_id=db_id,
                            bracket_start=b_start,
                            bracket_end=b_end,
                            coarse_min_distance_km=dist_i,
                            coarse_time=t_i,
                        )
                    )

            # Pass 2: Refine each identified coarse approach
            for approach in coarse_approaches:
                coarse_pair_hits += 1

                refinement: TCARefinementResult = refine_tca(
                    candidate_orbit=candidate_orbit,
                    debris_propagator=deb_prop,
                    bracket_start=approach.bracket_start,
                    bracket_end=approach.bracket_end,
                )

                # Keep event ONLY if refined miss distance <= event acceptance threshold (25.0 km)
                if refinement.miss_distance_km <= event_thresh:
                    raw_events.append(
                        ConjunctionEventResult(
                            candidate_id=candidate_id,
                            debris_object_id=approach.debris_object_id,
                            debris_norad_id=approach.debris_record.norad_id,
                            tca=refinement.tca,
                            miss_distance_km=refinement.miss_distance_km,
                            relative_velocity_km_s=refinement.relative_velocity_km_s,
                            coarse_min_distance_km=approach.coarse_min_distance_km,
                            coarse_time=approach.coarse_time,
                            screening_start=screening_start,
                            screening_end=screening_end,
                            coarse_step_seconds=step_sec,
                            coarse_threshold_km=coarse_thresh,
                            acceptance_threshold_km=event_thresh,
                            propagation_model_candidate="CircularJ2",
                            propagation_model_debris="SGP4",
                        )
                    )

                    if len(raw_events) >= max_events:
                        limit_reached = True
                        warnings.append(
                            f"Safety cap reached: Candidate '{candidate_id}' exceeded "
                            f"{max_events} raw conjunction events. Event accumulation truncated."
                        )
                        break

        current_chunk_start_sec += chunk_sec

    # 5. Deterministic deduplication
    final_events = deduplicate_conjunction_events(raw_events, merge_window_seconds=step_sec)

    return ScreeningReport(
        candidate_id=candidate_id,
        screening_start=screening_start,
        screening_end=screening_end,
        coarse_step_seconds=step_sec,
        coarse_threshold_km=coarse_thresh,
        event_threshold_km=event_thresh,
        debris_objects_considered=considered_count,
        debris_objects_skipped=skipped_count,
        coarse_pair_hits=coarse_pair_hits,
        refined_event_count=len(final_events),
        events=final_events,
        warnings=warnings,
    )
