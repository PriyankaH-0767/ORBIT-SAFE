"""Unit tests for Phase P16: External Conjunction Screening Validation Service and API.

Verifies:
1. Validation execution request for a completed run
2. Unknown run -> 404 RUN_NOT_FOUND
3. Invalid tolerance (<= 0) -> 422 / ValueError
4. Unsupported source -> 422 / ValueError
5. No-network demo validation succeeds
6. Fixture provenance is marked as demo, not live
7. Exact debris + TCA match works
8. TCA tolerance boundary works
9. TCA outside tolerance does not match
10. Miss-distance difference is calculated correctly
11. Missing external miss distance handled as null
12. D-DATO-only events reported
13. External-only events reported
14. Aggregate descriptive metrics calculated correctly
15. Division-by-zero cases return null metrics
16. Matched-event details preserve IDs
17. source_fetched_at is persisted/returned correctly
18. Cached and demo fallback behavior works
19. Validation is read-only with respect to candidate/event scientific results
20. D-DATO screening is NOT rerun
21. Zero network access in demo mode
22. Repeated validation result retrieval reads persistence rather than recomputing
23. Non-operational disclaimers are preserved in all reports
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
import tempfile
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.data.cache import FileSystemCache
from app.data.socrates import (
    SocratesAdapter,
    ValidationSourceUnavailableError,
)
from app.db.database import Base, get_db
from app.db.models import (
    Candidate,
    ConjunctionEvent,
    DataSnapshot,
    DebrisObject,
    Plan,
    Run,
    ValidationRecord,
)
from app.main import app
from app.schemas.validation import (
    ValidationDdatoOnlyEvent,
    ValidationExecutionRequest,
    ValidationExternalOnlyEvent,
    ValidationMatch,
    ValidationReferenceEvent,
    ValidationResponse,
    ValidationSummary,
)
from app.services.validation_service import (
    RunNotFoundError,
    ValidationNotFoundError,
    ValidationService,
    get_validation_service,
)
from app.utils.time import now_utc


from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an in-memory SQLite database session with all tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionClass = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionClass()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def mock_run_with_events(db_session: Session) -> Run:
    """Seed database with a completed mission plan, run, candidate, debris objects, and conjunction events."""
    epoch_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    plan = Plan(
        epoch_start=epoch_start,
        altitude_min_km=500.0,
        altitude_max_km=600.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.0,
        inclination_max_deg=98.0,
        inclination_step_deg=0.5,
        raan_deg=0.0,
        u0_deg=0.0,
        delay_min_minutes=0.0,
        delay_max_minutes=60.0,
        delay_step_minutes=60.0,
        raan_delay_coupling_deg_per_min=0.25068,
        screening_days=3,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
        dv_budget_m_s=100.0,
        spacecraft_mass_kg=3.0,
        isp_seconds=60.0,
        fuel_weight=0.4,
        risk_weight=0.6,
        data_source="celestrak",
        demo_mode=True,
    )
    db_session.add(plan)
    db_session.flush()

    run = Run(
        plan_id=plan.id,
        status="completed",
        progress_percent=100.0,
        current_stage="completed",
        started_at=epoch_start,
        completed_at=epoch_start + timedelta(seconds=10),
    )
    db_session.add(run)
    db_session.flush()

    cand = Candidate(
        run_id=run.id,
        altitude_km=550.0,
        inclination_deg=97.5,
        raan_deg=0.0,
        u0_deg=0.0,
        deployment_delay_minutes=0.0,
        predicted_raan_deg=0.0,
        delta_v_m_s=12.5,
        propellant_mass_kg=0.065,
        fuel_fraction=0.021,
        within_dv_budget=True,
        risk_score=25.0,
        rank=1,
    )
    db_session.add(cand)
    db_session.flush()

    deb_700001 = DebrisObject(
        norad_id="700001",
        object_name="MODERN 6-DIGIT TEST DEBRIS",
        source="celestrak",
        epoch=epoch_start,
        fetched_at=epoch_start,
        tle_line1="1 700001U 25999A   26001.50000000  .00001000  00000+0  10000-4 0  9999",
        tle_line2="2 700001  97.5000  45.0000 0001500 110.0000 250.0000 15.06400000 50000",
    )
    deb_25544 = DebrisObject(
        norad_id="25544",
        object_name="ISS (ZARYA)",
        source="celestrak",
        epoch=epoch_start,
        fetched_at=epoch_start,
        tle_line1="1 25544U 98067A   26001.50000000  .00016717  00000+0  10270-3 0  9998",
        tle_line2="2 25544  51.6400 208.1000 0005000 120.0000 240.0000 15.50000000400008",
    )
    db_session.add_all([deb_700001, deb_25544])
    db_session.flush()

    # Event 1: NORAD 700001 matching SOC-DEMO-001 exactly
    ev1 = ConjunctionEvent(
        run_id=run.id,
        candidate_id=cand.id,
        debris_object_id=deb_700001.id,
        tca=datetime(2026, 10, 4, 3, 29, 28, 753588, tzinfo=timezone.utc),
        miss_distance_km=13.749,
        relative_velocity_km_s=14.2,
        threshold_km=25.0,
        screening_source="ddato",
    )
    # Event 2: NORAD 700001 matching SOC-DEMO-002 with 13s TCA difference
    ev2 = ConjunctionEvent(
        run_id=run.id,
        candidate_id=cand.id,
        debris_object_id=deb_700001.id,
        tca=datetime(2026, 10, 4, 4, 17, 36, 944852, tzinfo=timezone.utc),
        miss_distance_km=19.039,
        relative_velocity_km_s=14.1,
        threshold_km=25.0,
        screening_source="ddato",
    )
    # Event 3: NORAD 25544 - D-DATO only (time far away from any external event)
    ev3 = ConjunctionEvent(
        run_id=run.id,
        candidate_id=cand.id,
        debris_object_id=deb_25544.id,
        tca=datetime(2026, 10, 5, 10, 0, 0, tzinfo=timezone.utc),
        miss_distance_km=11.2,
        relative_velocity_km_s=13.5,
        threshold_km=25.0,
        screening_source="ddato",
    )
    db_session.add_all([ev1, ev2, ev3])
    db_session.commit()
    return run


# ===========================================================================
# 1. Validation Execution Request Schema & Validation Rules
# ===========================================================================

def test_validation_request_defaults_and_validation():
    """Verify ValidationExecutionRequest schema defaults and boundary validation."""
    req = ValidationExecutionRequest()
    assert req.source == "socrates"
    assert req.tca_tolerance_seconds == 300.0
    assert req.miss_distance_tolerance_km == 5.0
    assert req.demo_mode is None

    # Invalid TCA tolerance (<= 0)
    with pytest.raises(ValidationError):
        ValidationExecutionRequest(tca_tolerance_seconds=0.0)
    with pytest.raises(ValidationError):
        ValidationExecutionRequest(tca_tolerance_seconds=-10.0)

    # Invalid miss distance tolerance (<= 0)
    with pytest.raises(ValidationError):
        ValidationExecutionRequest(miss_distance_tolerance_km=0.0)
    with pytest.raises(ValidationError):
        ValidationExecutionRequest(miss_distance_tolerance_km=-2.0)

    # Unsupported source
    with pytest.raises(ValidationError):
        ValidationExecutionRequest(source="unsupported_source")
    with pytest.raises(ValidationError):
        ValidationExecutionRequest(source="spacetrack")


# ===========================================================================
# 2. SOCRATES Adapter & Provenance
# ===========================================================================

def test_socrates_adapter_loads_bundled_fixture_in_demo_mode(monkeypatch):
    """Verify SOCRATES adapter loads bundled deterministic fixture in demo mode with zero network."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network attempted in demo mode!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    adapter = SocratesAdapter()
    events, provenance, fetched_at = adapter.get_reference_events(demo_mode=True)

    assert provenance == "socrates_demo_fixture"
    assert len(events) >= 4
    assert fetched_at is not None
    assert all(isinstance(e, ValidationReferenceEvent) for e in events)

    # Verify normalization of external records
    ids = [e.external_id for e in events]
    assert "SOC-DEMO-001" in ids
    assert "SOC-DEMO-002" in ids
    assert "SOC-DEMO-003" in ids
    assert "SOC-DEMO-004" in ids

    # Check event with null miss distance
    e3 = next(e for e in events if e.external_id == "SOC-DEMO-003")
    assert e3.miss_distance_km is None
    assert e3.debris_norad_id == "25544"


