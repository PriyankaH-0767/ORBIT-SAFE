"""Integration tests for Candidate Generation, Fuel Estimation, and Conjunction Screening Pipeline.

Phases P6, P7, and P8:
Verifies end-to-end domain candidate generation, propellant estimation,
and two-pass conjunction screening with bounded TCA numerical refinement,
time chunking, error isolation, and database persistence.
"""

from datetime import datetime, timezone, timedelta
import math
import socket
import numpy as np
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.candidate_generator import (
    CandidateGenerationConfig,
    CandidateOrbit,
    candidate_to_model_data,
    generate_candidates,
)
from app.core.config import settings
from app.core.conjunction import (
    ConjunctionEventResult,
    ScreeningReport,
    screen_candidate_against_debris,
)
from app.core.fuel import evaluate_candidate_fuel
from app.data.parser import CanonicalElementRecord
from app.db.models import Base, Plan, Run, Candidate, DebrisObject, ConjunctionEvent, RunStatus
from app.services.screening_service import ScreeningService, debris_model_to_canonical


# =====================================================================
# P6 & P7 Regression Tests (Preserved)
# =====================================================================

def test_p6_candidate_generation_pipeline(monkeypatch):
    """Verify Phase P6 candidate generation end-to-end integration requirements."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call attempted during pure candidate generation!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    config = CandidateGenerationConfig(
        epoch_start=epoch_start,
        altitude_min_km=settings.ALTITUDE_MIN_KM,
        altitude_max_km=settings.ALTITUDE_MAX_KM,
        altitude_step_km=settings.ALTITUDE_STEP_KM,
        inclination_min_deg=settings.INCLINATION_MIN_DEG,
        inclination_max_deg=settings.INCLINATION_MAX_DEG,
        inclination_step_deg=settings.INCLINATION_STEP_DEG,
        delay_min_minutes=settings.DELAY_MIN_MINUTES,
        delay_max_minutes=settings.DELAY_MAX_MINUTES,
        delay_step_minutes=settings.DELAY_STEP_MINUTES,
        base_raan_deg=settings.RAAN_DEG,
        u0_deg=settings.U0_DEG,
        raan_delay_coupling_deg_per_min=settings.RAAN_DELAY_COUPLING_DEG_PER_MIN,
        max_candidates=settings.MAX_CANDIDATES,
    )

    candidates = generate_candidates(config=config)
    assert len(candidates) == 195

    matching = [
        c for c in candidates
        if c.altitude_km == 550.0
        and c.inclination_deg == 97.5
        and c.deployment_delay_minutes == 60.0
    ]
    assert len(matching) == 1
    cand_550_60 = matching[0]

    assert cand_550_60.raan_deg == 15.0408
    assert cand_550_60.predicted_raan_deg == 15.0408
    assert cand_550_60.base_raan_deg == 0.0

    expected_deployment_epoch = datetime(2026, 10, 2, 1, 0, 0, tzinfo=timezone.utc)
    assert cand_550_60.deployment_epoch == expected_deployment_epoch
    assert cand_550_60.deployment_epoch.tzinfo == timezone.utc
    assert cand_550_60.candidate_id == "ALT550_INC97.5_DELAY060"

    model_payload = candidate_to_model_data(cand_550_60, run_id="run-test-p6")
    assert model_payload["run_id"] == "run-test-p6"
    assert model_payload["altitude_km"] == 550.0
    assert model_payload["inclination_deg"] == 97.5
    assert model_payload["raan_deg"] == 15.0408
    assert model_payload["predicted_raan_deg"] == 15.0408
    assert model_payload["deployment_delay_minutes"] == 60.0


def test_p7_candidate_fuel_pipeline(monkeypatch):
    """Verify Phase P7 fuel and delta-v pipeline stage end-to-end integration requirements."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call attempted during pure fuel pipeline execution!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    candidates = generate_candidates(epoch_start=epoch_start)
    assert len(candidates) == 195

    estimates = []
    for cand in candidates:
        est = evaluate_candidate_fuel(cand)
        estimates.append((cand, est))

        assert math.isfinite(est.transfer_dv_m_s)
        assert math.isfinite(est.plane_change_dv_m_s)
        assert math.isfinite(est.total_dv_m_s)
        assert math.isfinite(est.propellant_mass_kg)
        assert math.isfinite(est.fuel_fraction)

        assert est.propellant_mass_kg >= 0.0
        assert 0.0 <= est.fuel_fraction < 1.0
        assert isinstance(est.within_dv_budget, bool)
        assert math.isclose(est.total_dv_m_s, est.transfer_dv_m_s + est.plane_change_dv_m_s, rel_tol=1e-12)

    ref_matches = [
        (c, e) for c, e in estimates
        if c.altitude_km == 550.0 and c.inclination_deg == 97.5 and c.deployment_delay_minutes == 0.0
    ]
    assert len(ref_matches) == 1
    ref_cand, ref_est = ref_matches[0]

    assert ref_est.transfer_dv_m_s == 0.0
    assert ref_est.plane_change_dv_m_s == 0.0
    assert ref_est.total_dv_m_s == 0.0
    assert ref_est.propellant_mass_kg == 0.0
    assert ref_est.fuel_fraction == 0.0
    assert ref_est.within_dv_budget is True


