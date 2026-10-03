"""Unit and integration tests for D-DATO Phase P15: 3D Globe Service and API.

Verifies:
 1. GlobeStatePoint schema validation (all fields, UTC enforcement)
 2. GlobeResponse schema field defaults and structure
 3. GlobeService raises ValueError for unknown run_id
 4. GlobeService returns empty tracks for a queued/empty run
 5. GlobeService propagates candidates via Circular J2
 6. Candidate trajectory points are physically reasonable (TEME LEO radii)
 7. Trajectory sample count matches the expected step count
 8. GlobeService respects max_candidates limit
 9. GlobeService selects debris from conjunction events first (priority)
10. GlobeService falls back to all debris when no events
11. GlobeService respects max_debris limit
12. GlobeService handles SGP4 propagation error gracefully (skips bad debris)
13. GlobeService builds event markers with norad_id from debris map
14. Globe endpoint returns HTTP 200 for a completed run (schema contract)
15. Globe endpoint returns HTTP 404 for unknown run_id
16. Globe endpoint returns HTTP 422 for out-of-range query parameters
17. Globe endpoint returns HTTP 200 for queued run (no candidates/debris yet)
18. Globe endpoint is read-only (does not change run status)
19. Globe endpoint makes no network call
"""

import math
import socket
from datetime import datetime, timezone
from typing import Generator, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.constants import RE
from app.db.database import Base, get_db
from app.db.models import Candidate, ConjunctionEvent, DebrisObject, Plan, Run
from app.main import app
from app.schemas.globe import (
    GlobeCandidateTrack,
    GlobeDebrisTrack,
    GlobeEventMarker,
    GlobeResponse,
    GlobeStatePoint,
)
from app.services.globe_service import GlobeService, _sv_to_point, get_globe_service
from app.services.heatmap_service import HeatmapService, get_heatmap_service
from app.services.run_service import RunService, get_run_service
from app.workers.screening_worker import WorkerManager
from app.core.propagation import StateVector


# ---------------------------------------------------------------------------
# TLE fixture for a realistic SSO-like debris object (ISS-like orbit)
# ---------------------------------------------------------------------------
ISS_LINE1 = "1 25544U 98067A   26001.50000000  .00016717  00000+0  10270-3 0  9998"
ISS_LINE2 = "2 25544  51.6400 208.1000 0005000 120.0000 240.0000 15.50000000400008"

# SSO-like debris at ~550 km
SSO_LINE1 = "1 40001U 14001A   26001.50000000  .00000500  00000+0  50000-4 0  9991"
SSO_LINE2 = "2 40001  97.6000  10.0000 0001000   0.0000 360.0000 15.20000000123456"


def _epoch_utc() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Isolated SQLite fixture for Globe tests
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_globe_setup(tmp_path) -> Generator[tuple, None, None]:
    """Provide an isolated SQLite database, GlobeService, and TestClient."""
    db_file = tmp_path / "test_globe.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    globe_service = GlobeService(session_factory=TestSessionLocal)
    heatmap_service = HeatmapService(session_factory=TestSessionLocal)
    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=TestSessionLocal, worker_manager=worker_mgr)

    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_get_globe_service():
        return globe_service

    def override_get_heatmap_service():
        return heatmap_service

    def override_get_run_service():
        return run_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_globe_service] = override_get_globe_service
    app.dependency_overrides[get_heatmap_service] = override_get_heatmap_service
    app.dependency_overrides[get_run_service] = override_get_run_service

    db_session = TestSessionLocal()
    with TestClient(app) as test_client:
        try:
            yield db_session, globe_service, TestSessionLocal, test_client
        finally:
            db_session.close()
            worker_mgr.shutdown(wait=True, cancel_futures=True)
            Base.metadata.drop_all(bind=test_engine)
            test_engine.dispose()
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Database seed helpers
# ---------------------------------------------------------------------------