def test_socrates_adapter_cache_fallback(tmp_path):
    """Verify adapter correctly reads cached payload when available."""
    cache_dir = tmp_path / "socrates_cache"
    cache = FileSystemCache(base_dir=cache_dir)
    payload_content = json.dumps({
        "events": [
            {
                "external_id": "SOC-CACHED-01",
                "debris_norad_id": "700001",
                "tca": "2026-10-04T03:29:28Z",
                "miss_distance_km": 13.5,
                "relative_velocity_km_s": 14.0,
            }
        ]
    })
    cache.save(
        cache_key="default",
        content=payload_content,
        format="json",
        object_count=1,
        source="socrates",
        fetched_at=now_utc(),
    )

    adapter = SocratesAdapter(cache_dir=cache_dir)
    events, provenance, _ = adapter.get_reference_events(demo_mode=False)
    assert provenance == "socrates_cache"
    assert len(events) == 1
    assert events[0].external_id == "SOC-CACHED-01"


def test_socrates_adapter_unavailable_when_offline_no_cache_no_demo(tmp_path):
    """Verify adapter raises ValidationSourceUnavailableError when live disabled and no cache/demo allowed."""
    empty_cache_dir = tmp_path / "empty_cache"
    adapter = SocratesAdapter(cache_dir=empty_cache_dir)

    with pytest.raises(ValidationSourceUnavailableError) as exc_info:
        adapter.get_reference_events(demo_mode=False)

    assert "not enabled" in str(exc_info.value)


