"""Offline Phase P11 demonstration of the complete D-DATO planning pipeline."""

from datetime import datetime, timezone
import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Plan, Run, RunStatus
from app.services.pipeline_service import PipelineService, PlanParameters


def run_demo():
    print("=" * 105)
    print("D-DATO PHASE P11: END-TO-END SYNCHRONOUS PLANNING PIPELINE DEMO")
    print("=" * 105)
    print("NON-OPERATIONAL DEMONSTRATION")
    print("IMPORTANT DISCLAIMER:")
    print("  - This pipeline is an early-stage screening orchestration demonstration.")
    print("  - It runs the complete D-DATO chain: Ingestion -> Candidates -> Fuel -> Screening -> Risk -> Ranking.")
    print("  - Candidates are 'screening-ranked candidates', NOT guaranteed 'optimal orbits'.")
    print("  - It is NOT a guarantee of collision avoidance or operational flight safety.")
    print("=" * 105)

    # 1. Initialize isolated in-memory database
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    epoch_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        # Create deterministic plan in demo mode
        plan = Plan(
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=600.0,
            altitude_step_km=25.0,
            inclination_min_deg=97.0,
            inclination_max_deg=98.0,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=720.0,
            delay_step_minutes=60.0,  # 5 * 3 * 13 = 195 candidates
            screening_days=1.0,
            demo_mode=True,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
            fuel_weight=0.4,
            risk_weight=0.6,
        )
        session.add(plan)
        session.flush()

        run = Run(
            plan_id=plan.id,
            status=RunStatus.queued.value,
            progress_percent=0.0,
            current_stage="queued",
            message="Run queued for synchronous execution",
        )
        session.add(run)
        session.commit()
        run_id = run.id

        params = PlanParameters(
            plan_id=plan.id,
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=600.0,
            altitude_step_km=25.0,
            inclination_min_deg=97.0,
            inclination_max_deg=98.0,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=720.0,
            delay_step_minutes=60.0,
            screening_days=1.0,
            demo_mode=True,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
            fuel_weight=0.4,
            risk_weight=0.6,
        )

        service = PipelineService()
        result = service.run_pipeline(params, run_id=run_id, db=session)

        # 2. Print pipeline execution metrics
        print("\nPIPELINE EXECUTION SUMMARY:")
        print(f"  - Pipeline status:          {result.status}")
        print(f"  - Run ID:                   {result.run_id}")
        print(f"  - Ingestion mode:           {result.ingestion_mode}")
        print(f"  - Catalog records seen:     {result.catalog_records_seen}")
        print(f"  - Catalog records accepted: {result.catalog_records_accepted}")
        print(f"  - Catalog records rejected: {result.catalog_records_rejected}")
        if result.data_age_seconds is not None:
            print(f"  - Data age:                 {result.data_age_seconds:.1f} s")
        else:
            print("  - Data age:                 N/A")
        print(f"  - Candidate count:          {result.candidate_count}")
        print(f"  - Within-budget count:      {result.within_budget_count}")
        print(f"  - Out-of-budget count:      {result.out_of_budget_count}")
        print(f"  - Conjunction event count:  {result.conjunction_event_count}")
        print(f"  - Risk assessment count:    {result.risk_assessment_count}")
        print(f"  - Ranked candidate count:   {result.ranked_candidate_count}")

        # 3. Print Top 10 screening-ranked candidates
        print("\n" + "=" * 110)
        print("TOP 10 SCREENING-RANKED CANDIDATES (NON-OPERATIONAL DEMONSTRATION):")
        print("=" * 110)
        print(f"{'Rank':<5} {'Candidate ID':<25} {'Alt(km)':<9} {'Inc(deg)':<9} {'Delay(m)':<9} {'dv(m/s)':<10} {'Risk':<8} {'Score':<8} {'InBudget'}")
        print("-" * 110)

        for rc in result.ranked_candidates[:10]:
            print(
                f"{rc.rank:<5} "
                f"{rc.candidate_id:<25} "
                f"{rc.altitude_km:<9.1f} "
                f"{rc.inclination_deg:<9.2f} "
                f"{rc.deployment_delay_minutes:<9.0f} "
                f"{rc.delta_v_m_s:<10.2f} "
                f"{rc.risk_score:<8.2f} "
                f"{rc.composite_score:<8.2f} "
                f"{str(rc.within_dv_budget)}"
            )
        print("=" * 110)

        print("\nEND OF PIPELINE DEMONSTRATION")
        print("=" * 105)


if __name__ == "__main__":
    run_demo()
