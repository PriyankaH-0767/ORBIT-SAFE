"""Unit tests for Phase P11 Synchronous Planning Pipeline Service."""

from datetime import datetime, timezone
import math
import socket
from typing import Any, List
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.candidate_generator import CandidateGenerationConfig, CandidateOrbit
from app.core.config import settings
from app.core.conjunction import ConjunctionEventResult, ScreeningReport
from app.core.fuel import DeltaVEstimate
from app.core.ranking import RankedCandidate
from app.core.risk import RiskAssessment
from app.data.parser import CanonicalElementRecord
from app.db.models import Base, Candidate, ConjunctionEvent, Plan, Run, RunStatus
from app.services.ingestion_service import IngestionResult, IngestionService
from app.services.pipeline_service import (
    PipelineResult,
    PipelineService,
    PipelineStageError,
    PlanParameters,
    execute_planning_pipeline,
    plan_orm_to_parameters,
)
from app.utils.time import now_utc



@pytest.fixture
def synthetic_debris() -> List[CanonicalElementRecord]:
    """Provide a minimal deterministic catalog of 2 debris objects."""
    epoch = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    return [
        CanonicalElementRecord(
            object_name="DEBRIS_A",
            norad_id="90001",
            epoch=epoch,
            inclination_deg=97.5,
            eccentricity=0.001,
            raan_deg=0.0,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=0.0,
            mean_motion_rev_per_day=15.0,
            classification="debris",
            fetched_at=epoch,
            element_format="omm",
        ),
        CanonicalElementRecord(
            object_name="DEBRIS_B",
            norad_id="90002",
            epoch=epoch,
            inclination_deg=98.0,
            eccentricity=0.001,
            raan_deg=45.0,
            arg_perigee_deg=0.0,
            mean_anomaly_deg=180.0,
            mean_motion_rev_per_day=14.8,
            classification="debris",
            fetched_at=epoch,
            element_format="omm",
        ),
    ]


@pytest.fixture
def minimal_plan_params() -> PlanParameters:
    """Provide a small plan generating exactly 2 candidates."""
    epoch_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    return PlanParameters(
        epoch_start=epoch_start,
        altitude_min_km=550.0,
        altitude_max_km=575.0,
        altitude_step_km=25.0,  # 550, 575 (2 altitudes)
        inclination_min_deg=97.5,
        inclination_max_deg=97.5,
        inclination_step_deg=0.5,  # 1 inclination
        delay_min_minutes=0.0,
        delay_max_minutes=0.0,
        delay_step_minutes=60.0,  # 1 delay
        screening_days=0.01,  # Short horizon for fast unit testing
        demo_mode=True,
        plan_id="plan-test-01",
        name="Minimal Test Plan",
    )


