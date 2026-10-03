"""Screening run lifecycle service and asynchronous execution coordinator.

Phase P12: Orchestrates asynchronous screening execution via WorkerManager and the synchronous P11 pipeline.
Manages:
- Plan creation and validation
- Run creation in 'queued' state
- Non-blocking submission to WorkerManager
- Deterministic lifecycle state transitions (queued -> running -> completed / failed)
- Thread-safe polling and status reporting
- Clean shutdown
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import (
    Candidate,
    ConjunctionEvent,
    Plan,
    Run,
    RunStatus,
)
from app.db.repositories import (
    CandidateRepository,
    ConjunctionEventRepository,
    PlanRepository,
    RunRepository,
)
from app.schemas.candidate import CandidateResultItem, CandidateResultsResponse
from app.schemas.event import EventResultItem, EventResultsResponse
from app.schemas.run import RunStatusResponse
from app.services.pipeline_service import (
    PipelineResult,
    PipelineService,
    PipelineStageError,
    PlanParameters,
    plan_orm_to_parameters,
)
from app.utils.time import now_utc
from app.workers.screening_worker import (
    DuplicateRunSubmissionError,
    WorkerManager,
    get_worker_manager,
)

logger = logging.getLogger(__name__)


class RunLifecycleError(Exception):
    """Raised when an invalid run lifecycle state transition is requested."""
    pass


# Legal state transitions definition
VALID_TRANSITIONS: Dict[str, set[str]] = {
    RunStatus.queued.value: {RunStatus.running.value, RunStatus.failed.value},
    RunStatus.running.value: {
        RunStatus.completed.value,
        RunStatus.failed.value,
        RunStatus.cancelled.value,
    },
    RunStatus.completed.value: set(),
    RunStatus.failed.value: set(),
    RunStatus.cancelled.value: set(),
}


def validate_lifecycle_transition(current_status: str, target_status: str) -> None:
    """Validate whether transitioning from current_status to target_status is legal.

    Raises:
        RunLifecycleError: If the transition is disallowed or from a terminal state.
    """
    allowed = VALID_TRANSITIONS.get(current_status)
    if allowed is None:
        raise RunLifecycleError(f"Unknown current run status: '{current_status}'.")
    if target_status not in allowed:
        terminal_msg = "none (terminal state)" if not allowed else f"allowed: {sorted(list(allowed))}"
        raise RunLifecycleError(
            f"Invalid lifecycle transition from '{current_status}' to '{target_status}'. {terminal_msg}."
        )


@dataclass(frozen=True)
class RunStatusSummary:
    """Immutable domain summary of a screening run's execution status and progress."""

    run_id: str
    plan_id: str
    status: str
    progress_percent: float
    current_stage: Optional[str]
    message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    candidate_count: int
    conjunction_event_count: int
    ranked_candidate_count: int

    def to_response(self) -> RunStatusResponse:
        """Convert domain summary to Pydantic RunStatusResponse model."""
        return RunStatusResponse(
            run_id=self.run_id,
            plan_id=self.plan_id,
            status=self.status,
            progress_percent=self.progress_percent,
            current_stage=self.current_stage,
            message=self.message,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error_message=self.error_message,
            candidate_count=self.candidate_count,
            conjunction_event_count=self.conjunction_event_count,
            ranked_candidate_count=self.ranked_candidate_count,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert domain summary to a dictionary."""
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "current_stage": self.current_stage,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "candidate_count": self.candidate_count,
            "conjunction_event_count": self.conjunction_event_count,
            "ranked_candidate_count": self.ranked_candidate_count,
        }


class RunService:
    """Service managing screening run lifecycle, background execution, and progress tracking."""

    def __init__(
        self,
        session_factory: Optional[Callable[[], Session]] = None,
        worker_manager: Optional[WorkerManager] = None,
        pipeline_service: Optional[PipelineService] = None,
    ):
        self.session_factory = session_factory or SessionLocal
        self.worker_manager = worker_manager or get_worker_manager()
        self.pipeline_service = pipeline_service or PipelineService()

    @contextmanager
    def _get_session(self, db: Optional[Session] = None) -> Generator[Session, None, None]:
        """Provide a database session. If db is provided, yields it without closing.

        If db is None, creates a fresh session from session_factory and closes it on exit.
        """
        if db is not None:
            yield db
        else:
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

    def create_plan(
        self,
        plan_data: Union[Plan, PlanParameters, Dict[str, Any]],
        db: Optional[Session] = None,
    ) -> Plan:
        """Validate and persist a mission planning envelope."""
        with self._get_session(db) as session:
            repo = PlanRepository(session)

            if isinstance(plan_data, Plan):
                plan_record = plan_data
            elif isinstance(plan_data, PlanParameters):
                plan_record = Plan(
                    epoch_start=plan_data.epoch_start,
                    altitude_min_km=plan_data.altitude_min_km,
                    altitude_max_km=plan_data.altitude_max_km,
                    altitude_step_km=plan_data.altitude_step_km,
                    inclination_min_deg=plan_data.inclination_min_deg,
                    inclination_max_deg=plan_data.inclination_max_deg,
                    inclination_step_deg=plan_data.inclination_step_deg,
                    raan_deg=plan_data.raan_deg,
                    u0_deg=plan_data.u0_deg,
                    delay_min_minutes=plan_data.delay_min_minutes,
                    delay_max_minutes=plan_data.delay_max_minutes,
                    delay_step_minutes=plan_data.delay_step_minutes,
                    raan_delay_coupling_deg_per_min=plan_data.raan_delay_coupling_deg_per_min,
                    screening_days=plan_data.screening_days,
                    reference_altitude_km=plan_data.reference_altitude_km,
                    reference_inclination_deg=plan_data.reference_inclination_deg,
                    dv_budget_m_s=plan_data.dv_budget_m_s,
                    spacecraft_mass_kg=plan_data.spacecraft_mass_kg,
                    isp_seconds=plan_data.isp_seconds,
                    fuel_weight=plan_data.fuel_weight,
                    risk_weight=plan_data.risk_weight,
                    data_source=plan_data.data_source,
                    demo_mode=plan_data.demo_mode,
                )
            elif isinstance(plan_data, dict):
                plan_record = Plan(
                    epoch_start=plan_data.get("epoch_start", now_utc()),
                    altitude_min_km=float(plan_data.get("altitude_min_km", settings.ALTITUDE_MIN_KM)),
                    altitude_max_km=float(plan_data.get("altitude_max_km", settings.ALTITUDE_MAX_KM)),
                    altitude_step_km=float(plan_data.get("altitude_step_km", settings.ALTITUDE_STEP_KM)),
                    inclination_min_deg=float(plan_data.get("inclination_min_deg", settings.INCLINATION_MIN_DEG)),
                    inclination_max_deg=float(plan_data.get("inclination_max_deg", settings.INCLINATION_MAX_DEG)),
                    inclination_step_deg=float(plan_data.get("inclination_step_deg", settings.INCLINATION_STEP_DEG)),
                    raan_deg=float(plan_data.get("raan_deg", settings.RAAN_DEG)),
                    u0_deg=float(plan_data.get("u0_deg", settings.U0_DEG)),
                    delay_min_minutes=float(plan_data.get("delay_min_minutes", settings.DELAY_MIN_MINUTES)),
                    delay_max_minutes=float(plan_data.get("delay_max_minutes", settings.DELAY_MAX_MINUTES)),
                    delay_step_minutes=float(plan_data.get("delay_step_minutes", settings.DELAY_STEP_MINUTES)),
                    raan_delay_coupling_deg_per_min=float(
                        plan_data.get("raan_delay_coupling_deg_per_min", settings.RAAN_DELAY_COUPLING_DEG_PER_MIN)
                    ),
                    screening_days=float(plan_data.get("screening_days", settings.SCREENING_DAYS)),
                    reference_altitude_km=float(plan_data.get("reference_altitude_km", settings.REFERENCE_ALTITUDE_KM)),
                    reference_inclination_deg=float(
                        plan_data.get("reference_inclination_deg", settings.REFERENCE_INCLINATION_DEG)
                    ),
                    dv_budget_m_s=float(plan_data.get("dv_budget_m_s", settings.DV_BUDGET_M_S)),
                    spacecraft_mass_kg=float(plan_data.get("spacecraft_mass_kg", settings.SPACECRAFT_MASS_KG)),
                    isp_seconds=float(plan_data.get("isp_seconds", settings.ISP_SECONDS)),
                    fuel_weight=float(plan_data.get("fuel_weight", settings.FUEL_WEIGHT)),
                    risk_weight=float(plan_data.get("risk_weight", settings.RISK_WEIGHT)),
                    data_source=str(plan_data.get("data_source", settings.DATA_SOURCE)),
                    demo_mode=bool(plan_data.get("demo_mode", False)),
                )
            else:
                raise TypeError(f"Unsupported plan_data type: {type(plan_data)}")

            persisted = repo.create(plan_record)
            logger.info("Created mission plan '%s' (demo_mode=%s)", persisted.id, persisted.demo_mode)
            return persisted

    def create_run(self, plan_id: str, db: Optional[Session] = None) -> Run:
        """Create a new screening run initialized in the 'queued' lifecycle state."""
        with self._get_session(db) as session:
            plan_repo = PlanRepository(session)
            plan = plan_repo.get_by_id(plan_id)
            if not plan:
                raise ValueError(f"Plan '{plan_id}' does not exist.")

            run_repo = RunRepository(session)
            run = Run(
                plan_id=plan_id,
                status=RunStatus.queued.value,
                progress_percent=0.0,
                current_stage="queued",
                message="Run queued for execution",
            )
            persisted_run = run_repo.create(run)
            logger.info("Created queued screening run '%s' for plan '%s'", persisted_run.id, plan_id)
            return persisted_run

    def submit_run(self, run_id: str, db: Optional[Session] = None) -> RunStatusSummary:
        """Submit an existing queued run to the background WorkerManager.

        Returns immediately without waiting for P11 pipeline completion.
        """
        # 1. Prevent duplicate active submission
        if self.worker_manager.is_active(run_id):
            raise DuplicateRunSubmissionError(
                f"Run '{run_id}' is already queued or active in the worker manager."
            )

        # 2. Check and validate database state
        with self._get_session(db) as session:
            run_repo = RunRepository(session)
            run = run_repo.get_by_id(run_id)
            if not run:
                raise ValueError(f"Run '{run_id}' not found.")

            if run.status in (RunStatus.completed.value, RunStatus.failed.value, RunStatus.cancelled.value):
                raise RunLifecycleError(
                    f"Cannot submit run '{run_id}' in terminal state '{run.status}'."
                )

            if run.status == RunStatus.running.value:
                raise RunLifecycleError(f"Run '{run_id}' is already executing.")

            if run.status != RunStatus.queued.value:
                raise RunLifecycleError(
                    f"Run '{run_id}' must be in '{RunStatus.queued.value}' state to submit (found '{run.status}')."
                )

        # 3. Snapshot queued status before dispatching to worker
        queued_summary = self.get_run_status(run_id, db=db)

        # 4. Submit to WorkerManager
        try:
            self.worker_manager.submit(run_id, self.execute_run, run_id)
            logger.info("Asynchronously dispatched run '%s' to worker", run_id)
        except Exception as submit_err:
            # If submission fails, mark Run failed immediately so it is not permanently stuck in queued
            with self._get_session(db) as session:
                run_repo = RunRepository(session)
                run_repo.update_status(
                    run_id=run_id,
                    status=RunStatus.failed.value,
                    current_stage="failed",
                    error_message=f"Worker submission failed: {submit_err}",
                    message="Failed to submit run to background worker",
                )
            logger.error("Failed to submit run '%s' to worker: %s", run_id, submit_err)
            raise

        return queued_summary

    def create_and_submit_run(
        self,
        plan_data: Union[Plan, PlanParameters, Dict[str, Any]],
        db: Optional[Session] = None,
    ) -> RunStatusSummary:
        """Create a plan, create a queued run, and submit it to the background worker.

        Returns immediately with initial status 'queued'.
        """
        plan = self.create_plan(plan_data, db=db)
        run = self.create_run(plan.id, db=db)
        return self.submit_run(run.id, db=db)

    def execute_run(self, run_id: str, db: Optional[Session] = None) -> PipelineResult:
        """Synchronously execute the planning pipeline for run_id.

        This method is invoked by the background worker thread using its own fresh DB session.
        Handles run state transition from 'queued' -> 'running' -> 'completed' / 'failed'.
        """
        with self._get_session(db) as session:
            run_repo = RunRepository(session)
            plan_repo = PlanRepository(session)

            run = run_repo.get_by_id(run_id)
            if not run:
                raise ValueError(f"Run '{run_id}' does not exist.")

            # Validate lifecycle transition into running
            validate_lifecycle_transition(run.status, RunStatus.running.value)

            # Transition state to running
            run_repo.update_status(
                run_id=run_id,
                status=RunStatus.running.value,
                progress_percent=0.0,
                current_stage="ingestion",
                message="Starting planning pipeline execution",
            )
            logger.info("Worker started executing run '%s' (status=running)", run_id)

            plan = plan_repo.get_by_id(run.plan_id)
            if not plan:
                err_msg = f"Plan '{run.plan_id}' associated with run '{run_id}' not found."
                run_repo.update_status(
                    run_id=run_id,
                    status=RunStatus.failed.value,
                    current_stage="failed",
                    error_message=err_msg,
                    message="Associated mission plan not found",
                )
                raise ValueError(err_msg)

            plan_params = plan_orm_to_parameters(plan)

            try:
                # Execute synchronous scientific pipeline
                result = self.pipeline_service.run_pipeline(
                    plan=plan_params,
                    db=session,
                    run_id=run_id,
                    raise_on_failure=True,
                )

                # Finalize lifecycle state to completed
                run_repo.update_status(
                    run_id=run_id,
                    status=RunStatus.completed.value,
                    progress_percent=100.0,
                    current_stage="completed",
                    message="Run completed successfully",
                )
                logger.info(
                    "Worker successfully completed run '%s' (candidates=%d, events=%d)",
                    run_id,
                    result.candidate_count,
                    result.conjunction_event_count,
                )
                return result

            except PipelineStageError as pse:
                logger.error(
                    "PipelineStageError in worker execution for run '%s' at stage '%s': %s",
                    run_id,
                    pse.stage,
                    pse,
                )
                run_repo.update_status(
                    run_id=run_id,
                    status=RunStatus.failed.value,
                    current_stage="failed",
                    error_message=pse.message,
                    message=f"Run failed during {pse.stage}",
                )
                raise

            except Exception as exc:
                logger.error("Unexpected failure in worker execution for run '%s': %s", run_id, exc)
                run_repo.update_status(
                    run_id=run_id,
                    status=RunStatus.failed.value,
                    current_stage="failed",
                    error_message=str(exc),
                    message="Run failed due to unexpected internal error",
                )
                raise

    def get_run_status(self, run_id: str, db: Optional[Session] = None) -> RunStatusSummary:
        """Retrieve read-only execution progress and lifecycle summary for run_id."""
        with self._get_session(db) as session:
            run_repo = RunRepository(session)
            run = run_repo.get_by_id(run_id)
            if not run:
                raise ValueError(f"Run '{run_id}' not found.")

            # Compute entity counts for reporting
            cand_count_stmt = select(func.count(Candidate.id)).where(Candidate.run_id == run_id)
            candidate_count = session.scalar(cand_count_stmt) or 0

            event_count_stmt = select(func.count(ConjunctionEvent.id)).where(ConjunctionEvent.run_id == run_id)
            conjunction_event_count = session.scalar(event_count_stmt) or 0

            ranked_count_stmt = (
                select(func.count(Candidate.id))
                .where(Candidate.run_id == run_id, Candidate.rank.is_not(None))
            )
            ranked_candidate_count = session.scalar(ranked_count_stmt) or 0

            return RunStatusSummary(
                run_id=run.id,
                plan_id=run.plan_id,
                status=run.status,
                progress_percent=run.progress_percent,
                current_stage=run.current_stage,
                message=run.message,
                created_at=run.created_at,
                started_at=run.started_at,
                completed_at=run.completed_at,
                error_message=run.error_message,
                candidate_count=candidate_count,
                conjunction_event_count=conjunction_event_count,
                ranked_candidate_count=ranked_candidate_count,
            )

    def list_runs(self, plan_id: str, db: Optional[Session] = None) -> List[RunStatusSummary]:
        """List all runs associated with a plan ID."""
        with self._get_session(db) as session:
            run_repo = RunRepository(session)
            runs = run_repo.list_by_plan(plan_id)
            return [self.get_run_status(r.id, db=session) for r in runs]

    def get_run_results(self, run_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Retrieve persisted candidates and conjunction events for a completed run."""
        with self._get_session(db) as session:
            status = self.get_run_status(run_id, db=session)
            plan_repo = PlanRepository(session)
            cand_repo = CandidateRepository(session)
            event_repo = ConjunctionEventRepository(session)

            plan = plan_repo.get_by_id(status.plan_id)
            candidates = cand_repo.list_by_run(run_id)
            events = event_repo.list_by_run(run_id)

            return {
                "run": status.to_dict(),
                "plan": {
                    "id": plan.id if plan else None,
                    "epoch_start": plan.epoch_start.isoformat() if plan else None,
                    "altitude_range_km": [plan.altitude_min_km, plan.altitude_max_km] if plan else [],
                    "inclination_range_deg": [plan.inclination_min_deg, plan.inclination_max_deg] if plan else [],
                    "demo_mode": plan.demo_mode if plan else False,
                },
                "candidates": [
                    {
                        "id": c.id,
                        "altitude_km": c.altitude_km,
                        "inclination_deg": c.inclination_deg,
                        "raan_deg": c.raan_deg,
                        "deployment_delay_minutes": c.deployment_delay_minutes,
                        "delta_v_m_s": c.delta_v_m_s,
                        "propellant_mass_kg": c.propellant_mass_kg,
                        "fuel_fraction": c.fuel_fraction,
                        "within_dv_budget": c.within_dv_budget,
                        "risk_score": c.risk_score,
                        "rank": c.rank,
                    }
                    for c in candidates
                ],
                "conjunction_events": [
                    {
                        "id": e.id,
                        "candidate_id": e.candidate_id,
                        "debris_object_id": e.debris_object_id,
                        "tca": e.tca.isoformat(),
                        "miss_distance_km": e.miss_distance_km,
                        "relative_velocity_km_s": e.relative_velocity_km_s,
                        "threshold_km": e.threshold_km,
                    }
                    for e in events
                ],
            }

    def get_run_candidates_paginated(
        self,
        run_id: str,
        limit: int = 100,
        offset: int = 0,
        db: Optional[Session] = None,
    ) -> CandidateResultsResponse:
        """Retrieve paginated evaluated candidates for run_id ordered by rank ASC."""
        with self._get_session(db) as session:
            run_repo = RunRepository(session)
            run = run_repo.get_by_id(run_id)
            if not run:
                raise ValueError(f"Run '{run_id}' not found.")

            cand_repo = CandidateRepository(session)
            candidates, total = cand_repo.list_by_run_paginated(run_id, limit=limit, offset=offset)

            plan_repo = PlanRepository(session)
            plan = plan_repo.get_by_id(run.plan_id)
            plan_epoch = plan.epoch_start if plan else None

            # Efficiently compute per-candidate conjunction stats in a single grouped query
            event_stats_stmt = (
                select(
                    ConjunctionEvent.candidate_id,
                    func.count(ConjunctionEvent.id),
                    func.min(ConjunctionEvent.miss_distance_km),
                )
                .where(ConjunctionEvent.run_id == run_id)
                .group_by(ConjunctionEvent.candidate_id)
            )
            event_rows = session.execute(event_stats_stmt).all()
            event_stats: Dict[str, Tuple[int, Optional[float]]] = {
                str(row[0]): (int(row[1]), float(row[2]) if row[2] is not None else None)
                for row in event_rows
                if row[0] is not None
            }

            candidate_items: List[CandidateResultItem] = []
            for c in candidates:
                dep_epoch = None
                if plan_epoch is not None:
                    dep_epoch = plan_epoch + timedelta(minutes=c.deployment_delay_minutes)

                evt_info = event_stats.get(c.id)
                evt_count = evt_info[0] if evt_info else 0
                min_miss = evt_info[1] if evt_info else None

                candidate_items.append(
                    CandidateResultItem(
                        candidate_id=c.id,
                        altitude_km=c.altitude_km,
                        inclination_deg=c.inclination_deg,
                        raan_deg=c.raan_deg,
                        u0_deg=c.u0_deg,
                        deployment_delay_minutes=c.deployment_delay_minutes,
                        deployment_epoch=dep_epoch,
                        delta_v_m_s=c.delta_v_m_s,
                        propellant_mass_kg=c.propellant_mass_kg,
                        fuel_fraction=c.fuel_fraction,
                        within_dv_budget=c.within_dv_budget,
                        risk_score=c.risk_score,
                        accepted_event_count=evt_count,
                        minimum_miss_distance_km=min_miss,
                        uncertainty_level="nominal",
                        normalized_fuel_cost=None,
                        normalized_risk_cost=None,
                        composite_score=None,
                        rank=c.rank,
                    )
                )

            return CandidateResultsResponse(
                run_id=run.id,
                total=total,
                limit=limit,
                offset=offset,
                candidate_count=total,
                status=run.status,
                candidates=candidate_items,
            )

    def get_run_events_paginated(
        self,
        run_id: str,
        limit: int = 100,
        offset: int = 0,
        db: Optional[Session] = None,
    ) -> EventResultsResponse:
        """Retrieve paginated close-approach conjunction events for run_id."""
        with self._get_session(db) as session:
            run_repo = RunRepository(session)
            run = run_repo.get_by_id(run_id)
            if not run:
                raise ValueError(f"Run '{run_id}' not found.")

            event_repo = ConjunctionEventRepository(session)
            events, total = event_repo.list_by_run_paginated(run_id, limit=limit, offset=offset)

            event_items: List[EventResultItem] = []
            for ev in events:
                norad_id = ev.debris_object.norad_id if ev.debris_object else None
                event_items.append(
                    EventResultItem(
                        id=ev.id,
                        candidate_id=ev.candidate_id,
                        debris_object_id=ev.debris_object_id,
                        debris_norad_id=norad_id,
                        tca=ev.tca,
                        miss_distance_km=ev.miss_distance_km,
                        relative_velocity_km_s=ev.relative_velocity_km_s,
                        threshold_km=ev.threshold_km,
                        screening_source=ev.screening_source,
                    )
                )

            return EventResultsResponse(
                run_id=run.id,
                total=total,
                limit=limit,
                offset=offset,
                event_count=total,
                status=run.status,
                events=event_items,
            )

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """Gracefully shut down the underlying background worker manager."""
        self.worker_manager.shutdown(wait=wait, cancel_futures=cancel_futures)


_global_run_service: Optional[RunService] = None


def get_run_service() -> RunService:
    """Dependency provider returning singleton RunService instance."""
    global _global_run_service
    if _global_run_service is None:
        _global_run_service = RunService()
    return _global_run_service