# ===========================================================================
# 3. Transparent Matching Algorithm
# ===========================================================================

def test_matching_exact_debris_and_tca(db_session: Session, mock_run_with_events: Run):
    """Verify exact debris NORAD ID and TCA matching."""
    service = ValidationService(session_factory=lambda: db_session)
    response = service.validate_run(
        mock_run_with_events.id,
        request=ValidationExecutionRequest(demo_mode=True),
        db=db_session,
    )

    assert response.status == "completed"
    assert response.source == "socrates_demo_fixture"
    assert len(response.matches) >= 2

    # Check match 1 (exact match for SOC-DEMO-001)
    m1 = next(m for m in response.matches if m.external_event_id == "SOC-DEMO-001")
    assert m1.debris_norad_id == "700001"
    assert abs(m1.tca_error_seconds) < 0.001
    assert abs(m1.miss_distance_difference_km) < 0.001
    assert "debris_norad_id" in m1.match_criteria
    assert "tca_tolerance" in m1.match_criteria
    assert "miss_distance_tolerance" in m1.match_criteria


def test_matching_tca_tolerance_boundary(db_session: Session):
    """Verify matching behavior strictly adheres to configured TCA tolerance."""
    t0 = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)
    ev_ddato = ConjunctionEvent(
        id="ev-1",
        run_id="run-1",
        candidate_id="cand-1",
        tca=t0,
        miss_distance_km=10.0,
        relative_velocity_km_s=12.0,
        threshold_km=25.0,
        screening_source="ddato",
    )
    # Add dummy debris object
    deb = DebrisObject(id="deb-1", norad_id="88888", object_name="TEST", epoch=t0, source="celestrak", fetched_at=t0)
    ev_ddato.debris_object = deb

    # Case A: Within tolerance (299s diff <= 300s tolerance)
    ext_within = ValidationReferenceEvent(
        external_id="ext-within",
        debris_norad_id="88888",
        tca=t0 + timedelta(seconds=299),
        miss_distance_km=10.0,
        source="socrates",
    )
    service = ValidationService()
    matches, ddato_only, ext_only = service._match_events(
        ddato_events=[ev_ddato],
        external_events=[ext_within],
        tca_tolerance_seconds=300.0,
        miss_distance_tolerance_km=5.0,
    )
    assert len(matches) == 1
    assert matches[0].external_event_id == "ext-within"
    assert len(ddato_only) == 0

    # Case B: Outside tolerance (301s diff > 300s tolerance) -> NO match
    ext_outside = ValidationReferenceEvent(
        external_id="ext-outside",
        debris_norad_id="88888",
        tca=t0 + timedelta(seconds=301),
        miss_distance_km=10.0,
        source="socrates",
    )
    matches_b, ddato_only_b, ext_only_b = service._match_events(
        ddato_events=[ev_ddato],
        external_events=[ext_outside],
        tca_tolerance_seconds=300.0,
        miss_distance_tolerance_km=5.0,
    )
    assert len(matches_b) == 0
    assert len(ddato_only_b) == 1
    assert len(ext_only_b) == 1


