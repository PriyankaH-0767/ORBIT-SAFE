"""Integration test suite for D-DATO API v1 (Phase P13).

Covers:
- POST /api/v1/plans (202 Accepted, asynchronous non-blocking submission)
- GET /api/v1/plans/{plan_id} (200 with persisted parameters, 404 if unknown)
- GET /api/v1/plans/{plan_id}/runs (200 newest first, 404 if unknown)
- GET /api/v1/runs/{run_id} (200 status polling, 404 if unknown, strictly read-only)
- GET /api/v1/runs/{run_id}/candidates (200 ranked results, pagination, 422 on bad params, run isolation)
- GET /api/v1/runs/{run_id}/events (200 conjunction events, pagination, ordering, run isolation)
- OpenAPI schema contract verification
- Health check regression
- Zero live network dependency in demo mode
"""

import math
import socket
import time
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.services.export_service import ExportService, get_export_service
from app.services.globe_service import GlobeService, get_globe_service
from app.services.heatmap_service import HeatmapService, get_heatmap_service
from app.services.run_service import RunService, get_run_service
from app.services.validation_service import ValidationService, get_validation_service
from app.workers.screening_worker import WorkerManager


@pytest.fixture
def isolated_db_and_service(tmp_path) -> Generator[tuple[Session, RunService, sessionmaker], None, None]:
    """Provide an isolated SQLite database file and dedicated RunService instance per test."""
    db_file = tmp_path / "test_api_v1.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(
        session_factory=TestSessionLocal,
        worker_manager=worker_mgr,
    )

    db_session = TestSessionLocal()
    try:
        yield db_session, run_service, TestSessionLocal
    finally:
        db_session.close()
        worker_mgr.shutdown(wait=True, cancel_futures=True)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture
