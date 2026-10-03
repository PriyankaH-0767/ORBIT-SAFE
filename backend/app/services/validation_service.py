"""External Conjunction Screening Validation Service (Phase P16).

The original D-DATO specification is authoritative.

Validates D-DATO's persisted conjunction-screening results against an external
validation source (specifically SOCRATES reference datasets).

NON-OPERATIONAL POSITIONING:
Validation means "D-DATO screening result compared with an independently supplied/queried
external close-approach source."
It does NOT mean:
- true collision probability
- operational conjunction assessment
- certified flight safety
- maneuver recommendation
- CDM generation
- launch COLA

This service is strictly read-only with respect to scientific screening results.
D-DATO conjunction screening is NEVER rerun during validation.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from typing import Callable, Generator, List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.data.socrates import (
    SocratesAdapter,
    ValidationSourceError,
    ValidationSourceUnavailableError,
)
from app.db.database import SessionLocal
from app.db.models import ConjunctionEvent, DataSnapshot, Run, ValidationRecord
from app.db.repositories import (
    DataSnapshotRepository,
    RunRepository,
    ValidationRecordRepository,
)
from app.schemas.validation import (
    ValidationDdatoOnlyEvent,
    ValidationExecutionRequest,
    ValidationExternalOnlyEvent,
    ValidationMatch,
    ValidationReferenceEvent,
    ValidationResponse,
    ValidationSummary,
)
from app.utils.time import ensure_utc, format_iso_utc, now_utc

logger = logging.getLogger(__name__)

NON_OPERATIONAL_DISCLAIMER = (
    "NON-OPERATIONAL VALIDATION: D-DATO conjunction validation comparison is external "
    "reference evidence only. It does NOT represent certified flight safety, operational "
    "conjunction assessment, true collision probability, CDM generation, maneuver "
    "planning, or launch COLA."
)


class RunNotFoundError(ValueError):
    """Raised when the specified run_id is not found."""

    def __init__(self, run_id: str):
        super().__init__(f"Run '{run_id}' not found.")
        self.run_id = run_id


class ValidationNotFoundError(ValueError):
    """Raised when the specified validation_id or validation record is not found."""

    def __init__(self, message: str):
        super().__init__(message)


class InvalidValidationRequestError(ValueError):
    """Raised when validation request options are malformed or invalid."""
    pass


def _normalize_norad_id(val: Optional[object]) -> Optional[str]:
    """Normalize NORAD catalog ID string for consistent comparison."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.isdigit():
        return str(int(s))
    return s.upper()