def _seed_plan_and_run(
    session: Session,
    status: str = "completed",
    screening_days: int = 1,
) -> tuple[Plan, Run]:
    """Seed a Plan and Run into the database."""
    now = _epoch_utc()
    plan = Plan(
        epoch_start=now,
        altitude_min_km=540.0,
        altitude_max_km=560.0,
        altitude_step_km=20.0,
        inclination_min_deg=97.0,
        inclination_max_deg=97.5,
        inclination_step_deg=0.5,
        raan_deg=0.0,
        u0_deg=0.0,
        delay_min_minutes=0.0,
        delay_max_minutes=60.0,
        delay_step_minutes=60.0,
        raan_delay_coupling_deg_per_min=0.25,
        screening_days=screening_days,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
        dv_budget_m_s=100.0,
        spacecraft_mass_kg=3.0,
        isp_seconds=60.0,
        fuel_weight=0.4,
        risk_weight=0.6,
        data_source="demo",
        demo_mode=True,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)

    run = Run(
        plan_id=plan.id,
        status=status,
        progress_percent=100.0,
        current_stage="completed" if status == "completed" else status,
        message=f"Run {status}",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return plan, run


def _seed_candidates(
    session: Session,
    run_id: str,
    n: int = 3,
    altitude_km: float = 550.0,
    inclination_deg: float = 97.5,
) -> List[Candidate]:
    """Seed N simple candidates into the database."""
    candidates = []
    for i in range(n):
        cand = Candidate(
            run_id=run_id,
            altitude_km=altitude_km,
            inclination_deg=inclination_deg,
            raan_deg=float(i * 10.0),
            u0_deg=0.0,
            deployment_delay_minutes=float(i * 30.0),
            predicted_raan_deg=float(i * 10.0),
            delta_v_m_s=25.0,
            propellant_mass_kg=0.12,
            fuel_fraction=0.04,
            within_dv_budget=True,
            risk_score=float(10 + i * 5),
            rank=i + 1,
        )
        candidates.append(cand)
        session.add(cand)
    session.commit()
    for c in candidates:
        session.refresh(c)
    return candidates


def _seed_debris(
    session: Session,
    norad_id: str = "25544",
    name: str = "ISS (ZARYA)",
    tle1: str = ISS_LINE1,
    tle2: str = ISS_LINE2,
) -> DebrisObject:
    """Seed a single DebrisObject with given TLE."""
    now = _epoch_utc()
    deb = DebrisObject(
        norad_id=norad_id,
        object_name=name,
        element_format="tle",
        tle_line1=tle1,
        tle_line2=tle2,
        epoch=now,
        inclination_deg=51.64,
        eccentricity=0.0005,
        raan_deg=208.1,
        arg_perigee_deg=120.0,
        mean_anomaly_deg=240.0,
        mean_motion_rev_per_day=15.5,
        bstar=1.027e-4,
        mean_motion_dot=1.6717e-5,
        mean_motion_ddot=0.0,
        source="demo",
        fetched_at=now,
    )
    session.add(deb)
    session.commit()
    session.refresh(deb)
    return deb


def _seed_conjunction_event(
    session: Session,
    run_id: str,
    candidate_id: str,
    debris_object_id: str,
    tca: datetime,
) -> ConjunctionEvent:
    """Seed a single conjunction event."""
    evt = ConjunctionEvent(
        run_id=run_id,
        candidate_id=candidate_id,
        debris_object_id=debris_object_id,
        tca=tca,
        miss_distance_km=15.0,
        relative_velocity_km_s=7.5,
        threshold_km=25.0,
        screening_source="ddato",
    )
    session.add(evt)
    session.commit()
    session.refresh(evt)
    return evt


# ===========================================================================
# Test 1: GlobeStatePoint schema validation
# ===========================================================================

def test_globe_state_point_valid():
    """Test 1a: GlobeStatePoint accepts valid UTC data."""
    t = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    pt = GlobeStatePoint(t=t, x_km=6000.0, y_km=0.0, z_km=100.0, vx_km_s=0.0, vy_km_s=7.5, vz_km_s=0.1)
    assert pt.x_km == 6000.0
    assert pt.x == 6000.0
    assert pt.vy_km_s == 7.5
    assert pt.vy == 7.5
    assert pt.t.tzinfo is not None


def test_globe_state_point_all_fields_present():
    """Test 1b: GlobeStatePoint exposes all required fields."""
    t = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    pt = GlobeStatePoint(t=t, x=1.0, y=2.0, z=3.0, vx=4.0, vy=5.0, vz=6.0)
    for attr in ("t", "x", "y", "z", "vx", "vy", "vz", "x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"):
        assert hasattr(pt, attr), f"Missing field: {attr}"


# ===========================================================================
# Test 2: GlobeResponse schema defaults
# ===========================================================================

def test_globe_response_defaults():
    """Test 2: GlobeResponse frame defaults to TEME, time_scale to UTC, and lists default empty."""
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    resp = GlobeResponse(
        run_id="r1",
        status="completed",
        sample_step_seconds=300,
        epoch_start=t0,
        epoch_end=t1,
        candidate_count=0,
        debris_count=0,
        event_count=0,
    )
    assert resp.frame == "TEME"
    assert resp.time_scale == "UTC"
    assert resp.candidates == []
    assert resp.debris == []
    assert resp.events == []


# ===========================================================================
# Test 3: GlobeService – run not found
# ===========================================================================

def test_globe_service_run_not_found(isolated_globe_setup):
    """Test 3: GlobeService raises ValueError for unknown run_id."""
    session, globe_service, _, _ = isolated_globe_setup
    with pytest.raises(ValueError, match="not found"):
        globe_service.get_globe_data(run_id="nonexistent-run-id", db=session)


# ===========================================================================
# Test 4: GlobeService – empty/queued run returns 200 with empty tracks
# ===========================================================================

def test_globe_service_empty_run(isolated_globe_setup):
    """Test 4: GlobeService returns empty tracks for run with no candidates."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="queued")

    result = globe_service.get_globe_data(run_id=run.id, db=session)

    assert result.run_id == run.id
    assert result.status == "queued"
    assert result.frame == "TEME"
    assert result.candidate_count == 0
    assert result.debris_count == 0
    assert result.event_count == 0
    assert result.candidates == []
    assert result.debris == []
    assert result.events == []


# ===========================================================================
# Test 5: GlobeService – candidate propagation uses Circular J2
# ===========================================================================

def test_globe_service_propagates_candidates(isolated_globe_setup):
    """Test 5: GlobeService propagates candidates and returns non-empty trajectories."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=2)

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,  # 1-hour step: 25 points for 1 day
        db=session,
    )

    assert result.candidate_count == 2
    assert len(result.candidates) == 2
    for track in result.candidates:
        assert track.point_count > 0
        assert len(track.trajectory) == track.point_count
        assert track.altitude_km == pytest.approx(550.0)
        assert track.inclination_deg == pytest.approx(97.5)


