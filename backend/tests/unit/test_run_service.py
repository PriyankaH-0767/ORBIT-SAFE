"""Unit tests for RunService and asynchronous execution lifecycle (Phase P12)."""

from datetime import datetime, timezone
import math
import socket
import threading
import time
from typing import Any, Dict, List, Optional
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.models import Base, Candidate, ConjunctionEvent, Plan, Run, RunStatus
from app.services.pipeline_service import PipelineResult, PipelineService, PipelineStageError, PlanParameters
from app.services.run_service import (
    RunLifecycleError,
    RunService,
    RunStatusSummary,
    validate_lifecycle_transition,
)
from app.workers.screening_worker import (
    DuplicateRunSubmissionError,
    WorkerManager,
    reset_global_worker_manager,
)


@pytest.fixture
def isolated_db(tmp_path):
    """Create an isolated, thread-safe SQLite database file for testing."""
    db_file = tmp_path / "test_run.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture(autouse=True)
def cleanup_workers():
    """Ensure all background workers are shut down cleanly after every test."""
    yield
    reset_global_worker_manager(wait=True)


def test_lifecycle_transition_validation():
    """Verify legal and illegal state transitions defined in Phase P12."""
    # Legal transitions
    validate_lifecycle_transition("queued", "running")
    validate_lifecycle_transition("queued", "failed")
    validate_lifecycle_transition("running", "completed")
    validate_lifecycle_transition("running", "failed")
    validate_lifecycle_transition("running", "cancelled")

    # Illegal transitions
    with pytest.raises(RunLifecycleError):
        validate_lifecycle_transition("completed", "running")

    with pytest.raises(RunLifecycleError):
        validate_lifecycle_transition("failed", "running")

    with pytest.raises(RunLifecycleError):
        validate_lifecycle_transition("completed", "queued")

    with pytest.raises(RunLifecycleError):
        validate_lifecycle_transition("failed", "queued")

    with pytest.raises(RunLifecycleError):
        validate_lifecycle_transition("queued", "completed")


def test_run_service_create_plan(isolated_db):
    """Verify plan creation and persistence through RunService."""
    service = RunService(session_factory=isolated_db)
    epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    plan = service.create_plan({
        "epoch_start": epoch_start,
        "altitude_min_km": 500.0,
        "altitude_max_km": 550.0,
        "demo_mode": True,
    })

    assert plan.id is not None
    assert plan.demo_mode is True
    assert plan.altitude_min_km == 500.0
    assert plan.altitude_max_km == 550.0
    assert plan.altitude_step_km == settings.ALTITUDE_STEP_KM


def test_run_service_create_queued_run(isolated_db):
    """Verify run creation initializes in 'queued' state with progress 0."""
    service = RunService(session_factory=isolated_db)
    plan = service.create_plan({"demo_mode": True})

    run = service.create_run(plan.id)
    assert run.id is not None
    assert run.plan_id == plan.id
    assert run.status == RunStatus.queued.value
    assert run.progress_percent == 0.0
    assert run.current_stage == "queued"
    assert run.started_at is None
    assert run.completed_at is None
    assert run.error_message is None


def test_run_service_submit_run_non_blocking(isolated_db):
    """Verify submit_run returns immediately with status 'queued' without waiting for completion."""
    worker_manager = WorkerManager(max_concurrency=1)
    service = RunService(session_factory=isolated_db, worker_manager=worker_manager)

    plan = service.create_plan({
        "altitude_min_km": 500.0,
        "altitude_max_km": 500.0,
        "altitude_step_km": 50.0,
        "inclination_min_deg": 97.5,
        "inclination_max_deg": 97.5,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 0.0,
        "screening_days": 0.01,
        "demo_mode": True,
    })
    run = service.create_run(plan.id)

    # Submit task
    summary = service.submit_run(run.id)
    assert summary.run_id == run.id
    assert summary.status == RunStatus.queued.value
    assert summary.progress_percent == 0.0

    # Wait for completion via polling
    start_t = time.time()
    final_summary = None
    while time.time() - start_t < 5.0:
        final_summary = service.get_run_status(run.id)
        if final_summary.status in (RunStatus.completed.value, RunStatus.failed.value):
            break
        time.sleep(0.05)

    assert final_summary is not None
    assert final_summary.status == RunStatus.completed.value
    assert final_summary.progress_percent == 100.0
    worker_manager.shutdown(wait=True)


