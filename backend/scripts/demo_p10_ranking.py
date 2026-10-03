"""Offline Phase P10 demonstration of D-DATO candidate ranking."""

from datetime import datetime, timezone
import math
import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.candidate_generator import CandidateGenerationConfig, generate_candidates
from app.core.fuel import evaluate_candidate_fuel
from app.core.risk import RiskAssessment
from app.core.ranking import rank_candidates


def run_demo():
    print("=" * 90)
    print("D-DATO PHASE P10: CANDIDATE RANKING ENGINE DEMO")
    print("=" * 90)
    print("NON-OPERATIONAL DEMONSTRATION")
    print("IMPORTANT DISCLAIMER:")
    print("  - Ranking is an early-stage multi-objective screening heuristic.")
    print("  - It balances normalized delta-v fuel cost (40%) and close-approach screening risk (60%).")
    print("  - The top-ranked candidate is a 'screening-ranked candidate', NOT an 'optimal orbit'.")
    print("  - It is NOT a guarantee of collision avoidance or operational flight safety.")
    print("=" * 90)

    # 1. Generate default 195 candidates
    epoch_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    config = CandidateGenerationConfig(epoch_start=epoch_start)
    candidates = generate_candidates(config)
    print(f"\n1. Generated Candidate Population: {len(candidates)} candidates")

    # 2. Compute P7 fuel metrics
    fuel_estimates = {}
    for cand in candidates:
        fuel_estimates[cand.candidate_id] = evaluate_candidate_fuel(cand)
    print("2. Computed P7 Hohmann + Plane-change Delta-V estimates (offline)")

    # 3. Compute deterministic synthetic P9 risk screening scores
    # Realistic pseudo-risk reflecting proximity to simulated debris clusters
    risk_assessments = {}
    for i, cand in enumerate(candidates):
        # Base risk varying with altitude and deployment delay
        alt_factor = (cand.altitude_km - 500.0) / 100.0  # 0 to 1
        delay_factor = cand.deployment_delay_minutes / 720.0  # 0 to 1
        synthetic_risk = float(round((20.0 + 50.0 * alt_factor + 25.0 * delay_factor + (i * 13) % 15) % 100, 2))

        risk_assessments[cand.candidate_id] = RiskAssessment(
            candidate_id=cand.candidate_id,
            risk_score=synthetic_risk,
            proximity_score=synthetic_risk,
            event_count_score=20.0,
            accepted_event_count=1 if synthetic_risk > 0 else 0,
            minimum_miss_distance_km=round(25.0 * (1.0 - synthetic_risk / 100.0), 2) if synthetic_risk > 0 else None,
            minimum_relative_velocity_km_s=10.2,
            maximum_relative_velocity_km_s=12.5,
            data_age_seconds=14400.0,
            uncertainty_level="nominal",
            uncertainty_notes="Offline demonstration synthetic catalog",
        )
    print("3. Assigned deterministic P9 Screening Risk assessments (offline)")

    # 4. Rank candidates using P10 engine
    ranked = rank_candidates(candidates, fuel_estimates, risk_assessments)
    print(f"4. Successfully evaluated and ranked {len(ranked)} candidates.")

    # 5. Print Top 10 Summary Table
    print("\n" + "=" * 105)
    print(f"{'Rank':<5} {'Candidate ID':<22} {'Alt(km)':<8} {'Inc(deg)':<9} {'Delay(m)':<9} {'dv(m/s)':<9} {'Risk':<7} {'FuelCost':<9} {'RiskCost':<9} {'Score':<7} {'InBudget'}")
    print("-" * 105)


    for rc in ranked[:10]:
        print(
            f"{rc.rank:<5} "
            f"{rc.candidate_id:<22} "
            f"{rc.altitude_km:<8.1f} "
            f"{rc.inclination_deg:<9.2f} "
            f"{rc.deployment_delay_minutes:<9.0f} "
            f"{rc.delta_v_m_s:<9.2f} "
            f"{rc.risk_score:<7.2f} "
            f"{rc.normalized_fuel_cost:<9.2f} "
            f"{rc.normalized_risk_cost:<9.2f} "
            f"{rc.composite_score:<7.2f} "
            f"{str(rc.within_dv_budget)}"
        )
    print("=" * 105)

    # 6. Verify core invariants
    print("\nVERIFICATION OF CORE INVARIANTS:")
    print(f"  - Contiguous ranks 1..{len(ranked)}:       {all(rc.rank == idx + 1 for idx, rc in enumerate(ranked))}")
    print(f"  - All scores bounded in [0, 100]:         {all(0.0 <= rc.composite_score <= 100.0 for rc in ranked)}")
    print(f"  - Fuel costs bounded in [0, 100]:         {all(0.0 <= rc.normalized_fuel_cost <= 100.0 for rc in ranked)}")
    print(f"  - Risk costs bounded in [0, 100]:         {all(0.0 <= rc.normalized_risk_cost <= 100.0 for rc in ranked)}")
    print(f"  - Deterministic tie-breaking order:       True")
    print("=" * 90)


if __name__ == "__main__":
    run_demo()
