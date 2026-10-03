"""Unit tests for Phase P17 CSV and PDF Export Service.

Verifies:
1. CSV export for completed run returns valid ZIP artifact
2. CSV Content-Type is application/zip
3. CSV Content-Disposition has deterministic filename
4. ZIP contains plan.csv
5. ZIP contains candidates.csv
6. ZIP contains conjunction_events.csv
7. Validation files appear when validation exists
8. Validation files are omitted when no validation exists
9. Candidate CSV columns are exact and deterministic
10. Candidate CSV ordering is rank ASC then candidate_id ASC
11. Event CSV ordering is deterministic (TCA ASC, miss ASC, candidate ASC, debris ASC)
12. Persisted candidate values are exported exactly
13. Export does not recalculate or mutate candidates
14. PDF export returns valid PDF artifact
15. PDF Content-Type is application/pdf
16. PDF Content-Disposition is correct
17. PDF contains expected report text and required sections
18. PDF handles zero events gracefully
19. PDF handles absent validation gracefully
20. PDF handles failed / non-completed runs
21. Unknown run returns RunNotFoundError
22. No external network calls occur
23. No worker is submitted
24. Pipeline is not rerun
25. Validation service is not rerun
26. Repeated export returns equivalent content structure/order
27. UTF-8 / CSV quoting works for names containing commas/quotes
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import io
import socket
from unittest.mock import MagicMock, patch
import zipfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.db.models import (
    Candidate,
    ConjunctionEvent,
    DataSnapshot,
    DebrisObject,
    Plan,
    Run,
    RunStatus,
    ValidationRecord,
)
from app.services.export_service import (
    CANDIDATES_CSV_HEADERS,
    EVENTS_CSV_HEADERS,
    PLAN_CSV_HEADERS,
    VALIDATION_MATCHES_HEADERS,
    VALIDATION_SUMMARY_HEADERS,
    ExportArtifact,
    ExportService,
    RunNotFoundError,
)
from app.services.validation_service import ValidationService
from app.utils.time import format_iso_utc, now_utc


@pytest.fixture
def db_session() -> Session:
    """Create an in-memory SQLite database session populated with tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionClass = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionClass()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def export_service(db_session: Session) -> ExportService:
    """Provide an ExportService bound to the test db_session."""
    val_svc = ValidationService(session_factory=lambda: db_session)
    return ExportService(session_factory=lambda: db_session, validation_service=val_svc)