def client(isolated_db_and_service) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient with isolated DB and RunService overrides."""
    _, run_service, session_factory = isolated_db_and_service
    heatmap_service = HeatmapService(session_factory=session_factory)
    globe_service = GlobeService(session_factory=session_factory)
    validation_service = ValidationService(session_factory=session_factory)
    export_service = ExportService(session_factory=session_factory, validation_service=validation_service)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_get_run_service():
        return run_service

    def override_get_heatmap_service():
        return heatmap_service

    def override_get_globe_service():
        return globe_service

    def override_get_validation_service():
        return validation_service

    def override_get_export_service():
        return export_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_run_service] = override_get_run_service
    app.dependency_overrides[get_heatmap_service] = override_get_heatmap_service
    app.dependency_overrides[get_globe_service] = override_get_globe_service
    app.dependency_overrides[get_validation_service] = override_get_validation_service
    app.dependency_overrides[get_export_service] = override_get_export_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def wait_for_run_terminal_state(
    client: TestClient,
    run_id: str,
    timeout_seconds: float = 25.0,
    interval_seconds: float = 0.05,
) -> dict:
    """Poll GET /api/v1/runs/{run_id} until terminal state (completed or failed)."""
    start_time = time.time()
    last_response = None
    while time.time() - start_time < timeout_seconds:
        res = client.get(f"/api/v1/runs/{run_id}")
        assert res.status_code == 200, f"Polling failed with {res.status_code}: {res.text}"
        data = res.json()
        last_response = data
        if data.get("status") in ("completed", "failed", "cancelled"):
            return data
        time.sleep(interval_seconds)
    raise TimeoutError(
        f"Run '{run_id}' did not reach terminal state within {timeout_seconds}s. Last status: {last_response}"
    )


# ==============================================================================
# 1. POST /api/v1/plans Acceptance Tests
# ==============================================================================

SMALL_DEMO_PLAN = {
    "altitude_min_km": 550.0,
    "altitude_max_km": 575.0,
    "altitude_step_km": 25.0,
    "inclination_min_deg": 97.5,
    "inclination_max_deg": 97.5,
    "inclination_step_deg": 0.5,
    "delay_min_minutes": 0.0,
    "delay_max_minutes": 0.0,
    "delay_step_minutes": 60.0,
    "screening_days": 1,
    "demo_mode": True,
}


def test_post_plan_returns_202_accepted(client: TestClient):
    """Test 1-4: POST /api/v1/plans returns HTTP 202, plan_id, run_id, and race-safe status."""
    res = client.post("/api/v1/plans", json=SMALL_DEMO_PLAN)
    assert res.status_code == 202

    data = res.json()
    assert "plan_id" in data and len(data["plan_id"]) > 0
    assert "run_id" in data and len(data["run_id"]) > 0
    assert data["status"] in ("queued", "running")
    assert "created_at" in data
    assert "message" in data


def test_post_plan_returns_immediately_non_blocking(client: TestClient):
    """Test 5: POST /api/v1/plans returns immediately without waiting for pipeline completion."""
    start = time.perf_counter()
    res = client.post("/api/v1/plans", json={"demo_mode": True})
    elapsed = time.perf_counter() - start

    assert res.status_code == 202
    # Full pipeline for 195 candidates takes >0.2s; endpoint returns almost instantaneously (<0.15s)
    assert elapsed < 0.25


def test_post_plan_defaults_populated(client: TestClient):
    """Test 6: Minimal payload relies on centralized settings defaults."""
    res = client.post("/api/v1/plans", json={"demo_mode": True})
    assert res.status_code == 202
    plan_id = res.json()["plan_id"]

    plan_res = client.get(f"/api/v1/plans/{plan_id}")
    assert plan_res.status_code == 200
    plan_data = plan_res.json()

    assert plan_data["altitude_min_km"] == settings.ALTITUDE_MIN_KM
    assert plan_data["altitude_max_km"] == settings.ALTITUDE_MAX_KM
    assert plan_data["fuel_weight"] == settings.FUEL_WEIGHT
    assert plan_data["risk_weight"] == settings.RISK_WEIGHT
    assert plan_data["demo_mode"] is True


# ==============================================================================
# 2. Polling and Run Lifecycle Tests
# ==============================================================================

def test_get_run_polling_lifecycle(client: TestClient):
    """Test 7: Polling GET /api/v1/runs/{run_id} transitions from active to completed."""
    small_plan = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 575.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.5,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 0.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    create_res = client.post("/api/v1/plans", json=small_plan)
    run_id = create_res.json()["run_id"]

    # Poll until terminal
    terminal = wait_for_run_terminal_state(client, run_id, timeout_seconds=10.0)

    assert terminal["status"] == "completed"
    assert terminal["progress_percent"] == 100.0
    assert terminal["completed_at"] is not None
    assert terminal["started_at"] is not None
    assert terminal["error_message"] is None
    assert terminal["candidate_count"] == 2
    assert terminal["ranked_candidate_count"] == 2


def test_get_run_polling_is_read_only(client: TestClient):
    """Test 8: GET /runs/{run_id} does not alter run state or resubmit."""
    res = client.post("/api/v1/plans", json=SMALL_DEMO_PLAN)
    run_id = res.json()["run_id"]

    status1 = client.get(f"/api/v1/runs/{run_id}").json()
    status2 = client.get(f"/api/v1/runs/{run_id}").json()

    assert status1["run_id"] == status2["run_id"]
    assert status1["created_at"] == status2["created_at"]


# ==============================================================================
# 3. Plan Retrieval Endpoints
# ==============================================================================

def test_get_plan_returns_persisted_parameters(client: TestClient):
    """Test 9: GET /api/v1/plans/{plan_id} returns all planning parameters."""
    custom_plan = {
        "altitude_min_km": 520.0,
        "altitude_max_km": 580.0,
        "altitude_step_km": 30.0,
        "inclination_min_deg": 97.2,
        "inclination_max_deg": 97.8,
        "inclination_step_deg": 0.3,
        "delay_min_minutes": 10.0,
        "delay_max_minutes": 70.0,
        "delay_step_minutes": 30.0,
        "reference_altitude_km": 540.0,
        "reference_inclination_deg": 97.5,
        "dv_budget_m_s": 150.0,
        "spacecraft_mass_kg": 4.5,
        "isp_seconds": 65.0,
        "fuel_weight": 0.5,
        "risk_weight": 0.5,
        "screening_days": 2,
        "demo_mode": True,
    }
    post_res = client.post("/api/v1/plans", json=custom_plan)
    plan_id = post_res.json()["plan_id"]

    get_res = client.get(f"/api/v1/plans/{plan_id}")
    assert get_res.status_code == 200
    data = get_res.json()

    assert data["plan_id"] == plan_id
    assert math.isclose(data["altitude_min_km"], 520.0)
    assert math.isclose(data["altitude_max_km"], 580.0)
    assert math.isclose(data["dv_budget_m_s"], 150.0)
    assert math.isclose(data["spacecraft_mass_kg"], 4.5)
    assert data["screening_days"] == 2
    assert data["demo_mode"] is True


def test_get_plan_runs_list(client: TestClient):
    """Test 10: GET /api/v1/plans/{plan_id}/runs returns associated runs newest first."""
    post_res = client.post("/api/v1/plans", json=SMALL_DEMO_PLAN)
    plan_id = post_res.json()["plan_id"]
    run_id = post_res.json()["run_id"]

    runs_res = client.get(f"/api/v1/plans/{plan_id}/runs")
    assert runs_res.status_code == 200
    data = runs_res.json()

    assert data["plan_id"] == plan_id
    assert data["total"] >= 1
    assert len(data["runs"]) >= 1
    assert data["runs"][0]["run_id"] == run_id


# ==============================================================================
# 4. Candidates and Events Retrieval & Pagination
# ==============================================================================

def test_read_only_candidate_events_for_uncompleted_run(client: TestClient, isolated_db_and_service):
    """Test 10b: Querying candidates and events before completion returns HTTP 200 with total=0 and empty list without blocking."""
    _, run_service, session_factory = isolated_db_and_service
    with session_factory() as session:
        plan = run_service.create_plan({"demo_mode": True}, db=session)
        run = run_service.create_run(plan.id, db=session)
        run_id = run.id

    cand_res = client.get(f"/api/v1/runs/{run_id}/candidates")
    assert cand_res.status_code == 200
    cand_data = cand_res.json()
    assert cand_data["run_id"] == run_id
    assert cand_data["total"] == 0
    assert cand_data["candidates"] == []

    evt_res = client.get(f"/api/v1/runs/{run_id}/events")
    assert evt_res.status_code == 200
    evt_data = evt_res.json()
    assert evt_data["run_id"] == run_id
    assert evt_data["total"] == 0
    assert evt_data["events"] == []

def test_get_candidates_after_completion(client: TestClient):
    """Test 11: GET /api/v1/runs/{run_id}/candidates returns ranked results ordered by rank."""
    small_plan = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 575.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.5,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 0.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    create_res = client.post("/api/v1/plans", json=small_plan)
    run_id = create_res.json()["run_id"]

    wait_for_run_terminal_state(client, run_id, timeout_seconds=10.0)

    cand_res = client.get(f"/api/v1/runs/{run_id}/candidates")
    assert cand_res.status_code == 200
    data = cand_res.json()

    assert data["run_id"] == run_id
    assert data["total"] == 2
    assert len(data["candidates"]) == 2

    cands = data["candidates"]
    assert cands[0]["rank"] == 1
    assert cands[1]["rank"] == 2
    assert cands[0]["rank"] <= cands[1]["rank"]
    assert cands[0]["delta_v_m_s"] >= 0.0
    assert cands[0]["risk_score"] >= 0.0


def test_candidates_pagination(client: TestClient):
    """Test 12: Candidates pagination with limit and offset."""
    small_plan = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 575.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.5,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 0.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    create_res = client.post("/api/v1/plans", json=small_plan)
    run_id = create_res.json()["run_id"]
    wait_for_run_terminal_state(client, run_id, timeout_seconds=10.0)

    # Page 1: limit 1, offset 0
    p1 = client.get(f"/api/v1/runs/{run_id}/candidates?limit=1&offset=0").json()
    assert p1["total"] == 2
    assert len(p1["candidates"]) == 1
    assert p1["candidates"][0]["rank"] == 1

    # Page 2: limit 1, offset 1
    p2 = client.get(f"/api/v1/runs/{run_id}/candidates?limit=1&offset=1").json()
    assert p2["total"] == 2
    assert len(p2["candidates"]) == 1
    assert p2["candidates"][0]["rank"] == 2


def test_get_events_after_completion(client: TestClient):
    """Test 13: GET /api/v1/runs/{run_id}/events returns close-approach conjunction events."""
    event_plan = {
        "epoch_start": "2026-10-02T12:00:00Z",
        "altitude_min_km": 500.0,
        "altitude_max_km": 600.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 98.0,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 60.0,
        "delay_step_minutes": 60.0,
        "screening_days": 3,
        "demo_mode": True,
    }
    create_res = client.post("/api/v1/plans", json=event_plan)
    run_id = create_res.json()["run_id"]
    wait_for_run_terminal_state(client, run_id, timeout_seconds=30.0)

    evt_res = client.get(f"/api/v1/runs/{run_id}/events")
    assert evt_res.status_code == 200
    data = evt_res.json()

    assert data["run_id"] == run_id
    assert data["total"] == 2
    assert len(data["events"]) == 2

    ev1 = data["events"][0]
    assert ev1["miss_distance_km"] > 0.0
    assert ev1["relative_velocity_km_s"] > 0.0
    assert ev1["threshold_km"] == 25.0
    assert ev1["screening_source"] == "ddato"

    # Verify ordering by TCA ascending
    assert data["events"][0]["tca"] <= data["events"][1]["tca"]


def test_events_pagination(client: TestClient):
    """Test 14: Events pagination parameters limit and offset."""
    event_plan = {
        "epoch_start": "2026-10-02T12:00:00Z",
        "altitude_min_km": 500.0,
        "altitude_max_km": 600.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 98.0,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 60.0,
        "delay_step_minutes": 60.0,
        "screening_days": 3,
        "demo_mode": True,
    }
    create_res = client.post("/api/v1/plans", json=event_plan)
    run_id = create_res.json()["run_id"]
    wait_for_run_terminal_state(client, run_id, timeout_seconds=15.0)

    # Page 1: limit 1, offset 0
    p1 = client.get(f"/api/v1/runs/{run_id}/events?limit=1&offset=0").json()
    assert p1["total"] == 2
    assert p1["limit"] == 1
    assert p1["offset"] == 0
    assert len(p1["events"]) == 1

    # Page 2: limit 1, offset 1
    p2 = client.get(f"/api/v1/runs/{run_id}/events?limit=1&offset=1").json()
    assert p2["total"] == 2
    assert p2["limit"] == 1
    assert p2["offset"] == 1
    assert len(p2["events"]) == 1
    assert p1["events"][0]["id"] != p2["events"][0]["id"]


# ==============================================================================
# 5. Validation Errors (422) & Not Found (404)
# ==============================================================================

def test_invalid_plan_inputs_rejected_with_422(client: TestClient):
    """Test 15: Invalid plan inputs produce clear HTTP 422 validation errors."""
    cases = [
        {"altitude_min_km": 600.0, "altitude_max_km": 500.0},  # min > max
        {"inclination_min_deg": 190.0},  # > 180
        {"fuel_weight": 0.8, "risk_weight": 0.8},  # sum != 1.0
        {"spacecraft_mass_kg": -2.0},  # negative mass
        {"screening_days": 10},  # > 7 days max
        {"data_source": "unknown_catalog"},  # invalid data source
    ]

    for case in cases:
        payload = {"demo_mode": True, **case}
        res = client.post("/api/v1/plans", json=payload)
        assert res.status_code == 422, f"Expected 422 for payload {payload}, got {res.status_code}"


def test_invalid_pagination_rejected_with_422(client: TestClient):
    """Test 16: Invalid candidate and event query pagination parameters return 422."""
    res1 = client.get("/api/v1/runs/dummy-id/candidates?limit=0")
    assert res1.status_code == 422

    res2 = client.get("/api/v1/runs/dummy-id/candidates?limit=500")
    assert res2.status_code == 422

    res3 = client.get("/api/v1/runs/dummy-id/candidates?offset=-1")
    assert res3.status_code == 422

    res4 = client.get("/api/v1/runs/dummy-id/events?limit=0")
    assert res4.status_code == 422


def test_unknown_plan_returns_404(client: TestClient):
    """Test 17: Unknown plan IDs return HTTP 404 with structured error."""
    res = client.get("/api/v1/plans/non-existent-plan-id")
    assert res.status_code == 404
    detail = res.json().get("detail", {})
    assert detail.get("code") == "PLAN_NOT_FOUND"

    runs_res = client.get("/api/v1/plans/non-existent-plan-id/runs")
    assert runs_res.status_code == 404
    detail2 = runs_res.json().get("detail", {})
    assert detail2.get("code") == "PLAN_NOT_FOUND"


def test_unknown_run_returns_404(client: TestClient):
    """Test 18: Unknown run IDs return HTTP 404 with structured error."""
    for path in [
        "/api/v1/runs/non-existent-run-id",
        "/api/v1/runs/non-existent-run-id/candidates",
        "/api/v1/runs/non-existent-run-id/events",
    ]:
        res = client.get(path)
        assert res.status_code == 404
        detail = res.json().get("detail", {})
        assert detail.get("code") == "RUN_NOT_FOUND"


# ==============================================================================
# 6. Run-Scoped Isolation Tests
# ==============================================================================

def test_run_scoped_isolation(client: TestClient):
    """Test 19: Results from Run A are strictly isolated and not returned for Run B."""
    small_plan_a = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 550.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 97.0,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 0.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    small_plan_b = {
        "altitude_min_km": 600.0,
        "altitude_max_km": 600.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 98.0,
        "inclination_max_deg": 98.0,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 0.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }

    res_a = client.post("/api/v1/plans", json=small_plan_a)
    run_id_a = res_a.json()["run_id"]
    wait_for_run_terminal_state(client, run_id_a, timeout_seconds=10.0)

    res_b = client.post("/api/v1/plans", json=small_plan_b)
    run_id_b = res_b.json()["run_id"]
    wait_for_run_terminal_state(client, run_id_b, timeout_seconds=10.0)

    cands_a = client.get(f"/api/v1/runs/{run_id_a}/candidates").json()["candidates"]
    cands_b = client.get(f"/api/v1/runs/{run_id_b}/candidates").json()["candidates"]

    assert len(cands_a) == 1
    assert len(cands_b) == 1
    assert math.isclose(cands_a[0]["altitude_km"], 550.0)
    assert math.isclose(cands_b[0]["altitude_km"], 600.0)
    assert cands_a[0]["candidate_id"] != cands_b[0]["candidate_id"]


# ==============================================================================
# 7. OpenAPI & Health Contract Tests
# ==============================================================================

def test_openapi_schema_contains_p13_endpoints(client: TestClient):
    """Test 20: /openapi.json contains all required Phase P13 routes and status codes."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    paths = schema["paths"]

    assert "/api/v1/plans" in paths
    assert "post" in paths["/api/v1/plans"]
    assert "202" in paths["/api/v1/plans"]["post"]["responses"]

    assert "/api/v1/plans/{plan_id}" in paths
    assert "get" in paths["/api/v1/plans/{plan_id}"]

    assert "/api/v1/plans/{plan_id}/runs" in paths
    assert "get" in paths["/api/v1/plans/{plan_id}/runs"]

    assert "/api/v1/runs/{run_id}" in paths
    assert "get" in paths["/api/v1/runs/{run_id}"]

    assert "/api/v1/runs/{run_id}/candidates" in paths
    assert "get" in paths["/api/v1/runs/{run_id}/candidates"]

    assert "/api/v1/runs/{run_id}/events" in paths
    assert "get" in paths["/api/v1/runs/{run_id}/events"]