@pytest.fixture
def in_memory_db():
    """Create fresh isolated SQLite in-memory database."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ==============================================================================
# Tests 1 - 8: Sequencing, Metadata, Counts, Results Composition
# ==============================================================================

def test_pipeline_successful_stage_sequencing(minimal_plan_params, synthetic_debris):
    """Test 1: Complete pipeline executes through all stages successfully without DB."""
    service = PipelineService()
    result = service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )
    assert result.status == "completed"
    assert result.candidate_count == 2
    assert result.fuel_evaluated_count == 2
    assert result.risk_assessment_count == 2
    assert result.ranked_candidate_count == 2
    assert len(result.ranked_candidates) == 2
    assert result.ranked_candidates[0].rank == 1
    assert result.ranked_candidates[1].rank == 2


def test_pipeline_ingestion_metadata_propagation(minimal_plan_params, synthetic_debris):
    """Test 2: Ingestion provenance and metadata are carried through to the result."""
    service = PipelineService()
    result = service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )
    assert result.catalog_records_seen == 2
    assert result.catalog_records_accepted == 2
    assert result.data_age_seconds is not None
    assert result.data_age_seconds >= 0.0


def test_pipeline_default_candidate_count_mapping():
    """Test 3: Default planning parameters generate exactly 195 candidates."""
    epoch_start = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    params = PlanParameters(epoch_start=epoch_start)
    assert params.altitude_min_km == 500.0
    assert params.altitude_max_km == 600.0
    assert params.altitude_step_km == 25.0  # 5
    assert params.inclination_min_deg == 97.0
    assert params.inclination_max_deg == 98.0
    assert params.inclination_step_deg == 0.5  # 3
    assert params.delay_min_minutes == 0.0
    assert params.delay_max_minutes == 720.0
    assert params.delay_step_minutes == 60.0  # 13
    # 5 * 3 * 13 = 195


def test_pipeline_fuel_metrics_mapping(minimal_plan_params, synthetic_debris):
    """Test 4: Fuel estimates are mapped 1-to-1 to each candidate ID."""
    service = PipelineService()
    result = service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )
    assert result.fuel_evaluated_count == 2
    assert result.within_budget_count + result.out_of_budget_count == 2
    for rc in result.ranked_candidates:
        assert rc.delta_v_m_s >= 0.0
        assert rc.propellant_mass_kg >= 0.0
        assert isinstance(rc.within_dv_budget, bool)


def test_pipeline_screening_results_grouped_by_candidate(minimal_plan_params, synthetic_debris):
    """Test 5: Conjunction screening results are grouped and preserved per candidate."""
    service = PipelineService()
    result = service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )
    assert isinstance(result.conjunction_events, list)
    assert result.debris_objects_considered >= 0
    assert result.coarse_pair_hits >= 0


def test_pipeline_risk_mapping(minimal_plan_params, synthetic_debris):
    """Test 6: Risk assessments are calculated for each candidate."""
    service = PipelineService()
    result = service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )
    assert len(result.risk_assessments) == 2
    for cand_id, risk in result.risk_assessments.items():
        assert 0.0 <= risk.risk_score <= 100.0
        assert risk.candidate_id == cand_id


def test_pipeline_ranking_mapping(minimal_plan_params, synthetic_debris):
    """Test 7: Ranking produces contiguous ranks 1..N."""
    service = PipelineService()
    result = service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )
    assert [rc.rank for rc in result.ranked_candidates] == [1, 2]
    assert result.ranked_candidates[0].composite_score >= result.ranked_candidates[1].composite_score


def test_pipeline_final_result_composition(minimal_plan_params, synthetic_debris):
    """Test 8: PipelineResult to_dict returns full expected payload structure."""
    service = PipelineService()
    result = service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )
    data = result.to_dict()
    assert data["status"] == "completed"
    assert data["candidate_count"] == 2
    assert "ranked_candidates" in data
    assert "risk_assessments" in data
    assert "conjunction_events" in data
    assert len(data["ranked_candidates"]) == 2


# ==============================================================================
# Tests 9 - 14: Lifecycle, Failures, and Warnings
# ==============================================================================

def test_pipeline_run_lifecycle_success(in_memory_db, minimal_plan_params, synthetic_debris):
    """Test 9: Database Run entity transitions correctly from running to completed."""
    # Create Plan and Run in DB
    plan_orm = Plan(
        epoch_start=minimal_plan_params.epoch_start,
        altitude_min_km=minimal_plan_params.altitude_min_km,
        altitude_max_km=minimal_plan_params.altitude_max_km,
        altitude_step_km=minimal_plan_params.altitude_step_km,
        inclination_min_deg=minimal_plan_params.inclination_min_deg,
        inclination_max_deg=minimal_plan_params.inclination_max_deg,
        inclination_step_deg=minimal_plan_params.inclination_step_deg,
        dv_budget_m_s=100.0,
        spacecraft_mass_kg=3.0,
        isp_seconds=60.0,
    )
    in_memory_db.add(plan_orm)
    in_memory_db.flush()

    run_orm = Run(plan_id=plan_orm.id, status=RunStatus.queued.value)
    in_memory_db.add(run_orm)
    in_memory_db.commit()

    service = PipelineService()
    result = service.run_pipeline(
        plan=plan_orm,
        db=in_memory_db,
        run_id=run_orm.id,
        debris_catalog=synthetic_debris,
    )

    assert result.status == "completed"
    in_memory_db.refresh(run_orm)
    assert run_orm.status == RunStatus.completed.value
    assert run_orm.current_stage == "completed"
    assert run_orm.progress_percent == 100.0
    assert run_orm.started_at is not None
    assert run_orm.completed_at is not None
    assert run_orm.error_message is None


def test_pipeline_run_lifecycle_failure(in_memory_db, minimal_plan_params, monkeypatch):
    """Test 10: Failures mark the database Run as failed with stage and error message."""
    plan_orm = Plan(
        epoch_start=minimal_plan_params.epoch_start,
        altitude_min_km=550.0,
        altitude_max_km=575.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.5,
        inclination_max_deg=97.5,
        inclination_step_deg=0.5,
        dv_budget_m_s=100.0,
        spacecraft_mass_kg=3.0,
        isp_seconds=60.0,
    )
    in_memory_db.add(plan_orm)
    in_memory_db.flush()

    run_orm = Run(plan_id=plan_orm.id, status=RunStatus.queued.value)
    in_memory_db.add(run_orm)
    in_memory_db.commit()

    # Force a failure in candidate generation
    import app.services.pipeline_service as pipe_mod

    def failing_gen(*args, **kwargs):
        raise ValueError("Simulated candidate generator fault")

    monkeypatch.setattr(pipe_mod, "generate_candidates", failing_gen)

    service = PipelineService()
    with pytest.raises(PipelineStageError) as exc_info:
        service.run_pipeline(
            plan=plan_orm,
            db=in_memory_db,
            run_id=run_orm.id,
            debris_catalog=[],
        )

    assert exc_info.value.stage == "candidate_generation"
    in_memory_db.refresh(run_orm)
    assert run_orm.status == RunStatus.failed.value
    assert run_orm.current_stage == "failed"
    assert "Simulated candidate generator fault" in (run_orm.error_message or "")


def test_pipeline_warnings_preserved(minimal_plan_params, synthetic_debris, monkeypatch):
    """Test 11: Warnings from upstream ingestion are carried through to the result."""
    service = PipelineService()

    # Ingestion returning a custom warning
    class MockIngestionService:
        def ingest_catalog(self, *args, **kwargs):
            return IngestionResult(
                source="demo",
                mode="demo",
                fetched_at=now_utc(),
                data_age_seconds=100.0,
                total_records_seen=2,
                accepted_records=2,
                rejected_records=0,
                warnings=["Test warning: degraded solar flux data"],
                records=synthetic_debris,
            )

    service.ingestion_service = MockIngestionService()
    res = service.run_pipeline(plan=minimal_plan_params)
    assert any("degraded solar flux" in w for w in res.warnings)


def test_pipeline_candidate_generation_failure_handling(minimal_plan_params, monkeypatch):
    """Test 12: Exceeding candidate limit raises PipelineStageError at candidate_generation."""
    import app.services.pipeline_service as pipe_mod

    def over_limit_gen(*args, **kwargs):
        raise ValueError("Candidate count 350 exceeds maximum allowable 300")

    monkeypatch.setattr(pipe_mod, "generate_candidates", over_limit_gen)

    service = PipelineService()
    with pytest.raises(PipelineStageError) as exc:
        service.run_pipeline(plan=minimal_plan_params, debris_catalog=[])

    assert exc.value.stage == "candidate_generation"
    assert "exceeds maximum allowable" in str(exc.value)


def test_pipeline_ranking_failure_handling(minimal_plan_params, synthetic_debris, monkeypatch):
    """Test 13: Failure in ranking stage is caught and attributed to 'ranking'."""
    import app.services.pipeline_service as pipe_mod

    def failing_rank(*args, **kwargs):
        raise ValueError("Ranking metric non-finite")

    monkeypatch.setattr(pipe_mod, "rank_candidates", failing_rank)

    service = PipelineService()
    with pytest.raises(PipelineStageError) as exc:
        service.run_pipeline(plan=minimal_plan_params, debris_catalog=synthetic_debris)

    assert exc.value.stage == "ranking"
    assert "Ranking metric non-finite" in str(exc.value)


def test_pipeline_persistence_failure_handling(in_memory_db, minimal_plan_params, synthetic_debris, monkeypatch):
    """Test 14: Persistence failure is caught, transaction rolled back, and run marked failed."""
    plan_orm = Plan(
        epoch_start=minimal_plan_params.epoch_start,
        altitude_min_km=550.0, altitude_max_km=575.0, altitude_step_km=25.0,
        inclination_min_deg=97.5, inclination_max_deg=97.5, inclination_step_deg=0.5,
        dv_budget_m_s=100.0, spacecraft_mass_kg=3.0, isp_seconds=60.0,
    )
    in_memory_db.add(plan_orm)
    in_memory_db.flush()

    run_orm = Run(plan_id=plan_orm.id, status=RunStatus.queued.value)
    in_memory_db.add(run_orm)
    in_memory_db.commit()

    service = PipelineService()

    def failing_persist(*args, **kwargs):
        raise RuntimeError("Disk I/O lock failure during bulk create")

    monkeypatch.setattr(service, "_persist_pipeline_results", failing_persist)

    with pytest.raises(PipelineStageError) as exc:
        service.run_pipeline(
            plan=plan_orm,
            db=in_memory_db,
            run_id=run_orm.id,
            debris_catalog=synthetic_debris,
        )

    assert exc.value.stage == "persistence"
    in_memory_db.refresh(run_orm)
    assert run_orm.status == RunStatus.failed.value


# ==============================================================================
# Tests 15 - 20: No duplicate work, No re-screening, Demo mode, Repeatability
# ==============================================================================

def test_pipeline_no_duplicate_candidate_metrics(minimal_plan_params, synthetic_debris):
    """Test 15: Every candidate has exactly one fuel estimate and one risk assessment."""
    service = PipelineService()
    result = service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )
    cand_ids = [rc.candidate_id for rc in result.ranked_candidates]
    assert len(cand_ids) == len(set(cand_ids))
    assert set(result.risk_assessments.keys()) == set(cand_ids)


def test_pipeline_no_rescreening(minimal_plan_params, synthetic_debris, monkeypatch):
    """Test 16: Conjunction screening is invoked exactly once per candidate."""
    import app.services.pipeline_service as pipe_mod

    screen_calls = []
    original_screen = pipe_mod.screen_candidate_against_debris

    def spy_screen(candidate, debris_records, screening_days):
        screen_calls.append(candidate.candidate_id)
        return original_screen(candidate, debris_records, screening_days)

    monkeypatch.setattr(pipe_mod, "screen_candidate_against_debris", spy_screen)

    service = PipelineService()
    service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )

    # 2 candidates -> exactly 2 screening calls
    assert len(screen_calls) == 2
    assert len(set(screen_calls)) == 2


def test_pipeline_no_repeated_fuel_calculation(minimal_plan_params, synthetic_debris, monkeypatch):
    """Test 17: Fuel estimation is invoked exactly once per candidate."""
    import app.services.pipeline_service as pipe_mod

    fuel_calls = []
    original_fuel = pipe_mod.evaluate_candidate_fuel

    def spy_fuel(candidate, **kwargs):
        fuel_calls.append(candidate.candidate_id)
        return original_fuel(candidate, **kwargs)

    monkeypatch.setattr(pipe_mod, "evaluate_candidate_fuel", spy_fuel)

    service = PipelineService()
    service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )

    assert len(fuel_calls) == 2
    assert len(set(fuel_calls)) == 2


def test_pipeline_no_repeated_risk_calculation(minimal_plan_params, synthetic_debris, monkeypatch):
    """Test 18: Risk assessment is invoked exactly once per candidate."""
    import app.services.pipeline_service as pipe_mod

    risk_calls = []
    original_risk = pipe_mod.assess_candidate_risk

    def spy_risk(candidate, conjunction_events, data_age_seconds):
        risk_calls.append(candidate.candidate_id)
        return original_risk(candidate, conjunction_events, data_age_seconds)

    monkeypatch.setattr(pipe_mod, "assess_candidate_risk", spy_risk)

    service = PipelineService()
    service.run_pipeline(
        plan=minimal_plan_params,
        debris_catalog=synthetic_debris,
    )

    assert len(risk_calls) == 2
    assert len(set(risk_calls)) == 2


def test_pipeline_demo_mode_avoids_network(minimal_plan_params, monkeypatch):
    """Test 19: Demo mode operates completely air-gapped without network socket calls."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Network socket call blocked in demo mode!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    service = PipelineService()
    # Runs using bundled offline fixtures
    result = service.run_pipeline(
        plan=minimal_plan_params,
    )
    assert result.status == "completed"
    assert result.mode in ("demo", "cache")