def test_run_service_running_transition(isolated_db):
    """Verify worker transitions run to 'running' at execution start."""
    pipeline_entered = threading.Event()
    pipeline_release = threading.Event()

    class MockPipeline:
        def run_pipeline(self, *args, **kwargs):
            pipeline_entered.set()
            pipeline_release.wait(timeout=3.0)
            return PipelineResult(
                plan_id="p1", run_id="r1", status="completed", mode="demo",
                started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
                source="demo", ingestion_mode="demo", fetched_at=datetime.now(timezone.utc),
                data_age_seconds=0.0, catalog_records_seen=1, catalog_records_accepted=1,
                catalog_records_rejected=0, snapshot_id=None, candidate_count=1,
                fuel_evaluated_count=1, within_budget_count=1, out_of_budget_count=0,
                debris_objects_considered=1, debris_objects_skipped=0, coarse_pair_hits=0,
                conjunction_event_count=0, risk_assessment_count=1, ranked_candidate_count=1,
                ranked_candidates=[], risk_assessments={}, conjunction_events=[],
                warnings=[], errors=[],
            )

    worker_manager = WorkerManager(max_concurrency=1)
    service = RunService(
        session_factory=isolated_db,
        worker_manager=worker_manager,
        pipeline_service=MockPipeline(),
    )

    plan = service.create_plan({"demo_mode": True})
    run = service.create_run(plan.id)

    try:
        service.submit_run(run.id)
        assert pipeline_entered.wait(timeout=2.0)

        # While blocked in pipeline, status must be running
        mid_status = service.get_run_status(run.id)
        assert mid_status.status == RunStatus.running.value
        assert mid_status.started_at is not None
        assert mid_status.current_stage == "ingestion"

        pipeline_release.set()
        time.sleep(0.1)

        final_status = service.get_run_status(run.id)
        assert final_status.status == RunStatus.completed.value
    finally:
        pipeline_release.set()
        worker_manager.shutdown(wait=True)


def test_run_service_failed_transition_on_pipeline_error(isolated_db):
    """Verify run transitions to 'failed' on PipelineStageError with diagnostics preserved."""
    class FailingPipeline:
        def run_pipeline(self, *args, **kwargs):
            raise PipelineStageError(
                stage="conjunction_screening",
                message="Simulated sensor failure in conjunction screening",
            )

    worker_manager = WorkerManager(max_concurrency=1)
    service = RunService(
        session_factory=isolated_db,
        worker_manager=worker_manager,
        pipeline_service=FailingPipeline(),
    )

    plan = service.create_plan({"demo_mode": True})
    run = service.create_run(plan.id)

    try:
        service.submit_run(run.id)
        start_t = time.time()
        status = None
        while time.time() - start_t < 5.0:
            status = service.get_run_status(run.id)
            if status.status in (RunStatus.completed.value, RunStatus.failed.value):
                break
            time.sleep(0.05)

        assert status is not None
        assert status.status == RunStatus.failed.value
        assert status.current_stage == "failed"
        assert status.completed_at is not None
        assert "Simulated sensor failure" in status.error_message
        assert "failed during conjunction_screening" in status.message
    finally:
        worker_manager.shutdown(wait=True)


def test_run_service_failed_on_worker_submission_error(isolated_db):
    """Verify that if WorkerManager rejects submission, run is marked failed immediately."""
    worker_manager = WorkerManager(max_concurrency=1)
    worker_manager.shutdown(wait=True)  # Shut down to simulate rejection

    service = RunService(session_factory=isolated_db, worker_manager=worker_manager)
    plan = service.create_plan({"demo_mode": True})
    run = service.create_run(plan.id)

    with pytest.raises(RuntimeError):
        service.submit_run(run.id)

    status = service.get_run_status(run.id)
    assert status.status == RunStatus.failed.value
    assert status.current_stage == "failed"
    assert "Worker submission failed" in status.error_message


def test_run_service_get_run_status(isolated_db):
    """Verify read-only status retrieval with candidate and event counts."""
    service = RunService(session_factory=isolated_db)
    plan = service.create_plan({"demo_mode": True})
    run = service.create_run(plan.id)

    status = service.get_run_status(run.id)
    assert status.run_id == run.id
    assert status.plan_id == plan.id
    assert status.status == RunStatus.queued.value
    assert status.candidate_count == 0
    assert status.conjunction_event_count == 0
    assert status.ranked_candidate_count == 0

    response_dict = status.to_dict()
    assert response_dict["run_id"] == run.id
    assert response_dict["status"] == "queued"

    pydantic_resp = status.to_response()
    assert pydantic_resp.run_id == run.id
    assert pydantic_resp.status == "queued"