def test_health_endpoint_contract_unmodified(client: TestClient):
    """Test 21: GET /api/v1/health contract remains strictly unmodified."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {
        "status": "ok",
        "service": "D-DATO",
        "version": "0.1.0",
        "environment": "development",
    }


def test_demo_mode_avoids_network(client: TestClient, monkeypatch):
    """Test 22: Demo mode executes completely offline with zero network connectivity."""
    def block_connect(*args, **kwargs):
        raise socket.error("Live network access is strictly prohibited in demo mode!")

    monkeypatch.setattr(socket.socket, "connect", block_connect)

    small_plan = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 575.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.5,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 0.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }

    res = client.post("/api/v1/plans", json=small_plan)
    assert res.status_code == 202
    run_id = res.json()["run_id"]

    terminal = wait_for_run_terminal_state(client, run_id, timeout_seconds=10.0)
    assert terminal["status"] == "completed"


def test_openapi_schema_contains_p14_heatmap_endpoint(client: TestClient):
    """Test 23: /openapi.json contains Phase P14 heatmap route and models."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    paths = schema["paths"]

    assert "/api/v1/runs/{run_id}/heatmap" in paths
    assert "get" in paths["/api/v1/runs/{run_id}/heatmap"]
    get_op = paths["/api/v1/runs/{run_id}/heatmap"]["get"]
    assert "200" in get_op["responses"]
    assert "404" in get_op["responses"]
    assert "422" in get_op["responses"]

    # Parameter check
    param_names = [p["name"] for p in get_op.get("parameters", [])]
    assert "run_id" in param_names
    assert "inclination_deg" in param_names

    # Component schemas check
    schemas = schema["components"]["schemas"]
    assert "HeatmapResponse" in schemas
    assert "HeatmapLayer" in schemas
    assert "HeatmapCell" in schemas


