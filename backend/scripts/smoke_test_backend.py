"""End-to-end backend smoke test for D-DATO (Phase P18).

Comprehensive verification of all Phase P1–P17 API endpoints:
- Operates strictly offline with blocked external network sockets.
- Creates a mission plan and tracks asynchronous execution lifecycle.
- Retrieves plan details, historical runs, candidates, events, heatmap, globe.
- Executes and retrieves external reference validation.
- Downloads and validates CSV archive and executive PDF report.
- Verifies that read-only GET endpoints perform zero scientific recomputation.
- Reports latency/performance metrics across all phases.
- Emits a concise PASS/FAIL summary and exits non-zero on failure.
"""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
from unittest.mock import patch
import zipfile

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.services.export_service import ExportService, get_export_service
from app.services.globe_service import GlobeService, get_globe_service
from app.services.heatmap_service import HeatmapService, get_heatmap_service
from app.services.run_service import RunService, get_run_service
from app.services.validation_service import ValidationService, get_validation_service
from app.workers.screening_worker import WorkerManager


def block_network() -> None:
    """Strictly block external outbound network connections."""
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) and address else ""
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(self, address)
        raise socket.error(
            f"External network connection to {address} blocked. D-DATO smoke test must run strictly offline."
        )

    socket.socket.connect = guarded_connect