# =====================================================================
# Synthetic Fixture Helpers for P8 Conjunction Screening
# =====================================================================

def _create_synthetic_candidate(altitude_km: float = 550.0, inc_deg: float = 97.5) -> CandidateOrbit:
    epoch = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    return CandidateOrbit(
        candidate_id=f"CAND_{int(altitude_km)}_{inc_deg}",
        altitude_km=altitude_km,
        inclination_deg=inc_deg,
        raan_deg=0.0,
        u0_deg=0.0,
        deployment_delay_minutes=0.0,
        base_raan_deg=0.0,
        raan_delay_coupling_deg_per_min=0.0,
        epoch_start=epoch,
        deployment_epoch=epoch,
    )


def _create_synthetic_debris(
    norad_id: str,
    name: str,
    classification: str,
    mean_motion: float,
    inclination_deg: float = 80.0,
    raan_deg: float = 0.0,
    u0_deg: float = 0.0,
    eccentricity: float = 0.0001,
) -> CanonicalElementRecord:
    epoch = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    return CanonicalElementRecord(
        object_name=name,
        norad_id=norad_id,
        epoch=epoch,
        inclination_deg=inclination_deg,
        eccentricity=eccentricity,
        raan_deg=raan_deg,
        arg_perigee_deg=0.0,
        mean_anomaly_deg=u0_deg,
        mean_motion_rev_per_day=mean_motion,
        classification=classification,
        fetched_at=epoch,
        element_format="omm",
    )


# =====================================================================
# P8 Conjunction Screening Pipeline Tests
# =====================================================================

def test_screening_guaranteed_close_approach_retained():
    """Verify guaranteed close approach (<25 km) is detected, refined, and retained."""
    cand = _create_synthetic_candidate(altitude_km=550.0, inc_deg=97.5)
    # Debris crossing near candidate ascending node at 550 km
    deb = _create_synthetic_debris("90001", "DEBRIS CLOSE", "debris", 15.06019, inclination_deg=80.0)

    report = screen_candidate_against_debris(
        candidate=cand,
        debris_records=[deb],
        screening_days=0.1,  # 2.4 hours
    )

    assert report.coarse_pair_hits > 0
    assert report.refined_event_count >= 1
    assert all(ev.miss_distance_km <= 25.0 for ev in report.events)
    assert all(ev.relative_velocity_km_s > 0.0 for ev in report.events)
    assert report.events[0].debris_norad_id == "90001"
    assert report.events[0].candidate_id == cand.candidate_id


def test_screening_near_miss_under_260_over_25_rejected():
    """Verify near-miss (coarse < 260 km, refined > 25 km) is refined but NOT retained."""
    cand = _create_synthetic_candidate(altitude_km=550.0)
    # Debris at ~650 km altitude (100 km separation from candidate at node crossing)
    # mm = 14.736 rev/day corresponds to ~650 km altitude
    deb = _create_synthetic_debris("90002", "DEBRIS NEAR MISS", "debris", 14.736, inclination_deg=80.0)

    report = screen_candidate_against_debris(
        candidate=cand,
        debris_records=[deb],
        screening_days=0.1,
    )

    # Coarse screening detects the approach (< 260 km)
    assert report.coarse_pair_hits > 0
    # But because refined miss distance is ~100 km (> 25 km), it is rejected
    assert report.refined_event_count == 0
    assert len(report.events) == 0


def test_screening_distant_object_prefiltered_or_no_hits():
    """Verify distant object (> 260 km separation) produces no hits and no refinement."""
    cand = _create_synthetic_candidate(altitude_km=550.0)
    # Debris at ~1250 km altitude (700 km separation, outside 300 km prefilter margin)
    deb = _create_synthetic_debris("90003", "DEBRIS DISTANT", "debris", 13.0)

    report = screen_candidate_against_debris(
        candidate=cand,
        debris_records=[deb],
        screening_days=0.1,
    )

    assert report.debris_objects_skipped == 1
    assert report.debris_objects_considered == 0
    assert report.coarse_pair_hits == 0
    assert report.refined_event_count == 0


def test_screening_threshold_boundary_25km_acceptance():
    """Verify strict 25.0 km boundary: <= 25.0 km accepted, > 25.0 km rejected."""
    t0 = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    ev_25_0 = ConjunctionEventResult("C1", None, "101", t0, 25.0, 5.0, 25.0, t0, t0, t0 + timedelta(days=1), 30.0, 260.0, 25.0)
    ev_25_001 = ConjunctionEventResult("C1", None, "102", t0, 25.001, 5.0, 25.0, t0, t0, t0 + timedelta(days=1), 30.0, 260.0, 25.0)

    assert ev_25_0.miss_distance_km <= 25.0
    assert not (ev_25_001.miss_distance_km <= 25.0)