def test_heatmap_endpoint_integration(client: TestClient):
    """Test 24: End-to-end integration of GET /api/v1/runs/{run_id}/heatmap after completed run."""
    plan_payload = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 575.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 60.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    # 2 altitudes x 2 inclinations x 2 delays = 8 candidates
    res = client.post("/api/v1/plans", json=plan_payload)
    assert res.status_code == 202
    run_id = res.json()["run_id"]

    terminal = wait_for_run_terminal_state(client, run_id, timeout_seconds=15.0)
    assert terminal["status"] == "completed"

    # Query heatmap
    h_res = client.get(f"/api/v1/runs/{run_id}/heatmap")
    assert h_res.status_code == 200
    data = h_res.json()
    assert data["run_id"] == run_id
    assert data["status"] == "completed"
    assert data["metric"] == "risk_score"
    assert data["total_candidates"] == 8
    assert data["populated_cells"] == 8
    assert len(data["layers"]) == 2
    assert data["layers"][0]["altitude_values_km"] == [550.0, 575.0]
    assert data["layers"][0]["delay_values_minutes"] == [0.0, 60.0]
    assert len(data["layers"][0]["values"]) == 2
    assert len(data["layers"][0]["values"][0]) == 2


# ==============================================================================
# 25. Phase P15 Globe Endpoint Tests
# ==============================================================================