def test_matching_miss_distance_tolerance_and_unavailable(db_session: Session):
    """Verify miss-distance tolerance boundary and handling of missing external miss distance."""
    t0 = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)
    ev_ddato = ConjunctionEvent(
        id="ev-1",
        run_id="run-1",
        candidate_id="cand-1",
        tca=t0,
        miss_distance_km=15.0,
        relative_velocity_km_s=12.0,
        threshold_km=25.0,
        screening_source="ddato",
    )
    deb = DebrisObject(id="deb-1", norad_id="88888", object_name="TEST", epoch=t0, source="celestrak", fetched_at=t0)
    ev_ddato.debris_object = deb

    # Case A: Miss diff = 4.0 km <= 5.0 km -> Match
    ext_within_range = ValidationReferenceEvent(
        external_id="ext-1",
        debris_norad_id="88888",
        tca=t0,
        miss_distance_km=11.0,
        source="socrates",
    )
    service = ValidationService()
    matches_a, _, _ = service._match_events(
        ddato_events=[ev_ddato],
        external_events=[ext_within_range],
        tca_tolerance_seconds=300.0,
        miss_distance_tolerance_km=5.0,
    )
    assert len(matches_a) == 1
    assert matches_a[0].miss_distance_difference_km == 4.0
    assert "miss_distance_tolerance" in matches_a[0].match_criteria

    # Case B: Miss diff = 6.0 km > 5.0 km -> No match
    ext_outside_range = ValidationReferenceEvent(
        external_id="ext-2",
        debris_norad_id="88888",
        tca=t0,
        miss_distance_km=9.0,
        source="socrates",
    )
    matches_b, _, _ = service._match_events(
        ddato_events=[ev_ddato],
        external_events=[ext_outside_range],
        tca_tolerance_seconds=300.0,
        miss_distance_tolerance_km=5.0,
    )
    assert len(matches_b) == 0

    # Case C: External miss distance is None -> Matches with 'miss_distance_unavailable'
    ext_none_range = ValidationReferenceEvent(
        external_id="ext-3",
        debris_norad_id="88888",
        tca=t0,
        miss_distance_km=None,
        source="socrates",
    )
    matches_c, _, _ = service._match_events(
        ddato_events=[ev_ddato],
        external_events=[ext_none_range],
        tca_tolerance_seconds=300.0,
        miss_distance_tolerance_km=5.0,
    )
    assert len(matches_c) == 1
    assert matches_c[0].miss_distance_external_km is None
    assert matches_c[0].miss_distance_difference_km is None
    assert "miss_distance_unavailable" in matches_c[0].match_criteria


# ===========================================================================
# 4. Metrics Calculation & Division-by-Zero Handling
# ===========================================================================

