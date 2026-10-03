"""Synchronous end-to-end planning pipeline service for D-DATO.

Phase P11: Orchestrates the complete scientific chain:
1. Ingest catalog (via IngestionService)
2. Generate candidate orbits (via CandidateGenerator)
3. Calculate Delta-V and propellant estimates (via FuelEstimator)
4. Screen conjunctions and refine TCA (via ScreeningService)
5. Assess physical close-approach risk (via RiskAssessor)
6. Rank candidates using multi-objective metrics (via RankingService)
7. Persist run, candidate, and event results atomically
8. Return structured PipelineResult domain object

IMPORTANT:
- Orchestration ONLY: Does not re-implement or duplicate astrodynamics or scoring formulas.
- Synchronous execution providing the computational core for future asynchronous workers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Union
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.candidate_generator import (
    CandidateGenerationConfig,
    CandidateOrbit,
    generate_candidates,
)
from app.core.config import settings
from app.core.conjunction import (
    ConjunctionEventResult,
    ScreeningReport,
    screen_candidate_against_debris,
)
from app.core.fuel import DeltaVEstimate, evaluate_candidate_fuel
from app.core.ranking import (
    RankedCandidate,
    rank_candidates,
)
from app.core.risk import RiskAssessment, assess_candidate_risk
from app.data.parser import CanonicalElementRecord
from app.db.models import (
    Candidate,
    ConjunctionEvent,
    DebrisObject,
    Plan,
    Run,
    RunStatus,
    generate_uuid,
)
from app.db.repositories import (
    CandidateRepository,
    ConjunctionEventRepository,
    RunRepository,
)
from app.services.ingestion_service import IngestionResult, IngestionService
from app.services.ranking_service import RankingService
from app.services.screening_service import ScreeningService, conjunction_result_to_model
from app.utils.time import now_utc

logger = logging.getLogger(__name__)


class PipelineStageError(Exception):
    """Raised when a specific stage of the planning pipeline fails."""

    def __init__(self, stage: str, message: str, original_error: Optional[Exception] = None):
        super().__init__(f"[{stage}] {message}")
        self.stage = stage
        self.message = message
        self.original_error = original_error


@dataclass(frozen=True)
class PlanParameters:
    """Domain representation of input parameters required to run a planning pipeline."""

    epoch_start: datetime
    altitude_min_km: float = settings.ALTITUDE_MIN_KM
    altitude_max_km: float = settings.ALTITUDE_MAX_KM
    altitude_step_km: float = settings.ALTITUDE_STEP_KM
    inclination_min_deg: float = settings.INCLINATION_MIN_DEG
    inclination_max_deg: float = settings.INCLINATION_MAX_DEG
    inclination_step_deg: float = settings.INCLINATION_STEP_DEG
    raan_deg: float = settings.RAAN_DEG
    u0_deg: float = settings.U0_DEG
    delay_min_minutes: float = settings.DELAY_MIN_MINUTES
    delay_max_minutes: float = settings.DELAY_MAX_MINUTES
    delay_step_minutes: float = settings.DELAY_STEP_MINUTES
    raan_delay_coupling_deg_per_min: float = settings.RAAN_DELAY_COUPLING_DEG_PER_MIN
    screening_days: float = settings.SCREENING_DAYS
    reference_altitude_km: float = settings.REFERENCE_ALTITUDE_KM
    reference_inclination_deg: float = settings.REFERENCE_INCLINATION_DEG
    spacecraft_mass_kg: float = settings.SPACECRAFT_MASS_KG
    isp_seconds: float = settings.ISP_SECONDS
    dv_budget_m_s: float = settings.DV_BUDGET_M_S
    fuel_weight: float = settings.FUEL_WEIGHT
    risk_weight: float = settings.RISK_WEIGHT
    data_source: str = settings.DATA_SOURCE
    demo_mode: bool = True
    plan_id: Optional[str] = None
    name: str = "Mission Plan"


def plan_orm_to_parameters(plan: Any) -> PlanParameters:
    """Map SQLAlchemy Plan model, dictionary, or parameters object to PlanParameters."""
    if isinstance(plan, PlanParameters):
        return plan

    if isinstance(plan, dict):
        return PlanParameters(
            epoch_start=plan.get("epoch_start", now_utc()),
            altitude_min_km=float(plan.get("altitude_min_km", settings.ALTITUDE_MIN_KM)),
            altitude_max_km=float(plan.get("altitude_max_km", settings.ALTITUDE_MAX_KM)),
            altitude_step_km=float(plan.get("altitude_step_km", settings.ALTITUDE_STEP_KM)),
            inclination_min_deg=float(plan.get("inclination_min_deg", settings.INCLINATION_MIN_DEG)),
            inclination_max_deg=float(plan.get("inclination_max_deg", settings.INCLINATION_MAX_DEG)),
            inclination_step_deg=float(plan.get("inclination_step_deg", settings.INCLINATION_STEP_DEG)),
            raan_deg=float(plan.get("raan_deg", settings.RAAN_DEG)),
            u0_deg=float(plan.get("u0_deg", settings.U0_DEG)),
            delay_min_minutes=float(plan.get("delay_min_minutes", settings.DELAY_MIN_MINUTES)),
            delay_max_minutes=float(plan.get("delay_max_minutes", settings.DELAY_MAX_MINUTES)),
            delay_step_minutes=float(plan.get("delay_step_minutes", settings.DELAY_STEP_MINUTES)),
            raan_delay_coupling_deg_per_min=float(
                plan.get("raan_delay_coupling_deg_per_min", settings.RAAN_DELAY_COUPLING_DEG_PER_MIN)
            ),
            screening_days=float(plan.get("screening_days", settings.SCREENING_DAYS)),
            reference_altitude_km=float(plan.get("reference_altitude_km", settings.REFERENCE_ALTITUDE_KM)),
            reference_inclination_deg=float(plan.get("reference_inclination_deg", settings.REFERENCE_INCLINATION_DEG)),
            spacecraft_mass_kg=float(plan.get("spacecraft_mass_kg", settings.SPACECRAFT_MASS_KG)),
            isp_seconds=float(plan.get("isp_seconds", settings.ISP_SECONDS)),
            dv_budget_m_s=float(plan.get("dv_budget_m_s", settings.DV_BUDGET_M_S)),
            fuel_weight=float(plan.get("fuel_weight", settings.FUEL_WEIGHT)),
            risk_weight=float(plan.get("risk_weight", settings.RISK_WEIGHT)),
            data_source=str(plan.get("data_source", settings.DATA_SOURCE)),
            demo_mode=bool(plan.get("demo_mode", True)),
            plan_id=str(plan.get("id") or plan.get("plan_id") or "") or None,
            name=str(plan.get("name", "Mission Plan")),
        )

    # Object / ORM model
    return PlanParameters(
        epoch_start=getattr(plan, "epoch_start", now_utc()),
        altitude_min_km=float(getattr(plan, "altitude_min_km", settings.ALTITUDE_MIN_KM)),
        altitude_max_km=float(getattr(plan, "altitude_max_km", settings.ALTITUDE_MAX_KM)),
        altitude_step_km=float(getattr(plan, "altitude_step_km", settings.ALTITUDE_STEP_KM)),
        inclination_min_deg=float(getattr(plan, "inclination_min_deg", settings.INCLINATION_MIN_DEG)),
        inclination_max_deg=float(getattr(plan, "inclination_max_deg", settings.INCLINATION_MAX_DEG)),
        inclination_step_deg=float(getattr(plan, "inclination_step_deg", settings.INCLINATION_STEP_DEG)),
        raan_deg=float(getattr(plan, "raan_deg", settings.RAAN_DEG)),
        u0_deg=float(getattr(plan, "u0_deg", settings.U0_DEG)),
        delay_min_minutes=float(getattr(plan, "delay_min_minutes", settings.DELAY_MIN_MINUTES)),
        delay_max_minutes=float(getattr(plan, "delay_max_minutes", settings.DELAY_MAX_MINUTES)),
        delay_step_minutes=float(getattr(plan, "delay_step_minutes", settings.DELAY_STEP_MINUTES)),
        raan_delay_coupling_deg_per_min=float(
            getattr(plan, "raan_delay_coupling_deg_per_min", settings.RAAN_DELAY_COUPLING_DEG_PER_MIN)
        ),
        screening_days=float(getattr(plan, "screening_days", settings.SCREENING_DAYS)),
        reference_altitude_km=float(getattr(plan, "reference_altitude_km", settings.REFERENCE_ALTITUDE_KM)),
        reference_inclination_deg=float(getattr(plan, "reference_inclination_deg", settings.REFERENCE_INCLINATION_DEG)),
        spacecraft_mass_kg=float(getattr(plan, "spacecraft_mass_kg", settings.SPACECRAFT_MASS_KG)),
        isp_seconds=float(getattr(plan, "isp_seconds", settings.ISP_SECONDS)),
        dv_budget_m_s=float(getattr(plan, "dv_budget_m_s", settings.DV_BUDGET_M_S)),
        fuel_weight=float(getattr(plan, "fuel_weight", settings.FUEL_WEIGHT)),
        risk_weight=float(getattr(plan, "risk_weight", settings.RISK_WEIGHT)),
        data_source=str(getattr(plan, "data_source", settings.DATA_SOURCE)),
        demo_mode=bool(getattr(plan, "demo_mode", True)),
        plan_id=str(getattr(plan, "id", None) or getattr(plan, "plan_id", None) or "") or None,
        name=str(getattr(plan, "name", "Mission Plan")),
    )


@dataclass(frozen=True)
class PipelineResult:
    """Immutable domain representation of an end-to-end planning pipeline execution."""

    plan_id: Optional[str]
    run_id: Optional[str]
    status: str  # "completed", "failed"
    mode: str  # "live", "cache", "demo"
    started_at: datetime
    completed_at: Optional[datetime]

    # Ingestion provenance
    source: str
    ingestion_mode: str
    fetched_at: Optional[datetime]
    data_age_seconds: Optional[float]
    catalog_records_seen: int
    catalog_records_accepted: int
    catalog_records_rejected: int
    snapshot_id: Optional[str]

    # Candidate metrics
    candidate_count: int

    # Fuel metrics
    fuel_evaluated_count: int
    within_budget_count: int
    out_of_budget_count: int

    # Screening metrics
    debris_objects_considered: int
    debris_objects_skipped: int
    coarse_pair_hits: int
    conjunction_event_count: int

    # Risk metrics
    risk_assessment_count: int

    # Ranking metrics
    ranked_candidate_count: int

    # Result models
    ranked_candidates: List[RankedCandidate] = field(default_factory=list)
    risk_assessments: Dict[str, RiskAssessment] = field(default_factory=dict)
    conjunction_events: List[ConjunctionEventResult] = field(default_factory=list)

    # Diagnostics
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert pipeline result to dictionary representation."""
        return {
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "status": self.status,
            "mode": self.mode,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "source": self.source,
            "ingestion_mode": self.ingestion_mode,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "data_age_seconds": self.data_age_seconds,
            "catalog_records_seen": self.catalog_records_seen,
            "catalog_records_accepted": self.catalog_records_accepted,
            "catalog_records_rejected": self.catalog_records_rejected,
            "snapshot_id": self.snapshot_id,
            "candidate_count": self.candidate_count,
            "fuel_evaluated_count": self.fuel_evaluated_count,
            "within_budget_count": self.within_budget_count,
            "out_of_budget_count": self.out_of_budget_count,
            "debris_objects_considered": self.debris_objects_considered,
            "debris_objects_skipped": self.debris_objects_skipped,
            "coarse_pair_hits": self.coarse_pair_hits,
            "conjunction_event_count": self.conjunction_event_count,
            "risk_assessment_count": self.risk_assessment_count,
            "ranked_candidate_count": self.ranked_candidate_count,
            "ranked_candidates": [rc.to_dict() for rc in self.ranked_candidates],
            "risk_assessments": {k: v.to_dict() for k, v in self.risk_assessments.items()},
            "conjunction_events": [
                asdict(ev) if hasattr(ev, "__dataclass_fields__") else (ev.to_dict() if hasattr(ev, "to_dict") else dict(ev))
                for ev in self.conjunction_events
            ],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }



