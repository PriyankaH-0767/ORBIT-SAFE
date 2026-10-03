"""Offline Phase P17 demonstration of D-DATO CSV and PDF Export REST APIs.

NON-OPERATIONAL POSITIONING:
D-DATO is an early-stage screening/planning aid. It is NOT a certified collision-probability
system, operational conjunction assessment tool, maneuver planner, CDM generator, or launch
COLA system. Exports are strictly read-only serialization over persisted database results.
No scientific recomputation, worker submission, or external network access is triggered.

Demonstrates:
1. Creating a deterministic demo-mode mission plan via POST /api/v1/plans
2. Polling GET /api/v1/runs/{run_id} until completion
3. Creating a demo validation record via POST /api/v1/runs/{run_id}/validation
4. Requesting CSV ZIP export via GET /api/v1/runs/{run_id}/exports/csv
5. Saving CSV archive temporarily, inspecting members, headers, and row counts
6. Requesting PDF report export via GET /api/v1/runs/{run_id}/exports/pdf
7. Saving PDF temporarily, verifying PDF signature (%PDF-) and report title
8. Verifying strictly offline execution with blocked external networking
9. Verifying that export generation does not trigger workers or pipeline recomputation
10. Exiting non-zero on failure
"""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile

# Ensure backend directory is on sys.path
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
    """Block external network connections while allowing local IPC."""
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) and address else ""
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_connect(self, address)
        raise socket.error(
            f"External network connection to {address} blocked: Demo mode is strictly offline."
        )

    socket.socket.connect = guarded_connect


