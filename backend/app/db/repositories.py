"""Database repository implementations for D-DATO ORM entities.

Repositories handle persistence, atomic transaction boundaries, and query retrieval.
They contain persistence logic only without embedding scientific ranking or screening logic.
"""

from typing import Dict, List, Optional, Tuple, Union
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Plan,
    Run,
    Candidate,
    DebrisObject,
    DataSnapshot,
    ConjunctionEvent,
    ValidationRecord,
    RunStatus,
)
from app.utils.time import now_utc


class PlanRepository:
    """Repository handling persistence for Plan entities."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, plan: Plan) -> Plan:
        """Persist a new mission plan."""
        try:
            self.db.add(plan)
            self.db.commit()
            self.db.refresh(plan)
            return plan
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, plan_id: str) -> Optional[Plan]:
        """Retrieve a mission plan by its unique string ID."""
        stmt = select(Plan).where(Plan.id == plan_id)
        return self.db.scalars(stmt).first()

    def list_all(self, limit: int = 100) -> List[Plan]:
        """List all stored mission plans ordered by creation time descending."""
        stmt = select(Plan).order_by(desc(Plan.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())


class RunRepository:
    """Repository handling execution state and progress tracking for Run entities."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, run: Run) -> Run:
        """Persist a new screening run."""
        try:
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, run_id: str) -> Optional[Run]:
        """Retrieve a screening run by ID."""
        stmt = select(Run).where(Run.id == run_id)
        return self.db.scalars(stmt).first()

    def update_status(
        self,
        run_id: str,
        status: Union[RunStatus, str],
        progress_percent: Optional[float] = None,
        current_stage: Optional[str] = None,
        message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Run]:
        """Atomically update run status, progress, and stage."""
        run = self.get_by_id(run_id)
        if not run:
            return None

        status_str = status.value if isinstance(status, RunStatus) else str(status)
        try:
            run.status = status_str
            if progress_percent is not None:
                run.progress_percent = progress_percent
            if current_stage is not None:
                run.current_stage = current_stage
            if message is not None:
                run.message = message
            if error_message is not None:
                run.error_message = error_message

            # Lifecycle timestamps
            if status_str == RunStatus.running.value and not run.started_at:
                run.started_at = now_utc()
            elif status_str in (RunStatus.completed.value, RunStatus.failed.value, RunStatus.cancelled.value):
                if not run.completed_at:
                    run.completed_at = now_utc()

            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception:
            self.db.rollback()
            raise

    def list_by_plan(self, plan_id: str) -> List[Run]:
        """List all runs linked to a given plan ID."""
        stmt = select(Run).where(Run.plan_id == plan_id).order_by(desc(Run.created_at))
        return list(self.db.scalars(stmt).all())


