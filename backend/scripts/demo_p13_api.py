"""Offline Phase P13 demonstration of D-DATO FastAPI REST API endpoints.

Demonstrates:
1. POST /api/v1/plans (HTTP 202 Accepted, asynchronous non-blocking submission)
2. Extracting plan_id and run_id
3. Polling GET /api/v1/runs/{run_id} until terminal state
4. GET /api/v1/plans/{plan_id} (retrieving persisted plan configuration)
5. GET /api/v1/plans/{plan_id}/runs (retrieving associated run history)
6. GET /api/v1/runs/{run_id}/candidates (retrieving ranked deployment candidates)
7. GET /api/v1/runs/{run_id}/events (retrieving detected close-approach events)
8. Pagination and result inspection

NON-OPERATIONAL API DEMONSTRATION
No live network connectivity used.
"""

from datetime import datetime, timezone
import json
import os
import shutil
import socket
import sys
import tempfile
import time

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.services.run_service import RunService, get_run_service
from app.workers.screening_worker import WorkerManager


def block_network():
    """Block external network socket connections while permitting local asyncio loopback IPC."""
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) and address else ""
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_connect(self, address)
        raise socket.error(f"External network connection to {address} is blocked: Demo mode is strictly offline.")

    socket.socket.connect = guarded_connect