def run_demo() -> int:
    print("=" * 110)
    print("D-DATO PHASE P17: READ-ONLY CSV & PDF EXPORT SERVICE DEMONSTRATION")
    print("=" * 110)
    print("NON-OPERATIONAL DEMONSTRATION")
    print("Serialization Layer Over Persisted Screening Results")
    print("Strictly Read-Only | No Science Recalculation | No Worker Submission | Offline Fixtures")
    print("=" * 110)

    # 1. Enforce strict offline execution
    block_network()
    print("\n[OFFLINE] External network connections blocked.")

    # 2. Setup isolated database and services
    temp_dir = tempfile.mkdtemp(prefix="ddato_p17_demo_")
    try:
        db_file = os.path.join(temp_dir, "demo_p17.db")
        engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
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

        with TestClient(app) as client:
            # 3. Submit deterministic planning request
            print("\n[1/6] Submitting mission plan via POST /api/v1/plans...")
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
            plan_res = client.post("/api/v1/plans", json=plan_payload)
            if plan_res.status_code != 202:
                print(f"[ERROR] Plan submission failed ({plan_res.status_code}): {plan_res.text}")
                return 1

            run_id = plan_res.json()["run_id"]
            plan_id = plan_res.json()["plan_id"]
            print(f"      Plan ID : {plan_id}")
            print(f"      Run ID  : {run_id}")

            # 4. Wait for run completion
            print("\n[2/6] Polling GET /api/v1/runs/{run_id} until completion...")
            start_poll = time.time()
            final_status = None
            while time.time() - start_poll < 25.0:
                poll_res = client.get(f"/api/v1/runs/{run_id}")
                if poll_res.status_code != 200:
                    print(f"[ERROR] Polling failed ({poll_res.status_code}): {poll_res.text}")
                    return 1
                status_data = poll_res.json()
                if status_data["status"] in ("completed", "failed"):
                    final_status = status_data
                    break
                time.sleep(0.05)

            if not final_status or final_status["status"] != "completed":
                print(f"[ERROR] Run failed to reach completed state: {final_status}")
                return 1
            print(f"      Status             : {final_status['status'].upper()}")
            print(f"      Candidate Count    : {final_status['candidate_count']}")
            print(f"      Conjunction Events : {final_status['conjunction_event_count']}")

            # 5. Create validation record using P16 workflow
            print("\n[3/6] Generating validation comparison record via POST /api/v1/runs/{run_id}/validation...")
            val_res = client.post(
                f"/api/v1/runs/{run_id}/validation",
                json={
                    "source": "socrates",
                    "tca_tolerance_seconds": 300.0,
                    "miss_distance_tolerance_km": 5.0,
                    "demo_mode": True,
                },
            )
            if val_res.status_code != 200:
                print(f"[ERROR] Validation failed ({val_res.status_code}): {val_res.text}")
                return 1
            val_data = val_res.json()
            print(f"      Validation ID      : {val_data['validation_id']}")
            print(f"      Matched Pairs      : {val_data['summary']['matched_event_count']}")

            # 6. Request CSV Export
            print("\n[4/6] Requesting CSV export via GET /api/v1/runs/{run_id}/exports/csv...")
            # Verify no worker submissions or pipeline calls during export
            with patch("app.workers.screening_worker.WorkerManager.submit") as mock_submit:
                with patch("app.services.pipeline_service.PipelineService.run_pipeline") as mock_pipeline:
                    csv_res = client.get(f"/api/v1/runs/{run_id}/exports/csv")
                    mock_submit.assert_not_called()
                    mock_pipeline.assert_not_called()

            if csv_res.status_code != 200:
                print(f"[ERROR] CSV export failed ({csv_res.status_code}): {csv_res.text}")
                return 1

            csv_size = len(csv_res.content)
            csv_path = os.path.join(temp_dir, f"d-dato-{run_id}-export.zip")
            with open(csv_path, "wb") as f:
                f.write(csv_res.content)

            print(f"      Content-Type       : {csv_res.headers.get('content-type')}")
            print(f"      Content-Disp       : {csv_res.headers.get('content-disposition')}")
            print(f"      Archive Size       : {csv_size:,} bytes")
            print(f"      Saved Temporarily  : {csv_path}")

            # Inspect ZIP archive
            with zipfile.ZipFile(io.BytesIO(csv_res.content)) as zf:
                members = zf.namelist()
                print(f"      ZIP Members ({len(members)})   : {members}")

                # candidates.csv
                cand_rows = list(csv.reader(io.StringIO(zf.read("candidates.csv").decode("utf-8"))))
                cand_headers = cand_rows[0]
                cand_data_rows = cand_rows[1:]

                # events.csv
                evt_rows = list(csv.reader(io.StringIO(zf.read("conjunction_events.csv").decode("utf-8"))))
                evt_headers = evt_rows[0]
                evt_data_rows = evt_rows[1:]

                # validation_summary.csv
                val_rows = list(csv.reader(io.StringIO(zf.read("validation_summary.csv").decode("utf-8"))))
                val_headers = val_rows[0]

                print(f"\n      [candidates.csv]       : {len(cand_data_rows)} rows")
                print(f"        Columns ({len(cand_headers)}) : {', '.join(cand_headers[:6])}...")
                print(f"      [conjunction_events.csv] : {len(evt_data_rows)} rows")
                print(f"        Columns ({len(evt_headers)}) : {', '.join(evt_headers[:6])}...")
                print(f"      [validation_summary.csv] : Available (1 summary record)")

            # 7. Request PDF Report Export
            print("\n[5/6] Requesting PDF report via GET /api/v1/runs/{run_id}/exports/pdf...")
            with patch("app.workers.screening_worker.WorkerManager.submit") as mock_submit:
                with patch("app.services.pipeline_service.PipelineService.run_pipeline") as mock_pipeline:
                    pdf_res = client.get(f"/api/v1/runs/{run_id}/exports/pdf")
                    mock_submit.assert_not_called()
                    mock_pipeline.assert_not_called()

            if pdf_res.status_code != 200:
                print(f"[ERROR] PDF export failed ({pdf_res.status_code}): {pdf_res.text}")
                return 1

            pdf_size = len(pdf_res.content)
            pdf_path = os.path.join(temp_dir, f"d-dato-{run_id}-report.pdf")
            with open(pdf_path, "wb") as f:
                f.write(pdf_res.content)

            print(f"      Content-Type       : {pdf_res.headers.get('content-type')}")
            print(f"      Content-Disp       : {pdf_res.headers.get('content-disposition')}")
            print(f"      PDF Size           : {pdf_size:,} bytes")
            print(f"      Saved Temporarily  : {pdf_path}")

            # Verify PDF signature and semantic text presence
            if not pdf_res.content.startswith(b"%PDF-"):
                print("[ERROR] PDF content does not begin with %PDF- header signature!")
                return 1

            pdf_text = pdf_res.content.decode("latin1", errors="ignore")
            expected_titles = [
                "D-DATO Screening Report",
                "NON-OPERATIONAL NOTICE",
                "1. Run Summary",
                "2. Planning Inputs",
                "3. Ranked Candidates",
                "4. Close-Approach Conjunction Events",
                "5. External Reference Comparison",
                "6. Data Age and Provenance",
                "7. Methodological Scope and Limitations",
            ]
            for title in expected_titles:
                if title not in pdf_text:
                    print(f"[ERROR] Missing expected report section title: '{title}'")
                    return 1

            print(f"      PDF Signature      : Valid (%PDF-)")
            print(f"      Report Sections    : All 7 required sections verified present.")

            # 8. Print Executive Summary
            print("\n[6/6] Export Verification Summary:")
            print("-" * 60)
            print(f"  Run Identifier          : {run_id}")
            print(f"  CSV ZIP Archive Size    : {csv_size:,} bytes")
            print(f"  PDF Screening Size      : {pdf_size:,} bytes")
            print(f"  CSV Member Files        : {', '.join(members)}")
            print(f"  Exported Candidate Rows : {len(cand_data_rows)}")
            print(f"  Exported Conjunctions   : {len(evt_data_rows)}")
            print(f"  Validation Included     : Yes (SOCRATES fixture)")
            print(f"  Read-Only Verification  : No workers, no recomputations, offline socket intact")
            print("-" * 60)
            print("\nDEMONSTRATION COMPLETED SUCCESSFULLY.")
            return 0

    finally:
        # Clean up temporary database directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        worker_mgr.shutdown(wait=True, cancel_futures=True)
        app.dependency_overrides.clear()


if __name__ == "__main__":
    sys.exit(run_demo())