def test_globe_endpoint_run_not_found(client: TestClient):
    """Test 25: GET /api/v1/runs/NONEXISTENT/globe returns 404."""
    res = client.get("/api/v1/runs/nonexistent-run-99/globe")
    assert res.status_code == 404
    data = res.json()
    assert data["detail"]["code"] == "RUN_NOT_FOUND"


def test_globe_endpoint_query_param_validation_step_too_small(client: TestClient):
    """Test 26: sample_step_seconds < 30 returns 422 Unprocessable Entity."""
    res = client.get("/api/v1/runs/any-run-id/globe?sample_step_seconds=29")
    assert res.status_code == 422


def test_globe_endpoint_queued_run_returns_200_empty(client: TestClient):
    """Test 27: Globe endpoint returns 200 with empty tracks for a queued run."""
    # Create a plan (triggers async run creation)
    res = client.post("/api/v1/plans", json={"demo_mode": True})
    assert res.status_code == 202
    run_id = res.json()["run_id"]

    # Do NOT wait for completion – poll globe immediately (run is queued or running)
    globe_res = client.get(f"/api/v1/runs/{run_id}/globe?sample_step_seconds=3600")
    assert globe_res.status_code == 200
    data = globe_res.json()
    assert data["run_id"] == run_id
    assert data["frame"] == "TEME"
    assert data["time_scale"] == "UTC"
    # Queued or just started run: may have 0 candidates yet
    assert isinstance(data["candidate_count"], int)
    assert isinstance(data["candidates"], list)