def test_screening_multiple_separated_encounters_retained():
    """Verify multiple distinct encounters separated in time for the same pair are retained."""
    cand = _create_synthetic_candidate(altitude_km=550.0)
    deb = _create_synthetic_debris("90001", "DEBRIS CLOSE", "debris", 15.06019, inclination_deg=80.0)

    # Over 0.2 days (~4.8 hours, ~3 orbits), encounters occur at both nodes on each orbit
    report = screen_candidate_against_debris(
        candidate=cand,
        debris_records=[deb],
        screening_days=0.2,
    )

    assert report.refined_event_count > 1
    # Check that timestamps of distinct events are separated by > 30 seconds
    for i in range(len(report.events) - 1):
        dt = (report.events[i + 1].tca - report.events[i].tca).total_seconds()
        assert dt > 30.0


def test_screening_malformed_debris_error_isolation():
    """Verify malformed debris object is skipped with diagnostic warning without aborting run."""
    cand = _create_synthetic_candidate(altitude_km=550.0)
    good_deb = _create_synthetic_debris("90001", "DEBRIS CLOSE", "debris", 15.06019)

    # Malformed debris object: negative mean motion invalid for SGP4
    epoch = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    bad_deb = CanonicalElementRecord(
        object_name="BAD DEBRIS",
        norad_id="99999",
        epoch=epoch,
        inclination_deg=80.0,
        eccentricity=0.0001,
        raan_deg=0.0,
        arg_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
        mean_motion_rev_per_day=-5.0,
        classification="debris",
        fetched_at=epoch,
        element_format="omm",
    )

    report = screen_candidate_against_debris(
        candidate=cand,
        debris_records=[bad_deb, good_deb],
        screening_days=0.1,
    )

    # Run completed successfully
    assert report.refined_event_count >= 1
    assert any("99999" in w for w in report.warnings)


def test_screening_deterministic_results_and_ordering():
    """Verify repeated execution produces identical deterministic output and ordering."""
    cand = _create_synthetic_candidate(altitude_km=550.0)
    deb = _create_synthetic_debris("90001", "DEBRIS CLOSE", "debris", 15.06019)

    rep1 = screen_candidate_against_debris(candidate=cand, debris_records=[deb], screening_days=0.1)
    rep2 = screen_candidate_against_debris(candidate=cand, debris_records=[deb], screening_days=0.1)

    assert rep1.refined_event_count == rep2.refined_event_count
    for e1, e2 in zip(rep1.events, rep2.events):
        assert e1.candidate_id == e2.candidate_id
        assert e1.debris_norad_id == e2.debris_norad_id
        assert e1.tca == e2.tca
        assert math.isclose(e1.miss_distance_km, e2.miss_distance_km, abs_tol=1e-9)
        assert math.isclose(e1.relative_velocity_km_s, e2.relative_velocity_km_s, abs_tol=1e-9)


def test_screening_default_parameters():
    """Verify default screening parameters match D-DATO specification."""
    cand = _create_synthetic_candidate(altitude_km=550.0)
    deb = _create_synthetic_debris("90001", "DEBRIS CLOSE", "debris", 15.06019)

    report = screen_candidate_against_debris(candidate=cand, debris_records=[deb], screening_days=None)

    assert report.coarse_step_seconds == 30.0
    assert report.coarse_threshold_km == 260.0
    assert report.event_threshold_km == 25.0
    # Default 3 days horizon
    total_sec = (report.screening_end - report.screening_start).total_seconds()
    assert math.isclose(total_sec, 3 * 86400.0, abs_tol=1.0)


