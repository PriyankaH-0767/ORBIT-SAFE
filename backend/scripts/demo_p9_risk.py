"""Offline Phase P9 demonstration of D-DATO screening risk scoring."""

import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.risk import assess_candidate_risk


def run_demo():
    print("=" * 72)
    print("D-DATO PHASE P9: DEBRIS CLOSE-APPROACH RISK SCREENING DEMO")
    print("=" * 72)
    print("IMPORTANT DISCLAIMER:")
    print("  - D-DATO risk is a bounded [0, 100] early-stage screening index.")
    print("  - It is NOT probability of collision (Pc) or probability of impact.")
    print("  - It is NOT an operational flight-safety determination.")
    print("  - No loaded terms ('safe', 'dangerous') are used.")
    print("=" * 72)

    # 1. Candidate with 0 events (clean corridor)
    cand_0 = "cand-baseline-clean"
    events_0 = []
    res_0 = assess_candidate_risk(cand_0, events_0, data_age_seconds=3600.0)

    # 2. Candidate A: 1 event at exact 25 km threshold
    cand_A = "cand-threshold-25km"
    events_A = [{"candidate_id": cand_A, "miss_distance_km": 25.0, "relative_velocity_km_s": 11.2}]
    res_A = assess_candidate_risk(cand_A, events_A, data_age_seconds=14400.0)

    # 3. Candidate B: 1 event at 12.5 km (midpoint)
    cand_B = "cand-midpoint-12.5km"
    events_B = [{"candidate_id": cand_B, "miss_distance_km": 12.5, "relative_velocity_km_s": 9.8}]
    res_B = assess_candidate_risk(cand_B, events_B, data_age_seconds=86400.0)

    # 4. Candidate C: 1 event at 0 km (grazing / co-orbital)
    cand_C = "cand-direct-0km"
    events_C = [{"candidate_id": cand_C, "miss_distance_km": 0.0, "relative_velocity_km_s": 14.5}]
    res_C = assess_candidate_risk(cand_C, events_C, data_age_seconds=172800.0)

    # 5. Candidate D: 5 events (saturation count), min miss = 12.5 km
    cand_D = "cand-cluster-5events"
    events_D = [
        {"candidate_id": cand_D, "miss_distance_km": 12.5, "relative_velocity_km_s": 10.1},
        {"candidate_id": cand_D, "miss_distance_km": 15.0, "relative_velocity_km_s": 12.3},
        {"candidate_id": cand_D, "miss_distance_km": 18.2, "relative_velocity_km_s": 8.4},
        {"candidate_id": cand_D, "miss_distance_km": 21.0, "relative_velocity_km_s": 11.0},
        {"candidate_id": cand_D, "miss_distance_km": 24.5, "relative_velocity_km_s": 13.7},
    ]
    res_D = assess_candidate_risk(cand_D, events_D, data_age_seconds=300000.0)  # > 3 days -> elevated uncertainty

    scenarios = [
        ("Candidate 0 (No Events)", res_0),
        ("Candidate A (Threshold 25.0 km, 1 Event)", res_A),
        ("Candidate B (Midpoint 12.5 km, 1 Event)", res_B),
        ("Candidate C (Zero-Distance 0.0 km, 1 Event)", res_C),
        ("Candidate D (Saturated 5 Events, Min 12.5 km)", res_D),
    ]

    for label, res in scenarios:
        print(f"\nScenario: {label}")
        print(f"  Candidate ID:             {res.candidate_id}")
        print(f"  Accepted Event Count (N): {res.accepted_event_count}")
        print(f"  Minimum Miss Distance:    {res.minimum_miss_distance_km} km" if res.minimum_miss_distance_km is not None else "  Minimum Miss Distance:    None")
        print(f"  Velocity Range (km/s):    [{res.minimum_relative_velocity_km_s}, {res.maximum_relative_velocity_km_s}]" if res.minimum_relative_velocity_km_s is not None else "  Velocity Range (km/s):    None")
        print(f"  Proximity Score (80%):    {res.proximity_score:.2f} / 100")
        print(f"  Event Count Score (20%):  {res.event_count_score:.2f} / 100")
        print(f"  Composite Risk Score:     {res.risk_score:.2f} / 100")
        print(f"  Uncertainty Level:        {res.uncertainty_level}")
        print(f"  Uncertainty Notes:        {res.uncertainty_notes}")
        print(f"  Scoring Method:           {res.scoring_method}")

    print("\n" + "=" * 72)
    print("VERIFICATION OF CORE PROPERTIES:")
    print(f"  - No events gives score = 0:               {res_0.risk_score == 0.0}")
    print(f"  - d=25 km gives proximity score = 0:       {res_A.proximity_score == 0.0}")
    print(f"  - Monotonicity with distance (C >= B >= A): {res_C.risk_score >= res_B.risk_score >= res_A.risk_score}")
    print(f"  - Monotonicity with count (D >= B):        {res_D.risk_score >= res_B.risk_score}")
    print(f"  - Saturated count score = 100:             {res_D.event_count_score == 100.0}")
    print(f"  - All scores bounded in [0, 100]:          {all(0.0 <= r.risk_score <= 100.0 for _, r in scenarios)}")
    print("=" * 72)


if __name__ == "__main__":
    run_demo()