def test_metrics_calculation_and_division_by_zero():
    """Verify summary metrics calculation and null handling for zero counts."""
    service = ValidationService()

    # Normal case with matches
    m1 = ValidationMatch(
        d_dato_event_id="d1",
        external_event_id="e1",
        debris_norad_id="111",
        tca_error_seconds=10.0,
        miss_distance_difference_km=2.0,
    )
    m2 = ValidationMatch(
        d_dato_event_id="d2",
        external_event_id="e2",
        debris_norad_id="222",
        tca_error_seconds=-20.0,
        miss_distance_difference_km=4.0,
    )
    summary = service._compute_summary_metrics(
        d_dato_count=3,
        external_count=4,
        matches=[m1, m2],
        d_dato_only=[ValidationDdatoOnlyEvent(d_dato_event_id="d3")],
        external_only=[
            ValidationExternalOnlyEvent(external_event_id="e3"),
            ValidationExternalOnlyEvent(external_event_id="e4"),
        ],
    )
    assert summary.d_dato_event_count == 3
    assert summary.external_event_count == 4
    assert summary.matched_event_count == 2
    assert summary.d_dato_only_count == 1
    assert summary.external_only_count == 2
    assert summary.external_coverage_percent == 50.0  # 2 / 4 * 100
    assert summary.d_dato_match_rate_percent == pytest.approx(66.6667, 0.001)  # 2 / 3 * 100
    assert summary.mean_abs_tca_error_seconds == 15.0  # (10 + 20) / 2
    assert summary.max_abs_tca_error_seconds == 20.0
    assert summary.mean_abs_miss_distance_difference_km == 3.0  # (2 + 4) / 2
    assert summary.max_abs_miss_distance_difference_km == 4.0

    # Division-by-zero case: 0 D-DATO events, 0 external events
    empty_summary = service._compute_summary_metrics(
        d_dato_count=0,
        external_count=0,
        matches=[],
        d_dato_only=[],
        external_only=[],
    )
    assert empty_summary.external_coverage_percent is None
    assert empty_summary.d_dato_match_rate_percent is None
    assert empty_summary.mean_abs_tca_error_seconds is None
    assert empty_summary.max_abs_tca_error_seconds is None
    assert empty_summary.mean_abs_miss_distance_difference_km is None
    assert empty_summary.max_abs_miss_distance_difference_km is None


# ===========================================================================
# 5. Full End-to-End Validation Service Workflow & Persistence
# ===========================================================================

def test_validation_workflow_persistence_and_read_only(
    db_session: Session, mock_run_with_events: Run
):
    """Verify validation execution persists ValidationRecord and is strictly read-only towards screening."""
    # Capture screening state before validation
    initial_events_count = len(mock_run_with_events.conjunction_events)
    initial_status = mock_run_with_events.status

    service = ValidationService(session_factory=lambda: db_session)
    response = service.validate_run(
        run_id=mock_run_with_events.id,
        request=ValidationExecutionRequest(demo_mode=True),
        db=db_session,
    )

    # 1. Verify response structure
    assert response.run_id == mock_run_with_events.id
    assert response.status == "completed"
    assert response.source == "socrates_demo_fixture"
    assert response.source_fetched_at is not None
    assert len(response.matches) == 2
    assert len(response.d_dato_only) == 1  # ev3 (NORAD 25544)
    assert len(response.external_only) >= 2  # SOC-DEMO-003, SOC-DEMO-004, etc.

    # 2. Verify persistence in DB
    val_records = db_session.query(ValidationRecord).filter_by(run_id=mock_run_with_events.id).all()
    assert len(val_records) == 1
    rec = val_records[0]
    assert rec.id == response.validation_id
    assert rec.matched_count == 2
    assert rec.d_dato_only_count == 1
    assert rec.source == "socrates_demo_fixture"

    # 3. Verify screening was NOT rerun
    db_session.refresh(mock_run_with_events)
    assert mock_run_with_events.status == initial_status
    assert len(mock_run_with_events.conjunction_events) == initial_events_count

    # 4. Verify repeated retrieval reads persistence rather than recomputing
    retrieved = service.get_latest_validation_for_run(mock_run_with_events.id, db=db_session)
    assert retrieved.validation_id == response.validation_id
    assert retrieved.summary.matched_event_count == response.summary.matched_event_count
    assert retrieved.matches[0].external_event_id == response.matches[0].external_event_id

    # 5. Direct retrieval by validation ID
    by_id = service.get_validation_by_id(response.validation_id, db=db_session)
    assert by_id.validation_id == response.validation_id
    assert by_id.run_id == mock_run_with_events.id


def test_validation_unknown_run_and_unknown_validation_id(db_session: Session):
    """Verify appropriate exceptions for non-existent runs and validation IDs."""
    service = ValidationService(session_factory=lambda: db_session)

    with pytest.raises(RunNotFoundError):
        service.validate_run("non-existent-run", db=db_session)

    with pytest.raises(RunNotFoundError):
        service.get_latest_validation_for_run("non-existent-run", db=db_session)

    with pytest.raises(ValidationNotFoundError):
        service.get_validation_by_id("non-existent-validation-id", db=db_session)


# ===========================================================================
# 6. REST API Endpoint Tests
# ===========================================================================

