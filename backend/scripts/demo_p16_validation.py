"""Offline Phase P16 demonstration of D-DATO External Conjunction Validation REST API.

The original D-DATO specification is authoritative.

NON-OPERATIONAL POSITIONING:
Validation compares D-DATO conjunction screening outputs against external reference
sources (specifically SOCRATES). It is external reference evidence only and does NOT
represent certified flight safety, operational conjunction assessment, true collision
probability, CDM generation, maneuver planning, or launch COLA.

Demonstrates:
1. Creating a deterministic demo-mode mission plan via POST /api/v1/plans
2. Polling GET /api/v1/runs/{run_id} until terminal state (completed)
3. Executing validation via POST /api/v1/runs/{run_id}/validation
4. Retrieving the resulting validation record via GET /api/v1/runs/{run_id}/validation
   and GET /api/v1/validations/{validation_id}
5. Printing run and validation metadata (IDs, status, source, provenance, fetched_at)
6. Printing validation summary metrics (counts, coverage %, match rate %, TCA errors, miss errors)
7. Printing matched-event details (IDs, debris ID, TCAs, errors, criteria)
8. Printing D-DATO-only and external-only events
9. Verifying strictly offline execution with zero external network connectivity
10. Exiting non-zero on failure
"""

import json
import math
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import time

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.services.globe_service import GlobeService, get_globe_service
from app.services.heatmap_service import HeatmapService, get_heatmap_service
from app.services.run_service import RunService, get_run_service
from app.services.validation_service import ValidationService, get_validation_service
from app.workers.screening_worker import WorkerManager