class ValidationService:
    """Service providing external validation comparison and persistence."""

    def __init__(
        self,
        session_factory: Optional[Callable[[], Session]] = None,
        socrates_adapter: Optional[SocratesAdapter] = None,
    ):
        self.session_factory = session_factory or SessionLocal
        self.socrates_adapter = socrates_adapter or SocratesAdapter()

    @contextmanager
    def _get_session(self, db: Optional[Session] = None) -> Generator[Session, None, None]:
        if db is not None:
            yield db
        else:
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

    def validate_run(
        self,
        run_id: str,
        request: Optional[ValidationExecutionRequest] = None,
        db: Optional[Session] = None,
    ) -> ValidationResponse:
        """Execute validation comparison for a completed run against an external source.

        Workflow:
        1. Verify run exists.
        2. Read persisted D-DATO ConjunctionEvent records (never rerun screening).
        3. Read the run's relevant data snapshot/source metadata.
        4. Obtain external reference records from adapter (live, cached, or bundled fixture).
        5. Match D-DATO events to external records using transparent criteria.
        6. Compute descriptive validation metrics (null on division-by-zero).
        7. Persist ValidationRecord entity in database.
        8. Return read-only ValidationResponse.
        """
        req = request or ValidationExecutionRequest()

        with self._get_session(db) as session:
            # 1. Verify run exists
            run_repo = RunRepository(session)
            run = run_repo.get_by_id(run_id)
            if not run:
                raise RunNotFoundError(run_id)

            # 2. Read persisted D-DATO ConjunctionEvent records
            stmt = (
                select(ConjunctionEvent)
                .where(ConjunctionEvent.run_id == run_id)
                .options(joinedload(ConjunctionEvent.debris_object))
                .order_by(ConjunctionEvent.tca.asc(), ConjunctionEvent.id.asc())
            )
            ddato_events = list(session.scalars(stmt).all())

            # 3. Read relevant data snapshot metadata if available
            snapshot_repo = DataSnapshotRepository(session)
            catalog_source = run.plan.data_source if run.plan else "celestrak"
            snapshot = snapshot_repo.get_latest_by_source(catalog_source)

            # 4. Obtain external reference events
            reference_events, provenance, source_fetched_at = (
                self.socrates_adapter.get_reference_events(demo_mode=req.demo_mode)
            )

            # 5. Execute matching
            matches, d_dato_only, external_only = self._match_events(
                ddato_events=ddato_events,
                external_events=reference_events,
                tca_tolerance_seconds=req.tca_tolerance_seconds,
                miss_distance_tolerance_km=req.miss_distance_tolerance_km,
            )

            # 6. Compute metrics
            summary = self._compute_summary_metrics(
                d_dato_count=len(ddato_events),
                external_count=len(reference_events),
                matches=matches,
                d_dato_only=d_dato_only,
                external_only=external_only,
            )

            # 7. Assemble notes
            notes: List[str] = [
                NON_OPERATIONAL_DISCLAIMER,
                f"Validation reference source: {provenance} (dataset: {req.source}).",
                (
                    f"Matching criteria applied: canonical debris NORAD identifier, "
                    f"TCA tolerance <= {req.tca_tolerance_seconds:.1f}s, "
                    f"miss distance tolerance <= {req.miss_distance_tolerance_km:.1f}km."
                ),
            ]
            if source_fetched_at:
                notes.append(f"External reference snapshot epoch: {format_iso_utc(source_fetched_at)}.")
            if snapshot:
                notes.append(
                    f"D-DATO screening catalog snapshot: source={snapshot.source}, "
                    f"fetched_at={format_iso_utc(snapshot.fetched_at)}."
                )

            validation_created_at = now_utc()
            val_id = f"val-{run_id[:8]}-{int(validation_created_at.timestamp())}"

            response = ValidationResponse(
                validation_id=val_id,
                run_id=run.id,
                status="completed",
                source=provenance,
                source_fetched_at=source_fetched_at,
                validation_created_at=validation_created_at,
                summary=summary,
                matches=matches,
                d_dato_only=d_dato_only,
                external_only=external_only,
                notes=notes,
            )

            # 8. Persist the validation result
            record = ValidationRecord(
                id=val_id,
                run_id=run.id,
                source=provenance,
                status="completed",
                source_fetched_at=source_fetched_at,
                event_time=validation_created_at,
                matched_count=summary.matched_event_count,
                d_dato_only_count=summary.d_dato_only_count,
                external_only_count=summary.external_only_count,
                external_coverage_percent=summary.external_coverage_percent,
                d_dato_match_rate_percent=summary.d_dato_match_rate_percent,
                comparison_details=response.model_dump(mode="json"),
                notes="\n".join(notes),
                created_at=validation_created_at,
            )

            val_repo = ValidationRecordRepository(session)
            val_repo.create(record)

            return response

    def get_latest_validation_for_run(
        self, run_id: str, db: Optional[Session] = None
    ) -> ValidationResponse:
        """Retrieve the latest persisted validation report for a screening run.

        Strictly read-only: does NOT re-run screening or validation.
        """
        with self._get_session(db) as session:
            run_repo = RunRepository(session)
            run = run_repo.get_by_id(run_id)
            if not run:
                raise RunNotFoundError(run_id)

            val_repo = ValidationRecordRepository(session)
            record = val_repo.get_latest_by_run(run_id)
            if not record:
                raise ValidationNotFoundError(f"No validation record found for run '{run_id}'.")

            return self._record_to_response(record)

    def get_validation_by_id(
        self, validation_id: str, db: Optional[Session] = None
    ) -> ValidationResponse:
        """Retrieve a specific persisted validation report by ID.

        Strictly read-only.
        """
        with self._get_session(db) as session:
            val_repo = ValidationRecordRepository(session)
            record = val_repo.get_by_id(validation_id)
            if not record:
                raise ValidationNotFoundError(f"Validation record '{validation_id}' was not found.")

            return self._record_to_response(record)

    def _match_events(
        self,
        ddato_events: List[ConjunctionEvent],
        external_events: List[ValidationReferenceEvent],
        tca_tolerance_seconds: float,
        miss_distance_tolerance_km: float,
    ) -> Tuple[
        List[ValidationMatch],
        List[ValidationDdatoOnlyEvent],
        List[ValidationExternalOnlyEvent],
    ]:
        """Perform transparent 1-to-1 greedy matching between D-DATO and external reference events."""
        possible_pairs: List[dict] = []

        for d_ev in ddato_events:
            d_norad = _normalize_norad_id(
                d_ev.debris_object.norad_id if d_ev.debris_object else None
            )
            if not d_norad or not d_ev.tca:
                continue

            d_tca = ensure_utc(d_ev.tca)

            for ext_ev in external_events:
                ext_norad = _normalize_norad_id(ext_ev.debris_norad_id)
                if not ext_norad or not ext_ev.tca:
                    continue

                # A. Match canonical debris/NORAD ID
                if d_norad != ext_norad:
                    continue

                # B. Match TCA within tolerance
                ext_tca = ensure_utc(ext_ev.tca)
                tca_diff_seconds = (d_tca - ext_tca).total_seconds()
                abs_tca_error = abs(tca_diff_seconds)
                if abs_tca_error > tca_tolerance_seconds:
                    continue

                # C. Match miss distance within tolerance if external value exists
                criteria = ["debris_norad_id", "tca_tolerance"]
                miss_diff: Optional[float] = None
                abs_miss_diff = 0.0

                if (
                    d_ev.miss_distance_km is not None
                    and ext_ev.miss_distance_km is not None
                ):
                    miss_diff = d_ev.miss_distance_km - ext_ev.miss_distance_km
                    abs_miss_diff = abs(miss_diff)
                    if abs_miss_diff > miss_distance_tolerance_km:
                        continue
                    criteria.append("miss_distance_tolerance")
                else:
                    criteria.append("miss_distance_unavailable")

                possible_pairs.append(
                    {
                        "d_ev": d_ev,
                        "ext_ev": ext_ev,
                        "abs_tca_error": abs_tca_error,
                        "tca_diff_seconds": tca_diff_seconds,
                        "miss_diff": miss_diff,
                        "abs_miss_diff": abs_miss_diff,
                        "criteria": criteria,
                    }
                )

        # Sort candidate pairs greedily: smallest TCA error first, then smallest miss-distance error
        possible_pairs.sort(
            key=lambda p: (
                p["abs_tca_error"],
                p["abs_miss_diff"],
                p["d_ev"].id,
                p["ext_ev"].external_id,
            )
        )

        matches: List[ValidationMatch] = []
        matched_ddato_ids = set()
        matched_ext_ids = set()

        for pair in possible_pairs:
            d_id = pair["d_ev"].id
            ext_id = pair["ext_ev"].external_id

            if d_id in matched_ddato_ids or ext_id in matched_ext_ids:
                continue

            matched_ddato_ids.add(d_id)
            matched_ext_ids.add(ext_id)

            d_ev = pair["d_ev"]
            ext_ev = pair["ext_ev"]
            d_norad = _normalize_norad_id(
                d_ev.debris_object.norad_id if d_ev.debris_object else None
            )

            matches.append(
                ValidationMatch(
                    d_dato_event_id=d_id,
                    external_event_id=ext_id,
                    candidate_id=d_ev.candidate_id,
                    debris_norad_id=d_norad,
                    tca_d_dato=ensure_utc(d_ev.tca),
                    tca_external=ensure_utc(ext_ev.tca),
                    tca_error_seconds=round(pair["tca_diff_seconds"], 4),
                    miss_distance_d_dato_km=round(d_ev.miss_distance_km, 4)
                    if d_ev.miss_distance_km is not None
                    else None,
                    miss_distance_external_km=round(ext_ev.miss_distance_km, 4)
                    if ext_ev.miss_distance_km is not None
                    else None,
                    miss_distance_difference_km=round(pair["miss_diff"], 4)
                    if pair["miss_diff"] is not None
                    else None,
                    match_criteria=pair["criteria"],
                )
            )

        # Build unmatched D-DATO events
        d_dato_only: List[ValidationDdatoOnlyEvent] = []
        for d_ev in ddato_events:
            if d_ev.id not in matched_ddato_ids:
                d_norad = _normalize_norad_id(
                    d_ev.debris_object.norad_id if d_ev.debris_object else None
                )
                d_dato_only.append(
                    ValidationDdatoOnlyEvent(
                        d_dato_event_id=d_ev.id,
                        candidate_id=d_ev.candidate_id,
                        debris_norad_id=d_norad,
                        tca=ensure_utc(d_ev.tca) if d_ev.tca else None,
                        miss_distance_km=d_ev.miss_distance_km,
                        relative_velocity_km_s=d_ev.relative_velocity_km_s,
                        notes="No matching external reference event within configured tolerances.",
                    )
                )

        # Build unmatched external events
        external_only: List[ValidationExternalOnlyEvent] = []
        for ext_ev in external_events:
            if ext_ev.external_id not in matched_ext_ids:
                external_only.append(
                    ValidationExternalOnlyEvent(
                        external_event_id=ext_ev.external_id,
                        debris_norad_id=_normalize_norad_id(ext_ev.debris_norad_id),
                        tca=ensure_utc(ext_ev.tca) if ext_ev.tca else None,
                        miss_distance_km=ext_ev.miss_distance_km,
                        relative_velocity_km_s=ext_ev.relative_velocity_km_s,
                        candidate_identifier=ext_ev.candidate_identifier,
                        notes="No matching D-DATO conjunction event within configured tolerances.",
                    )
                )

        return matches, d_dato_only, external_only

    def _compute_summary_metrics(
        self,
        d_dato_count: int,
        external_count: int,
        matches: List[ValidationMatch],
        d_dato_only: List[ValidationDdatoOnlyEvent],
        external_only: List[ValidationExternalOnlyEvent],
    ) -> ValidationSummary:
        """Compute aggregate descriptive comparison metrics; returns None for undefined divisions."""
        matched_count = len(matches)

        external_coverage_percent = (
            round((matched_count / external_count) * 100.0, 4)
            if external_count > 0
            else None
        )
        d_dato_match_rate_percent = (
            round((matched_count / d_dato_count) * 100.0, 4)
            if d_dato_count > 0
            else None
        )

        tca_errors = [
            abs(m.tca_error_seconds)
            for m in matches
            if m.tca_error_seconds is not None
        ]
        mean_abs_tca_error_seconds = (
            round(sum(tca_errors) / len(tca_errors), 4) if tca_errors else None
        )
        max_abs_tca_error_seconds = (
            round(max(tca_errors), 4) if tca_errors else None
        )

        miss_diffs = [
            abs(m.miss_distance_difference_km)
            for m in matches
            if m.miss_distance_difference_km is not None
        ]
        mean_abs_miss_diff_km = (
            round(sum(miss_diffs) / len(miss_diffs), 4) if miss_diffs else None
        )
        max_abs_miss_diff_km = (
            round(max(miss_diffs), 4) if miss_diffs else None
        )

        return ValidationSummary(
            d_dato_event_count=d_dato_count,
            external_event_count=external_count,
            matched_event_count=matched_count,
            d_dato_only_count=len(d_dato_only),
            external_only_count=len(external_only),
            external_coverage_percent=external_coverage_percent,
            d_dato_match_rate_percent=d_dato_match_rate_percent,
            mean_abs_tca_error_seconds=mean_abs_tca_error_seconds,
            max_abs_tca_error_seconds=max_abs_tca_error_seconds,
            mean_abs_miss_distance_difference_km=mean_abs_miss_diff_km,
            max_abs_miss_distance_difference_km=max_abs_miss_diff_km,
        )

    def _record_to_response(self, record: ValidationRecord) -> ValidationResponse:
        """Reconstruct a ValidationResponse from a persisted ValidationRecord."""
        if record.comparison_details and isinstance(record.comparison_details, dict):
            try:
                return ValidationResponse.model_validate(record.comparison_details)
            except Exception as exc:
                logger.warning(
                    "Failed to validate cached comparison_details for record '%s': %s",
                    record.id,
                    exc,
                )

        # Fallback reconstruction from column values
        summary = ValidationSummary(
            d_dato_event_count=0,
            external_event_count=0,
            matched_event_count=record.matched_count or 0,
            d_dato_only_count=record.d_dato_only_count or 0,
            external_only_count=record.external_only_count or 0,
            external_coverage_percent=record.external_coverage_percent,
            d_dato_match_rate_percent=record.d_dato_match_rate_percent,
        )
        notes = record.notes.split("\n") if record.notes else [NON_OPERATIONAL_DISCLAIMER]

        return ValidationResponse(
            validation_id=record.id,
            run_id=record.run_id,
            status=record.status or "completed",
            source=record.source,
            source_fetched_at=record.source_fetched_at,
            validation_created_at=record.created_at,
            summary=summary,
            matches=[],
            d_dato_only=[],
            external_only=[],
            notes=notes,
        )


# Singleton provider for FastAPI dependency injection
_validation_service_instance: Optional[ValidationService] = None


def get_validation_service() -> ValidationService:
    """Dependency provider returning a singleton ValidationService instance."""
    global _validation_service_instance
    if _validation_service_instance is None:
        _validation_service_instance = ValidationService()
    return _validation_service_instance
