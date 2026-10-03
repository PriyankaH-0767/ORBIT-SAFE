"""Offline Phase P14 demonstration of D-DATO 2D Risk Heatmap REST API.

The original D-DATO specification is authoritative.
Demonstrates:
1. Creating a small deterministic demo-mode mission plan via POST /api/v1/plans
2. Polling GET /api/v1/runs/{run_id} until terminal state (completed)
3. Calling GET /api/v1/runs/{run_id}/heatmap to retrieve complete multi-layer 2D risk matrices
4. Printing run summary, layer dimensions, altitude and delay axes, risk statistics, and sample cells
5. Calling GET /api/v1/runs/{run_id}/heatmap?inclination_deg=97.5 to demonstrate filtered single-layer retrieval
6. Strictly offline execution with zero network connectivity
7. Non-zero exit code on failure
"""

import os
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
from app.services.heatmap_service import HeatmapService, get_heatmap_service
from app.services.run_service import RunService, get_run_service
from app.workers.screening_worker import WorkerManager


def block_network():
    """Block external network connections while allowing local IPC."""
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) and address else ""
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_connect(self, address)
        raise socket.error(f"External network connection to {address} blocked: Demo mode is strictly offline.")

    socket.socket.connect = guarded_connect


def run_demo() -> int:
    print("=" * 110)
    print("D-DATO PHASE P14: 2D RISK HEATMAP SERVICE & REST API DEMONSTRATION")
    print("=" * 110)
    print("NON-OPERATIONAL DEMONSTRATION")
    print("Screened Candidate Risk Density Matrix for React/Plotly Frontend")
    print("=" * 110)

    # 1. Enforce strict offline execution
    block_network()

    # 2. Setup isolated database and services
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "demo_p14.db")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=session_factory, worker_manager=worker_mgr)
    heatmap_service = HeatmapService(session_factory=session_factory)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_run_service():
        return run_service

    def override_heatmap_service():
        return heatmap_service

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_run_service] = override_run_service
    app.dependency_overrides[get_heatmap_service] = override_heatmap_service

    client = TestClient(app)

    try:
        # Step 1: Create a small deterministic demo plan
        print("\n[Step 1] POST /api/v1/plans -> Submitting asynchronous planning request...")
        # 3 altitudes x 3 inclinations x 2 delays = 18 candidates
        plan_payload = {
            "epoch_start": "2026-10-02T12:00:00Z",
            "altitude_min_km": 550.0,
            "altitude_max_km": 600.0,
            "altitude_step_km": 25.0,
            "inclination_min_deg": 97.0,
            "inclination_max_deg": 98.0,
            "inclination_step_deg": 0.5,
            "delay_min_minutes": 0.0,
            "delay_max_minutes": 60.0,
            "delay_step_minutes": 60.0,
            "raan_delay_coupling_deg_per_min": 0.25,
            "screening_days": 1,
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

        # Step 2: Poll GET /api/v1/runs/{run_id} until completed
        print("\n[Step 2] Polling GET /api/v1/runs/{run_id} until completed...")
        start_time = time.time()
        timeout_seconds = 35.0
        terminal_status = None
        while time.time() - start_time < timeout_seconds:
            poll_res = client.get(f"/api/v1/runs/{run_id}")
            if poll_res.status_code != 200:
                print(f"FAILED: Polling returned {poll_res.status_code}: {poll_res.text}")
                return 1
            data = poll_res.json()
            status_val = data["status"]
            if status_val in ("completed", "failed", "cancelled"):
                terminal_status = status_val
                break
            time.sleep(0.1)

        print(f"  Final Status: {terminal_status} (in {time.time() - start_time:.2f}s)")
        if terminal_status != "completed":
            print(f"FAILED: Expected run status 'completed', got '{terminal_status}'")
            return 1

        # Step 3: GET /api/v1/runs/{run_id}/heatmap (all layers)
        print("\n[Step 3] GET /api/v1/runs/{run_id}/heatmap -> Retrieving all inclination layers...")
        h_res = client.get(f"/api/v1/runs/{run_id}/heatmap")
        if h_res.status_code != 200:
            print(f"FAILED: Heatmap endpoint returned {h_res.status_code}: {h_res.text}")
            return 1

        heatmap_data = h_res.json()
        print(f"  Run ID                  : {heatmap_data['run_id']}")
        print(f"  Status                  : {heatmap_data['status']}")
        print(f"  Metric                  : {heatmap_data['metric']}")
        print(f"  X Axis (Columns)        : {heatmap_data['x_axis']}")
        print(f"  Y Axis (Rows)           : {heatmap_data['y_axis']}")
        print(f"  Total Candidates        : {heatmap_data['total_candidates']}")
        print(f"  Populated Cells         : {heatmap_data['populated_cells']}")
        min_risk_str = f"{heatmap_data['min_risk_score']:.4f}" if heatmap_data['min_risk_score'] is not None else "None"
        max_risk_str = f"{heatmap_data['max_risk_score']:.4f}" if heatmap_data['max_risk_score'] is not None else "None"
        print(f"  Min Risk Score          : {min_risk_str}")
        print(f"  Max Risk Score          : {max_risk_str}")
        print(f"  Inclination Layers Count: {len(heatmap_data['layers'])}")
        print(f"  Inclinations            : {heatmap_data['inclination_values_deg']}")

        # Print details for each layer
        for idx, layer in enumerate(heatmap_data["layers"]):
            inc = layer["inclination_deg"]
            alts = layer["altitude_values_km"]
            delays = layer["delay_values_minutes"]
            matrix = layer["values"]
            n_rows = len(matrix)
            n_cols = len(matrix[0]) if n_rows > 0 else 0
            print(f"\n  --- Layer {idx + 1}: Inclination {inc:.1f} deg ---")
            print(f"      Altitudes (km)  : {alts}")
            print(f"      Delays (minutes): {delays}")
            print(f"      Matrix Shape    : {n_rows} rows x {n_cols} cols")
            print("      Risk Matrix (values[row][col]):")
            header = "      Alt \\ Delay | " + " | ".join(f"{d:6.1f}m" for d in delays)
            print(header)
            print("      " + "-" * (len(header) - 6))
            for r_idx, alt in enumerate(alts):
                row_str = f"      {alt:7.1f}km  | " + " | ".join(
                    f"{matrix[r_idx][c_idx]:7.3f}" if matrix[r_idx][c_idx] is not None else "   null"
                    for c_idx in range(len(delays))
                )
                print(row_str)

        # Print sample cells
        print("\n[Step 4] Example Populated Heatmap Cells:")
        first_layer = heatmap_data["layers"][0]
        for cell in first_layer["cells"][:2]:
            print(f"  - Candidate {cell['candidate_id']}:")
            print(f"      Alt={cell['altitude_km']}km, Inc={cell['inclination_deg']} deg, Delay={cell['delay_minutes']}m")
            print(f"      Risk Score={cell['risk_score']:.3f}, Rank={cell['rank']}, Delta-V={cell['delta_v_m_s']:.2f} m/s")
            print(f"      Within Budget={cell['within_dv_budget']}, Events={cell['accepted_event_count']}, Miss Dist={cell['minimum_miss_distance_km']}")

        # Step 5: GET /api/v1/runs/{run_id}/heatmap?inclination_deg=97.5 (filtered slice)
        target_inc = 97.5
        print(f"\n[Step 5] GET /api/v1/runs/{run_id}/heatmap?inclination_deg={target_inc} -> Sliced Layer...")
        filter_res = client.get(f"/api/v1/runs/{run_id}/heatmap?inclination_deg={target_inc}")
        if filter_res.status_code != 200:
            print(f"FAILED: Filtered heatmap returned {filter_res.status_code}: {filter_res.text}")
            return 1

        filter_data = filter_res.json()
        print(f"  Total Layers Returned: {len(filter_data['layers'])}")
        print(f"  Inclinations         : {filter_data['inclination_values_deg']}")
        print(f"  Total Candidates     : {filter_data['total_candidates']}")
        print(f"  Populated Cells      : {filter_data['populated_cells']}")
        f_min_risk = f"{filter_data['min_risk_score']:.4f}" if filter_data['min_risk_score'] is not None else "None"
        f_max_risk = f"{filter_data['max_risk_score']:.4f}" if filter_data['max_risk_score'] is not None else "None"
        print(f"  Min Risk Score       : {f_min_risk}")
        print(f"  Max Risk Score       : {f_max_risk}")

        if len(filter_data["layers"]) != 1:
            print(f"FAILED: Expected 1 layer for inclination {target_inc}, got {len(filter_data['layers'])}")
            return 1

        print("\n" + "=" * 110)
        print("DEMO P14 SUCCESSFUL: Heatmap service returned exact matrix data completely offline.")
        print("=" * 110)
        return 0

    finally:
        worker_mgr.shutdown(wait=True, cancel_futures=True)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        app.dependency_overrides.clear()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    exit_code = run_demo()
    sys.exit(exit_code)