class CandidateRepository:
    """Repository handling persistence for Candidate deployment orbits."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, candidate: Candidate) -> Candidate:
        """Persist a single candidate deployment option."""
        try:
            self.db.add(candidate)
            self.db.commit()
            self.db.refresh(candidate)
            return candidate
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, candidate_id: str) -> Optional[Candidate]:
        """Retrieve a candidate orbit by ID."""
        stmt = select(Candidate).where(Candidate.id == candidate_id)
        return self.db.scalars(stmt).first()

    def bulk_create(self, candidates: List[Candidate]) -> List[Candidate]:
        """Persist multiple candidate orbits in a single atomic transaction."""
        if not candidates:
            return []
        try:
            self.db.add_all(candidates)
            self.db.commit()
            for cand in candidates:
                self.db.refresh(cand)
            return candidates
        except Exception:
            self.db.rollback()
            raise

    def list_by_run(self, run_id: str, limit: Optional[int] = None) -> List[Candidate]:
        """List evaluated candidate options for a run, ordered by rank."""
        stmt = select(Candidate).where(Candidate.run_id == run_id).order_by(Candidate.rank)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).all())

    def list_by_run_paginated(
        self,
        run_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Candidate], int]:
        """Retrieve candidates for a run ordered by rank ASC with limit and offset, and total count."""
        total_stmt = select(func.count(Candidate.id)).where(Candidate.run_id == run_id)
        total = self.db.scalar(total_stmt) or 0

        stmt = (
            select(Candidate)
            .where(Candidate.run_id == run_id)
            .order_by(Candidate.rank.asc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).all())
        return items, total

    def list_by_run_for_heatmap(
        self,
        run_id: str,
        inclination_deg: Optional[float] = None,
    ) -> List[Candidate]:
        """Retrieve evaluated candidate orbits for a run ordered deterministically for heatmap generation.

        Ordered by inclination_deg ASC, altitude_km ASC, deployment_delay_minutes ASC.
        Optionally filters by inclination_deg using floating-point tolerance bounds.
        """
        stmt = (
            select(Candidate)
            .where(Candidate.run_id == run_id)
            .order_by(
                Candidate.inclination_deg.asc(),
                Candidate.altitude_km.asc(),
                Candidate.deployment_delay_minutes.asc(),
            )
        )
        if inclination_deg is not None:
            stmt = stmt.where(
                Candidate.inclination_deg >= inclination_deg - 1e-4,
                Candidate.inclination_deg <= inclination_deg + 1e-4,
            )
        return list(self.db.scalars(stmt).all())

    def bulk_update_ranks(self, rank_map: Dict[str, int]) -> int:
        """Atomically update ranks for multiple candidates by ID.

        Preserves all physical metrics, delta-v, risk, and within_dv_budget.
        Rolls back on error.
        """
        if not rank_map:
            return 0
        try:
            updated = 0
            for cand_id, r in rank_map.items():
                cand = self.get_by_id(cand_id)
                if cand:
                    cand.rank = r
                    updated += 1
            self.db.commit()
            return updated
        except Exception:
            self.db.rollback()
            raise



class DebrisObjectRepository:
    """Repository handling persistence and lookup for cataloged DebrisObject entities."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_norad_id(self, norad_id: str, source: Optional[str] = None) -> Optional[DebrisObject]:
        """Find a debris object by its NORAD catalog ID, optionally filtering by source."""
        stmt = select(DebrisObject).where(DebrisObject.norad_id == norad_id)
        if source:
            stmt = stmt.where(DebrisObject.source == source)
        return self.db.scalars(stmt).first()

    def create_or_update(self, debris: DebrisObject) -> DebrisObject:
        """Persist or update a space debris object based on NORAD ID and source."""
        try:
            if not debris.element_format:
                debris.element_format = "tle"
            existing = self.get_by_norad_id(debris.norad_id, debris.source)
            if existing:
                existing.object_name = debris.object_name
                if debris.object_id is not None:
                    existing.object_id = debris.object_id
                if debris.classification is not None:
                    existing.classification = debris.classification
                if debris.element_format:
                    existing.element_format = debris.element_format
                if debris.tle_line1 is not None:
                    existing.tle_line1 = debris.tle_line1
                if debris.tle_line2 is not None:
                    existing.tle_line2 = debris.tle_line2
                existing.epoch = debris.epoch
                if debris.inclination_deg is not None:
                    existing.inclination_deg = debris.inclination_deg
                if debris.eccentricity is not None:
                    existing.eccentricity = debris.eccentricity
                if debris.raan_deg is not None:
                    existing.raan_deg = debris.raan_deg
                if debris.arg_perigee_deg is not None:
                    existing.arg_perigee_deg = debris.arg_perigee_deg
                if debris.mean_anomaly_deg is not None:
                    existing.mean_anomaly_deg = debris.mean_anomaly_deg
                if debris.mean_motion_rev_per_day is not None:
                    existing.mean_motion_rev_per_day = debris.mean_motion_rev_per_day
                if debris.bstar is not None:
                    existing.bstar = debris.bstar
                if debris.mean_motion_dot is not None:
                    existing.mean_motion_dot = debris.mean_motion_dot
                if debris.mean_motion_ddot is not None:
                    existing.mean_motion_ddot = debris.mean_motion_ddot
                if debris.ephemeris_type is not None:
                    existing.ephemeris_type = debris.ephemeris_type
                if debris.element_set_no is not None:
                    existing.element_set_no = debris.element_set_no
                if debris.rev_at_epoch is not None:
                    existing.rev_at_epoch = debris.rev_at_epoch
                if debris.raw_source_payload is not None:
                    existing.raw_source_payload = debris.raw_source_payload
                existing.fetched_at = debris.fetched_at
                if debris.data_age_seconds is not None:
                    existing.data_age_seconds = debris.data_age_seconds
                self.db.commit()
                self.db.refresh(existing)
                return existing
            else:
                self.db.add(debris)
                self.db.commit()
                self.db.refresh(debris)
                return debris
        except Exception:
            self.db.rollback()
            raise

    def bulk_upsert(self, debris_list: List[DebrisObject]) -> int:
        """Bulk persist or update multiple debris objects atomically. Returns count of processed objects."""
        if not debris_list:
            return 0
        count = 0
        try:
            for item in debris_list:
                if not item.element_format:
                    item.element_format = "tle"
                existing = self.get_by_norad_id(item.norad_id, item.source)
                if existing:
                    existing.object_name = item.object_name
                    if item.object_id is not None:
                        existing.object_id = item.object_id
                    if item.classification is not None:
                        existing.classification = item.classification
                    if item.element_format:
                        existing.element_format = item.element_format
                    if item.tle_line1 is not None:
                        existing.tle_line1 = item.tle_line1
                    if item.tle_line2 is not None:
                        existing.tle_line2 = item.tle_line2
                    existing.epoch = item.epoch
                    if item.inclination_deg is not None:
                        existing.inclination_deg = item.inclination_deg
                    if item.eccentricity is not None:
                        existing.eccentricity = item.eccentricity
                    if item.raan_deg is not None:
                        existing.raan_deg = item.raan_deg
                    if item.arg_perigee_deg is not None:
                        existing.arg_perigee_deg = item.arg_perigee_deg
                    if item.mean_anomaly_deg is not None:
                        existing.mean_anomaly_deg = item.mean_anomaly_deg
                    if item.mean_motion_rev_per_day is not None:
                        existing.mean_motion_rev_per_day = item.mean_motion_rev_per_day
                    if item.bstar is not None:
                        existing.bstar = item.bstar
                    if item.mean_motion_dot is not None:
                        existing.mean_motion_dot = item.mean_motion_dot
                    if item.mean_motion_ddot is not None:
                        existing.mean_motion_ddot = item.mean_motion_ddot
                    if item.ephemeris_type is not None:
                        existing.ephemeris_type = item.ephemeris_type
                    if item.element_set_no is not None:
                        existing.element_set_no = item.element_set_no
                    if item.rev_at_epoch is not None:
                        existing.rev_at_epoch = item.rev_at_epoch
                    if item.raw_source_payload is not None:
                        existing.raw_source_payload = item.raw_source_payload
                    existing.fetched_at = item.fetched_at
                    if item.data_age_seconds is not None:
                        existing.data_age_seconds = item.data_age_seconds
                else:
                    self.db.add(item)
                count += 1
            self.db.commit()
            return count
        except Exception:
            self.db.rollback()
            raise