def block_network():
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
    print("D-DATO PHASE P16: EXTERNAL CONJUNCTION VALIDATION SERVICE & REST API DEMONSTRATION")
    print("=" * 110)
    print("NON-OPERATIONAL DEMONSTRATION")
    print("External Reference Comparison against SOCRATES Conjunction Reference Dataset")
    print("Screening is NOT rerun | Read-Only Audit Evidence | Offline Deterministic Fixture")
    print("=" * 110)

    # 1. Enforce strict offline execution
    block_network()
    print("\n[OFFLINE] External network connections blocked.")

    # 2. Setup isolated database and services
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "demo_p16.db")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=session_factory, worker_manager=worker_mgr)
    heatmap_service = HeatmapService(session_factory=session_factory)
    globe_service = GlobeService(session_factory=session_factory)
    validation_service = ValidationService(session_factory=session_factory)

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

    client = TestClient(app)

    try:
        # ----------------------------------------------------------------
        # Step 1: Create a deterministic demo-mode mission plan
        # ----------------------------------------------------------------
        print("\n[Step 1] POST /api/v1/plans -> Submitting asynchronous planning request...")
        plan_payload = {
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
            "reference_altitude_km": 550.0,
            "reference_inclination_deg": 97.5,
            "dv_budget_m_s": 100.0,
            "spacecraft_mass_kg": 3.0,
            "isp_seconds": 60.0,
            "fuel_weight": 0.4,
            "risk_weight": 0.6,
            "data_source": "celestrak",
            "demo_mode": True,
        }
        res = client.post("/api/v1/plans", json=plan_payload)
        if res.status_code != 202:
            print(f"FAILED: Expected 202 Accepted, got {res.status_code}: {res.text}")
            return 1

        run_id = res.json()["run_id"]
        plan_id = res.json()["plan_id"]
        print(f"  Plan ID : {plan_id}")
        print(f"  Run ID  : {run_id}")
        print(f"  Status  : {res.json()['status']}")

        # ----------------------------------------------------------------
        # Step 2: Poll GET /api/v1/runs/{run_id} until completed
        # ----------------------------------------------------------------
        print("\n[Step 2] Polling GET /api/v1/runs/{run_id} until completed...")
        start_time = time.time()
        timeout_seconds = 40.0
        terminal_status = None

        while time.time() - start_time < timeout_seconds:
            poll_res = client.get(f"/api/v1/runs/{run_id}")
            if poll_res.status_code != 200:
                print(f"FAILED: Poll returned {poll_res.status_code}: {poll_res.text}")
                return 1
            poll_data = poll_res.json()
            terminal_status = poll_data.get("status")
            print(
                f"  [{time.time() - start_time:.1f}s] status={terminal_status} "
                f"progress={poll_data.get('progress_percent', 0):.0f}% "
                f"stage={poll_data.get('current_stage', '')}"
            )
            if terminal_status in ("completed", "failed", "cancelled"):
                break
            time.sleep(0.2)

        if terminal_status != "completed":
            print(f"FAILED: Expected 'completed', got '{terminal_status}'")
            return 1
        print(f"  Run completed in {time.time() - start_time:.2f}s")

        # ----------------------------------------------------------------
        # Step 3: Trigger external validation via POST /api/v1/runs/{run_id}/validation
        # ----------------------------------------------------------------
        print("\n[Step 3] POST /api/v1/runs/{run_id}/validation -> Triggering external validation...")
        print("  Validation Tolerances:")
        print("    TCA tolerance used         : 10.0 s")
        print("    Default TCA tolerance      : 300.0 s")
        print("    Miss dist tolerance used   : 5.0 km")
        print("    Default miss dist tolerance: 5.0 km")
        print("  Configured to exercise:")
        print("  - Exact match (Event #1 within 0.001s)")
        print("  - D-DATO-only event (Event #2 with 13.05s TCA offset exceeding 10.0s tolerance)")
        print("  - External-only events (Unmatched SOCRATES reference records)")
        val_req = {
            "source": "socrates",
            "tca_tolerance_seconds": 10.0,
            "miss_distance_tolerance_km": 5.0,
            "demo_mode": True,
        }
        val_res = client.post(f"/api/v1/runs/{run_id}/validation", json=val_req)
        if val_res.status_code != 200:
            print(f"FAILED: Expected 200, got {val_res.status_code}: {val_res.text}")
            return 1

        val_data = val_res.json()
        val_id = val_data["validation_id"]
        print(f"  Validation executed successfully. Validation ID: {val_id}")

        # ----------------------------------------------------------------
        # Step 4: Retrieve persisted validation record
        # ----------------------------------------------------------------
        print(f"\n[Step 4] GET /api/v1/runs/{run_id}/validation -> Reading persisted validation...")
        read_res = client.get(f"/api/v1/runs/{run_id}/validation")
        if read_res.status_code != 200:
            print(f"FAILED: Expected 200, got {read_res.status_code}: {read_res.text}")
            return 1
        data = read_res.json()

        # Also verify direct retrieval by validation ID
        print(f"  GET /api/v1/validations/{val_id} -> Direct retrieval verification...")
        direct_res = client.get(f"/api/v1/validations/{val_id}")
        if direct_res.status_code != 200 or direct_res.json()["validation_id"] != val_id:
            print(f"FAILED: Direct retrieval failed: {direct_res.status_code}")
            return 1
        print("  Direct retrieval by validation ID: OK")

        # ----------------------------------------------------------------
        # Step 5: Print metadata
        # ----------------------------------------------------------------
        print("\n[Step 5] Validation Metadata:")
        print(f"  Run ID           : {data['run_id']}")
        print(f"  Validation ID    : {data['validation_id']}")
        print(f"  Status           : {data['status']}")
        print(f"  Source           : {data['source']}")
        print(f"  Provenance       : demo fixture (strictly offline deterministic reference)")
        print(f"  Source Fetched At: {data['source_fetched_at']}")
        print(f"  Validation Time  : {data['validation_created_at']}")

        # ----------------------------------------------------------------
        # Step 6: Print validation summary metrics
        # ----------------------------------------------------------------
        summary = data["summary"]
        print("\n[Step 6] Validation Summary Metrics:")
        print(f"  D-DATO Event Count   : {summary['d_dato_event_count']}")
        print(f"  External Event Count : {summary['external_event_count']}")
        print(f"  Matched Count        : {summary['matched_event_count']}")
        print(f"  D-DATO-Only Count    : {summary['d_dato_only_count']}")
        print(f"  External-Only Count  : {summary['external_only_count']}")
        print(f"  External Coverage %  : {summary['external_coverage_percent']}%")
        print(f"  D-DATO Match Rate %  : {summary['d_dato_match_rate_percent']}%")
        if summary['mean_abs_tca_error_seconds'] is not None:
            print(f"  Mean |TCA Error| (s) : {summary['mean_abs_tca_error_seconds']:.3f} s")
            print(f"  Max  |TCA Error| (s) : {summary['max_abs_tca_error_seconds']:.3f} s")
        if summary['mean_abs_miss_distance_difference_km'] is not None:
            print(f"  Mean |Miss Diff| (km): {summary['mean_abs_miss_distance_difference_km']:.3f} km")
            print(f"  Max  |Miss Diff| (km): {summary['max_abs_miss_distance_difference_km']:.3f} km")

        # ----------------------------------------------------------------
        # Step 7: Print matched-event examples
        # ----------------------------------------------------------------
        matches = data.get("matches", [])
        print(f"\n[Step 7] Matched-Event Details ({len(matches)} matches):")
        for i, m in enumerate(matches, 1):
            print(f"  Match #{i}:")
            print(f"    D-DATO Event ID   : {m['d_dato_event_id']}")
            print(f"    External Event ID : {m['external_event_id']}")
            print(f"    Candidate ID      : {m['candidate_id']}")
            print(f"    Debris NORAD ID   : {m['debris_norad_id']}")
            print(f"    TCA D-DATO        : {m['tca_d_dato']}")
            print(f"    TCA External      : {m['tca_external']}")
            print(f"    TCA Error (s)     : {m['tca_error_seconds']:+.4f} s")
            print(f"    Miss Dist D-DATO  : {m['miss_distance_d_dato_km']} km")
            print(f"    Miss Dist External: {m['miss_distance_external_km']} km")
            print(f"    Miss Dist Diff    : {m['miss_distance_difference_km']:+.4f} km")
            print(f"    Match Criteria    : {', '.join(m['match_criteria'])}")

        # ----------------------------------------------------------------
        # Step 8: Print D-DATO-only event if available
        # ----------------------------------------------------------------
        d_dato_only = data.get("d_dato_only", [])
        print(f"\n[Step 8] D-DATO-Only Events ({len(d_dato_only)} total):")
        if d_dato_only:
            ev = d_dato_only[0]
            print(f"  Example D-DATO-only event:")
            print(f"    Event ID     : {ev['d_dato_event_id']}")
            print(f"    Candidate ID : {ev['candidate_id']}")
            print(f"    Debris NORAD : {ev['debris_norad_id']}")
            print(f"    TCA          : {ev['tca']}")
            print(f"    Miss Distance: {ev['miss_distance_km']} km")
            print(f"    Notes        : {ev['notes']}")
        else:
            print("  (All D-DATO events matched external reference)")

        # ----------------------------------------------------------------
        # Step 9: Print external-only event if available
        # ----------------------------------------------------------------
        external_only = data.get("external_only", [])
        print(f"\n[Step 9] External-Only Reference Events ({len(external_only)} total):")
        if external_only:
            ev = external_only[0]
            print(f"  Example external-only reference event:")
            print(f"    External ID  : {ev['external_event_id']}")
            print(f"    Debris NORAD : {ev['debris_norad_id']}")
            print(f"    TCA          : {ev['tca']}")
            print(f"    Miss Distance: {ev['miss_distance_km']} km")
            print(f"    Notes        : {ev['notes']}")
        else:
            print("  (All external events matched D-DATO screening events)")

        # ----------------------------------------------------------------
        # Step 10: Print disclaimers and notes
        # ----------------------------------------------------------------
        print("\n[Step 10] Audit & Provenance Notes:")
        for note in data.get("notes", []):
            print(f"  * {note}")

        # ----------------------------------------------------------------
        # Step 11: Schema and non-operational contract validation
        # ----------------------------------------------------------------
        assert data["status"] == "completed"
        assert data["source"] == "socrates_demo_fixture"
        assert len(matches) >= 1, "Expected at least 1 match"
        assert len(external_only) >= 1, "Expected at least 1 external-only event"
        print("\n[Step 11] Contract and data integrity verification: OK")

        print("\n" + "=" * 110)
        print("PHASE P16 DEMONSTRATION: ALL CHECKS PASSED")
        print(f"  Validation ID: {val_id}")
        print(f"  Source       : {data['source']}")
        print(f"  Matches      : {len(matches)}")
        print(f"  D-DATO Only  : {len(d_dato_only)}")
        print(f"  External Only: {len(external_only)}")
        print("=" * 110)
        return 0

    except Exception as exc:
        print(f"\nFATAL DEMO ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        worker_mgr.shutdown(wait=True, cancel_futures=True)
        Base.metadata.drop_all(engine)
        engine.dispose()
        app.dependency_overrides.clear()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(run_demo())