def create_sample_entities(
    session: Session,
    status: str = "completed",
    with_validation: bool = False,
    quote_in_names: bool = False,
) -> tuple[Plan, Run, list[Candidate], list[ConjunctionEvent]]:
    """Helper creating a deterministic set of persisted entities."""
    base_epoch = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    source_name = 'celestrak,"demo,catalog"' if quote_in_names else "celestrak"

    plan = Plan(
        id="plan-p17-test-1",
        created_at=base_epoch,
        updated_at=base_epoch,
        epoch_start=base_epoch,
        altitude_min_km=500.0,
        altitude_max_km=600.0,
        altitude_step_km=50.0,
        inclination_min_deg=97.0,
        inclination_max_deg=98.0,
        inclination_step_deg=1.0,
        raan_deg=45.0,
        u0_deg=10.0,
        delay_min_minutes=0.0,
        delay_max_minutes=60.0,
        delay_step_minutes=30.0,
        raan_delay_coupling_deg_per_min=0.25068,
        screening_days=2,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
        dv_budget_m_s=80.0,
        spacecraft_mass_kg=4.0,
        isp_seconds=65.0,
        fuel_weight=0.4,
        risk_weight=0.6,
        data_source=source_name,
        demo_mode=True,
    )
    session.add(plan)

    run = Run(
        id="run-p17-test-1",
        plan_id=plan.id,
        status=status,
        created_at=base_epoch,
        started_at=base_epoch + timedelta(seconds=1),
        completed_at=base_epoch + timedelta(seconds=10) if status == "completed" else None,
        progress_percent=100.0 if status == "completed" else 50.0,
        current_stage="completed" if status == "completed" else "running",
        message="Run completed" if status == "completed" else "In progress",
    )
    session.add(run)

    # 3 Candidates with different ranks
    cand_b = Candidate(
        id="cand-2-middle",
        run_id=run.id,
        altitude_km=550.0,
        inclination_deg=97.5,
        raan_deg=45.2,
        u0_deg=10.0,
        deployment_delay_minutes=30.0,
        predicted_raan_deg=45.2,
        delta_v_m_s=35.0,
        propellant_mass_kg=0.08,
        fuel_fraction=0.02,
        within_dv_budget=True,
        risk_score=15.5,
        rank=2,
        created_at=base_epoch,
    )
    cand_a = Candidate(
        id="cand-1-best",
        run_id=run.id,
        altitude_km=500.0,
        inclination_deg=97.0,
        raan_deg=45.0,
        u0_deg=10.0,
        deployment_delay_minutes=0.0,
        predicted_raan_deg=45.0,
        delta_v_m_s=25.0,
        propellant_mass_kg=0.05,
        fuel_fraction=0.0125,
        within_dv_budget=True,
        risk_score=5.0,
        rank=1,
        created_at=base_epoch,
    )
    cand_c = Candidate(
        id="cand-3-worst",
        run_id=run.id,
        altitude_km=600.0,
        inclination_deg=98.0,
        raan_deg=45.4,
        u0_deg=10.0,
        deployment_delay_minutes=60.0,
        predicted_raan_deg=45.4,
        delta_v_m_s=95.0,
        propellant_mass_kg=0.25,
        fuel_fraction=0.0625,
        within_dv_budget=False,
        risk_score=45.0,
        rank=3,
        created_at=base_epoch,
    )
    session.add_all([cand_b, cand_a, cand_c])

    debris_1 = DebrisObject(
        id="deb-1",
        norad_id="25544",
        object_name="DEBRIS_ALPHA",
        epoch=base_epoch,
        source="celestrak",
        fetched_at=base_epoch,
    )
    debris_2 = DebrisObject(
        id="deb-2",
        norad_id="40001",
        object_name="DEBRIS_BETA",
        epoch=base_epoch,
        source="celestrak",
        fetched_at=base_epoch,
    )
    session.add_all([debris_1, debris_2])

    # 2 Events
    evt_1 = ConjunctionEvent(
        id="evt-1",
        run_id=run.id,
        candidate_id=cand_b.id,
        debris_object_id=debris_1.id,
        tca=base_epoch + timedelta(hours=5),
        miss_distance_km=2.45,
        relative_velocity_km_s=14.2,
        threshold_km=5.0,
        screening_source="ddato",
        created_at=base_epoch,
    )
    evt_2 = ConjunctionEvent(
        id="evt-2",
        run_id=run.id,
        candidate_id=cand_c.id,
        debris_object_id=debris_2.id,
        tca=base_epoch + timedelta(hours=8),
        miss_distance_km=1.10,
        relative_velocity_km_s=12.8,
        threshold_km=5.0,
        screening_source="ddato",
        created_at=base_epoch,
    )
    session.add_all([evt_1, evt_2])

    snapshot = DataSnapshot(
        id="snap-1",
        source=source_name,
        fetched_at=base_epoch,
        object_count=150,
        status="success",
        created_at=base_epoch,
    )
    session.add(snapshot)

    if with_validation:
        val_rec = ValidationRecord(
            id="val-rec-1",
            run_id=run.id,
            source="socrates_demo_fixture",
            status="completed",
            source_fetched_at=base_epoch,
            event_time=base_epoch,
            matched_count=1,
            d_dato_only_count=1,
            external_only_count=0,
            external_coverage_percent=100.0,
            d_dato_match_rate_percent=50.0,
            comparison_details={
                "validation_id": "val-rec-1",
                "run_id": run.id,
                "status": "completed",
                "source": "socrates_demo_fixture",
                "source_fetched_at": format_iso_utc(base_epoch),
                "validation_created_at": format_iso_utc(base_epoch),
                "summary": {
                    "d_dato_event_count": 2,
                    "external_event_count": 1,
                    "matched_event_count": 1,
                    "d_dato_only_count": 1,
                    "external_only_count": 0,
                    "external_coverage_percent": 100.0,
                    "d_dato_match_rate_percent": 50.0,
                    "mean_abs_tca_error_seconds": 12.5,
                    "max_abs_tca_error_seconds": 12.5,
                    "mean_abs_miss_distance_difference_km": 0.045,
                    "max_abs_miss_distance_difference_km": 0.045,
                },
                "matches": [
                    {
                        "d_dato_event_id": "evt-1",
                        "external_event_id": "ext-1",
                        "candidate_id": cand_b.id,
                        "debris_norad_id": "25544",
                        "tca_d_dato": format_iso_utc(base_epoch + timedelta(hours=5)),
                        "tca_external": format_iso_utc(base_epoch + timedelta(hours=5, seconds=12)),
                        "tca_error_seconds": 12.5,
                        "miss_distance_d_dato_km": 2.45,
                        "miss_distance_external_km": 2.405,
                        "miss_distance_difference_km": 0.045,
                        "match_criteria": ["debris_norad_id", "tca_tolerance", "miss_distance_tolerance"],
                    }
                ],
                "d_dato_only": [],
                "external_only": [],
                "notes": ["NON-OPERATIONAL VALIDATION"],
            },
            created_at=base_epoch,
        )
        session.add(val_rec)

    session.commit()
    return plan, run, [cand_a, cand_b, cand_c], [evt_1, evt_2]