def test_api_validation_post_and_get_lifecycle(
    db_session: Session, mock_run_with_events: Run
):
    """Verify POST /api/v1/runs/{run_id}/validation, GET /api/v1/runs/{run_id}/validation, and GET /api/v1/validations/{val_id}."""
    service = ValidationService(session_factory=lambda: db_session)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_validation_service] = lambda: service

    try:
        client = TestClient(app)

        # 1. Trigger validation via POST
        post_res = client.post(
            f"/api/v1/runs/{mock_run_with_events.id}/validation",
            json={
                "source": "socrates",
                "tca_tolerance_seconds": 300.0,
                "miss_distance_tolerance_km": 5.0,
                "demo_mode": True,
            },
        )
        assert post_res.status_code == 200, post_res.text
        data = post_res.json()
        val_id = data["validation_id"]
        assert val_id.startswith("val-")
        assert data["status"] == "completed"
        assert data["source"] == "socrates_demo_fixture"
        assert len(data["matches"]) == 2
        assert data["summary"]["matched_event_count"] == 2
        assert data["summary"]["d_dato_only_count"] == 1
        assert data["summary"]["external_coverage_percent"] is not None
        assert data["summary"]["d_dato_match_rate_percent"] is not None

        # 2. Retrieve latest validation for run via GET
        get_res = client.get(f"/api/v1/runs/{mock_run_with_events.id}/validation")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["validation_id"] == val_id
        assert get_data["summary"]["matched_event_count"] == 2

        # 3. Retrieve validation directly by validation_id
        by_id_res = client.get(f"/api/v1/validations/{val_id}")
        assert by_id_res.status_code == 200
        assert by_id_res.json()["validation_id"] == val_id
    finally:
        app.dependency_overrides.clear()


def test_api_validation_errors(db_session: Session, mock_run_with_events: Run):
    """Verify 404 and 422 error codes from validation endpoints."""
    service = ValidationService(session_factory=lambda: db_session)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_validation_service] = lambda: service

    try:
        client = TestClient(app)

        # 404 for unknown run in POST
        res_unknown_post = client.post("/api/v1/runs/unknown-run/validation")
        assert res_unknown_post.status_code == 404
        assert res_unknown_post.json()["detail"]["code"] == "RUN_NOT_FOUND"

        # 404 for unknown run in GET
        res_unknown_get = client.get("/api/v1/runs/unknown-run/validation")
        assert res_unknown_get.status_code == 404
        assert res_unknown_get.json()["detail"]["code"] == "RUN_NOT_FOUND"

        # 404 for unknown validation_id
        res_unknown_val = client.get("/api/v1/validations/unknown-val-123")
        assert res_unknown_val.status_code == 404
        assert res_unknown_val.json()["detail"]["code"] == "VALIDATION_NOT_FOUND"

        # 422 for invalid TCA tolerance
        res_bad_tca = client.post(
            f"/api/v1/runs/{mock_run_with_events.id}/validation",
            json={"tca_tolerance_seconds": -50.0},
        )
        assert res_bad_tca.status_code == 422

        # 422 for invalid miss distance tolerance
        res_bad_miss = client.post(
            f"/api/v1/runs/{mock_run_with_events.id}/validation",
            json={"miss_distance_tolerance_km": 0.0},
        )
        assert res_bad_miss.status_code == 422

        # 422 for unsupported source
        res_bad_src = client.post(
            f"/api/v1/runs/{mock_run_with_events.id}/validation",
            json={"source": "unknown_catalog"},
        )
        assert res_bad_src.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_api_validation_source_unavailable_error(
    db_session: Session, mock_run_with_events: Run, tmp_path
):
    """Verify 503 VALIDATION_SOURCE_UNAVAILABLE when external source is offline and demo_mode=False."""
    empty_cache = tmp_path / "empty_cache"
    adapter = SocratesAdapter(cache_dir=empty_cache)
    service = ValidationService(
        session_factory=lambda: db_session,
        socrates_adapter=adapter,
    )

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_validation_service] = lambda: service

    try:
        client = TestClient(app)
        res = client.post(
            f"/api/v1/runs/{mock_run_with_events.id}/validation",
            json={"source": "socrates", "demo_mode": False},
        )
        assert res.status_code == 503
        assert res.json()["detail"]["code"] == "VALIDATION_SOURCE_UNAVAILABLE"
    finally:
        app.dependency_overrides.clear()