# ===========================================================================
# Test 6: Trajectory points are physically reasonable (LEO TEME radii)
# ===========================================================================

def test_candidate_trajectory_physically_reasonable(isolated_globe_setup):
    """Test 6: Candidate trajectory positions correspond to valid LEO TEME state vectors."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=1, altitude_km=550.0)

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        db=session,
    )

    assert len(result.candidates) == 1
    track = result.candidates[0]
    expected_r = RE + 550.0  # ~6928 km

    for pt in track.trajectory:
        r = math.sqrt(pt.x**2 + pt.y**2 + pt.z**2)
        # Allow 2 km tolerance for J2 precession effects on circular orbit
        assert abs(r - expected_r) < 2.0, f"Unexpected radius: {r:.2f} km (expected ~{expected_r:.2f})"
        v = math.sqrt(pt.vx**2 + pt.vy**2 + pt.vz**2)
        # Circular orbital speed at 550 km ≈ 7.59 km/s; allow ±0.1 km/s
        assert 7.4 < v < 7.8, f"Unexpected speed: {v:.4f} km/s"


# ===========================================================================
# Test 7: Sample count matches expected step count
# ===========================================================================

def test_trajectory_sample_count_matches_step(isolated_globe_setup):
    """Test 7: Trajectory sample count matches expected number of samples for given step."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=1)

    step = 3600  # 1 hour
    result = globe_service.get_globe_data(
        run_id=run.id, sample_step_seconds=step, db=session
    )

    # 1 day = 86400 s; ceil(86400/3600) + 1 = 25 + epoch_end = 25 or 26 points
    track = result.candidates[0]
    # At minimum 25 points; epoch_end appended if not coinciding with last step
    assert track.point_count >= 25
    assert track.point_count <= 26  # at most +1 for epoch_end