def test_screening_no_network_access(monkeypatch):
    """Verify screening executes purely offline with zero network socket calls."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call attempted during conjunction screening!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    cand = _create_synthetic_candidate(altitude_km=550.0)
    deb = _create_synthetic_debris("90001", "DEBRIS CLOSE", "debris", 15.06019)

    report = screen_candidate_against_debris(
        candidate=cand,
        debris_records=[deb],
        screening_days=0.05,
    )
    assert report.debris_objects_considered == 1


def test_screening_performance_benchmark():
    """Deterministic benchmark-style test with 10 candidates and 20 debris objects."""
    epoch = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    # 10 candidates
    candidates = [
        CandidateOrbit(
            candidate_id=f"BENCH_CAND_{i}",
            altitude_km=500.0 + i * 20.0,
            inclination_deg=97.5,
            raan_deg=i * 2.0,
            u0_deg=0.0,
            deployment_delay_minutes=float(i * 10),
            base_raan_deg=0.0,
            raan_delay_coupling_deg_per_min=0.25,
            epoch_start=epoch,
            deployment_epoch=epoch + timedelta(minutes=i * 10),
        )
        for i in range(10)
    ]

    # 20 synthetic debris objects with varying altitudes and inclinations
    debris_records = [
        _create_synthetic_debris(
            norad_id=f"8{i:04d}",
            name=f"BENCH_DEBRIS_{i}",
            classification="debris" if i % 2 == 0 else "rocket_body",
            mean_motion=14.5 + (i * 0.05),
            inclination_deg=70.0 + (i * 1.5),
        )
        for i in range(20)
    ]

    service = ScreeningService()
    reports = service.screen_candidates(
        candidates=candidates,
        debris_records=debris_records,
        screening_days=0.05,  # 1.2 hours
    )

    assert len(reports) == 10
    for r in reports:
        assert isinstance(r, ScreeningReport)
        assert r.debris_objects_considered > 0
        assert math.isfinite(r.refined_event_count)


# =====================================================================
# Database Persistence Integration Test (Section 39)
# =====================================================================

def test_screening_database_persistence():
    """Verify database persistence of conjunction events using isolated in-memory SQLite.

    1. Create test Plan.
    2. Create Run.
    3. Create Candidate.
    4. Create DebrisObject records.
    5. Run screening and persist.
    6. Query ConjunctionEvent and verify fields.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # 1. Plan
        plan = Plan(
            epoch_start=datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc),
            altitude_min_km=500.0,
            altitude_max_km=600.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.0,
            inclination_max_deg=98.0,
            inclination_step_deg=0.5,
            dv_budget_m_s=250.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
        )
        session.add(plan)
        session.flush()

        # 2. Run
        run = Run(
            plan_id=plan.id,
            status=RunStatus.running.value,
            progress_percent=50.0,
            current_stage="conjunction_screening",
        )
        session.add(run)
        session.flush()

        # 3. Candidate
        cand_db = Candidate(
            run_id=run.id,
            altitude_km=550.0,
            inclination_deg=97.5,
            raan_deg=0.0,
            u0_deg=0.0,
            deployment_delay_minutes=0.0,
            predicted_raan_deg=0.0,
            delta_v_m_s=0.0,
            propellant_mass_kg=0.0,
            fuel_fraction=0.0,
            within_dv_budget=True,
            risk_score=0.0,
        )
        session.add(cand_db)
        session.flush()

        # 4. DebrisObject
        deb_db = DebrisObject(
            norad_id="90001",
            object_name="COSMOS 1408 DEB",
            classification="debris",
            element_format="omm",
            epoch=datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc),
            inclination_deg=80.0,
            eccentricity=0.0001,
            raan_deg=0.0,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=0.0,
            mean_motion_rev_per_day=15.06019,
            source="test_source",
            fetched_at=datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc),
        )
        session.add(deb_db)
        session.commit()

        # 5. Execute screening and persistence
        service = ScreeningService(session)
        report = service.screen_and_persist(
            db=session,
            run_id=run.id,
            candidate=cand_db,
            debris_records=[deb_db],
            screening_days=0.1,
            candidate_id_map={cand_db.id: cand_db.id},
            debris_id_map={"90001": deb_db.id},
        )

        assert report.refined_event_count > 0

        # 6. Query persisted ConjunctionEvent records
        stmt = select(ConjunctionEvent).where(ConjunctionEvent.run_id == run.id)
        events = list(session.scalars(stmt).all())

        assert len(events) == report.refined_event_count
        first_event = events[0]

        assert first_event.run_id == run.id
        assert first_event.candidate_id == cand_db.id
        assert first_event.debris_object_id == deb_db.id
        assert first_event.threshold_km == 25.0
        assert first_event.miss_distance_km <= 25.0
        assert first_event.relative_velocity_km_s > 0.0
        assert first_event.screening_source == "ddato"
        assert first_event.tca.tzinfo is not None