def run_demo():
    print("=" * 110)
    print("D-DATO PHASE P13: FASTAPI PLANNING, RUN-STATUS, CANDIDATE-RESULTS & CONJUNCTION-EVENT API")
    print("=" * 110)
    print("NON-OPERATIONAL API DEMONSTRATION")
    print("IMPORTANT DISCLAIMER:")
    print("  - This demonstration exercises the FastAPI REST layer over the asynchronous screening worker.")
    print("  - POST /plans queues execution and returns HTTP 202 Accepted immediately without blocking.")
    print("  - Status polling, candidate ranking, and conjunction event results are exposed as JSON contracts.")
    print("  - It is NOT a guarantee of collision avoidance or operational flight safety.")
    print("=" * 110)

    # 1. Enforce strict offline execution
    block_network()

    # 2. Set up isolated test database and RunService
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "demo_p13.db")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=session_factory, worker_manager=worker_mgr)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_service():
        return run_service

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_run_service] = override_service

    client = TestClient(app)

    try:
        # Step 1: POST /api/v1/plans
        print("\n[Step 1] POST /api/v1/plans -> Submitting asynchronous planning request...")
        plan_request = {
            "epoch_start": "2026-10-02T12:00:00Z",
            "altitude_min_km": 500.0,
            "altitude_max_km": 600.0,
            "altitude_step_km": 25.0,
            "inclination_min_deg": 97.0,
            "inclination_max_deg": 98.0,
            "inclination_step_deg": 0.5,
            "raan_deg": 0.0,
            "u0_deg": 0.0,
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

        start_time = time.perf_counter()
        post_res = client.post("/api/v1/plans", json=plan_request)
        elapsed_submit = time.perf_counter() - start_time

        print(f"HTTP Status: {post_res.status_code} Accepted (response time: {elapsed_submit * 1000:.1f} ms)")
        post_data = post_res.json()
        print("Response JSON:")
        print(json.dumps(post_data, indent=2))

        plan_id = post_data["plan_id"]
        run_id = post_data["run_id"]
        initial_status = post_data["status"]
        print(f"\nExtracted Plan ID: {plan_id}")
        print(f"Extracted Run ID:  {run_id}")
        print(f"Initial Status:    {initial_status}")

        # Step 2: Poll GET /api/v1/runs/{run_id}
        print(f"\n[Step 2] GET /api/v1/runs/{run_id} -> Polling run status until terminal state...")
        poll_count = 0
        terminal_data = None
        poll_start = time.perf_counter()

        while time.perf_counter() - poll_start < 25.0:
            poll_count += 1
            res = client.get(f"/api/v1/runs/{run_id}")
            assert res.status_code == 200
            data = res.json()
            curr_status = data["status"]
            progress = data.get("progress_percent", 0.0)
            stage = data.get("current_stage", "unknown")
            msg = data.get("message", "")

            print(f"  Poll #{poll_count:02d} (+{time.perf_counter() - poll_start:.2f}s): "
                  f"status={curr_status:<9} progress={progress:5.1f}% stage={stage:<22} msg={msg}")

            if curr_status in ("completed", "failed", "cancelled"):
                terminal_data = data
                break
            time.sleep(0.4)

        if not terminal_data or terminal_data["status"] != "completed":
            print(f"ERROR: Run did not complete successfully. Status: {terminal_data}")
            return

        print(f"\nRun reached terminal status: {terminal_data['status']} in {time.perf_counter() - poll_start:.2f}s")
        print(f"Candidates Evaluated: {terminal_data['candidate_count']}")
        print(f"Candidates Ranked:    {terminal_data['ranked_candidate_count']}")
        print(f"Conjunction Events:   {terminal_data['conjunction_event_count']}")

        # Step 3: GET /api/v1/plans/{plan_id}
        print(f"\n[Step 3] GET /api/v1/plans/{plan_id} -> Retrieving persisted plan parameters...")
        plan_res = client.get(f"/api/v1/plans/{plan_id}")
        print(f"HTTP Status: {plan_res.status_code} OK")
        plan_details = plan_res.json()
        print(f"  Altitude Bounds:     {plan_details['altitude_min_km']} - {plan_details['altitude_max_km']} km (step: {plan_details['altitude_step_km']} km)")
        print(f"  Inclination Bounds:  {plan_details['inclination_min_deg']} - {plan_details['inclination_max_deg']} deg (step: {plan_details['inclination_step_deg']} deg)")
        print(f"  Deployment Delays:   {plan_details['delay_min_minutes']} - {plan_details['delay_max_minutes']} min (step: {plan_details['delay_step_minutes']} min)")
        print(f"  Weights:             Fuel={plan_details['fuel_weight']:.2f}, Risk={plan_details['risk_weight']:.2f}")

        # Step 4: GET /api/v1/plans/{plan_id}/runs
        print(f"\n[Step 4] GET /api/v1/plans/{plan_id}/runs -> Listing associated runs...")
        runs_res = client.get(f"/api/v1/plans/{plan_id}/runs")
        print(f"HTTP Status: {runs_res.status_code} OK")
        runs_list = runs_res.json()
        print(f"  Total Runs for Plan: {runs_list['total']}")
        for r in runs_list["runs"]:
            print(f"    - Run: {r['run_id']} | Status: {r['status']} | Progress: {r['progress_percent']}% | Created: {r['created_at']}")

        # Step 5: GET /api/v1/runs/{run_id}/candidates (Top 5 paginated)
        print(f"\n[Step 5] GET /api/v1/runs/{run_id}/candidates?limit=5&offset=0 -> Top Ranked Candidates...")
        cand_res = client.get(f"/api/v1/runs/{run_id}/candidates?limit=5&offset=0")
        print(f"HTTP Status: {cand_res.status_code} OK")
        cand_data = cand_res.json()
        print(f"  Total Evaluated: {cand_data['total']} | Returned: {len(cand_data['candidates'])} | Limit: {cand_data['limit']} | Offset: {cand_data['offset']}")
        print("-" * 110)
        print(f"{'Rank':<6}{'Alt (km)':<10}{'Inc (deg)':<11}{'Delay (m)':<11}{'Delta-V (m/s)':<15}{'Propellant (kg)':<17}{'Budget OK':<11}{'Risk (0-100)':<12}")
        print("-" * 110)
        for c in cand_data["candidates"]:
            print(
                f"{c['rank']:<6}"
                f"{c['altitude_km']:<10.1f}"
                f"{c['inclination_deg']:<11.2f}"
                f"{c['deployment_delay_minutes']:<11.1f}"
                f"{c['delta_v_m_s']:<15.2f}"
                f"{c['propellant_mass_kg']:<17.4f}"
                f"{str(c['within_dv_budget']):<11}"
                f"{c['risk_score']:<12.2f}"
            )
        print("-" * 110)

        # Step 6: GET /api/v1/runs/{run_id}/events
        print(f"\n[Step 6] GET /api/v1/runs/{run_id}/events -> Detected Close-Approach Conjunction Events...")
        evt_res = client.get(f"/api/v1/runs/{run_id}/events?limit=10&offset=0")
        print(f"HTTP Status: {evt_res.status_code} OK")
        evt_data = evt_res.json()
        print(f"  Total Conjunction Events Detected: {evt_data['total']}")
        if evt_data["events"]:
            print("-" * 110)
            print(f"{'Event ID':<38}{'Candidate ID':<38}{'Miss Dist (km)':<16}{'Rel Vel (km/s)':<16}")
            print("-" * 110)
            for ev in evt_data["events"]:
                print(
                    f"{ev.get('id', 'N/A'):<38}"
                    f"{ev['candidate_id']:<38}"
                    f"{ev['miss_distance_km']:<16.3f}"
                    f"{ev['relative_velocity_km_s']:<16.3f}"
                )
            print("-" * 110)
        else:
            print("  No close approaches detected within the 25.0 km threshold for this parameter envelope.")

        print("\n" + "=" * 110)
        print("PHASE P13 API DEMONSTRATION COMPLETE: ALL CHECKS PASSED SUCCESSFULLY")
        print("=" * 110)

    finally:
        worker_mgr.shutdown(wait=True, cancel_futures=True)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_demo()
