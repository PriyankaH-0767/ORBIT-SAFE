"""3D globe trajectory generation service for D-DATO (Phase P15).

The original D-DATO specification is authoritative.

Generates TEME-frame Cartesian orbital trajectories for:
  - Ranked candidate deployment orbits (Circular J2 propagation)
  - Debris objects involved in screening (SGP4 propagation)
  - Conjunction event markers from persisted ConjunctionEvent records

Strictly read-only and offline:
  - Does NOT call CelesTrak, fetch fresh elements, or make network calls.
  - Does NOT re-trigger screening, workers, or recomputation.
  - Reuses app.core.propagation (SGP4 + CircularJ2) without modification.

Frame: TEME. Position: km. Velocity: km/s. Time: UTC ISO 8601.
"""

from __future__ import annotations

from contextlib import contextmanager
import logging
import math
from datetime import timedelta
from typing import Callable, Generator, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.orbit import create_circular_j2_orbit
from app.core.propagation import (
    PropagationError,
    Sgp4Propagator,
    StateVector,
    propagate_circular_j2_many,
)
from app.db.database import SessionLocal
from app.db.models import Candidate, ConjunctionEvent, DebrisObject, Run
from app.db.repositories import CandidateRepository, ConjunctionEventRepository, RunRepository
from app.schemas.globe import (
    GlobeCandidateTrack,
    GlobeDebrisTrack,
    GlobeEventMarker,
    GlobeResponse,
    GlobeStatePoint,
)
from app.services.screening_service import debris_model_to_canonical
from app.utils.time import ensure_utc

logger = logging.getLogger(__name__)

# Hard cap on sample points per track to bound memory and payload size
_GLOBE_MAX_SAMPLE_POINTS = 10_000


class RunNotFoundError(ValueError):
    """Raised when the specified run_id is not found."""

    def __init__(self, run_id: str):
        super().__init__(f"Run '{run_id}' not found.")
        self.run_id = run_id


class CandidateNotFoundError(ValueError):
    """Raised when an explicitly requested candidate_id is not found in the run."""

    def __init__(self, candidate_id: str, run_id: str):
        super().__init__(f"Candidate '{candidate_id}' was not found for run '{run_id}'.")
        self.candidate_id = candidate_id
        self.run_id = run_id


def _sv_to_point(sv: StateVector) -> GlobeStatePoint:
    """Convert a StateVector to a GlobeStatePoint schema instance."""
    return GlobeStatePoint(
        t=sv.timestamp,
        x_km=sv.position_km[0],
        y_km=sv.position_km[1],
        z_km=sv.position_km[2],
        vx_km_s=sv.velocity_km_s[0],
        vy_km_s=sv.velocity_km_s[1],
        vz_km_s=sv.velocity_km_s[2],
    )