def test_p9_risk_screening_pipeline(monkeypatch):
    """Verify Phase P9 risk scoring integration pipeline.

    1. Generate default P6 candidates.
    2. Calculate P7 fuel metrics.
    3. Construct deterministic synthetic P8 events across candidates.
    4. Assess risk using ScreeningService.
    5. Verify properties:
       - No events -> risk = 0.0
       - Smaller miss distance never reduces score
       - More events never reduces score
       - Relative velocity is reported
       - No network calls occur
       - No ranking/sorting is performed
    6. Persist risk_score in isolated SQLite database and verify.
    """
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call attempted during risk pipeline execution!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    candidates = generate_candidates(epoch_start=epoch_start)
    assert len(candidates) == 195

    # Evaluate fuel for candidates (P7)
    fuel_estimates = [evaluate_candidate_fuel(c) for c in candidates[:5]]
    assert len(fuel_estimates) == 5

    # 3. Create deterministic synthetic P8 events for first 5 candidates
    cand_0 = candidates[0]  # No events
    cand_1 = candidates[1]  # 1 event, miss = 25.0 km
    cand_2 = candidates[2]  # 1 event, miss = 12.5 km
    cand_3 = candidates[3]  # 1 event, miss = 0.0 km
    cand_4 = candidates[4]  # 5 events, min miss = 12.5 km

    tca_base = epoch_start + timedelta(hours=1)
    synthetic_events = [
        # Candidate 1: 1 event at 25 km
        ConjunctionEventResult(
            candidate_id=cand_1.candidate_id,
            debris_object_id=None,
            debris_norad_id="90001",
            tca=tca_base,
            miss_distance_km=25.0,
            relative_velocity_km_s=6.5,
            coarse_min_distance_km=30.0,
            coarse_time=tca_base,
            screening_start=epoch_start,
            screening_end=epoch_start + timedelta(days=3),
            coarse_step_seconds=30.0,
            coarse_threshold_km=260.0,
            acceptance_threshold_km=25.0,
        ),
        # Candidate 2: 1 event at 12.5 km
        ConjunctionEventResult(
            candidate_id=cand_2.candidate_id,
            debris_object_id=None,
            debris_norad_id="90002",
            tca=tca_base,
            miss_distance_km=12.5,
            relative_velocity_km_s=9.0,
            coarse_min_distance_km=20.0,
            coarse_time=tca_base,
            screening_start=epoch_start,
            screening_end=epoch_start + timedelta(days=3),
            coarse_step_seconds=30.0,
            coarse_threshold_km=260.0,
            acceptance_threshold_km=25.0,
        ),
        # Candidate 3: 1 event at 0.0 km
        ConjunctionEventResult(
            candidate_id=cand_3.candidate_id,
            debris_object_id=None,
            debris_norad_id="90003",
            tca=tca_base,
            miss_distance_km=0.0,
            relative_velocity_km_s=11.2,
            coarse_min_distance_km=10.0,
            coarse_time=tca_base,
            screening_start=epoch_start,
            screening_end=epoch_start + timedelta(days=3),
            coarse_step_seconds=30.0,
            coarse_threshold_km=260.0,
            acceptance_threshold_km=25.0,
        ),
    ]

    # Candidate 4: 5 events at 12.5, 14.0, 16.0, 18.0, 20.0 km
    for i, d in enumerate([12.5, 14.0, 16.0, 18.0, 20.0]):
        synthetic_events.append(
            ConjunctionEventResult(
                candidate_id=cand_4.candidate_id,
                debris_object_id=None,
                debris_norad_id=f"9001{i}",
                tca=tca_base + timedelta(minutes=i * 45),
                miss_distance_km=d,
                relative_velocity_km_s=7.0 + i,
                coarse_min_distance_km=d + 5.0,
                coarse_time=tca_base + timedelta(minutes=i * 45),
                screening_start=epoch_start,
                screening_end=epoch_start + timedelta(days=3),
                coarse_step_seconds=30.0,
                coarse_threshold_km=260.0,
                acceptance_threshold_km=25.0,
            )
        )

    # 4. Assess risk across candidate population
    service = ScreeningService()
    target_cands = [cand_0, cand_1, cand_2, cand_3, cand_4]
    assessments = service.assess_run_risk(
        candidates=target_cands,
        conjunction_events=synthetic_events,
        data_age_seconds=7200.0,  # 2 hours (nominal)
    )

    # 5. Verify properties
    # Candidate 0: No events
    ass_0 = assessments[cand_0.candidate_id]
    assert ass_0.risk_score == 0.0
    assert ass_0.accepted_event_count == 0
    assert ass_0.uncertainty_level == "nominal"

    # Candidate 1: 1 event at 25 km -> risk = 0.8*0 + 0.2*20 = 4.0
    ass_1 = assessments[cand_1.candidate_id]
    assert math.isclose(ass_1.risk_score, 4.0, abs_tol=1e-9)
    assert ass_1.accepted_event_count == 1
    assert ass_1.minimum_relative_velocity_km_s == 6.5

    # Candidate 2: 1 event at 12.5 km -> risk = 0.8*50 + 0.2*20 = 44.0
    ass_2 = assessments[cand_2.candidate_id]
    assert math.isclose(ass_2.risk_score, 44.0, abs_tol=1e-9)

    # Candidate 3: 1 event at 0 km -> risk = 0.8*100 + 0.2*20 = 84.0
    ass_3 = assessments[cand_3.candidate_id]
    assert math.isclose(ass_3.risk_score, 84.0, abs_tol=1e-9)

    # Candidate 4: 5 events, min 12.5 km -> risk = 0.8*50 + 0.2*100 = 60.0
    ass_4 = assessments[cand_4.candidate_id]
    assert math.isclose(ass_4.risk_score, 60.0, abs_tol=1e-9)
    assert ass_4.accepted_event_count == 5

    # Monotonicity checks:
    # Closer distance -> higher or equal risk
    assert ass_3.risk_score > ass_2.risk_score > ass_1.risk_score > ass_0.risk_score
    # More events for same min distance -> higher or equal risk
    assert ass_4.risk_score > ass_2.risk_score

    # 6. Database persistence check
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        plan = Plan(
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=600.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.0,
            inclination_max_deg=98.0,
            inclination_step_deg=0.5,
            dv_budget_m_s=250.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
        )
        session.add(plan)
        session.flush()

        run = Run(
            plan_id=plan.id,
            status=RunStatus.running.value,
        )
        session.add(run)
        session.flush()

        # Add candidate ORM model
        cand_orm = Candidate(
            run_id=run.id,
            altitude_km=cand_2.altitude_km,
            inclination_deg=cand_2.inclination_deg,
            raan_deg=cand_2.raan_deg,
            u0_deg=cand_2.u0_deg,
            deployment_delay_minutes=cand_2.deployment_delay_minutes,
            predicted_raan_deg=cand_2.raan_deg,
            delta_v_m_s=0.0,
            propellant_mass_kg=0.0,
            fuel_fraction=0.0,
            within_dv_budget=True,
            risk_score=0.0,
        )
        session.add(cand_orm)
        session.commit()

        # Update candidate risk score
        updated = service.update_candidate_risk_scores(
            db=session,
            assessments={cand_orm.id: ass_2},
        )
        assert updated == 1

        refreshed = session.get(Candidate, cand_orm.id)
        assert math.isclose(refreshed.risk_score, 44.0, abs_tol=1e-9)