class PipelineService:
    """Service executing synchronous end-to-end planning pipeline runs."""

    def __init__(
        self,
        ingestion_service: Optional[IngestionService] = None,
        screening_service: Optional[ScreeningService] = None,
        ranking_service: Optional[RankingService] = None,
    ):
        self.ingestion_service = ingestion_service or IngestionService()
        self.screening_service = screening_service or ScreeningService()
        self.ranking_service = ranking_service or RankingService()

    def run_pipeline(
        self,
        plan: Any,
        db: Optional[Session] = None,
        run_id: Optional[str] = None,
        debris_catalog: Optional[List[CanonicalElementRecord]] = None,
        force_refresh_catalog: bool = False,
        raise_on_failure: bool = True,
    ) -> PipelineResult:
        """Synchronously execute complete D-DATO planning pipeline.

        Args:
            plan: Plan ORM model, PlanParameters, or dictionary of planning parameters.
            db: Optional SQLAlchemy database session for persistence and lifecycle updates.
            run_id: Optional existing Run ID to attach execution to.
            debris_catalog: Optional pre-loaded catalog records (bypasses ingestion fetch).
            force_refresh_catalog: Whether to force cache bypass during ingestion.
            raise_on_failure: If True, raises PipelineStageError on failure; if False, returns failed PipelineResult.

        Returns:
            PipelineResult domain object containing complete metrics, rankings, and events.
        """
        started_at = now_utc()
        warnings: List[str] = []
        errors: List[str] = []
        current_stage = "initialization"

        # 1. Parameter extraction and normalization
        plan_params = plan_orm_to_parameters(plan)
        effective_run_id = run_id or (uuid.uuid4().hex)

        # 2. Database Run record initialization
        run_repo = RunRepository(db) if db is not None else None
        if run_repo and run_id:
            run_repo.update_status(
                run_id=effective_run_id,
                status=RunStatus.running.value,
                progress_percent=0.0,
                current_stage="ingestion",
                message="Starting planning pipeline",
            )

        logger.info(
            "Starting D-DATO planning pipeline [run_id=%s, plan_id=%s, demo_mode=%s]",
            effective_run_id,
            plan_params.plan_id,
            plan_params.demo_mode,
        )

        try:
            # -------------------------------------------------------------
            # Stage 1: Ingestion
            # -------------------------------------------------------------
            current_stage = "ingestion"
            if run_repo and run_id:
                run_repo.update_status(
                    run_id=effective_run_id,
                    status=RunStatus.running.value,
                    progress_percent=5.0,
                    current_stage=current_stage,
                    message="Ingesting space debris catalog",
                )

            ingestion_mode = "demo" if plan_params.demo_mode else "cache"
            fetched_at = started_at
            data_age_sec = 0.0
            seen_cnt = 0
            accepted_cnt = 0
            rejected_cnt = 0
            snapshot_id = None
            source_name = "demo" if plan_params.demo_mode else plan_params.data_source

            if debris_catalog is not None:
                # Custom or mocked catalog supplied by caller
                records = list(debris_catalog)
                seen_cnt = len(records)
                accepted_cnt = len(records)
                data_age_sec = max(0.0, (now_utc() - (records[0].fetched_at if records and records[0].fetched_at else started_at)).total_seconds())
                logger.info("Using caller-provided catalog with %d records", len(records))
            else:
                # Standard ingestion flow adhering to P4 caching policy
                ingest_source = "demo" if plan_params.demo_mode else plan_params.data_source
                try:
                    ingest_res: IngestionResult = self.ingestion_service.ingest_catalog(
                        db=db,
                        source=ingest_source,
                        force_refresh=force_refresh_catalog,
                        apply_filter=True,
                    )
                    records = ingest_res.records
                    source_name = ingest_res.source
                    ingestion_mode = ingest_res.mode
                    fetched_at = ingest_res.fetched_at
                    data_age_sec = ingest_res.data_age_seconds
                    seen_cnt = ingest_res.total_records_seen
                    accepted_cnt = ingest_res.accepted_records
                    rejected_cnt = ingest_res.rejected_records
                    snapshot_id = ingest_res.snapshot_id
                    warnings.extend(ingest_res.warnings)
                except Exception as ie:
                    raise PipelineStageError("ingestion", f"Catalog ingestion failed: {ie}", ie) from ie

            logger.info("Ingestion stage complete: %d accepted debris records (mode=%s)", len(records), ingestion_mode)

            # -------------------------------------------------------------
            # Stage 2: Candidate Generation
            # -------------------------------------------------------------
            current_stage = "candidate_generation"
            if run_repo and run_id:
                run_repo.update_status(
                    run_id=effective_run_id,
                    status=RunStatus.running.value,
                    progress_percent=15.0,
                    current_stage=current_stage,
                    message="Generating candidate orbit grid",
                )

            gen_config = CandidateGenerationConfig(
                epoch_start=plan_params.epoch_start,
                altitude_min_km=plan_params.altitude_min_km,
                altitude_max_km=plan_params.altitude_max_km,
                altitude_step_km=plan_params.altitude_step_km,
                inclination_min_deg=plan_params.inclination_min_deg,
                inclination_max_deg=plan_params.inclination_max_deg,
                inclination_step_deg=plan_params.inclination_step_deg,
                delay_min_minutes=plan_params.delay_min_minutes,
                delay_max_minutes=plan_params.delay_max_minutes,
                delay_step_minutes=plan_params.delay_step_minutes,
                base_raan_deg=plan_params.raan_deg,
                u0_deg=plan_params.u0_deg,
                raan_delay_coupling_deg_per_min=plan_params.raan_delay_coupling_deg_per_min,
            )

            try:
                candidates: List[CandidateOrbit] = generate_candidates(gen_config)
            except Exception as ge:
                raise PipelineStageError("candidate_generation", f"Candidate generation failed: {ge}", ge) from ge

            if len(candidates) == 0:
                raise PipelineStageError("candidate_generation", "Candidate generation produced zero candidates.")

            logger.info("Candidate generation complete: %d candidates generated", len(candidates))

            # -------------------------------------------------------------
            # Stage 3: Fuel / Delta-V Estimation
            # -------------------------------------------------------------
            current_stage = "fuel_estimation"
            if run_repo and run_id:
                run_repo.update_status(
                    run_id=effective_run_id,
                    status=RunStatus.running.value,
                    progress_percent=25.0,
                    current_stage=current_stage,
                    message="Calculating maneuver delta-v and propellant budgets",
                )

            fuel_estimates: Dict[str, DeltaVEstimate] = {}
            for cand in candidates:
                try:
                    f_est = evaluate_candidate_fuel(
                        candidate=cand,
                        reference_altitude_km=plan_params.reference_altitude_km,
                        reference_inclination_deg=plan_params.reference_inclination_deg,
                        spacecraft_mass_kg=plan_params.spacecraft_mass_kg,
                        isp_seconds=plan_params.isp_seconds,
                        dv_budget_m_s=plan_params.dv_budget_m_s,
                    )
                    fuel_estimates[cand.candidate_id] = f_est
                except Exception as fe:
                    raise PipelineStageError(
                        "fuel_estimation",
                        f"Fuel calculation failed for candidate {cand.candidate_id}: {fe}",
                        fe,
                    ) from fe

            fuel_eval_count = len(fuel_estimates)
            within_budget_count = sum(1 for f in fuel_estimates.values() if f.within_dv_budget)
            out_of_budget_count = fuel_eval_count - within_budget_count
            logger.info(
                "Fuel estimation complete: %d evaluated (%d within budget, %d above budget)",
                fuel_eval_count,
                within_budget_count,
                out_of_budget_count,
            )

            # -------------------------------------------------------------
            # Stage 4: Conjunction Screening & TCA Refinement
            # -------------------------------------------------------------
            current_stage = "conjunction_screening"
            if run_repo and run_id:
                run_repo.update_status(
                    run_id=effective_run_id,
                    status=RunStatus.running.value,
                    progress_percent=35.0,
                    current_stage=current_stage,
                    message="Performing close-approach screening and TCA numerical refinement",
                )

            norm_debris = self.screening_service.prepare_debris_input(records)
            conjunction_events_by_cand: Dict[str, List[ConjunctionEventResult]] = {}
            all_conjunction_events: List[ConjunctionEventResult] = []
            debris_considered_total = 0
            debris_skipped_total = 0
            coarse_hits_total = 0

            for cand in candidates:
                try:
                    report: ScreeningReport = screen_candidate_against_debris(
                        candidate=cand,
                        debris_records=norm_debris,
                        screening_days=plan_params.screening_days,
                    )
                    conjunction_events_by_cand[cand.candidate_id] = report.events
                    all_conjunction_events.extend(report.events)
                    debris_considered_total += report.debris_objects_considered
                    debris_skipped_total += report.debris_objects_skipped
                    coarse_hits_total += report.coarse_pair_hits
                except Exception as se:
                    raise PipelineStageError(
                        "conjunction_screening",
                        f"Conjunction screening failed for candidate {cand.candidate_id}: {se}",
                        se,
                    ) from se

            logger.info(
                "Conjunction screening complete: %d events retained across %d candidates (%d coarse hits)",
                len(all_conjunction_events),
                len(candidates),
                coarse_hits_total,
            )

            # -------------------------------------------------------------
            # Stage 5: Screening Risk Assessment
            # -------------------------------------------------------------
            current_stage = "risk_assessment"
            if run_repo and run_id:
                run_repo.update_status(
                    run_id=effective_run_id,
                    status=RunStatus.running.value,
                    progress_percent=75.0,
                    current_stage=current_stage,
                    message="Evaluating physical close-approach risk screening scores",
                )

            risk_assessments: Dict[str, RiskAssessment] = {}
            for cand in candidates:
                cand_events = conjunction_events_by_cand.get(cand.candidate_id, [])
                try:
                    assessment = assess_candidate_risk(
                        candidate=cand,
                        conjunction_events=cand_events,
                        data_age_seconds=data_age_sec,
                    )
                    risk_assessments[cand.candidate_id] = assessment
                except Exception as re:
                    raise PipelineStageError(
                        "risk_assessment",
                        f"Risk assessment failed for candidate {cand.candidate_id}: {re}",
                        re,
                    ) from re

            logger.info("Risk assessment complete: %d candidates scored", len(risk_assessments))

            # -------------------------------------------------------------
            # Stage 6: Multi-Objective Candidate Ranking
            # -------------------------------------------------------------
            current_stage = "ranking"
            if run_repo and run_id:
                run_repo.update_status(
                    run_id=effective_run_id,
                    status=RunStatus.running.value,
                    progress_percent=85.0,
                    current_stage=current_stage,
                    message="Ranking candidate deployment windows",
                )

            try:
                ranked_candidates: List[RankedCandidate] = rank_candidates(
                    candidates=candidates,
                    fuel_estimates=fuel_estimates,
                    risk_assessments=risk_assessments,
                    fuel_weight=plan_params.fuel_weight,
                    risk_weight=plan_params.risk_weight,
                )
            except Exception as rke:
                raise PipelineStageError("ranking", f"Candidate ranking failed: {rke}", rke) from rke

            logger.info("Candidate ranking complete: %d candidates ranked", len(ranked_candidates))

            # -------------------------------------------------------------
            # Stage 7: Persistence
            # -------------------------------------------------------------
            current_stage = "persistence"
            if run_repo and run_id:
                run_repo.update_status(
                    run_id=effective_run_id,
                    status=RunStatus.running.value,
                    progress_percent=95.0,
                    current_stage=current_stage,
                    message="Persisting candidate and conjunction records",
                )

            if db is not None and effective_run_id:
                try:
                    self._persist_pipeline_results(
                        db=db,
                        run_id=effective_run_id,
                        ranked_candidates=ranked_candidates,
                        conjunction_events=all_conjunction_events,
                    )
                except Exception as pe:
                    raise PipelineStageError("persistence", f"Database persistence failed: {pe}", pe) from pe

            # -------------------------------------------------------------
            # Completion
            # -------------------------------------------------------------
            completed_at = now_utc()
            if run_repo and run_id:
                run_repo.update_status(
                    run_id=effective_run_id,
                    status=RunStatus.completed.value,
                    progress_percent=100.0,
                    current_stage="completed",
                    message="Planning pipeline completed successfully",
                )

            logger.info(
                "Planning pipeline run %s completed successfully in %.2fs",
                effective_run_id,
                (completed_at - started_at).total_seconds(),
            )

            return PipelineResult(
                plan_id=plan_params.plan_id,
                run_id=effective_run_id,
                status="completed",
                mode=ingestion_mode,
                started_at=started_at,
                completed_at=completed_at,
                source=source_name,
                ingestion_mode=ingestion_mode,
                fetched_at=fetched_at,
                data_age_seconds=data_age_sec,
                catalog_records_seen=seen_cnt,
                catalog_records_accepted=accepted_cnt,
                catalog_records_rejected=rejected_cnt,
                snapshot_id=snapshot_id,
                candidate_count=len(candidates),
                fuel_evaluated_count=fuel_eval_count,
                within_budget_count=within_budget_count,
                out_of_budget_count=out_of_budget_count,
                debris_objects_considered=debris_considered_total,
                debris_objects_skipped=debris_skipped_total,
                coarse_pair_hits=coarse_hits_total,
                conjunction_event_count=len(all_conjunction_events),
                risk_assessment_count=len(risk_assessments),
                ranked_candidate_count=len(ranked_candidates),
                ranked_candidates=ranked_candidates,
                risk_assessments=risk_assessments,
                conjunction_events=all_conjunction_events,
                warnings=warnings,
                errors=[],
            )

        except Exception as exc:
            completed_at = now_utc()
            err_msg = str(exc)
            errors.append(err_msg)
            logger.error("Planning pipeline failed at stage '%s': %s", current_stage, exc, exc_info=True)

            if db is not None and effective_run_id:
                try:
                    db.rollback()
                    if run_repo:
                        run_repo.update_status(
                            run_id=effective_run_id,
                            status=RunStatus.failed.value,
                            current_stage="failed",
                            message=f"Pipeline failed at stage {current_stage}",
                            error_message=err_msg,
                        )
                except Exception as rollback_err:
                    logger.error("Failed to mark run as failed in database: %s", rollback_err)

            if raise_on_failure:
                if isinstance(exc, PipelineStageError):
                    raise
                raise PipelineStageError(current_stage, err_msg, exc) from exc

            return PipelineResult(
                plan_id=plan_params.plan_id,
                run_id=effective_run_id,
                status="failed",
                mode="demo" if plan_params.demo_mode else "cache",
                started_at=started_at,
                completed_at=completed_at,
                source=plan_params.data_source,
                ingestion_mode="demo" if plan_params.demo_mode else "cache",
                fetched_at=None,
                data_age_seconds=None,
                catalog_records_seen=0,
                catalog_records_accepted=0,
                catalog_records_rejected=0,
                snapshot_id=None,
                candidate_count=0,
                fuel_evaluated_count=0,
                within_budget_count=0,
                out_of_budget_count=0,
                debris_objects_considered=0,
                debris_objects_skipped=0,
                coarse_pair_hits=0,
                conjunction_event_count=0,
                risk_assessment_count=0,
                ranked_candidate_count=0,
                ranked_candidates=[],
                risk_assessments={},
                conjunction_events=[],
                warnings=warnings,
                errors=errors,
            )

    def _persist_pipeline_results(
        self,
        db: Session,
        run_id: str,
        ranked_candidates: List[RankedCandidate],
        conjunction_events: List[ConjunctionEventResult],
    ) -> None:
        """Persist candidate and conjunction event records within an atomic transaction boundary."""
        cand_repo = CandidateRepository(db)
        event_repo = ConjunctionEventRepository(db)

        # 1. Bulk persist candidates
        cand_models: List[Candidate] = []
        cand_db_id_map: Dict[str, str] = {}
        for rc in ranked_candidates:
            cand_db_id = generate_uuid()
            cand_db_id_map[rc.candidate_id] = cand_db_id
            cand_models.append(
                Candidate(
                    id=cand_db_id,
                    run_id=run_id,
                    altitude_km=rc.altitude_km,
                    inclination_deg=rc.inclination_deg,
                    raan_deg=rc.raan_deg,
                    u0_deg=rc.u0_deg,
                    deployment_delay_minutes=rc.deployment_delay_minutes,
                    predicted_raan_deg=rc.raan_deg,
                    delta_v_m_s=rc.delta_v_m_s,
                    propellant_mass_kg=rc.propellant_mass_kg,
                    fuel_fraction=rc.fuel_fraction,
                    within_dv_budget=rc.within_dv_budget,
                    risk_score=rc.risk_score,
                    rank=rc.rank,
                )
            )

        cand_repo.bulk_create(cand_models)

        # 2. Look up DebrisObject database IDs by NORAD ID for foreign-key consistency
        debris_stmt = select(DebrisObject.id, DebrisObject.norad_id)
        deb_rows = db.execute(debris_stmt).all()
        debris_id_map = {norad: deb_id for deb_id, norad in deb_rows}

        # 3. Bulk persist conjunction events
        event_models: List[ConjunctionEvent] = []
        for ev in conjunction_events:
            deb_db_id = debris_id_map.get(ev.debris_norad_id, ev.debris_object_id)
            c_db_id = cand_db_id_map.get(ev.candidate_id)
            event_models.append(
                conjunction_result_to_model(
                    result=ev,
                    run_id=run_id,
                    candidate_db_id=c_db_id,
                    debris_db_id=deb_db_id,
                )
            )

        if event_models:
            event_repo.bulk_create(event_models)

        db.commit()


def execute_planning_pipeline(
    plan: Any,
    db: Optional[Session] = None,
    run_id: Optional[str] = None,
    **kwargs: Any,
) -> PipelineResult:
    """Convenience helper function executing the planning pipeline synchronously."""
    service = PipelineService()
    return service.run_pipeline(plan=plan, db=db, run_id=run_id, **kwargs)