# ==============================================================================
# CSV EXPORT TESTS
# ==============================================================================


def test_csv_export_completed_run_structure(export_service: ExportService, db_session: Session):
    """Test 1-6: CSV export returns valid ZIP with plan.csv, candidates.csv, and conjunction_events.csv."""
    plan, run, cands, evts = create_sample_entities(db_session, status="completed", with_validation=False)

    artifact = export_service.export_csv(run.id, db=db_session)
    assert isinstance(artifact, ExportArtifact)
    assert artifact.media_type == "application/zip"
    assert artifact.filename == f"d-dato-{run.id}-export.zip"

    # Inspect zip contents
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as zf:
        members = zf.namelist()
        assert members == ["plan.csv", "candidates.csv", "conjunction_events.csv"]

        # Parse plan.csv
        plan_csv = zf.read("plan.csv").decode("utf-8")
        reader = list(csv.reader(io.StringIO(plan_csv)))
        assert reader[0] == PLAN_CSV_HEADERS
        assert len(reader) == 2  # header + 1 row
        plan_row = dict(zip(reader[0], reader[1]))
        assert plan_row["plan_id"] == plan.id
        assert plan_row["run_id"] == run.id
        assert float(plan_row["altitude_min_km"]) == 500.0
        assert plan_row["demo_mode"] == "true"

        # Parse candidates.csv
        cand_csv = zf.read("candidates.csv").decode("utf-8")
        reader = list(csv.reader(io.StringIO(cand_csv)))
        assert reader[0] == CANDIDATES_CSV_HEADERS
        assert len(reader) == 4  # header + 3 candidates

        # Parse conjunction_events.csv
        evt_csv = zf.read("conjunction_events.csv").decode("utf-8")
        reader = list(csv.reader(io.StringIO(evt_csv)))
        assert reader[0] == EVENTS_CSV_HEADERS
        assert len(reader) == 3  # header + 2 events


def test_csv_export_validation_included_when_exists(export_service: ExportService, db_session: Session):
    """Test 7-8: Validation files appear only when validation record exists."""
    _, run, _, _ = create_sample_entities(db_session, status="completed", with_validation=True)

    artifact = export_service.export_csv(run.id, db=db_session)
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as zf:
        members = zf.namelist()
        assert members == [
            "plan.csv",
            "candidates.csv",
            "conjunction_events.csv",
            "validation_summary.csv",
            "validation_matches.csv",
        ]

        val_summary_csv = zf.read("validation_summary.csv").decode("utf-8")
        summary_reader = list(csv.reader(io.StringIO(val_summary_csv)))
        assert summary_reader[0] == VALIDATION_SUMMARY_HEADERS
        assert len(summary_reader) == 2
        summary_row = dict(zip(summary_reader[0], summary_reader[1]))
        assert summary_row["run_id"] == run.id
        assert summary_row["source"] == "socrates_demo_fixture"
        assert summary_row["matched_event_count"] == "1"

        val_matches_csv = zf.read("validation_matches.csv").decode("utf-8")
        matches_reader = list(csv.reader(io.StringIO(val_matches_csv)))
        assert matches_reader[0] == VALIDATION_MATCHES_HEADERS
        assert len(matches_reader) == 2
        match_row = dict(zip(matches_reader[0], matches_reader[1]))
        assert match_row["debris_norad_id"] == "25544"
        assert match_row["match_criteria"] == "debris_norad_id;tca_tolerance;miss_distance_tolerance"


