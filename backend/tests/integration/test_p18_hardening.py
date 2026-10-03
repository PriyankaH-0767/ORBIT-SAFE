"""Phase P18 Hardening and Contract Freeze Integration Tests.

Validates:
1. Complete OpenAPI contract contains all 13 frozen endpoints from Phases P13–P17.
2. Health check endpoint contract invariance.
3. Read-only GET endpoints (plans, runs, candidates, events, heatmap, globe, validation, exports)
   never trigger worker submission, pipeline execution, candidate generation, screening,
   ranking, or validation re-runs.
"""

from __future__ import annotations

import io
from typing import Generator
from unittest.mock import patch
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.services.export_service import ExportService, get_export_service
from app.services.globe_service import GlobeService, get_globe_service
from app.services.heatmap_service import HeatmapService, get_heatmap_service
from app.services.run_service import RunService, get_run_service
from app.services.validation_service import ValidationService, get_validation_service
from app.workers.screening_worker import WorkerManager


@pytest.fixture
def isolated_client(tmp_path) -> Generator[TestClient, None, None]:
    """Provide a TestClient with isolated SQLite database and fresh services."""
    db_file = tmp_path / "test_p18_hardening.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=TestSessionLocal, worker_manager=worker_mgr)
    heatmap_service = HeatmapService(session_factory=TestSessionLocal)
    globe_service = GlobeService(session_factory=TestSessionLocal)
    validation_service = ValidationService(session_factory=TestSessionLocal)
    export_service = ExportService(session_factory=TestSessionLocal, validation_service=validation_service)

    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_heatmap_service] = lambda: heatmap_service
    app.dependency_overrides[get_globe_service] = lambda: globe_service
    app.dependency_overrides[get_validation_service] = lambda: validation_service
    app.dependency_overrides[get_export_service] = lambda: export_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    worker_mgr.shutdown(wait=True, cancel_futures=True)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_frozen_openapi_surface(isolated_client: TestClient):
    """Test: OpenAPI schema contains all 13 frozen endpoints from Phases P13–P17."""
    res = isolated_client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    paths = schema.get("paths", {})

    expected_endpoints = [
        "/api/v1/health",
        "/api/v1/plans",
        "/api/v1/plans/{plan_id}",
        "/api/v1/plans/{plan_id}/runs",
        "/api/v1/runs/{run_id}",
        "/api/v1/runs/{run_id}/candidates",
        "/api/v1/runs/{run_id}/events",
        "/api/v1/runs/{run_id}/heatmap",
        "/api/v1/runs/{run_id}/globe",
        "/api/v1/runs/{run_id}/validation",
        "/api/v1/validations/{validation_id}",
        "/api/v1/runs/{run_id}/exports/csv",
        "/api/v1/runs/{run_id}/exports/pdf",
    ]

    for ep in expected_endpoints:
        assert ep in paths, f"Missing frozen endpoint in OpenAPI schema: {ep}"


def test_health_payload_contract(isolated_client: TestClient):
    """Test: Health check endpoint contract invariance."""
    res = isolated_client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {
        "status": "ok",
        "service": "D-DATO",
        "version": "0.1.0",
        "environment": "development",
    }


def test_read_only_endpoints_do_not_trigger_computation(isolated_client: TestClient):
    """Test: Focused regression ensuring GET endpoints perform zero scientific recomputation."""
    # 1. Create a demo-mode plan and wait for run completion
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
    plan_res = isolated_client.post("/api/v1/plans", json=plan_payload)
    assert plan_res.status_code == 202
    plan_id = plan_res.json()["plan_id"]
    run_id = plan_res.json()["run_id"]

    # Poll run status until completed
    import time
    start = time.time()
    while time.time() - start < 20.0:
        run_res = isolated_client.get(f"/api/v1/runs/{run_id}")
        if run_res.json()["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)
    assert run_res.json()["status"] == "completed"

    # Create one validation record
    val_res = isolated_client.post(
        f"/api/v1/runs/{run_id}/validation",
        json={"source": "socrates", "demo_mode": True},
    )
    assert val_res.status_code == 200
    val_id = val_res.json()["validation_id"]

    # 2. Patch scientific, worker, and pipeline execution methods
    with patch("app.workers.screening_worker.WorkerManager.submit") as mock_submit:
        with patch("app.services.pipeline_service.PipelineService.run_pipeline") as mock_pipeline:
            with patch("app.core.candidate_generator.generate_candidates") as mock_grid:
                with patch("app.core.conjunction.screen_candidate_against_debris") as mock_screen:
                    with patch("app.core.ranking.rank_candidates") as mock_rank:
                        with patch("app.services.validation_service.ValidationService.validate_run") as mock_val:

                            # Exercise all read-only GET endpoints:
                            r_plan = isolated_client.get(f"/api/v1/plans/{plan_id}")
                            assert r_plan.status_code == 200

                            r_plan_runs = isolated_client.get(f"/api/v1/plans/{plan_id}/runs")
                            assert r_plan_runs.status_code == 200

                            r_run = isolated_client.get(f"/api/v1/runs/{run_id}")
                            assert r_run.status_code == 200

                            r_cands = isolated_client.get(f"/api/v1/runs/{run_id}/candidates")
                            assert r_cands.status_code == 200

                            r_events = isolated_client.get(f"/api/v1/runs/{run_id}/events")
                            assert r_events.status_code == 200

                            r_heatmap = isolated_client.get(f"/api/v1/runs/{run_id}/heatmap")
                            assert r_heatmap.status_code == 200

                            r_globe = isolated_client.get(f"/api/v1/runs/{run_id}/globe")
                            assert r_globe.status_code == 200

                            r_val_run = isolated_client.get(f"/api/v1/runs/{run_id}/validation")
                            assert r_val_run.status_code == 200

                            r_val_id = isolated_client.get(f"/api/v1/validations/{val_id}")
                            assert r_val_id.status_code == 200

                            r_csv = isolated_client.get(f"/api/v1/runs/{run_id}/exports/csv")
                            assert r_csv.status_code == 200

                            r_pdf = isolated_client.get(f"/api/v1/runs/{run_id}/exports/pdf")
                            assert r_pdf.status_code == 200

                            # Assert none of the heavy/mutating methods were called
                            mock_submit.assert_not_called()
                            mock_pipeline.assert_not_called()
                            mock_grid.assert_not_called()
                            mock_screen.assert_not_called()
                            mock_rank.assert_not_called()
                            mock_val.assert_not_called()