class GlobeService:
    """Read-only 3D globe trajectory generation service.

    Propagates candidate and debris orbits over the run's screening window
    using the existing SGP4 (debris) and Circular J2 (candidates) propagators.
    Frame: TEME. Position: km. Velocity: km/s.

    Does not modify the database, does not make network calls.
    """

    def __init__(self, session_factory: Optional[Callable[[], Session]] = None):
        self.session_factory = session_factory or SessionLocal

    @contextmanager
    def _get_session(self, db: Optional[Session] = None) -> Generator[Session, None, None]:
        """Yield the provided session or create and close a new one."""
        if db is not None:
            yield db
        else:
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

    def get_globe_data(
        self,
        run_id: str,
        candidate_ids: Optional[List[str]] = None,
        sample_step_seconds: int = 300,
        max_candidates: int = 20,
        max_debris: int = 25,
        db: Optional[Session] = None,
    ) -> GlobeResponse:
        """Retrieve TEME-frame trajectories for candidates and debris in a run.

        Algorithm:
        1. Load Run (with Plan) from database; raise RunNotFoundError if not found.
        2. Determine plan visualization window: [plan.epoch_start, epoch_start + screening_days].
        3. Load candidates:
           - If candidate_ids is provided, load exactly those candidates belonging to run_id;
             raise CandidateNotFoundError if any requested candidate is missing.
           - If omitted, load top max_candidates candidates ordered by rank ASC.
        4. Propagate each candidate from its deployment_epoch (plan.epoch_start + delay)
           through deployment_epoch + screening_days using Circular J2.
        5. Load conjunction events; filter to selected candidates.
        6. Select debris involved in those events up to max_debris.
        7. Fill remaining debris slots deterministically ordered by (norad_id ASC, id ASC).
        8. Propagate each debris object using SGP4; skip on PropagationError.
        9. Build event markers for selected candidate & included debris subset, evaluating
           Cartesian position at exact TCA via SGP4 propagation.
        10. Return GlobeResponse.

        Raises:
            RunNotFoundError: If run_id does not identify a persisted Run.
            CandidateNotFoundError: If candidate_ids contains an ID not belonging to the run.
        """
        with self._get_session(db) as session:
            # ----------------------------------------------------------------
            # Step 1: Load Run with its parent Plan (single joinedload query)
            # ----------------------------------------------------------------
            stmt = (
                select(Run)
                .where(Run.id == run_id)
                .options(joinedload(Run.plan))
            )
            run = session.scalars(stmt).first()
            if run is None:
                raise RunNotFoundError(run_id)

            plan = run.plan

            # ----------------------------------------------------------------
            # Step 2: Plan parameters & global visualization window
            # ----------------------------------------------------------------
            epoch_start = ensure_utc(plan.epoch_start)
            screening_days = float(plan.screening_days)
            if screening_days <= 0.0:
                screening_days = 1.0  # guard against pathological plan
            epoch_end = epoch_start + timedelta(days=screening_days)
            step = max(int(sample_step_seconds), 1)

            # ----------------------------------------------------------------
            # Step 3: Load candidates (explicit candidate_ids or top-ranked)
            # ----------------------------------------------------------------
            if candidate_ids is not None:
                # Query candidates belonging to this run matching the requested IDs
                cand_stmt = select(Candidate).where(
                    Candidate.run_id == run_id,
                    Candidate.id.in_(candidate_ids),
                )
                found_cands = session.scalars(cand_stmt).all()
                found_cand_map = {c.id: c for c in found_cands}

                # Verify every requested ID exists in this run
                for cid in candidate_ids:
                    if cid not in found_cand_map:
                        raise CandidateNotFoundError(candidate_id=cid, run_id=run_id)

                # Preserve requested candidate order
                candidates: List[Candidate] = [found_cand_map[cid] for cid in candidate_ids]
            else:
                cand_repo = CandidateRepository(session)
                candidates = cand_repo.list_by_run(run_id=run_id, limit=max_candidates)

            selected_cand_ids = {c.id for c in candidates}

            # ----------------------------------------------------------------
            # Step 4: Propagate each candidate using Circular J2
            # Per-candidate visualization window:
            #   deployment_epoch = plan.epoch_start + deployment_delay_minutes
            #   trajectory window = [deployment_epoch, deployment_epoch + screening_days]
            # ----------------------------------------------------------------
            candidate_tracks: List[GlobeCandidateTrack] = []
            for cand in candidates:
                try:
                    deployment_delay_minutes = float(cand.deployment_delay_minutes)
                    cand_start = epoch_start + timedelta(minutes=deployment_delay_minutes)
                    cand_end = cand_start + timedelta(days=screening_days)

                    cand_total_sec = max((cand_end - cand_start).total_seconds(), 0.0)
                    cand_n_steps = min(
                        int(math.ceil(cand_total_sec / step)) + 1,
                        _GLOBE_MAX_SAMPLE_POINTS,
                    )
                    cand_sample_times = [
                        cand_start + timedelta(seconds=i * step)
                        for i in range(cand_n_steps)
                    ]
                    if cand_sample_times and cand_sample_times[-1] < cand_end:
                        cand_sample_times.append(cand_end)

                    orbit = create_circular_j2_orbit(
                        altitude_km=float(cand.altitude_km),
                        inclination_deg=float(cand.inclination_deg),
                        raan_deg=float(cand.raan_deg),
                        u0_deg=float(cand.u0_deg),
                        epoch=cand_start,
                    )
                    svs = propagate_circular_j2_many(
                        orbit, cand_sample_times, candidate_id=cand.id
                    )
                    points = [_sv_to_point(sv) for sv in svs]
                    candidate_tracks.append(
                        GlobeCandidateTrack(
                            candidate_id=cand.id,
                            rank=cand.rank,
                            altitude_km=float(cand.altitude_km),
                            inclination_deg=float(cand.inclination_deg),
                            raan_deg=float(cand.raan_deg),
                            risk_score=float(cand.risk_score),
                            within_dv_budget=bool(cand.within_dv_budget),
                            deployment_delay_minutes=deployment_delay_minutes,
                            deployment_epoch=cand_start,
                            trajectory_start=cand_start,
                            trajectory_end=cand_end,
                            point_count=len(points),
                            trajectory=points,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "Globe: candidate '%s' propagation failed: %s", cand.id, exc
                    )

            # ----------------------------------------------------------------
            # Step 5: Load conjunction events; filter to selected candidates
            # Order deterministically by TCA ASC, id ASC
            # ----------------------------------------------------------------
            evt_stmt = (
                select(ConjunctionEvent)
                .where(ConjunctionEvent.run_id == run_id)
                .order_by(ConjunctionEvent.tca.asc(), ConjunctionEvent.id.asc())
            )
            all_events = list(session.scalars(evt_stmt).all())
            candidate_events = [
                evt for evt in all_events
                if evt.candidate_id in selected_cand_ids
            ]

            # ----------------------------------------------------------------
            # Step 6: Select debris involved in events first (priority)
            # ----------------------------------------------------------------
            debris_ids_ordered: List[str] = []
            debris_id_set: set = set()
            for evt in candidate_events:
                if evt.debris_object_id and evt.debris_object_id not in debris_id_set:
                    debris_ids_ordered.append(evt.debris_object_id)
                    debris_id_set.add(evt.debris_object_id)

            selected_debris_ids: List[str] = debris_ids_ordered[:max_debris]

            # ----------------------------------------------------------------
            # Step 7: Deterministic fallback – fill remaining slots from DebrisObjects
            # MUST be deterministically ordered by (norad_id ASC, id ASC)
            # ----------------------------------------------------------------
            remaining_slots = max_debris - len(selected_debris_ids)
            if remaining_slots > 0:
                if debris_id_set:
                    fallback_stmt = (
                        select(DebrisObject)
                        .where(~DebrisObject.id.in_(list(debris_id_set)))
                        .order_by(DebrisObject.norad_id.asc(), DebrisObject.id.asc())
                        .limit(remaining_slots)
                    )
                else:
                    fallback_stmt = (
                        select(DebrisObject)
                        .order_by(DebrisObject.norad_id.asc(), DebrisObject.id.asc())
                        .limit(remaining_slots)
                    )
                for deb in session.scalars(fallback_stmt).all():
                    if deb.id not in debris_id_set:
                        selected_debris_ids.append(deb.id)
                        debris_id_set.add(deb.id)

            # Load selected DebrisObject records (one query)
            debris_by_id: dict[str, DebrisObject] = {}
            if selected_debris_ids:
                deb_stmt = select(DebrisObject).where(
                    DebrisObject.id.in_(selected_debris_ids)
                )
                for deb in session.scalars(deb_stmt).all():
                    debris_by_id[deb.id] = deb

            # ----------------------------------------------------------------
            # Step 8: Propagate debris tracks via SGP4
            # Debris trajectories cover the mission screening window [epoch_start, epoch_end]
            # ----------------------------------------------------------------
            deb_total_sec = max((epoch_end - epoch_start).total_seconds(), 0.0)
            deb_n_steps = min(
                int(math.ceil(deb_total_sec / step)) + 1,
                _GLOBE_MAX_SAMPLE_POINTS,
            )
            debris_sample_times = [
                epoch_start + timedelta(seconds=i * step)
                for i in range(deb_n_steps)
            ]
            if debris_sample_times and debris_sample_times[-1] < epoch_end:
                debris_sample_times.append(epoch_end)

            debris_tracks: List[GlobeDebrisTrack] = []
            debris_propagators: dict[str, Sgp4Propagator] = {}
            successful_debris_ids: set[str] = set()

            for deb_id in selected_debris_ids:
                deb = debris_by_id.get(deb_id)
                if deb is None:
                    continue
                try:
                    record = debris_model_to_canonical(deb)
                    propagator = Sgp4Propagator(record)
                    svs = propagator.propagate_many(debris_sample_times)
                    points = [_sv_to_point(sv) for sv in svs]
                    debris_tracks.append(
                        GlobeDebrisTrack(
                            norad_id=deb.norad_id,
                            object_name=deb.object_name,
                            debris_db_id=deb.id,
                            point_count=len(points),
                            trajectory=points,
                        )
                    )
                    debris_propagators[deb.id] = propagator
                    successful_debris_ids.add(deb.id)
                except PropagationError as exc:
                    logger.warning(
                        "Globe: SGP4 propagation failed for debris '%s' (%s): %s",
                        deb.norad_id,
                        deb.object_name,
                        exc,
                    )
                except Exception as exc:
                    logger.warning(
                        "Globe: unexpected error propagating debris '%s': %s",
                        deb.norad_id,
                        exc,
                    )

            # ----------------------------------------------------------------
            # Step 9: Build conjunction event markers
            # Consistency rules:
            # - candidate_ids filter limits event markers to selected candidates
            # - event markers must correspond to included, successfully propagated debris
            # - position (x_km, y_km, z_km) evaluated at exact TCA using SGP4
            # ----------------------------------------------------------------
            event_markers: List[GlobeEventMarker] = []
            for evt in candidate_events:
                # Must correspond to an included, successfully propagated debris object
                if not evt.debris_object_id or evt.debris_object_id not in successful_debris_ids:
                    continue

                deb = debris_by_id.get(evt.debris_object_id)
                propagator = debris_propagators.get(evt.debris_object_id)
                if deb is None or propagator is None:
                    continue

                tca_utc = ensure_utc(evt.tca)
                try:
                    sv_at_tca = propagator.propagate(tca_utc)
                    x_km = float(sv_at_tca.position_km[0])
                    y_km = float(sv_at_tca.position_km[1])
                    z_km = float(sv_at_tca.position_km[2])
                except Exception as exc:
                    logger.warning(
                        "Globe: failed to propagate debris '%s' at TCA %s for event '%s': %s",
                        deb.norad_id,
                        tca_utc,
                        evt.id,
                        exc,
                    )
                    continue

                event_markers.append(
                    GlobeEventMarker(
                        event_id=evt.id,
                        candidate_id=evt.candidate_id,
                        debris_object_id=evt.debris_object_id,
                        debris_norad_id=deb.norad_id,
                        tca=tca_utc,
                        miss_distance_km=float(evt.miss_distance_km),
                        relative_velocity_km_s=float(evt.relative_velocity_km_s),
                        x_km=x_km,
                        y_km=y_km,
                        z_km=z_km,
                    )
                )

            # ----------------------------------------------------------------
            # Step 10: Assemble and return the response
            # ----------------------------------------------------------------
            return GlobeResponse(
                run_id=run.id,
                status=run.status,
                frame="TEME",
                time_scale="UTC",
                sample_step_seconds=step,
                epoch_start=epoch_start,
                epoch_end=epoch_end,
                candidate_count=len(candidate_tracks),
                debris_count=len(debris_tracks),
                event_count=len(event_markers),
                candidates=candidate_tracks,
                debris=debris_tracks,
                events=event_markers,
            )


# ---------------------------------------------------------------------------
# Singleton provider for FastAPI dependency injection
# ---------------------------------------------------------------------------

_globe_service_instance: Optional[GlobeService] = None


def get_globe_service() -> GlobeService:
    """Dependency provider returning a singleton GlobeService instance."""
    global _globe_service_instance
    if _globe_service_instance is None:
        _globe_service_instance = GlobeService()
    return _globe_service_instance