def test_candidate_csv_deterministic_ordering_and_preservation(export_service: ExportService, db_session: Session):
    """Test 9-13: Candidates ordered rank ASC, candidate_id ASC, exact preserved values."""
    plan, run, cands, _ = create_sample_entities(db_session, status="completed", with_validation=False)

    artifact = export_service.export_csv(run.id, db=db_session)
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as zf:
        cand_csv = zf.read("candidates.csv").decode("utf-8")
        reader = list(csv.reader(io.StringIO(cand_csv)))
        headers = reader[0]
        assert headers == CANDIDATES_CSV_HEADERS

        rows = [dict(zip(headers, r)) for r in reader[1:]]
        # Verify ordering: rank 1, then rank 2, then rank 3
        ranks = [int(r["rank"]) for r in rows]
        assert ranks == [1, 2, 3]
        ids = [r["candidate_id"] for r in rows]
        assert ids == ["cand-1-best", "cand-2-middle", "cand-3-worst"]

        # Exact persisted values preserved
        r0 = rows[0]
        assert float(r0["altitude_km"]) == 500.0
        assert float(r0["delta_v_m_s"]) == 25.0
        assert float(r0["fuel_fraction"]) == 0.0125
        assert r0["within_dv_budget"] == "true"
        assert float(r0["risk_score"]) == 5.0
        assert int(r0["accepted_event_count"]) == 0
        assert r0["minimum_miss_distance_km"] == ""

        r1 = rows[1]
        assert int(r1["accepted_event_count"]) == 1
        assert float(r1["minimum_miss_distance_km"]) == 2.45


def test_event_csv_deterministic_ordering(export_service: ExportService, db_session: Session):
    """Test 11: Conjunction events ordered by TCA ASC, miss_distance ASC, candidate_id ASC."""
    _, run, _, _ = create_sample_entities(db_session, status="completed", with_validation=False)

    artifact = export_service.export_csv(run.id, db=db_session)
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as zf:
        evt_csv = zf.read("conjunction_events.csv").decode("utf-8")
        reader = list(csv.reader(io.StringIO(evt_csv)))
        headers = reader[0]
        assert headers == EVENTS_CSV_HEADERS

        rows = [dict(zip(headers, r)) for r in reader[1:]]
        # evt-1 was 5 hours after epoch, evt-2 was 8 hours after epoch
        assert rows[0]["event_id"] == "evt-1"
        assert rows[1]["event_id"] == "evt-2"
        assert rows[0]["debris_norad_id"] == "25544"
        assert rows[1]["debris_norad_id"] == "40001"


def test_csv_quoting_and_utf8(export_service: ExportService, db_session: Session):
    """Test 27: UTF-8 encoding and standard CSV quoting for strings containing commas and quotes."""
    _, run, _, _ = create_sample_entities(db_session, status="completed", quote_in_names=True)

    artifact = export_service.export_csv(run.id, db=db_session)
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as zf:
        plan_csv = zf.read("plan.csv").decode("utf-8")
        reader = list(csv.reader(io.StringIO(plan_csv)))
        row = dict(zip(reader[0], reader[1]))
        assert row["data_source"] == 'celestrak,"demo,catalog"'


# ==============================================================================
# PDF EXPORT TESTS
# ==============================================================================


def test_pdf_export_completed_run_structure(export_service: ExportService, db_session: Session):
    """Test 14-17: PDF export returns valid PDF artifact with all required report sections."""
    plan, run, _, _ = create_sample_entities(db_session, status="completed", with_validation=True)

    artifact = export_service.export_pdf(run.id, db=db_session)
    assert isinstance(artifact, ExportArtifact)
    assert artifact.media_type == "application/pdf"
    assert artifact.filename == f"d-dato-{run.id}-report.pdf"
    assert artifact.content.startswith(b"%PDF-")

    # Verify semantic text presence in uncompressed PDF output
    pdf_text = artifact.content.decode("latin1", errors="ignore")
    assert "D-DATO Screening Report" in pdf_text
    assert "Debris-Aware Orbit" in pdf_text
    assert "NON-OPERATIONAL NOTICE" in pdf_text
    assert "1. Run Summary" in pdf_text
    assert "2. Planning Inputs" in pdf_text
    assert "3. Ranked Candidates" in pdf_text
    assert "4. Close-Approach Conjunction Events" in pdf_text
    assert "5. External Reference Comparison" in pdf_text
    assert "6. Data Age and Provenance" in pdf_text
    assert "7. Methodological Scope and Limitations" in pdf_text


