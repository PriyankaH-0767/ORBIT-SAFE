"""Conjunction screening orchestration service.

Coordinates candidate orbit propagation, catalog prefiltering, coarse spatial
filtering, bounded numerical TCA refinement, event deduplication, and database persistence.
Keeps core orbital algorithms decoupled from SQLAlchemy persistence models.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.conjunction import (
    ConjunctionEventResult,
    ScreeningReport,
    screen_candidate_against_debris,
)
from app.core.risk import assess_candidate_risk, RiskAssessment
from app.data.parser import CanonicalElementRecord
from app.db.models import DebrisObject, ConjunctionEvent, Candidate
from app.db.repositories import ConjunctionEventRepository, CandidateRepository


def debris_model_to_canonical(debris: DebrisObject) -> CanonicalElementRecord:
    """Map SQLAlchemy DebrisObject ORM model to domain CanonicalElementRecord.

    Preserves full precision Keplerian elements, format, and identifiers.
    """
    return CanonicalElementRecord(
        object_name=debris.object_name,
        norad_id=debris.norad_id,
        epoch=debris.epoch,
        inclination_deg=debris.inclination_deg or 0.0,
        eccentricity=debris.eccentricity or 0.0,
        raan_deg=debris.raan_deg or 0.0,
        arg_perigee_deg=debris.arg_perigee_deg or 0.0,
        mean_anomaly_deg=debris.mean_anomaly_deg or 0.0,
        mean_motion_rev_per_day=debris.mean_motion_rev_per_day or 0.0,
        object_id=debris.object_id,
        classification=debris.classification or "U",
        mean_motion_dot=debris.mean_motion_dot,
        mean_motion_ddot=debris.mean_motion_ddot,
        bstar=debris.bstar,
        ephemeris_type=debris.ephemeris_type or 0,
        element_set_number=debris.element_set_no,
        revolution_number_at_epoch=debris.rev_at_epoch,
        source=debris.source,
        element_format=debris.element_format or "tle",
        raw_tle_line1=debris.tle_line1,
        raw_tle_line2=debris.tle_line2,
        raw_source_record=debris.raw_source_payload,
        fetched_at=debris.fetched_at,
        data_age_seconds=debris.data_age_seconds,
    )


def conjunction_result_to_model(
    result: ConjunctionEventResult,
    run_id: str,
    candidate_db_id: Optional[str] = None,
    debris_db_id: Optional[str] = None,
) -> ConjunctionEvent:
    """Map domain ConjunctionEventResult to SQLAlchemy ConjunctionEvent model.

    NOTE: threshold_km is recorded as 25.0 (the final acceptance threshold).
    """
    cand_id = candidate_db_id if candidate_db_id is not None else result.candidate_id
    deb_id = debris_db_id if debris_db_id is not None else result.debris_object_id

    return ConjunctionEvent(
        run_id=run_id,
        candidate_id=cand_id,
        debris_object_id=deb_id,
        tca=result.tca,
        miss_distance_km=result.miss_distance_km,
        relative_velocity_km_s=result.relative_velocity_km_s,
        threshold_km=25.0,
        screening_source="ddato",
    )


class ScreeningService:
    """Service coordinating candidate propagation, conjunction screening, and persistence."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def prepare_debris_input(
        self,
        debris_records: List[Union[CanonicalElementRecord, DebrisObject, Tuple[Any, Optional[str]]]],
    ) -> List[Tuple[CanonicalElementRecord, Optional[str]]]:
        """Normalize mixed debris inputs into a uniform list of (CanonicalElementRecord, db_id) tuples."""
        prepared: List[Tuple[CanonicalElementRecord, Optional[str]]] = []
        for item in debris_records:
            if isinstance(item, tuple):
                rec, db_id = item
                if isinstance(rec, DebrisObject):
                    prepared.append((debris_model_to_canonical(rec), db_id or rec.id))
                else:
                    prepared.append((rec, db_id))
            elif isinstance(item, DebrisObject):
                prepared.append((debris_model_to_canonical(item), item.id))
            elif isinstance(item, CanonicalElementRecord):
                prepared.append((item, getattr(item, "id", None)))
            else:
                raise TypeError(f"Unsupported debris input type: {type(item)}")
        return prepared

    def screen_candidate_against_catalog(
        self,
        candidate: Any,
        debris_records: List[Union[CanonicalElementRecord, DebrisObject, Tuple[Any, Optional[str]]]],
        screening_days: Optional[float] = None,
        coarse_step_seconds: Optional[float] = None,
        coarse_threshold_km: Optional[float] = None,
        event_threshold_km: Optional[float] = None,
        time_chunk_seconds: Optional[float] = None,
        max_events_per_candidate: Optional[int] = None,
    ) -> ScreeningReport:
        """Screen a single candidate orbit against a catalog of debris objects."""
        norm_debris = self.prepare_debris_input(debris_records)

        return screen_candidate_against_debris(
            candidate=candidate,
            debris_records=norm_debris,
            screening_days=screening_days,
            coarse_step_seconds=coarse_step_seconds,
            coarse_threshold_km=coarse_threshold_km,
            event_threshold_km=event_threshold_km,
            time_chunk_seconds=time_chunk_seconds,
            max_events_per_candidate=max_events_per_candidate,
        )

    def screen_candidates(
        self,
        candidates: List[Any],
        debris_records: List[Union[CanonicalElementRecord, DebrisObject, Tuple[Any, Optional[str]]]],
        screening_days: Optional[float] = None,
        coarse_step_seconds: Optional[float] = None,
        coarse_threshold_km: Optional[float] = None,
        event_threshold_km: Optional[float] = None,
        time_chunk_seconds: Optional[float] = None,
        max_events_per_candidate: Optional[int] = None,
    ) -> List[ScreeningReport]:
        """Screen multiple candidate orbits against a catalog of debris objects."""
        norm_debris = self.prepare_debris_input(debris_records)
        reports: List[ScreeningReport] = []

        for candidate in candidates:
            report = screen_candidate_against_debris(
                candidate=candidate,
                debris_records=norm_debris,
                screening_days=screening_days,
                coarse_step_seconds=coarse_step_seconds,
                coarse_threshold_km=coarse_threshold_km,
                event_threshold_km=event_threshold_km,
                time_chunk_seconds=time_chunk_seconds,
                max_events_per_candidate=max_events_per_candidate,
            )
            reports.append(report)

        return reports

    def persist_conjunction_events(
        self,
        db: Session,
        run_id: str,
        events: List[ConjunctionEventResult],
        candidate_id_map: Optional[Dict[str, str]] = None,
        debris_id_map: Optional[Dict[str, str]] = None,
    ) -> List[ConjunctionEvent]:
        """Persist a list of domain ConjunctionEventResult objects into the database."""
        if not events:
            return []

        models: List[ConjunctionEvent] = []
        for ev in events:
            cand_db_id = (candidate_id_map or {}).get(ev.candidate_id, ev.candidate_id)
            deb_db_id = (debris_id_map or {}).get(ev.debris_norad_id, ev.debris_object_id)
            models.append(
                conjunction_result_to_model(
                    result=ev,
                    run_id=run_id,
                    candidate_db_id=cand_db_id,
                    debris_db_id=deb_db_id,
                )
            )

        repo = ConjunctionEventRepository(db)
        return repo.bulk_create(models)

    def screen_and_persist(
        self,
        db: Session,
        run_id: str,
        candidate: Any,
        debris_records: List[Union[CanonicalElementRecord, DebrisObject, Tuple[Any, Optional[str]]]],
        screening_days: Optional[float] = None,
        candidate_id_map: Optional[Dict[str, str]] = None,
        debris_id_map: Optional[Dict[str, str]] = None,
    ) -> ScreeningReport:
        """Screen candidate and persist all qualifying conjunction events in one atomic call."""
        report = self.screen_candidate_against_catalog(
            candidate=candidate,
            debris_records=debris_records,
            screening_days=screening_days,
        )
        if report.events:
            self.persist_conjunction_events(
                db=db,
                run_id=run_id,
                events=report.events,
                candidate_id_map=candidate_id_map,
                debris_id_map=debris_id_map,
            )
        return report

    def assess_candidate_risk(
        self,
        candidate: Any,
        conjunction_events: Optional[List[Any]] = None,
        data_age_seconds: Optional[float] = None,
    ) -> RiskAssessment:
        """Compute RiskAssessment domain result for a candidate from its conjunction events."""
        return assess_candidate_risk(
            candidate=candidate,
            conjunction_events=conjunction_events,
            data_age_seconds=data_age_seconds,
        )

    def assess_run_risk(
        self,
        candidates: List[Any],
        conjunction_events: Optional[List[Any]] = None,
        data_age_seconds: Optional[float] = None,
    ) -> Dict[str, RiskAssessment]:
        """Group conjunction events by candidate and assess risk for each candidate.

        NOTE: Does NOT sort or rank candidates.
        """
        events_by_cand: Dict[str, List[Any]] = defaultdict(list)
        for ev in (conjunction_events or []):
            c_id = getattr(ev, "candidate_id", None) or (ev.get("candidate_id") if isinstance(ev, dict) else None)
            if c_id:
                events_by_cand[str(c_id)].append(ev)

        assessments: Dict[str, RiskAssessment] = {}
        for cand in candidates:
            c_id = str(getattr(cand, "candidate_id", None) or getattr(cand, "id", None) or cand)
            cand_events = events_by_cand.get(c_id, [])
            assessments[c_id] = assess_candidate_risk(
                candidate=cand,
                conjunction_events=cand_events,
                data_age_seconds=data_age_seconds,
            )
        return assessments

    def update_candidate_risk_scores(
        self,
        db: Session,
        assessments: Dict[str, RiskAssessment],
    ) -> int:
        """Persist risk_score values to Candidate database entities."""
        updated_count = 0
        repo = CandidateRepository(db)
        for cand_id, assessment in assessments.items():
            candidate = repo.get_by_id(cand_id)
            if candidate:
                candidate.risk_score = assessment.risk_score
                updated_count += 1
        if updated_count > 0:
            db.commit()
        return updated_count