class ConjunctionEventRepository:
    """Repository handling persistence for close-approach ConjunctionEvent records."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, event: ConjunctionEvent) -> ConjunctionEvent:
        """Persist a single conjunction event."""
        try:
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, event_id: str) -> Optional[ConjunctionEvent]:
        """Retrieve a conjunction event by ID."""
        stmt = select(ConjunctionEvent).where(ConjunctionEvent.id == event_id)
        return self.db.scalars(stmt).first()

    def bulk_create(self, events: List[ConjunctionEvent]) -> List[ConjunctionEvent]:
        """Persist multiple conjunction events in a single atomic transaction."""
        if not events:
            return []
        try:
            self.db.add_all(events)
            self.db.commit()
            for evt in events:
                self.db.refresh(evt)
            return events
        except Exception:
            self.db.rollback()
            raise

    def list_by_run(self, run_id: str) -> List[ConjunctionEvent]:
        """List all conjunction events detected during a specific screening run."""
        stmt = select(ConjunctionEvent).where(ConjunctionEvent.run_id == run_id).order_by(ConjunctionEvent.tca)
        return list(self.db.scalars(stmt).all())

    def list_by_run_paginated(
        self,
        run_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[ConjunctionEvent], int]:
        """Retrieve conjunction events for a run with ordering, limit, offset, and total count.

        Ordering:
        1. TCA ascending
        2. miss_distance ascending
        3. candidate_id ascending
        4. debris ID ascending
        """
        total_stmt = select(func.count(ConjunctionEvent.id)).where(ConjunctionEvent.run_id == run_id)
        total = self.db.scalar(total_stmt) or 0

        stmt = (
            select(ConjunctionEvent)
            .where(ConjunctionEvent.run_id == run_id)
            .options(joinedload(ConjunctionEvent.debris_object))
            .order_by(
                ConjunctionEvent.tca.asc(),
                ConjunctionEvent.miss_distance_km.asc(),
                ConjunctionEvent.candidate_id.asc(),
                ConjunctionEvent.debris_object_id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.scalars(stmt).all())
        return items, total

    def list_by_candidate(self, candidate_id: str) -> List[ConjunctionEvent]:
        """List all conjunction events associated with a specific candidate orbit."""
        stmt = (
            select(ConjunctionEvent)
            .where(ConjunctionEvent.candidate_id == candidate_id)
            .order_by(ConjunctionEvent.tca)
        )
        return list(self.db.scalars(stmt).all())


class DataSnapshotRepository:
    """Repository handling cache metadata and catalog freshness snapshots."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, snapshot: DataSnapshot) -> DataSnapshot:
        """Persist a new data fetch snapshot."""
        try:
            self.db.add(snapshot)
            self.db.commit()
            self.db.refresh(snapshot)
            return snapshot
        except Exception:
            self.db.rollback()
            raise

    def get_latest_by_source(self, source: str) -> Optional[DataSnapshot]:
        """Retrieve the most recent successful data snapshot for a catalog source."""
        stmt = (
            select(DataSnapshot)
            .where(DataSnapshot.source == source)
            .order_by(desc(DataSnapshot.fetched_at))
        )
        return self.db.scalars(stmt).first()


class ValidationRecordRepository:
    """Repository handling external benchmark / SOCRATES comparison records."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, record: ValidationRecord) -> ValidationRecord:
        """Persist an external validation comparison record."""
        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    def list_by_run(self, run_id: str) -> List[ValidationRecord]:
        """List validation records linked to a specific screening run."""
        stmt = select(ValidationRecord).where(ValidationRecord.run_id == run_id).order_by(ValidationRecord.event_time)
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, validation_id: str) -> Optional[ValidationRecord]:
        """Retrieve a validation record by its unique identifier."""
        stmt = select(ValidationRecord).where(ValidationRecord.id == validation_id)
        return self.db.scalars(stmt).first()

    def get_latest_by_run(self, run_id: str) -> Optional[ValidationRecord]:
        """Retrieve the most recently created validation record for a run."""
        stmt = (
            select(ValidationRecord)
            .where(ValidationRecord.run_id == run_id)
            .order_by(desc(ValidationRecord.created_at))
        )
        return self.db.scalars(stmt).first()