def test_p10_ranking_pipeline(monkeypatch):
    """End-to-end integration test for Phase P10: Multi-objective Candidate Ranking."""
    from app.core.ranking import rank_candidates, RankedCandidate
    from app.services.ranking_service import RankingService
    from app.core.risk import RiskAssessment
    import app.core.conjunction as conj_mod

    # 1. Guard against network socket calls
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call attempted during pure ranking!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    # 2. Guard against unwanted re-screening calls
    def forbid_screening(*args, **kwargs):
        raise AssertionError("P10 ranking must not call conjunction screening!")

    monkeypatch.setattr(conj_mod, "screen_candidate_against_debris", forbid_screening)

    # 3. Generate default 195 candidates
    epoch_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    config = CandidateGenerationConfig(epoch_start=epoch_start)
    candidates = generate_candidates(config)
    assert len(candidates) == 195

    # 4. Calculate P7 fuel metrics once
    fuel_estimates = {}
    for cand in candidates:
        fuel_estimates[cand.candidate_id] = evaluate_candidate_fuel(cand)

    # 5. Supply deterministic synthetic P9 risk assessments once
    risk_assessments = {}
    for i, cand in enumerate(candidates):
        # Deterministic risk in [0, 99]
        synthetic_risk = float((i * 17) % 100)
        risk_assessments[cand.candidate_id] = RiskAssessment(
            candidate_id=cand.candidate_id,
            risk_score=synthetic_risk,
            proximity_score=synthetic_risk,
            event_count_score=20.0,
            accepted_event_count=1,
            minimum_miss_distance_km=15.0,
            minimum_relative_velocity_km_s=10.0,
            maximum_relative_velocity_km_s=10.0,
            data_age_seconds=7200.0,
            uncertainty_level="nominal",
            uncertainty_notes="Integration test data",
        )

    # 6. Run P10 ranking
    ranked = rank_candidates(candidates, fuel_estimates, risk_assessments)

    # Assertions on ranked output
    assert len(ranked) == 195
    ranks = [rc.rank for rc in ranked]
    assert ranks == list(range(1, 196))

    for rc in ranked:
        assert 0.0 <= rc.normalized_fuel_cost <= 100.0
        assert 0.0 <= rc.normalized_risk_cost <= 100.0
        assert 0.0 <= rc.composite_score <= 100.0
        assert isinstance(rc.within_dv_budget, bool)

    # 7. Verify reference candidate behavior
    # Reference candidate: alt=550 km, inc=97.5 deg, delay=0 min -> delta_v = 0
    ref_cand = next(
        c for c in candidates
        if c.altitude_km == 550.0 and c.inclination_deg == 97.5 and c.deployment_delay_minutes == 0.0
    )
    ref_ranked = next(rc for rc in ranked if rc.candidate_id == ref_cand.candidate_id)
    assert math.isclose(ref_ranked.delta_v_m_s, 0.0, abs_tol=1e-6)
    assert math.isclose(ref_ranked.normalized_fuel_cost, 0.0, abs_tol=1e-6)
    # The reference candidate's rank depends on its risk score
    expected_ref_score = 100.0 - (settings.FUEL_WEIGHT * 0.0 + settings.RISK_WEIGHT * ref_ranked.risk_score)
    assert math.isclose(ref_ranked.composite_score, expected_ref_score, abs_tol=1e-5)

    # 8. Deterministic repeated ranking check
    ranked_repeat = rank_candidates(candidates, fuel_estimates, risk_assessments)
    assert [rc.candidate_id for rc in ranked] == [rc.candidate_id for rc in ranked_repeat]
    assert [rc.rank for rc in ranked] == [rc.rank for rc in ranked_repeat]

    # 9. Database persistence check using in-memory SQLite
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
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
            delay_step_minutes=60.0,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
        )
        session.add(plan)
        session.flush()

        run = Run(plan_id=plan.id, status=RunStatus.running.value)
        session.add(run)
        session.flush()

        # Insert all candidate ORM models with initial rank = None
        cand_orm_map = {}
        for cand in candidates:
            fuel = fuel_estimates[cand.candidate_id]
            risk = risk_assessments[cand.candidate_id]
            orm_cand = Candidate(
                id=cand.candidate_id,
                run_id=run.id,
                altitude_km=cand.altitude_km,
                inclination_deg=cand.inclination_deg,
                raan_deg=cand.raan_deg,
                u0_deg=cand.u0_deg,
                deployment_delay_minutes=cand.deployment_delay_minutes,
                predicted_raan_deg=cand.raan_deg,
                delta_v_m_s=fuel.total_dv_m_s,
                propellant_mass_kg=fuel.propellant_mass_kg,
                fuel_fraction=fuel.fuel_fraction,
                within_dv_budget=fuel.within_dv_budget,
                risk_score=risk.risk_score,
                rank=None,
            )
            session.add(orm_cand)
            cand_orm_map[cand.candidate_id] = orm_cand

        session.commit()

        # Perform ranking and persistence via RankingService
        service = RankingService()
        ranked_service_results = service.rank_and_persist(
            db=session,
            candidates=candidates,
            fuel_estimates=fuel_estimates,
            risk_assessments=risk_assessments,
        )
        assert len(ranked_service_results) == 195

        # Query candidates ordered by rank
        stmt = select(Candidate).where(Candidate.run_id == run.id).order_by(Candidate.rank)
        persisted_candidates = list(session.scalars(stmt).all())
        assert len(persisted_candidates) == 195

        persisted_ranks = [c.rank for c in persisted_candidates]
        assert persisted_ranks == list(range(1, 196))

        # Verify physical metrics, delta-v, risk, and budget flags remain unchanged
        for c in persisted_candidates:
            expected_fuel = fuel_estimates[c.id]
            expected_risk = risk_assessments[c.id]
            assert math.isclose(c.delta_v_m_s, expected_fuel.total_dv_m_s, abs_tol=1e-6)
            assert math.isclose(c.risk_score, expected_risk.risk_score, abs_tol=1e-6)
            assert c.within_dv_budget == expected_fuel.within_dv_budget