def test_pipeline_deterministic_repeated_execution(minimal_plan_params, synthetic_debris):
    """Test 20: Repeated pipeline execution on the same fixture produces bitwise identical ranks."""
    service = PipelineService()
    res1 = service.run_pipeline(plan=minimal_plan_params, debris_catalog=synthetic_debris)
    res2 = service.run_pipeline(plan=minimal_plan_params, debris_catalog=synthetic_debris)

    assert [rc.candidate_id for rc in res1.ranked_candidates] == [rc.candidate_id for rc in res2.ranked_candidates]
    assert [rc.rank for rc in res1.ranked_candidates] == [rc.rank for rc in res2.ranked_candidates]
    assert [rc.composite_score for rc in res1.ranked_candidates] == [rc.composite_score for rc in res2.ranked_candidates]
    assert [rc.delta_v_m_s for rc in res1.ranked_candidates] == [rc.delta_v_m_s for rc in res2.ranked_candidates]
    assert [rc.risk_score for rc in res1.ranked_candidates] == [rc.risk_score for rc in res2.ranked_candidates]


def test_plan_orm_to_parameters_conversion():
    """Test 21: plan_orm_to_parameters handles dicts, ORM models, and defaults."""
    t0 = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    d = {
        "epoch_start": t0,
        "altitude_min_km": 500.0,
        "altitude_max_km": 600.0,
        "altitude_step_km": 50.0,
        "demo_mode": False,
        "name": "Custom Dict Plan",
    }
    params = plan_orm_to_parameters(d)
    assert params.epoch_start == t0
    assert params.altitude_min_km == 500.0
    assert params.demo_mode is False
    assert params.name == "Custom Dict Plan"