def run_smoke_test() -> int:
    print("=" * 90)
    print("D-DATO END-TO-END BACKEND SMOKE TEST (PHASE P18 HARDENING)")
    print("=" * 90)
    print("Environment: Offline Verification | Mock Socket Guard | Headless Runtime")
    print("=" * 90)

    # 1. Enforce network block
    block_network()
    print("[OFFLINE] Outbound network connections blocked.")

    # 2. Setup isolated database and services
    temp_dir = tempfile.mkdtemp(prefix="ddato_smoke_test_")
    db_file = os.path.join(temp_dir, "smoke_test.db")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=session_factory, worker_manager=worker_mgr)
    heatmap_service = HeatmapService(session_factory=session_factory)
    globe_service = GlobeService(session_factory=session_factory)
    validation_service = ValidationService(session_factory=session_factory)
    export_service = ExportService(session_factory=session_factory, validation_service=validation_service)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_heatmap_service] = lambda: heatmap_service
    app.dependency_overrides[get_globe_service] = lambda: globe_service
    app.dependency_overrides[get_validation_service] = lambda: validation_service
    app.dependency_overrides[get_export_service] = lambda: export_service

    timings: Dict[str, float] = {}

    try:
        with TestClient(app) as client:
            # 3. Health Check
            t0 = time.perf_counter()
            r_health = client.get("/api/v1/health")
            timings["health_check"] = time.perf_counter() - t0
            assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
            assert r_health.json()["status"] == "ok"
            print("  [OK] GET /api/v1/health verified.")

            # 4. POST /api/v1/plans
            plan_payload = {
                "altitude_min_km": 500.0,
                "altitude_max_km": 550.0,
                "altitude_step_km": 25.0,
                "inclination_min_deg": 97.0,
                "inclination_max_deg": 97.5,
                "inclination_step_deg": 0.5,
                "delay_min_minutes": 0.0,
                "delay_max_minutes": 60.0,
                "delay_step_minutes": 30.0,
                "screening_days": 1,
                "demo_mode": True,
            }
            t0 = time.perf_counter()
            r_plan_post = client.post("/api/v1/plans", json=plan_payload)
            timings["post_plan_latency"] = time.perf_counter() - t0
            assert r_plan_post.status_code == 202, f"Plan creation failed: {r_plan_post.text}"
            plan_data = r_plan_post.json()
            plan_id = plan_data["plan_id"]
            run_id = plan_data["run_id"]
            assert plan_data["status"] == "queued"
            print(f"  [OK] POST /api/v1/plans (202 Accepted, run_id={run_id[:8]}..)")

            # 5. Poll GET /api/v1/runs/{run_id}
            t0 = time.perf_counter()
            start_time = time.time()
            final_status = None
            while time.time() - start_time < 30.0:
                r_poll = client.get(f"/api/v1/runs/{run_id}")
                assert r_poll.status_code == 200
                st = r_poll.json()
                if st["status"] in ("completed", "failed"):
                    final_status = st
                    break
                time.sleep(0.05)
            timings["pipeline_completion_time"] = time.perf_counter() - t0
            assert final_status is not None and final_status["status"] == "completed", (
                f"Run failed or timed out: {final_status}"
            )
            candidate_count = final_status["candidate_count"]
            assert candidate_count > 0, "No candidates generated"
            print(f"  [OK] GET /api/v1/runs/{run_id} terminal state=COMPLETED ({candidate_count} candidates)")

            # 6. Retrieve Read-Only Endpoints and verify zero science recomputation
            with patch("app.workers.screening_worker.WorkerManager.submit") as mock_submit:
                with patch("app.services.pipeline_service.PipelineService.run_pipeline") as mock_pipeline:
                    with patch("app.core.candidate_generator.generate_candidates") as mock_cands:
                        with patch("app.core.conjunction.screen_candidate_against_debris") as mock_screen:
                            with patch("app.core.ranking.rank_candidates") as mock_rank:
                                with patch("app.services.validation_service.ValidationService.validate_run") as mock_val:

                                    # GET /api/v1/plans/{plan_id}
                                    r_plan_get = client.get(f"/api/v1/plans/{plan_id}")
                                    assert r_plan_get.status_code == 200
                                    assert r_plan_get.json()["plan_id"] == plan_id

                                    # GET /api/v1/plans/{plan_id}/runs
                                    r_runs_list = client.get(f"/api/v1/plans/{plan_id}/runs")
                                    assert r_runs_list.status_code == 200
                                    assert len(r_runs_list.json()) >= 1

                                    # GET /api/v1/runs/{run_id}/candidates
                                    r_cands_res = client.get(f"/api/v1/runs/{run_id}/candidates")
                                    assert r_cands_res.status_code == 200
                                    assert len(r_cands_res.json()["candidates"]) == candidate_count

                                    # GET /api/v1/runs/{run_id}/events
                                    r_events_res = client.get(f"/api/v1/runs/{run_id}/events")
                                    assert r_events_res.status_code == 200
                                    assert "events" in r_events_res.json()

                                    # GET /api/v1/runs/{run_id}/heatmap
                                    t0 = time.perf_counter()
                                    r_heatmap_res = client.get(f"/api/v1/runs/{run_id}/heatmap")
                                    timings["heatmap_retrieval_time"] = time.perf_counter() - t0
                                    assert r_heatmap_res.status_code == 200
                                    hm_data = r_heatmap_res.json()
                                    assert len(hm_data["layers"]) > 0, "Heatmap layers missing"
                                    assert hm_data["metric"] == "risk_score"

                                    # GET /api/v1/runs/{run_id}/globe
                                    t0 = time.perf_counter()
                                    r_globe_res = client.get(f"/api/v1/runs/{run_id}/globe")
                                    timings["globe_retrieval_time"] = time.perf_counter() - t0
                                    assert r_globe_res.status_code == 200
                                    globe_data = r_globe_res.json()
                                    assert globe_data["frame"] == "TEME"
                                    assert len(globe_data["candidates"]) > 0

                                    # Assert no background or recomputation triggered
                                    mock_submit.assert_not_called()
                                    mock_pipeline.assert_not_called()
                                    mock_cands.assert_not_called()
                                    mock_screen.assert_not_called()
                                    mock_rank.assert_not_called()
                                    mock_val.assert_not_called()

            print("  [OK] Read-only endpoints verified (plans, candidates, events, heatmap, globe)")

            # 7. POST /api/v1/runs/{run_id}/validation
            t0 = time.perf_counter()
            r_val_post = client.post(
                f"/api/v1/runs/{run_id}/validation",
                json={"source": "socrates", "demo_mode": True},
            )
            timings["validation_execution_time"] = time.perf_counter() - t0
            assert r_val_post.status_code == 200, f"Validation failed: {r_val_post.text}"
            val_data = r_val_post.json()
            val_id = val_data["validation_id"]
            assert val_data["status"] == "completed"
            assert val_data["source"] == "socrates_demo_fixture"
            print(f"  [OK] POST /api/v1/runs/{run_id}/validation (completed, source={val_data['source']})")

            # 8. Retrieve validation endpoints
            r_val_run = client.get(f"/api/v1/runs/{run_id}/validation")
            assert r_val_run.status_code == 200
            assert r_val_run.json()["validation_id"] == val_id

            r_val_direct = client.get(f"/api/v1/validations/{val_id}")
            assert r_val_direct.status_code == 200
            assert r_val_direct.json()["validation_id"] == val_id
            print(f"  [OK] GET /api/v1/runs/{run_id}/validation & GET /api/v1/validations/{val_id} verified.")

            # 9. CSV Export
            t0 = time.perf_counter()
            r_csv = client.get(f"/api/v1/runs/{run_id}/exports/csv")
            timings["csv_export_time"] = time.perf_counter() - t0
            assert r_csv.status_code == 200, f"CSV export failed: {r_csv.text}"
            assert r_csv.headers["content-type"] == "application/zip"
            with zipfile.ZipFile(io.BytesIO(r_csv.content)) as zf:
                members = zf.namelist()
                assert "plan.csv" in members
                assert "candidates.csv" in members
                assert "conjunction_events.csv" in members
                assert "validation_summary.csv" in members
                assert "validation_matches.csv" in members
            print(f"  [OK] GET /api/v1/runs/{run_id}/exports/csv ({len(r_csv.content):,} bytes, 5 ZIP files)")

            # 10. PDF Export
            t0 = time.perf_counter()
            r_pdf = client.get(f"/api/v1/runs/{run_id}/exports/pdf")
            timings["pdf_export_time"] = time.perf_counter() - t0
            assert r_pdf.status_code == 200, f"PDF export failed: {r_pdf.text}"
            assert r_pdf.headers["content-type"] == "application/pdf"
            assert r_pdf.content.startswith(b"%PDF-"), "Invalid PDF signature"
            pdf_str = r_pdf.content.decode("latin1", errors="ignore")
            assert "D-DATO Screening Report" in pdf_str
            assert "NON-OPERATIONAL NOTICE" in pdf_str
            print(f"  [OK] GET /api/v1/runs/{run_id}/exports/pdf ({len(r_pdf.content):,} bytes, %PDF- verified)")

            # 11. Performance Sanity Report
            print("\n" + "=" * 90)
            print("PERFORMANCE SANITY OBSERVATIONS (LOCAL RUNTIME)")
            print("=" * 90)
            print(f"  - POST /plans Response Latency   : {timings['post_plan_latency'] * 1000.0:6.1f} ms")
            print(f"  - Pipeline Completion Duration   : {timings['pipeline_completion_time']:6.2f} s")
            print(f"  - Heatmap Retrieval Latency      : {timings['heatmap_retrieval_time'] * 1000.0:6.1f} ms")
            print(f"  - Globe Retrieval Latency        : {timings['globe_retrieval_time'] * 1000.0:6.1f} ms")
            print(f"  - Validation Execution Latency   : {timings['validation_execution_time'] * 1000.0:6.1f} ms")
            print(f"  - CSV Export Generation Time     : {timings['csv_export_time'] * 1000.0:6.1f} ms")
            print(f"  - PDF Report Generation Time     : {timings['pdf_export_time'] * 1000.0:6.1f} ms")
            print("=" * 90)
            print("SMOKE TEST RESULT: PASS (All P1-P17 Endpoints Verified Offline)")
            print("=" * 90)
            return 0

    except Exception as exc:
        print(f"\n[FAIL] Smoke test encountered an error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    finally:
        worker_mgr.shutdown(wait=True, cancel_futures=True)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.dependency_overrides.clear()


if __name__ == "__main__":
    sys.exit(run_smoke_test())