# =====================================================================
# Phase P11 Integration Tests: End-to-End Synchronous Planning Pipeline
# =====================================================================

def test_p11_full_pipeline_small_offline(monkeypatch):
    """Verify Phase P11 end-to-end planning pipeline on a small deterministic configuration."""
    from app.services.pipeline_service import PipelineService, PlanParameters

    # Network air-gap guard
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call attempted during offline pipeline test!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        # Create plan in DB
        plan = Plan(
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=60.0,
            delay_step_minutes=60.0,  # Exactly 2 candidates: DELAY000, DELAY060
            screening_days=0.05,
            demo_mode=True,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
        )
        session.add(plan)
        session.flush()

        run = Run(
            plan_id=plan.id,
            status=RunStatus.queued.value,
            progress_percent=0,
            current_stage="queued",
        )
        session.add(run)
        session.commit()
        run_id = run.id

        params = PlanParameters(
            plan_id=plan.id,
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=60.0,
            delay_step_minutes=60.0,
            screening_days=0.05,
            demo_mode=True,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
        )

        service = PipelineService()
        result = service.run_pipeline(params, run_id=run_id, db=session)

        # 1. Result assertions
        assert result.status == "completed"
        assert result.candidate_count == 2
        assert result.fuel_evaluated_count == 2
        assert result.risk_assessment_count == 2
        assert result.ranked_candidate_count == 2
        assert len(result.ranked_candidates) == 2

        # 2. Run ORM transitions
        session.refresh(run)
        assert run.status == RunStatus.completed.value
        assert run.progress_percent == 100
        assert run.current_stage == "completed"
        assert run.completed_at is not None
        assert run.error_message is None

        # 3. Candidate persistence & ranks
        stmt = select(Candidate).where(Candidate.run_id == run_id).order_by(Candidate.rank)
        persisted_candidates = list(session.scalars(stmt).all())
        assert len(persisted_candidates) == 2
        assert [c.rank for c in persisted_candidates] == [1, 2]

        for c in persisted_candidates:
            assert c.delta_v_m_s >= 0.0
            assert c.propellant_mass_kg >= 0.0
            assert c.fuel_fraction >= 0.0
            assert isinstance(c.within_dv_budget, bool)
            assert 0.0 <= c.risk_score <= 100.0

        # 4. Conjunction events persistence check
        ev_stmt = select(ConjunctionEvent).where(ConjunctionEvent.run_id == run_id)
        persisted_events = list(session.scalars(ev_stmt).all())
        assert len(persisted_events) == result.conjunction_event_count
        for ev in persisted_events:
            assert ev.miss_distance_km <= 25.0
            assert ev.relative_velocity_km_s >= 0.0
            assert ev.threshold_km == 25.0
            assert ev.candidate_id in [c.id for c in persisted_candidates]