# ===========================================================================
# Test 8: max_candidates limit is respected
# ===========================================================================

def test_max_candidates_limit_respected(isolated_globe_setup):
    """Test 8: GlobeService returns at most max_candidates candidate tracks."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=10)

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        max_candidates=3,
        db=session,
    )

    assert result.candidate_count == 3
    assert len(result.candidates) == 3


# ===========================================================================
# Test 9: Debris from conjunction events takes priority
# ===========================================================================

def test_debris_from_events_selected_first(isolated_globe_setup):
    """Test 9: Debris objects involved in events are selected before fallback."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    candidates = _seed_candidates(session, run_id=run.id, n=1)

    # Seed two debris: one involved in an event, one not
    deb_event = _seed_debris(session, norad_id="25544", name="ISS")
    _seed_debris(session, norad_id="40001", name="OTHER SAT", tle1=SSO_LINE1, tle2=SSO_LINE2)

    tca = _epoch_utc()
    _seed_conjunction_event(
        session,
        run_id=run.id,
        candidate_id=candidates[0].id,
        debris_object_id=deb_event.id,
        tca=tca,
    )

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        max_debris=1,  # only 1 slot - should pick the event debris
        db=session,
    )

    assert result.debris_count == 1
    assert result.debris[0].norad_id == "25544"


# ===========================================================================
# Test 10: Debris fallback when no events
# ===========================================================================

def test_debris_fallback_when_no_events(isolated_globe_setup):
    """Test 10: When no events exist, debris is still included via DB fallback."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=1)
    _seed_debris(session, norad_id="25544", name="ISS")

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        max_debris=5,
        db=session,
    )

    # No events, but debris found via fallback
    assert result.event_count == 0
    assert result.debris_count == 1
    assert result.debris[0].norad_id == "25544"


# ===========================================================================
# Test 11: max_debris limit is respected
# ===========================================================================

def test_max_debris_limit_respected(isolated_globe_setup):
    """Test 11: GlobeService returns at most max_debris debris tracks."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=1)

    # Seed three debris objects
    for i in range(3):
        _seed_debris(
            session,
            norad_id=str(25544 + i),
            name=f"DEBRIS-{i}",
            tle1=ISS_LINE1.replace("25544", f"{25544 + i}"),
            tle2=ISS_LINE2.replace("25544", f"{25544 + i}"),
        )

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        max_debris=2,
        db=session,
    )

    assert result.debris_count <= 2
    assert len(result.debris) <= 2


# ===========================================================================
# Test 12: SGP4 propagation error is handled gracefully (debris skipped)
# ===========================================================================