def test_globe_endpoint_integration_completed_run(client: TestClient):
    """Test 28: End-to-end integration of GET /api/v1/runs/{run_id}/globe after completed run."""
    plan_payload = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 575.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 60.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    res = client.post("/api/v1/plans", json=plan_payload)
    assert res.status_code == 202
    run_id = res.json()["run_id"]

    terminal = wait_for_run_terminal_state(client, run_id, timeout_seconds=20.0)
    assert terminal["status"] == "completed"

    # Query globe with 1-hour step (manageable payload)
    g_res = client.get(f"/api/v1/runs/{run_id}/globe?sample_step_seconds=3600")
    assert g_res.status_code == 200
    data = g_res.json()

    assert data["run_id"] == run_id
    assert data["status"] == "completed"
    assert data["frame"] == "TEME"
    assert data["time_scale"] == "UTC"
    assert data["sample_step_seconds"] == 3600
    assert "epoch_start" in data
    assert "epoch_end" in data
    # 8 candidates (2 altitudes x 2 inclinations x 2 delays)
    assert data["candidate_count"] == 8
    assert len(data["candidates"]) == 8

    # Verify trajectory structure for first candidate
    first = data["candidates"][0]
    assert "candidate_id" in first
    assert "altitude_km" in first
    assert "inclination_deg" in first
    assert "raan_deg" in first
    assert "risk_score" in first
    assert "within_dv_budget" in first
    assert "deployment_delay_minutes" in first
    assert "deployment_epoch" in first
    assert "trajectory_start" in first
    assert "trajectory_end" in first
    assert "point_count" in first
    assert "trajectory" in first
    assert len(first["trajectory"]) == first["point_count"]
    assert first["point_count"] > 0

    # Verify trajectory point fields
    pt = first["trajectory"][0]
    for field in ("t", "x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"):
        assert field in pt, f"Missing field '{field}' in trajectory point"

    # Verify counts are consistent
    assert data["candidate_count"] == len(data["candidates"])
    assert data["debris_count"] == len(data["debris"])
    assert data["event_count"] == len(data["events"])