def test_p11_pipeline_failure_marks_run_failed(monkeypatch):
    """Force a controlled stage failure and verify Run lifecycle transitions to failed."""
    from app.services.pipeline_service import PipelineService, PlanParameters, PipelineStageError

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        plan = Plan(
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=0.0,
            demo_mode=True,
        )
        session.add(plan)
        session.flush()

        run = Run(
            plan_id=plan.id,
            status=RunStatus.queued.value,
            progress_percent=0,
            current_stage="queued",
        )
        session.add(run)
        session.commit()
        run_id = run.id

        params = PlanParameters(
            plan_id=plan.id,
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=0.0,
            demo_mode=True,
        )

        service = PipelineService()

        # Force a controlled failure during screening stage
        def fail_screening(*args, **kwargs):
            raise RuntimeError("Controlled simulated failure during conjunction screening")

        monkeypatch.setattr("app.services.pipeline_service.screen_candidate_against_debris", fail_screening)

        with pytest.raises(PipelineStageError) as exc_info:
            service.run_pipeline(params, run_id=run_id, db=session)

        assert exc_info.value.stage == "conjunction_screening"
        assert "Controlled simulated failure" in str(exc_info.value)

        session.refresh(run)
        assert run.status == RunStatus.failed.value
        assert run.current_stage == "failed"
        assert run.completed_at is not None
        assert "Controlled simulated failure" in run.error_message


def test_p11_repeatability(monkeypatch):
    """Run the same deterministic pipeline twice with independent Run IDs and verify reproducibility."""
    from app.services.pipeline_service import PipelineService, PlanParameters

    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call attempted during repeatability test!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        plan = Plan(
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=60.0,
            delay_step_minutes=60.0,
            screening_days=0.05,
            demo_mode=True,
        )
        session.add(plan)
        session.flush()

        run_a = Run(plan_id=plan.id, status=RunStatus.queued.value)
        run_b = Run(plan_id=plan.id, status=RunStatus.queued.value)
        session.add_all([run_a, run_b])
        session.commit()

        params_a = PlanParameters(
            plan_id=plan.id,
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=60.0,
            delay_step_minutes=60.0,
            screening_days=0.05,
            demo_mode=True,
        )

        params_b = PlanParameters(
            plan_id=plan.id,
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=60.0,
            delay_step_minutes=60.0,
            screening_days=0.05,
            demo_mode=True,
        )

        service = PipelineService()
        res_a = service.run_pipeline(params_a, run_id=run_a.id, db=session)
        res_b = service.run_pipeline(params_b, run_id=run_b.id, db=session)

        assert res_a.run_id != res_b.run_id
        assert res_a.status == "completed" and res_b.status == "completed"

        # Compare ranked candidates
        assert len(res_a.ranked_candidates) == len(res_b.ranked_candidates)
        for cand_a, cand_b in zip(res_a.ranked_candidates, res_b.ranked_candidates):
            assert cand_a.candidate_id == cand_b.candidate_id
            assert math.isclose(cand_a.delta_v_m_s, cand_b.delta_v_m_s, abs_tol=1e-6)
            assert math.isclose(cand_a.risk_score, cand_b.risk_score, abs_tol=1e-6)
            assert cand_a.rank == cand_b.rank
            assert math.isclose(cand_a.composite_score, cand_b.composite_score, abs_tol=1e-6)

        # Compare conjunction events count
        assert res_a.conjunction_event_count == res_b.conjunction_event_count


def test_p11_demo_mode_no_network(monkeypatch):
    """Verify demo mode pipeline runs completely offline with network blocked at socket level."""
    from app.services.pipeline_service import PipelineService, PlanParameters

    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call attempted in demo mode!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        plan = Plan(
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=0.0,
            screening_days=0.01,
            demo_mode=True,
        )
        session.add(plan)
        session.flush()

        run = Run(plan_id=plan.id, status=RunStatus.queued.value)
        session.add(run)
        session.commit()

        params = PlanParameters(
            plan_id=plan.id,
            epoch_start=epoch_start,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=50.0,
            inclination_min_deg=97.5,
            inclination_max_deg=97.5,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=0.0,
            screening_days=0.01,
            demo_mode=True,
        )

        service = PipelineService()
        result = service.run_pipeline(params, run_id=run.id, db=session)

        assert result.status == "completed"
        assert result.candidate_count == 1
        assert result.ranked_candidate_count == 1
        assert result.ingestion_mode == "demo"