def test_sgp4_propagation_error_skips_debris(isolated_globe_setup):
    """Test 12: Debris with invalid TLE is skipped without crashing."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=1)

    # Seed a debris with invalid TLE lines
    bad_deb = DebrisObject(
        norad_id="99999",
        object_name="BAD DEBRIS",
        element_format="tle",
        tle_line1="bad TLE line 1",
        tle_line2="bad TLE line 2",
        epoch=_epoch_utc(),
        inclination_deg=97.0,
        eccentricity=0.0001,
        raan_deg=0.0,
        arg_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
        mean_motion_rev_per_day=15.0,
        bstar=0.0,
        source="demo",
        fetched_at=_epoch_utc(),
    )
    session.add(bad_deb)
    session.commit()

    # Should not raise; bad debris is silently skipped
    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        max_debris=5,
        db=session,
    )

    # The bad debris is skipped; no tracks for "99999"
    norad_ids = [d.norad_id for d in result.debris]
    assert "99999" not in norad_ids


# ===========================================================================
# Test 13: Event markers are built with correct norad_id
# ===========================================================================

def test_event_markers_include_norad_id(isolated_globe_setup):
    """Test 13: Event markers expose all required fields and exact SGP4 TEME coordinates at TCA."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    candidates = _seed_candidates(session, run_id=run.id, n=1)
    deb = _seed_debris(session, norad_id="25544", name="ISS")

    tca = _epoch_utc()
    evt = _seed_conjunction_event(
        session,
        run_id=run.id,
        candidate_id=candidates[0].id,
        debris_object_id=deb.id,
        tca=tca,
    )

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        db=session,
    )

    assert result.event_count == 1
    marker = result.events[0]
    assert marker.event_id == evt.id
    assert marker.candidate_id == candidates[0].id
    assert marker.debris_object_id == deb.id
    assert marker.debris_norad_id == "25544"
    assert marker.tca == tca
    assert marker.miss_distance_km == pytest.approx(15.0)
    assert marker.relative_velocity_km_s == pytest.approx(7.5)

    # Verify marker Cartesian coordinates match SGP4 propagation at TCA
    from app.services.screening_service import debris_model_to_canonical
    from app.core.propagation import Sgp4Propagator
    prop = Sgp4Propagator(debris_model_to_canonical(deb))
    expected_sv = prop.propagate(tca)
    assert marker.x_km == pytest.approx(expected_sv.position_km[0], abs=1e-3)
    assert marker.y_km == pytest.approx(expected_sv.position_km[1], abs=1e-3)
    assert marker.z_km == pytest.approx(expected_sv.position_km[2], abs=1e-3)


# ===========================================================================
# Test 14: Globe endpoint HTTP 200 for completed run (schema contract)
# ===========================================================================

def test_globe_endpoint_completed_run_schema(isolated_globe_setup):
    """Test 14: GET /api/v1/runs/{run_id}/globe returns 200 with correct schema."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=2)
    _seed_debris(session, norad_id="25544", name="ISS")

    res = client.get(f"/api/v1/runs/{run.id}/globe?sample_step_seconds=3600")
    assert res.status_code == 200

    data = res.json()
    assert data["run_id"] == run.id
    assert data["status"] == "completed"
    assert data["frame"] == "TEME"
    assert data["sample_step_seconds"] == 3600
    assert "epoch_start" in data
    assert "epoch_end" in data
    assert isinstance(data["candidate_count"], int)
    assert isinstance(data["debris_count"], int)
    assert isinstance(data["event_count"], int)
    assert isinstance(data["candidates"], list)
    assert isinstance(data["debris"], list)
    assert isinstance(data["events"], list)
    assert data["candidate_count"] == 2
    assert data["candidate_count"] == len(data["candidates"])
    assert data["debris_count"] == len(data["debris"])
    assert data["event_count"] == len(data["events"])


# ===========================================================================
# Test 15: Globe endpoint HTTP 404 for unknown run_id
# ===========================================================================

def test_globe_endpoint_run_not_found(isolated_globe_setup):
    """Test 15: GET /api/v1/runs/UNKNOWN/globe returns 404."""
    _, _, _, client = isolated_globe_setup
    res = client.get("/api/v1/runs/no-such-run-id/globe")
    assert res.status_code == 404
    data = res.json()
    assert data["detail"]["code"] == "RUN_NOT_FOUND"


# ===========================================================================
# Test 16: Globe endpoint HTTP 422 for invalid query params
# ===========================================================================

def test_globe_endpoint_invalid_sample_step_too_small(isolated_globe_setup):
    """Test 16a: sample_step_seconds < 30 returns 422, 30 is accepted (200)."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="queued")
    # 29 -> 422
    res29 = client.get(f"/api/v1/runs/{run.id}/globe?sample_step_seconds=29")
    assert res29.status_code == 422
    # 30 -> 200 accepted
    res30 = client.get(f"/api/v1/runs/{run.id}/globe?sample_step_seconds=30")
    assert res30.status_code == 200