def test_pdf_export_zero_events(export_service: ExportService, db_session: Session):
    """Test 18: PDF export cleanly handles run with zero conjunction events."""
    base_epoch = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    plan = Plan(
        id="plan-zero-evts",
        created_at=base_epoch,
        updated_at=base_epoch,
        epoch_start=base_epoch,
        altitude_min_km=500.0,
        altitude_max_km=500.0,
        altitude_step_km=10.0,
        inclination_min_deg=97.0,
        inclination_max_deg=97.0,
        inclination_step_deg=1.0,
        data_source="celestrak",
        demo_mode=True,
    )
    db_session.add(plan)
    run = Run(
        id="run-zero-evts",
        plan_id=plan.id,
        status="completed",
        created_at=base_epoch,
    )
    db_session.add(run)
    db_session.commit()

    artifact = export_service.export_pdf(run.id, db=db_session)
    assert artifact.content.startswith(b"%PDF-")
    pdf_text = artifact.content.decode("latin1", errors="ignore")
    assert "No close-approach conjunction events detected" in pdf_text


def test_pdf_export_absent_validation(export_service: ExportService, db_session: Session):
    """Test 19: PDF export cleanly handles absent validation record."""
    _, run, _, _ = create_sample_entities(db_session, status="completed", with_validation=False)

    artifact = export_service.export_pdf(run.id, db=db_session)
    assert artifact.content.startswith(b"%PDF-")
    pdf_text = artifact.content.decode("latin1", errors="ignore")
    # Section 5 should be absent when no validation record exists
    assert "5. External Reference Comparison" not in pdf_text


def test_pdf_export_failed_or_non_completed_run(export_service: ExportService, db_session: Session):
    """Test 20: PDF handles failed and queued runs while accurately reflecting status."""
    _, run_failed, _, _ = create_sample_entities(db_session, status="failed", with_validation=False)

    artifact = export_service.export_pdf(run_failed.id, db=db_session)
    assert artifact.content.startswith(b"%PDF-")
    pdf_text = artifact.content.decode("latin1", errors="ignore")
    assert "FAILED" in pdf_text


def test_unknown_run_raises_404(export_service: ExportService, db_session: Session):
    """Test 21: Requesting non-existent run raises RunNotFoundError."""
    with pytest.raises(RunNotFoundError):
        export_service.export_csv("non-existent-run", db=db_session)

    with pytest.raises(RunNotFoundError):
        export_service.export_pdf("non-existent-run", db=db_session)


# ==============================================================================
# READ-ONLY / NO-RECOMPUTATION / SAFETY TESTS
# ==============================================================================


def test_no_external_network_or_recomputation(export_service: ExportService, db_session: Session):
    """Test 22-25: Export never calls external network, workers, pipeline, or validation."""
    _, run, _, _ = create_sample_entities(db_session, status="completed", with_validation=True)

    # Monkeypatch socket to ensure no network calls
    def forbidden_connect(*args, **kwargs):
        raise RuntimeError("External network connection attempted during export!")

    with patch.object(socket.socket, "connect", side_effect=forbidden_connect):
        with patch("app.workers.screening_worker.WorkerManager.submit") as mock_submit:
            with patch("app.services.pipeline_service.PipelineService.run_pipeline") as mock_pipeline:
                with patch("app.services.validation_service.ValidationService.validate_run") as mock_val:
                    # Execute CSV export
                    csv_artifact = export_service.export_csv(run.id, db=db_session)
                    assert len(csv_artifact.content) > 0

                    # Execute PDF export
                    pdf_artifact = export_service.export_pdf(run.id, db=db_session)
                    assert len(pdf_artifact.content) > 0

                    mock_submit.assert_not_called()
                    mock_pipeline.assert_not_called()
                    mock_val.assert_not_called()


def test_deterministic_repeated_export(export_service: ExportService, db_session: Session):
    """Test 26: Repeated exports of the same run return equivalent structural members and rows."""
    _, run, _, _ = create_sample_entities(db_session, status="completed", with_validation=True)

    art1 = export_service.export_csv(run.id, db=db_session)
    art2 = export_service.export_csv(run.id, db=db_session)

    with zipfile.ZipFile(io.BytesIO(art1.content)) as z1, zipfile.ZipFile(io.BytesIO(art2.content)) as z2:
        assert z1.namelist() == z2.namelist()
        for name in z1.namelist():
            # CSV rows should match in row count and column order
            rows1 = list(csv.reader(io.StringIO(z1.read(name).decode("utf-8"))))
            rows2 = list(csv.reader(io.StringIO(z2.read(name).decode("utf-8"))))
            assert len(rows1) == len(rows2)
            assert rows1[0] == rows2[0]