def test_globe_openapi_schema_contract(client: TestClient):
    """Test 29: Globe endpoint is registered in OpenAPI schema with correct contract."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()

    # Verify the globe path exists
    paths = schema.get("paths", {})
    globe_path = "/api/v1/runs/{run_id}/globe"
    assert globe_path in paths, f"Globe path not in OpenAPI schema; found paths: {list(paths.keys())}"

    get_op = paths[globe_path].get("get", {})
    assert get_op.get("summary") == "Get 3D globe trajectory data"

    # Verify query parameters
    param_names = {p["name"] for p in get_op.get("parameters", [])}
    assert "run_id" in param_names
    assert "candidate_ids" in param_names
    assert "sample_step_seconds" in param_names
    assert "max_candidates" in param_names
    assert "max_debris" in param_names

    # Verify response schemas are registered
    component_schemas = schema["components"]["schemas"]
    assert "GlobeResponse" in component_schemas
    assert "GlobeCandidateTrack" in component_schemas
    assert "GlobeDebrisTrack" in component_schemas
    assert "GlobeEventMarker" in component_schemas
    assert "GlobeStatePoint" in component_schemas

    # Verify GlobeEventMarker has x_km, y_km, z_km
    event_props = component_schemas["GlobeEventMarker"]["properties"]
    assert "x_km" in event_props
    assert "y_km" in event_props
    assert "z_km" in event_props
    assert "event_id" in event_props


def test_globe_candidate_ids_filter_integration(client: TestClient):
    """Test 30: Integration test for candidate_ids query parameter."""
    plan_payload = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 575.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 60.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    res = client.post("/api/v1/plans", json=plan_payload)
    assert res.status_code == 202
    run_id = res.json()["run_id"]
    wait_for_run_terminal_state(client, run_id, timeout_seconds=20.0)

    # First fetch all candidates to get valid IDs
    cand_res = client.get(f"/api/v1/runs/{run_id}/candidates")
    all_cands = cand_res.json()["candidates"]
    assert len(all_cands) >= 2
    selected_id_1 = all_cands[0]["candidate_id"]
    selected_id_2 = all_cands[1]["candidate_id"]

    # Filter with 1 candidate ID
    filter_res1 = client.get(f"/api/v1/runs/{run_id}/globe?candidate_ids={selected_id_1}")
    assert filter_res1.status_code == 200
    data1 = filter_res1.json()
    assert data1["candidate_count"] == 1
    assert data1["candidates"][0]["candidate_id"] == selected_id_1

    # Filter with 2 candidate IDs
    filter_res2 = client.get(f"/api/v1/runs/{run_id}/globe?candidate_ids={selected_id_2},{selected_id_1}")
    assert filter_res2.status_code == 200
    data2 = filter_res2.json()
    assert data2["candidate_count"] == 2
    assert [c["candidate_id"] for c in data2["candidates"]] == [selected_id_2, selected_id_1]

    # Unknown candidate ID -> 404
    unknown_res = client.get(f"/api/v1/runs/{run_id}/globe?candidate_ids={selected_id_1},fake-candidate-99")
    assert unknown_res.status_code == 404
    assert unknown_res.json()["detail"]["code"] == "CANDIDATE_NOT_FOUND"


def test_validation_completed_run_integration(client: TestClient):
    """Test 31: End-to-end integration test for Phase P16 validation lifecycle."""
    plan_payload = {
        "altitude_min_km": 550.0,
        "altitude_max_km": 575.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 60.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    res = client.post("/api/v1/plans", json=plan_payload)
    assert res.status_code == 202
    run_id = res.json()["run_id"]
    wait_for_run_terminal_state(client, run_id, timeout_seconds=20.0)

    # 1. Trigger validation via POST /api/v1/runs/{run_id}/validation
    val_post = client.post(
        f"/api/v1/runs/{run_id}/validation",
        json={
            "source": "socrates",
            "tca_tolerance_seconds": 300.0,
            "miss_distance_tolerance_km": 5.0,
            "demo_mode": True,
        },
    )
    assert val_post.status_code == 200, val_post.text
    val_data = val_post.json()
    val_id = val_data["validation_id"]
    assert val_data["run_id"] == run_id
    assert val_data["status"] == "completed"
    assert val_data["source"] == "socrates_demo_fixture"
    assert "summary" in val_data
    assert "matches" in val_data
    assert "notes" in val_data
    assert any("NON-OPERATIONAL VALIDATION" in n for n in val_data["notes"])

    # 2. Retrieve latest validation for run via GET /api/v1/runs/{run_id}/validation
    val_get = client.get(f"/api/v1/runs/{run_id}/validation")
    assert val_get.status_code == 200
    assert val_get.json()["validation_id"] == val_id

    # 3. Retrieve validation directly via GET /api/v1/validations/{validation_id}
    val_direct = client.get(f"/api/v1/validations/{val_id}")
    assert val_direct.status_code == 200
    assert val_direct.json()["validation_id"] == val_id

    # 4. Verify candidate screening results remain intact and read-only
    cand_res = client.get(f"/api/v1/runs/{run_id}/candidates")
    assert cand_res.status_code == 200
    assert len(cand_res.json()["candidates"]) >= 2


def test_validation_openapi_contract(client: TestClient):
    """Test 32: Verify OpenAPI schema contract includes validation endpoints."""
    spec_res = client.get("/openapi.json")
    assert spec_res.status_code == 200
    spec = spec_res.json()
    paths = spec.get("paths", {})

    assert "/api/v1/runs/{run_id}/validation" in paths
    runs_val_ops = paths["/api/v1/runs/{run_id}/validation"]
    assert "post" in runs_val_ops
    assert "get" in runs_val_ops

    assert "/api/v1/validations/{validation_id}" in paths
    direct_val_ops = paths["/api/v1/validations/{validation_id}"]
    assert "get" in direct_val_ops


def test_export_csv_and_pdf_endpoints(client: TestClient):
    """Test 33: Verify CSV ZIP and PDF report export endpoints for completed runs."""
    import csv
    import io
    import zipfile

    plan_payload = {
        "altitude_min_km": 500.0,
        "altitude_max_km": 500.0,
        "altitude_step_km": 10.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 97.0,
        "inclination_step_deg": 1.0,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 60.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1,
        "demo_mode": True,
    }
    res = client.post("/api/v1/plans", json=plan_payload)
    assert res.status_code == 202
    run_id = res.json()["run_id"]
    wait_for_run_terminal_state(client, run_id, timeout_seconds=20.0)

    # 1. CSV export without validation
    csv_res = client.get(f"/api/v1/runs/{run_id}/exports/csv")
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"] == "application/zip"
    assert f'filename="d-dato-{run_id}-export.zip"' in csv_res.headers.get("content-disposition", "")

    with zipfile.ZipFile(io.BytesIO(csv_res.content)) as zf:
        members = zf.namelist()
        assert "plan.csv" in members
        assert "candidates.csv" in members
        assert "conjunction_events.csv" in members
        assert "validation_summary.csv" not in members
        assert "validation_matches.csv" not in members

        cand_csv = zf.read("candidates.csv").decode("utf-8")
        reader = list(csv.reader(io.StringIO(cand_csv)))
        assert len(reader) >= 2  # header + candidate rows

    # 2. PDF export without validation
    pdf_res = client.get(f"/api/v1/runs/{run_id}/exports/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert f'filename="d-dato-{run_id}-report.pdf"' in pdf_res.headers.get("content-disposition", "")
    assert pdf_res.content.startswith(b"%PDF-")
    pdf_text = pdf_res.content.decode("latin1", errors="ignore")
    assert "D-DATO Screening Report" in pdf_text
    assert "NON-OPERATIONAL NOTICE" in pdf_text

    # 3. Trigger validation and verify CSV + PDF include validation artifacts
    val_post = client.post(
        f"/api/v1/runs/{run_id}/validation",
        json={
            "source": "socrates",
            "tca_tolerance_seconds": 300.0,
            "miss_distance_tolerance_km": 5.0,
            "demo_mode": True,
        },
    )
    assert val_post.status_code == 200

    csv_val_res = client.get(f"/api/v1/runs/{run_id}/exports/csv")
    assert csv_val_res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(csv_val_res.content)) as zf:
        members = zf.namelist()
        assert "validation_summary.csv" in members
        assert "validation_matches.csv" in members

    pdf_val_res = client.get(f"/api/v1/runs/{run_id}/exports/pdf")
    assert pdf_val_res.status_code == 200
    pdf_val_text = pdf_val_res.content.decode("latin1", errors="ignore")
    assert "5. External Reference Comparison" in pdf_val_text


def test_export_endpoints_unknown_run_404(client: TestClient):
    """Test 34: Export endpoints return 404 for non-existent run_id."""
    res_csv = client.get("/api/v1/runs/unknown-run-id-999/exports/csv")
    assert res_csv.status_code == 404
    data_csv = res_csv.json()
    assert data_csv["detail"]["code"] == "RUN_NOT_FOUND"

    res_pdf = client.get("/api/v1/runs/unknown-run-id-999/exports/pdf")
    assert res_pdf.status_code == 404
    data_pdf = res_pdf.json()
    assert data_pdf["detail"]["code"] == "RUN_NOT_FOUND"


def test_export_openapi_contract(client: TestClient):
    """Test 35: Verify OpenAPI schema contract includes CSV and PDF export endpoints."""
    spec_res = client.get("/openapi.json")
    assert spec_res.status_code == 200
    spec = spec_res.json()
    paths = spec.get("paths", {})

    assert "/api/v1/runs/{run_id}/exports/csv" in paths
    csv_ops = paths["/api/v1/runs/{run_id}/exports/csv"]
    assert "get" in csv_ops
    assert "application/zip" in csv_ops["get"]["responses"]["200"]["content"]

    assert "/api/v1/runs/{run_id}/exports/pdf" in paths
    pdf_ops = paths["/api/v1/runs/{run_id}/exports/pdf"]
    assert "get" in pdf_ops
    assert "application/pdf" in pdf_ops["get"]["responses"]["200"]["content"]


