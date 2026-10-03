"""Offline Phase P15 demonstration of D-DATO 3D Globe Trajectory REST API.

The original D-DATO specification is authoritative.

Demonstrates:
1. Creating a small deterministic demo-mode mission plan via POST /api/v1/plans
2. Polling GET /api/v1/runs/{run_id} until terminal state (completed)
3. Calling GET /api/v1/runs/{run_id}/globe to retrieve TEME-frame trajectories
4. Printing candidate track summary: position radius, speed, inclination verification
5. Printing debris track summary (demo mode has no debris; shows fallback behavior)
6. Printing conjunction event markers
7. Strictly offline execution: zero network connectivity
8. Non-zero exit code on failure

Frame: TEME. Position: km. Velocity: km/s.
"""

import math
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
from app.services.globe_service import GlobeService, get_globe_service
from app.services.heatmap_service import HeatmapService, get_heatmap_service
from app.services.run_service import RunService, get_run_service
from app.workers.screening_worker import WorkerManager
from app.core.constants import RE


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
    print("D-DATO PHASE P15: 3D GLOBE TRAJECTORY SERVICE & REST API DEMONSTRATION")
    print("=" * 110)
    print("NON-OPERATIONAL DEMONSTRATION")
    print("TEME-Frame Orbital Trajectories for Cesium/React Frontend Visualization")
    print("Frame: TEME | Position: km | Velocity: km/s | Propagation: CircularJ2 + SGP4")
    print("=" * 110)

    # 1. Enforce strict offline execution
    block_network()
    print("\n[OFFLINE] External network connections blocked.")

    # 2. Setup isolated database and services
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "demo_p15.db")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=session_factory, worker_manager=worker_mgr)
    heatmap_service = HeatmapService(session_factory=session_factory)
    globe_service = GlobeService(session_factory=session_factory)

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

    client = TestClient(app)

    try:
        # ----------------------------------------------------------------
        # Step 1: Create a small deterministic demo plan with conjunctions
        # ----------------------------------------------------------------
        print("\n[Step 1] POST /api/v1/plans -> Submitting asynchronous planning request...")
        # 5 altitudes x 3 inclinations x 2 delays = 30 candidates with demo catalog debris
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
        # Step 3: Call GET /api/v1/runs/{run_id}/globe (1-hour step)
        # ----------------------------------------------------------------
        print("\n[Step 3] GET /api/v1/runs/{run_id}/globe?sample_step_seconds=3600")
        globe_res = client.get(
            f"/api/v1/runs/{run_id}/globe",
            params={"sample_step_seconds": 3600, "max_candidates": 35, "max_debris": 10},
        )
        if globe_res.status_code != 200:
            print(f"FAILED: Expected 200, got {globe_res.status_code}: {globe_res.text}")
            return 1

        data = globe_res.json()

        # ----------------------------------------------------------------
        # Step 4: Print run summary (all contract metadata)
        # ----------------------------------------------------------------
        print("\n[Step 4] Globe response summary:")
        print(f"  run ID              : {data['run_id']}")
        print(f"  final status        : {data['status']}")
        print(f"  frame               : {data['frame']}")
        print(f"  time scale          : {data['time_scale']}")
        print(f"  sample step         : {data['sample_step_seconds']}s")
        print(f"  epoch start         : {data['epoch_start']}")
        print(f"  epoch end           : {data['epoch_end']}")
        print(f"  candidate track count: {data['candidate_count']}")
        print(f"  debris track count  : {data['debris_count']}")
        print(f"  event marker count  : {data['event_count']}")

        # ----------------------------------------------------------------
        # Step 5: Inspect candidate trajectories and per-candidate start times
        # ----------------------------------------------------------------
        print("\n[Step 5] Candidate trajectory analysis (per-candidate deployment epoch):")
        for i, track in enumerate(data["candidates"][:4]):
            traj = track["trajectory"]
            pt0 = traj[0]
            pt_end = traj[-1]
            r = math.sqrt(pt0["x_km"] ** 2 + pt0["y_km"] ** 2 + pt0["z_km"] ** 2)
            v = math.sqrt(pt0["vx_km_s"] ** 2 + pt0["vy_km_s"] ** 2 + pt0["vz_km_s"] ** 2)
            expected_r = RE + track["altitude_km"]
            r_err = abs(r - expected_r)

            print(
                f"  Candidate {i+1} (id={track['candidate_id'][:8]}...): rank={track['rank']} "
                f"alt={track['altitude_km']:.1f}km delay={track['deployment_delay_minutes']:.1f}m"
            )
            print(f"    first timestamp (deployment_epoch): {track['trajectory_start']}")
            print(f"    last timestamp  (screening_end)   : {track['trajectory_end']}")
            print(
                f"    t0: x_km={pt0['x_km']:9.3f} y_km={pt0['y_km']:9.3f} z_km={pt0['z_km']:9.3f} "
                f"r={r:.3f}km |r-r_exp|={r_err:.3f}km |v|={v:.4f}km/s"
            )

            # Assert first timestamp matches deployment_epoch
            assert track["trajectory_start"] == track["deployment_epoch"], "First point != deployment_epoch"

        # ----------------------------------------------------------------
        # Step 6: Inspect debris tracks (first / last timestamps)
        # ----------------------------------------------------------------
        print(f"\n[Step 6] Debris track summary:")
        print(f"  Debris tracks returned: {data['debris_count']}")
        for deb in data["debris"][:4]:
            t_first = deb["trajectory"][0]["t"] if deb["trajectory"] else "N/A"
            t_last = deb["trajectory"][-1]["t"] if deb["trajectory"] else "N/A"
            print(
                f"  norad_id={deb['norad_id']} name={deb['object_name']!r} pts={deb['point_count']} "
                f"first={t_first} last={t_last}"
            )

        # ----------------------------------------------------------------
        # Step 7: Inspect conjunction event markers and Cartesian positions
        # ----------------------------------------------------------------
        print(f"\n[Step 7] Conjunction event markers with Cartesian positions (SGP4 at TCA):")
        print(f"  Event markers returned: {data['event_count']}")
        for evt in data["events"]:
            print(
                f"  event_id={evt['event_id'][:8]}... cand={str(evt.get('candidate_id', ''))[:8]}... "
                f"deb_norad={evt.get('debris_norad_id', 'N/A')} tca={evt['tca']} miss={evt['miss_distance_km']:.3f}km"
            )
            print(
                f"    SGP4 position at TCA: x_km={evt['x_km']:9.3f} y_km={evt['y_km']:9.3f} z_km={evt['z_km']:9.3f}"
            )

        # ----------------------------------------------------------------
        # Step 8: Verify schema fields
        # ----------------------------------------------------------------
        required_top = {
            "run_id", "status", "frame", "time_scale", "sample_step_seconds",
            "epoch_start", "epoch_end", "candidate_count", "debris_count",
            "event_count", "candidates", "debris", "events",
        }
        missing_top = required_top - set(data.keys())
        if missing_top:
            print(f"FAILED: Missing top-level fields: {missing_top}")
            return 1

        if data["candidates"]:
            first = data["candidates"][0]
            required_cand = {
                "candidate_id", "rank", "altitude_km", "inclination_deg",
                "raan_deg", "risk_score", "within_dv_budget", "deployment_delay_minutes",
                "deployment_epoch", "trajectory_start", "trajectory_end",
                "point_count", "trajectory"
            }
            missing_cand = required_cand - set(first.keys())
            if missing_cand:
                print(f"FAILED: Missing candidate track fields: {missing_cand}")
                return 1

            pt = first["trajectory"][0]
            for f in ("t", "x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"):
                if f not in pt:
                    print(f"FAILED: Missing trajectory point field '{f}'")
                    return 1

        print("\n[Step 8] Schema contract validation: OK")

        # ----------------------------------------------------------------
        # Step 9: Explicit candidate_ids request test
        # ----------------------------------------------------------------
        if data["events"]:
            # Pick the candidate that has a conjunction event + one other candidate
            event_cid = data["events"][0]["candidate_id"]
            other_cids = [c["candidate_id"] for c in data["candidates"] if c["candidate_id"] != event_cid]
            req_cands = [event_cid] + (other_cids[:1] if other_cids else [])
        else:
            req_cands = [c["candidate_id"] for c in data["candidates"][:2]]

        cand_ids_param = ",".join(req_cands)
        print(f"\n[Step 9] GET /api/v1/runs/{run_id}/globe?candidate_ids={cand_ids_param}")
        explicit_res = client.get(
            f"/api/v1/runs/{run_id}/globe",
            params={"candidate_ids": cand_ids_param, "sample_step_seconds": 3600},
        )
        if explicit_res.status_code != 200:
            print(f"FAILED: Expected 200, got {explicit_res.status_code}: {explicit_res.text}")
            return 1
        explicit_data = explicit_res.json()
        print(f"  Explicit candidate_ids request result:")
        print(f"    Requested count : {len(req_cands)}")
        print(f"    Returned count  : {explicit_data['candidate_count']}")
        returned_cids = [c["candidate_id"] for c in explicit_data["candidates"]]
        print(f"    Returned IDs    : {[cid[:8] + '...' for cid in returned_cids]}")
        print(f"    Event markers   : {explicit_data['event_count']}")
        for m in explicit_data["events"]:
            print(f"      Event marker: cand={m['candidate_id'][:8]}... deb={m['debris_norad_id']} TCA={m['tca']}")
            print(f"        SGP4 position: x_km={m['x_km']:.3f} y_km={m['y_km']:.3f} z_km={m['z_km']:.3f}")
        assert returned_cids == req_cands, "Requested candidate order/subset mismatch"
        print("  explicit candidate_ids filter: OK")

        # ----------------------------------------------------------------
        # Step 10: Validate 404 for unknown candidate ID
        # ----------------------------------------------------------------
        print("\n[Step 10] GET /api/v1/runs/{run_id}/globe?candidate_ids=invalid-id -> expect 404")
        err_res = client.get(f"/api/v1/runs/{run_id}/globe?candidate_ids=invalid-cand-id")
        if err_res.status_code != 404:
            print(f"FAILED: Expected 404, got {err_res.status_code}")
            return 1
        print(f"  404 Not Found (CANDIDATE_NOT_FOUND): OK -> {err_res.json()['detail']['code']}")

        # ----------------------------------------------------------------
        # Done
        # ----------------------------------------------------------------
        print("\n" + "=" * 110)
        print("PHASE P15 DEMONSTRATION: ALL CHECKS PASSED")
        print(f"  Endpoint  : GET /api/v1/runs/{{run_id}}/globe")
        print(f"  Candidates: {data['candidate_count']} tracks, {data['candidates'][0]['point_count']} pts each")
        print(f"  Debris    : {data['debris_count']} tracks")
        print(f"  Events    : {data['event_count']} markers")
        print(f"  Frame     : {data['frame']}")
        print(f"  Step      : {data['sample_step_seconds']}s")
        print("=" * 110)
        return 0

    except Exception as exc:
        import traceback
        print(f"\n[DEMO FAILED] Unexpected exception: {exc}")
        traceback.print_exc()
        return 1

    finally:
        worker_mgr.shutdown(wait=True, cancel_futures=True)
        app.dependency_overrides.clear()
        try:
            engine.dispose()
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(run_demo())