def test_run_service_list_runs_by_plan(isolated_db):
    """Verify list_runs correctly isolates runs by plan ID."""
    service = RunService(session_factory=isolated_db)
    plan_a = service.create_plan({"demo_mode": True})
    plan_b = service.create_plan({"demo_mode": True})

    run_a1 = service.create_run(plan_a.id)
    run_a2 = service.create_run(plan_a.id)
    run_b1 = service.create_run(plan_b.id)

    runs_a = service.list_runs(plan_a.id)
    runs_b = service.list_runs(plan_b.id)

    assert len(runs_a) == 2
    assert {r.run_id for r in runs_a} == {run_a1.id, run_a2.id}
    assert len(runs_b) == 1
    assert runs_b[0].run_id == run_b1.id


def test_run_service_duplicate_submission_prevented(isolated_db):
    """Verify submitting an already active run raises DuplicateRunSubmissionError."""
    worker_manager = WorkerManager(max_concurrency=1)
    start_event = threading.Event()
    continue_event = threading.Event()

    class PausingPipeline:
        def run_pipeline(self, *args, **kwargs):
            start_event.set()
            continue_event.wait(timeout=3.0)
            return PipelineResult(
                plan_id="p1", run_id="r1", status="completed", mode="demo",
                started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
                source="demo", ingestion_mode="demo", fetched_at=datetime.now(timezone.utc),
                data_age_seconds=0.0, catalog_records_seen=0, catalog_records_accepted=0,
                catalog_records_rejected=0, snapshot_id=None, candidate_count=0,
                fuel_evaluated_count=0, within_budget_count=0, out_of_budget_count=0,
                debris_objects_considered=0, debris_objects_skipped=0, coarse_pair_hits=0,
                conjunction_event_count=0, risk_assessment_count=0, ranked_candidate_count=0,
                ranked_candidates=[], risk_assessments={}, conjunction_events=[],
                warnings=[], errors=[],
            )

    service = RunService(
        session_factory=isolated_db,
        worker_manager=worker_manager,
        pipeline_service=PausingPipeline(),
    )

    plan = service.create_plan({"demo_mode": True})
    run = service.create_run(plan.id)

    try:
        service.submit_run(run.id)
        assert start_event.wait(timeout=2.0)

        with pytest.raises(DuplicateRunSubmissionError):
            service.submit_run(run.id)

        continue_event.set()
    finally:
        continue_event.set()
        worker_manager.shutdown(wait=True)


def test_run_service_completed_run_cannot_restart(isolated_db):
    """Verify submit_run on a completed run raises RunLifecycleError."""
    service = RunService(session_factory=isolated_db)
    plan = service.create_plan({"demo_mode": True})
    run = service.create_run(plan.id)

    with isolated_db() as session:
        r = session.get(Run, run.id)
        r.status = RunStatus.completed.value
        session.commit()

    with pytest.raises(RunLifecycleError) as exc_info:
        service.submit_run(run.id)

    assert "Cannot submit run" in str(exc_info.value)
    assert "terminal state" in str(exc_info.value)


def test_run_service_failed_run_cannot_restart(isolated_db):
    """Verify submit_run on a failed run raises RunLifecycleError."""
    service = RunService(session_factory=isolated_db)
    plan = service.create_plan({"demo_mode": True})
    run = service.create_run(plan.id)

    with isolated_db() as session:
        r = session.get(Run, run.id)
        r.status = RunStatus.failed.value
        session.commit()

    with pytest.raises(RunLifecycleError) as exc_info:
        service.submit_run(run.id)

    assert "terminal state" in str(exc_info.value)