def test_globe_endpoint_invalid_sample_step_too_large(isolated_globe_setup):
    """Test 16b: sample_step_seconds > 3600 returns 422, 3600 is accepted (200)."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="queued")
    # 3600 -> 200 accepted
    res3600 = client.get(f"/api/v1/runs/{run.id}/globe?sample_step_seconds=3600")
    assert res3600.status_code == 200
    # 3601 -> 422
    res3601 = client.get(f"/api/v1/runs/{run.id}/globe?sample_step_seconds=3601")
    assert res3601.status_code == 422


def test_globe_endpoint_invalid_max_candidates(isolated_globe_setup):
    """Test 16c: max_candidates=0 returns 422."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="queued")
    res = client.get(f"/api/v1/runs/{run.id}/globe?max_candidates=0")
    assert res.status_code == 422


def test_globe_endpoint_invalid_max_debris(isolated_globe_setup):
    """Test 16d: max_debris=0 returns 422."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="queued")
    res = client.get(f"/api/v1/runs/{run.id}/globe?max_debris=0")
    assert res.status_code == 422


# ===========================================================================
# Test 17: Globe endpoint returns 200 for queued run (no data yet)
# ===========================================================================

def test_globe_endpoint_queued_run_returns_200_empty(isolated_globe_setup):
    """Test 17: Queued run returns 200 with empty tracks (not 404 or 500)."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="queued")

    res = client.get(f"/api/v1/runs/{run.id}/globe?sample_step_seconds=3600")
    assert res.status_code == 200
    data = res.json()
    assert data["run_id"] == run.id
    assert data["status"] == "queued"
    assert data["candidate_count"] == 0
    assert data["debris_count"] == 0
    assert data["event_count"] == 0


# ===========================================================================
# Test 18: Globe endpoint is read-only (does not change run status)
# ===========================================================================

def test_globe_endpoint_is_read_only(isolated_globe_setup):
    """Test 18: Calling the globe endpoint does not alter run status."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed")

    res = client.get(f"/api/v1/runs/{run.id}/globe?sample_step_seconds=3600")
    assert res.status_code == 200

    # Verify run status unchanged
    session.refresh(run)
    assert run.status == "completed"


# ===========================================================================
# Test 19: Globe endpoint makes no network call
# ===========================================================================

def test_globe_endpoint_no_network_call(isolated_globe_setup):
    """Test 19: The globe endpoint does not open external network connections."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed")

    blocked_addresses = []
    original_connect = socket.socket.connect

    def spy_connect(self, address):
        host = address[0] if isinstance(address, tuple) else ""
        if host not in ("127.0.0.1", "localhost", "::1", ""):
            blocked_addresses.append(address)
        return original_connect(self, address)

    socket.socket.connect = spy_connect
    try:
        client.get(f"/api/v1/runs/{run.id}/globe?sample_step_seconds=3600")
    finally:
        socket.socket.connect = original_connect

    assert blocked_addresses == [], (
        f"Globe endpoint made external network call(s): {blocked_addresses}"
    )


# ===========================================================================
# Additional unit tests: _sv_to_point helper
# ===========================================================================

def test_sv_to_point_conversion():
    """Test: _sv_to_point correctly converts StateVector to GlobeStatePoint."""
    t = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sv = StateVector(
        timestamp=t,
        position_km=(1.0, 2.0, 3.0),
        velocity_km_s=(4.0, 5.0, 6.0),
        frame="TEME",
        model="CircularJ2",
        object_id="cand-001",
    )
    pt = _sv_to_point(sv)
    assert pt.t == t
    assert pt.x == pytest.approx(1.0)
    assert pt.y == pytest.approx(2.0)
    assert pt.z == pytest.approx(3.0)
    assert pt.vx == pytest.approx(4.0)
    assert pt.vy == pytest.approx(5.0)
    assert pt.vz == pytest.approx(6.0)


# ===========================================================================
# Additional: epoch_start and epoch_end are correctly computed from plan
# ===========================================================================

