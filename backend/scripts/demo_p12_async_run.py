"""Offline Phase P12 demonstration of asynchronous screening run lifecycle and background worker."""

from datetime import datetime, timezone
import os
import sys
import tempfile
import time

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.services.run_service import RunService
from app.workers.screening_worker import WorkerManager


def run_demo():
    print("=" * 105)
    print("D-DATO PHASE P12: ASYNCHRONOUS RUN LIFECYCLE & BACKGROUND WORKER DEMO")
    print("=" * 105)
    print("NON-OPERATIONAL DEMONSTRATION")
    print("IMPORTANT DISCLAIMER:")
    print("  - This demonstration showcases asynchronous background worker execution of the planning pipeline.")
    print("  - Runs are submitted non-blockingly, transitions are polled, and results are retrieved via service.")
    print("  - Candidates are 'screening-ranked candidates', NOT guaranteed 'optimal orbits'.")
    print("  - It is NOT a guarantee of collision avoidance or operational flight safety.")
    print("=" * 105)

    # 1. Initialize isolated thread-safe database for the demo
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "demo_p12.db")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 2. Initialize WorkerManager and RunService
    worker_manager = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=session_factory, worker_manager=worker_manager)

    epoch_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)

    # 3. Create deterministic offline demo plan
    # 3 altitudes x 2 inclinations x 4 delays = 24 candidates for clear and snappy progression
    plan = run_service.create_plan({
        "epoch_start": epoch_start,
        "altitude_min_km": 500.0,
        "altitude_max_km": 550.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 97.5,
        "inclination_step_deg": 0.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 180.0,
        "delay_step_minutes": 60.0,
        "screening_days": 1.0,
        "demo_mode": True,
        "dv_budget_m_s": 100.0,
        "spacecraft_mass_kg": 3.0,
        "isp_seconds": 60.0,
        "fuel_weight": 0.4,
        "risk_weight": 0.6,
    })
    print(f"\n1. Created Mission Plan: ID = {plan.id} (demo_mode=True)")

    # 4. Create queued run
    run = run_service.create_run(plan.id)
    print(f"2. Created Run Record: ID = {run.id}, Status = {run.status}")

    # 5. Submit run asynchronously (returns immediately)
    initial_summary = run_service.submit_run(run.id)
    print(f"3. Submitted Run to Worker: Returned Status = {initial_summary.status} (non-blocking)\n")

    # 6. Poll status transitions
    print("=" * 70)
    print(f"{'Observed Status':<15} {'Current Stage':<25} {'Progress':<10} {'Message'}")
    print("-" * 70)

    last_observed_state = None
    start_poll = time.time()
    final_summary = initial_summary

    while time.time() - start_poll < 30.0:
        summary = run_service.get_run_status(run.id)
        current_state = (summary.status, summary.current_stage, summary.progress_percent)

        if current_state != last_observed_state:
            stage_str = summary.current_stage or "none"
            msg_str = summary.message or ""
            print(f"{summary.status:<15} {stage_str:<25} {summary.progress_percent:>5.1f}%    {msg_str}")
            last_observed_state = current_state

        if summary.status in ("completed", "failed"):
            final_summary = summary
            break

        time.sleep(0.15)

    print("=" * 70)

    # 7. Print Execution Summary
    print("\nFINAL RUN SUMMARY:")
    print(f"  - Run ID:                   {final_summary.run_id}")
    print(f"  - Plan ID:                  {final_summary.plan_id}")
    print(f"  - Final Status:             {final_summary.status}")
    print(f"  - Current Stage:            {final_summary.current_stage}")
    print(f"  - Progress:                 {final_summary.progress_percent:.1f}%")
    print(f"  - Created At:               {final_summary.created_at.isoformat()}")
    print(f"  - Started At:               {final_summary.started_at.isoformat() if final_summary.started_at else 'N/A'}")
    print(f"  - Completed At:             {final_summary.completed_at.isoformat() if final_summary.completed_at else 'N/A'}")
    print(f"  - Candidate Count:          {final_summary.candidate_count}")
    print(f"  - Conjunction Events:       {final_summary.conjunction_event_count}")
    print(f"  - Ranked Candidate Count:   {final_summary.ranked_candidate_count}")

    # 8. Retrieve and Print Results
    results = run_service.get_run_results(run.id)
    candidates = results.get("candidates", [])

    print("\n" + "=" * 110)
    print("TOP 10 SCREENING-RANKED CANDIDATES (NON-OPERATIONAL DEMONSTRATION):")
    print("=" * 110)
    print(f"{'Rank':<5} {'Candidate ID':<25} {'Alt(km)':<9} {'Inc(deg)':<9} {'Delay(m)':<9} {'dv(m/s)':<10} {'Risk':<8} {'InBudget'}")
    print("-" * 110)

    for c in candidates[:10]:
        print(
            f"{c.get('rank', 'N/A'):<5} "
            f"{c.get('id', 'N/A'):<25} "
            f"{c.get('altitude_km', 0.0):<9.1f} "
            f"{c.get('inclination_deg', 0.0):<9.2f} "
            f"{c.get('deployment_delay_minutes', 0.0):<9.0f} "
            f"{c.get('delta_v_m_s', 0.0):<10.2f} "
            f"{c.get('risk_score', 0.0):<8.2f} "
            f"{str(c.get('within_dv_budget', True))}"
        )
    print("=" * 110)

    # 9. Clean shutdown
    run_service.shutdown(wait=True)
    engine.dispose()
    try:
        os.remove(db_file)
        os.rmdir(temp_dir)
    except OSError:
        pass

    print("\nEND OF ASYNCHRONOUS PIPELINE DEMONSTRATION")
    print("=" * 105)


if __name__ == "__main__":
    run_demo()