def test_run_service_create_and_submit_run_offline(monkeypatch, isolated_db):
    """Verify create_and_submit_run runs offline and executes P11 pipeline to completion."""
    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Socket call blocked in offline async test!")

    monkeypatch.setattr(socket, "socket", guarded_socket)

    worker_manager = WorkerManager(max_concurrency=1)
    service = RunService(session_factory=isolated_db, worker_manager=worker_manager)

    try:
        epoch_start = datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
        plan_params = PlanParameters(
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

        initial_summary = service.create_and_submit_run(plan_params)
        assert initial_summary.status == RunStatus.queued.value
        assert initial_summary.run_id is not None

        # Wait for worker thread to complete execution
        future = worker_manager.get_future(initial_summary.run_id)
        assert future is not None
        result = future.result(timeout=5.0)

        assert isinstance(result, PipelineResult)
        assert result.status == "completed"

        final_summary = service.get_run_status(initial_summary.run_id)
        assert final_summary.status == RunStatus.completed.value
        assert final_summary.progress_percent == 100.0
        assert final_summary.candidate_count == 2
        assert final_summary.ranked_candidate_count == 2
    finally:
        worker_manager.shutdown(wait=True)


def test_run_service_separate_runs_isolated(isolated_db):
    """Verify separate runs are isolated in status and candidate metrics."""
    service = RunService(session_factory=isolated_db)
    plan_a = service.create_plan({"demo_mode": True})
    plan_b = service.create_plan({"demo_mode": True})

    run_a = service.create_run(plan_a.id)
    run_b = service.create_run(plan_b.id)

    # Insert a candidate for Run A only
    with isolated_db() as session:
        cand_a = Candidate(
            run_id=run_a.id,
            altitude_km=500.0,
            inclination_deg=97.0,
            raan_deg=0.0,
            u0_deg=0.0,
            deployment_delay_minutes=0.0,
            predicted_raan_deg=0.0,
            delta_v_m_s=10.0,
            propellant_mass_kg=0.05,
            fuel_fraction=0.01,
            within_dv_budget=True,
            risk_score=0.0,
            rank=1,
        )
        session.add(cand_a)
        session.commit()

    status_a = service.get_run_status(run_a.id)
    status_b = service.get_run_status(run_b.id)

    assert status_a.candidate_count == 1
    assert status_b.candidate_count == 0


def test_run_service_worker_concurrency_one(isolated_db):
    """With max_concurrency=1, Run 2 stays queued while Run 1 is executing."""
    run1_started = threading.Event()
    run1_release = threading.Event()

    class CoordinatedPipeline:
        def run_pipeline(self, plan, db=None, run_id=None, **kwargs):
            if run_id == "run-coord-1":
                run1_started.set()
                run1_release.wait(timeout=3.0)
            return PipelineResult(
                plan_id="p1", run_id=run_id or "r", status="completed", mode="demo",
                started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
                source="demo", ingestion_mode="demo", fetched_at=datetime.now(timezone.utc),
                data_age_seconds=0.0, catalog_records_seen=0, catalog_records_accepted=0,
                catalog_records_rejected=0, snapshot_id=None, candidate_count=0,
                fuel_evaluated_count=0, within_budget_count=0, out_of_budget_count=0,
                debris_objects_considered=0, debris_objects_skipped=0, coarse_pair_hits=0,
                conjunction_event_count=0, risk_assessment_count=0, ranked_candidate_count=0,
                ranked_candidates=[], risk_assessments={}, conjunction_events=[],
                warnings=[], errors=[],
            )

    worker_manager = WorkerManager(max_concurrency=1)
    service = RunService(
        session_factory=isolated_db,
        worker_manager=worker_manager,
        pipeline_service=CoordinatedPipeline(),
    )

    plan = service.create_plan({"demo_mode": True})

    with isolated_db() as session:
        r1 = Run(id="run-coord-1", plan_id=plan.id, status=RunStatus.queued.value)
        r2 = Run(id="run-coord-2", plan_id=plan.id, status=RunStatus.queued.value)
        session.add_all([r1, r2])
        session.commit()

    try:
        service.submit_run("run-coord-1")
        assert run1_started.wait(timeout=2.0)

        service.submit_run("run-coord-2")

        # Run 1 is running, Run 2 must remain queued in DB
        s1 = service.get_run_status("run-coord-1")
        s2 = service.get_run_status("run-coord-2")
        assert s1.status == RunStatus.running.value
        assert s2.status == RunStatus.queued.value

        run1_release.set()
        f1 = worker_manager.get_future("run-coord-1")
        f2 = worker_manager.get_future("run-coord-2")
        if f1:
            f1.result(timeout=2.0)
        if f2:
            f2.result(timeout=2.0)

        # Both completed
        assert service.get_run_status("run-coord-1").status == RunStatus.completed.value
        assert service.get_run_status("run-coord-2").status == RunStatus.completed.value
    finally:
        run1_release.set()
        worker_manager.shutdown(wait=True)


def test_run_service_get_run_results(isolated_db):
    """Verify get_run_results returns complete run and candidate data."""
    service = RunService(session_factory=isolated_db)
    plan = service.create_plan({"demo_mode": True})
    run = service.create_run(plan.id)

    with isolated_db() as session:
        cand = Candidate(
            run_id=run.id,
            altitude_km=550.0,
            inclination_deg=97.5,
            raan_deg=0.0,
            u0_deg=0.0,
            deployment_delay_minutes=0.0,
            predicted_raan_deg=0.0,
            delta_v_m_s=25.0,
            propellant_mass_kg=0.1,
            fuel_fraction=0.03,
            within_dv_budget=True,
            risk_score=15.0,
            rank=1,
        )
        session.add(cand)
        session.commit()

    results = service.get_run_results(run.id)
    assert results["run"]["run_id"] == run.id
    assert results["plan"]["id"] == plan.id
    assert len(results["candidates"]) == 1
    assert results["candidates"][0]["rank"] == 1
    assert math.isclose(results["candidates"][0]["delta_v_m_s"], 25.0, abs_tol=1e-6)