def test_globe_epoch_window_from_plan(isolated_globe_setup):
    """Test: epoch_start and epoch_end in response correspond to plan parameters."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=2)

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        db=session,
    )

    expected_start = _epoch_utc()
    expected_end = expected_start.replace(day=expected_start.day + 2)

    # epoch_start must match plan.epoch_start
    assert abs((result.epoch_start - expected_start).total_seconds()) < 1.0
    # epoch_end must be 2 days after epoch_start
    delta_days = (result.epoch_end - result.epoch_start).total_seconds() / 86400.0
    assert delta_days == pytest.approx(2.0, abs=0.01)


# ===========================================================================
# Additional: Globe candidate tracks are ordered by rank
# ===========================================================================

def test_candidate_tracks_ordered_by_rank(isolated_globe_setup):
    """Test: Candidate tracks are returned in rank ASC order."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=3)

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        db=session,
    )

    ranks = [t.rank for t in result.candidates if t.rank is not None]
    assert ranks == sorted(ranks), "Candidate tracks must be ordered by rank ASC"


# ===========================================================================
# Additional: Candidate trajectory model is CircularJ2
# ===========================================================================

def test_candidate_trajectory_uses_circular_j2(isolated_globe_setup):
    """Test: Candidate trajectory produces constant-radius orbit (circular)."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=1, altitude_km=550.0)

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=1800,  # 30 min step
        db=session,
    )

    track = result.candidates[0]
    assert track.point_count > 1
    radii = [
        math.sqrt(pt.x**2 + pt.y**2 + pt.z**2)
        for pt in track.trajectory
    ]
    # Circular orbit: all radii should be within ~2 km of each other
    r_min, r_max = min(radii), max(radii)
    assert (r_max - r_min) < 2.0, (
        f"Non-circular orbit detected: r_min={r_min:.3f}, r_max={r_max:.3f}"
    )


# ===========================================================================
# Test: Delayed candidate trajectory starts at its deployment_epoch
# ===========================================================================

def test_delayed_candidate_trajectory_starts_at_deployment_epoch(isolated_globe_setup):
    """Test: A candidate with deployment delay starts propagation at deployment_epoch."""
    from datetime import timedelta
    session, globe_service, _, _ = isolated_globe_setup
    plan, run = _seed_plan_and_run(session, status="completed", screening_days=2)

    # Seed one delayed candidate (delay = 45 minutes)
    cands = _seed_candidates(session, run_id=run.id, n=1)
    cand = cands[0]
    cand.deployment_delay_minutes = 45.0
    session.commit()

    result = globe_service.get_globe_data(
        run_id=run.id,
        sample_step_seconds=3600,
        db=session,
    )

    assert result.candidate_count == 1
    track = result.candidates[0]
    expected_deployment_epoch = plan.epoch_start + timedelta(minutes=45.0)
    expected_screening_end = expected_deployment_epoch + timedelta(days=2)

    # Trajectory start must match deployment_epoch exactly
    assert track.deployment_epoch == expected_deployment_epoch
    assert track.trajectory_start == expected_deployment_epoch
    assert track.trajectory[0].t == expected_deployment_epoch
    # Trajectory end must match deployment_epoch + screening_days
    assert track.trajectory_end == expected_screening_end
    assert track.trajectory[-1].t == expected_screening_end
    # Ensure no points precede deployment_epoch
    for pt in track.trajectory:
        assert pt.t >= expected_deployment_epoch


# ===========================================================================
# Test: Debris fallback ordering is deterministic
# ===========================================================================

def test_debris_fallback_ordering_deterministic(isolated_globe_setup):
    """Test: Debris fallback ordering is strictly deterministic across repeated invocations."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    _seed_candidates(session, run_id=run.id, n=1)

    # Seed 5 debris objects with non-sequential norad_ids
    debris_norads = ["50005", "10001", "30003", "20002", "40004"]
    for norad in debris_norads:
        _seed_debris(
            session,
            norad_id=norad,
            name=f"DEB-{norad}",
            tle1=ISS_LINE1.replace("25544", norad),
            tle2=ISS_LINE2.replace("25544", norad),
        )

    # Call get_globe_data 3 times and verify exact identical ordering each time
    results = [
        globe_service.get_globe_data(run_id=run.id, max_debris=4, db=session)
        for _ in range(3)
    ]

    ordering_0 = [d.norad_id for d in results[0].debris]
    ordering_1 = [d.norad_id for d in results[1].debris]
    ordering_2 = [d.norad_id for d in results[2].debris]

    assert ordering_0 == ordering_1 == ordering_2
    # Verify ordered by norad_id ASC
    assert ordering_0 == sorted(ordering_0)


# ===========================================================================
# Test: Event markers filtered to selected candidate and included debris
# ===========================================================================

def test_event_markers_filtered_to_selected_candidates_and_debris(isolated_globe_setup):
    """Test: Event markers are strictly limited to the selected candidate and debris subset."""
    session, globe_service, _, _ = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    candidates = _seed_candidates(session, run_id=run.id, n=2)
    deb1 = _seed_debris(session, norad_id="11111", name="DEB-1")
    deb2 = _seed_debris(session, norad_id="22222", name="DEB-2", tle1=SSO_LINE1, tle2=SSO_LINE2)

    # Event 1: cand[0] with deb1
    _seed_conjunction_event(
        session, run_id=run.id, candidate_id=candidates[0].id, debris_object_id=deb1.id, tca=_epoch_utc()
    )
    # Event 2: cand[1] with deb2
    _seed_conjunction_event(
        session, run_id=run.id, candidate_id=candidates[1].id, debris_object_id=deb2.id, tca=_epoch_utc()
    )

    # Case A: Request only cand[0]
    res_cand0 = globe_service.get_globe_data(
        run_id=run.id,
        candidate_ids=[candidates[0].id],
        db=session,
    )
    assert res_cand0.candidate_count == 1
    assert res_cand0.candidates[0].candidate_id == candidates[0].id
    # Event marker must only be for cand[0]
    assert res_cand0.event_count == 1
    assert res_cand0.events[0].candidate_id == candidates[0].id
    assert res_cand0.events[0].debris_norad_id == "11111"

    # Case B: Request both candidates but max_debris=1 (only 1 debris track returned)
    res_deb_limit = globe_service.get_globe_data(
        run_id=run.id,
        max_debris=1,
        db=session,
    )
    assert res_deb_limit.debris_count == 1
    included_deb_ids = {d.debris_db_id for d in res_deb_limit.debris}
    # All event markers must belong to the included debris
    for evt in res_deb_limit.events:
        assert evt.debris_object_id in included_deb_ids


# ===========================================================================
# Test: Explicit candidate_ids query parameter handling
# ===========================================================================

def test_explicit_candidate_ids_via_endpoint(isolated_globe_setup):
    """Test: GET /api/v1/runs/{run_id}/globe with candidate_ids parameter."""
    session, _, _, client = isolated_globe_setup
    _, run = _seed_plan_and_run(session, status="completed", screening_days=1)
    candidates = _seed_candidates(session, run_id=run.id, n=3)

    # 1. Single valid candidate ID
    cid0 = candidates[0].id
    res1 = client.get(f"/api/v1/runs/{run.id}/globe?candidate_ids={cid0}")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["candidate_count"] == 1
    assert data1["candidates"][0]["candidate_id"] == cid0

    # 2. Comma-separated candidate IDs
    cid1 = candidates[1].id
    res2 = client.get(f"/api/v1/runs/{run.id}/globe?candidate_ids={cid1},{cid0}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["candidate_count"] == 2
    # Preserves requested selection
    cids_returned = [c["candidate_id"] for c in data2["candidates"]]
    assert cids_returned == [cid1, cid0]

    # 3. Unknown candidate ID -> 404 with deterministic error
    res_unknown = client.get(f"/api/v1/runs/{run.id}/globe?candidate_ids={cid0},unknown-cand-id")
    assert res_unknown.status_code == 404
    err_data = res_unknown.json()
    assert err_data["detail"]["code"] == "CANDIDATE_NOT_FOUND"
    assert "unknown-cand-id" in err_data["detail"]["message"]

    # 4. Malformed / empty candidate IDs -> 422
    res_empty = client.get(f"/api/v1/runs/{run.id}/globe?candidate_ids=")
    assert res_empty.status_code == 422
    res_trailing = client.get(f"/api/v1/runs/{run.id}/globe?candidate_ids={cid0},")
    assert res_trailing.status_code == 422

