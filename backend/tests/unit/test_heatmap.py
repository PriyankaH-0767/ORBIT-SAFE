"""Unit and integration test suite for D-DATO Phase P14 Risk Heatmap Service & API.

Verifies:
1. Completed run returns full heatmap data
2. All inclination layers are returned when no filter is provided
3. Inclination filter returns exactly one matching layer
4. Unknown inclination returns 200 with zero matching layers
5. Altitude/delay matrix dimensions are correct
6. Matrix coordinates map to the correct candidate_id and risk_score
7. Values and coordinates are ordered altitude ascending and delay ascending
8. Missing candidate cell becomes null
9. Min/max risk are computed from populated cells only
10. Queued/running run with no persisted candidates returns 200 and empty heatmap data
11. Unknown run returns 404
12. Malformed inclination query returns 422
13. Endpoint does not trigger a new screening/ranking execution
14. Endpoint makes no network call in demo mode
15. Conjunction event metadata is read-only aggregated without rescreening
"""

from datetime import datetime, timezone
import math
import socket
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, get_db
from app.db.models import Candidate, ConjunctionEvent, Plan, Run
from app.db.repositories import CandidateRepository
from app.main import app
from app.schemas.heatmap import HeatmapCell, HeatmapLayer, HeatmapResponse
from app.services.heatmap_service import HeatmapService, get_heatmap_service
from app.services.pipeline_service import PipelineService
from app.services.run_service import RunService, get_run_service
from app.workers.screening_worker import WorkerManager


@pytest.fixture
def isolated_heatmap_setup(tmp_path) -> Generator[tuple[Session, HeatmapService, sessionmaker, TestClient], None, None]:
    """Provide an isolated SQLite database, HeatmapService, and TestClient."""
    db_file = tmp_path / "test_heatmap.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    heatmap_service = HeatmapService(session_factory=TestSessionLocal)
    worker_mgr = WorkerManager(max_concurrency=1)
    run_service = RunService(session_factory=TestSessionLocal, worker_manager=worker_mgr)

    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_get_heatmap_service():
        return heatmap_service

    def override_get_run_service():
        return run_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_heatmap_service] = override_get_heatmap_service
    app.dependency_overrides[get_run_service] = override_get_run_service

    db_session = TestSessionLocal()
    with TestClient(app) as test_client:
        try:
            yield db_session, heatmap_service, TestSessionLocal, test_client
        finally:
            db_session.close()
            worker_mgr.shutdown(wait=True, cancel_futures=True)
            Base.metadata.drop_all(bind=test_engine)
            test_engine.dispose()
            app.dependency_overrides.clear()


def _seed_completed_run_and_candidates(
    session: Session,
    altitudes: list[float] = (550.0, 575.0, 600.0),
    inclinations: list[float] = (97.0, 97.5, 98.0),
    delays: list[float] = (0.0, 60.0),
    omit_coords: set[tuple[float, float, float]] = None,
) -> tuple[Run, list[Candidate]]:
    """Seed a deterministic test Plan, completed Run, and grid of evaluated Candidates."""
    omit_coords = omit_coords or set()
    now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)

    plan = Plan(
        epoch_start=now,
        altitude_min_km=min(altitudes),
        altitude_max_km=max(altitudes),
        altitude_step_km=25.0,
        inclination_min_deg=min(inclinations),
        inclination_max_deg=max(inclinations),
        inclination_step_deg=0.5,
        raan_deg=0.0,
        u0_deg=0.0,
        delay_min_minutes=min(delays),
        delay_max_minutes=max(delays),
        delay_step_minutes=60.0,
        raan_delay_coupling_deg_per_min=0.25,
        screening_days=3.0,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
        dv_budget_m_s=100.0,
        spacecraft_mass_kg=3.0,
        isp_seconds=60.0,
        fuel_weight=0.4,
        risk_weight=0.6,
        data_source="demo",
        demo_mode=True,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)

    run = Run(
        plan_id=plan.id,
        status="completed",
        progress_percent=100.0,
        current_stage="completed",
        message="Run completed",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    candidates: list[Candidate] = []
    rank_counter = 1
    score_counter = 10.0

    for inc in inclinations:
        for alt in altitudes:
            for delay in delays:
                if (alt, inc, delay) in omit_coords:
                    continue
                cand = Candidate(
                    run_id=run.id,
                    altitude_km=alt,
                    inclination_deg=inc,
                    raan_deg=0.0 + delay * 0.25,
                    u0_deg=0.0,
                    deployment_delay_minutes=delay,
                    predicted_raan_deg=0.0 + delay * 0.25,
                    delta_v_m_s=25.0,
                    propellant_mass_kg=0.12,
                    fuel_fraction=0.04,
                    within_dv_budget=True,
                    risk_score=score_counter,
                    rank=rank_counter,
                )
                candidates.append(cand)
                session.add(cand)
                rank_counter += 1
                score_counter += 2.5

    session.commit()
    for c in candidates:
        session.refresh(c)

    return run, candidates


def test_completed_run_returns_heatmap_data(isolated_heatmap_setup):
    """Test 1: Completed run returns full 2D heatmap data across all layers."""
    session, _, _, client = isolated_heatmap_setup
    run, candidates = _seed_completed_run_and_candidates(session)

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    assert data["run_id"] == run.id
    assert data["status"] == "completed"
    assert data["metric"] == "risk_score"
    assert data["x_axis"] == "delay_minutes"
    assert data["y_axis"] == "altitude_km"
    assert len(data["layers"]) == 3
    assert data["total_candidates"] == 18
    assert data["populated_cells"] == 18
    assert data["min_risk_score"] == pytest.approx(10.0)
    assert data["max_risk_score"] == pytest.approx(10.0 + 17 * 2.5)


def test_all_inclination_layers_returned_when_no_filter(isolated_heatmap_setup):
    """Test 2: All inclination layers are returned when query param is omitted."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(session)

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    assert data["inclination_values_deg"] == [97.0, 97.5, 98.0]
    layer_incs = [layer["inclination_deg"] for layer in data["layers"]]
    assert layer_incs == [97.0, 97.5, 98.0]


def test_inclination_filter_returns_exactly_one_matching_layer(isolated_heatmap_setup):
    """Test 3: Specifying inclination_deg returns only that specific slice."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(session)

    res = client.get(f"/api/v1/runs/{run.id}/heatmap?inclination_deg=97.5")
    assert res.status_code == 200
    data = res.json()

    assert data["inclination_values_deg"] == [97.5]
    assert len(data["layers"]) == 1
    assert data["layers"][0]["inclination_deg"] == 97.5
    assert data["total_candidates"] == 6
    assert data["populated_cells"] == 6


def test_unknown_inclination_returns_200_with_zero_matching_layers(isolated_heatmap_setup):
    """Test 4: Unmatched inclination returns HTTP 200 with empty layers list."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(session)

    res = client.get(f"/api/v1/runs/{run.id}/heatmap?inclination_deg=45.0")
    assert res.status_code == 200
    data = res.json()

    assert data["layers"] == []
    assert data["inclination_values_deg"] == []
    assert data["total_candidates"] == 0
    assert data["populated_cells"] == 0
    assert data["min_risk_score"] is None
    assert data["max_risk_score"] is None


def test_altitude_delay_matrix_dimensions_are_correct(isolated_heatmap_setup):
    """Test 5: Altitude/delay matrix dimensions match len(altitude) x len(delay)."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(
        session,
        altitudes=[500.0, 525.0, 550.0, 575.0, 600.0],
        inclinations=[97.0, 97.5],
        delays=[0.0, 60.0, 120.0, 180.0],
    )

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    assert len(data["layers"]) == 2
    for layer in data["layers"]:
        assert len(layer["altitude_values_km"]) == 5
        assert len(layer["delay_values_minutes"]) == 4
        assert len(layer["values"]) == 5  # 5 rows
        for row in layer["values"]:
            assert len(row) == 4  # 4 columns


def test_matrix_coordinates_map_to_correct_candidate_and_risk(isolated_heatmap_setup):
    """Test 6: Each matrix values[r][c] correctly corresponds to (altitude[r], delay[c]) candidate."""
    session, _, _, client = isolated_heatmap_setup
    run, candidates = _seed_completed_run_and_candidates(session)

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    cand_map = {
        (round(c.inclination_deg, 4), round(c.altitude_km, 4), round(c.deployment_delay_minutes, 4)): c
        for c in candidates
    }

    for layer in data["layers"]:
        inc = round(layer["inclination_deg"], 4)
        alts = layer["altitude_values_km"]
        delays = layer["delay_values_minutes"]

        for r_idx, alt in enumerate(alts):
            for c_idx, delay in enumerate(delays):
                expected_cand = cand_map[(inc, round(alt, 4), round(delay, 4))]
                cell_val = layer["values"][r_idx][c_idx]
                assert cell_val == pytest.approx(expected_cand.risk_score)


def test_values_and_coordinates_are_ordered_ascending(isolated_heatmap_setup):
    """Test 7: Values and axes are strictly ordered ascending."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(session)

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    # Inclinations ascending
    assert data["inclination_values_deg"] == sorted(data["inclination_values_deg"])

    for layer in data["layers"]:
        # Altitude and delay ascending
        assert layer["altitude_values_km"] == sorted(layer["altitude_values_km"])
        assert layer["delay_values_minutes"] == sorted(layer["delay_values_minutes"])

        # Detailed cells sorted by altitude ascending, then delay ascending
        prev_alt = -1.0
        prev_delay = -1.0
        for cell in layer["cells"]:
            if cell["altitude_km"] == prev_alt:
                assert cell["delay_minutes"] >= prev_delay
            else:
                assert cell["altitude_km"] > prev_alt
            prev_alt = cell["altitude_km"]
            prev_delay = cell["delay_minutes"]


def test_missing_candidate_cell_becomes_null(isolated_heatmap_setup):
    """Test 8: If a candidate coordinate is missing from persistence, matrix cell is null."""
    session, _, _, client = isolated_heatmap_setup
    # Omit altitude 600, delay 0 for inclination 97.0
    run, _ = _seed_completed_run_and_candidates(
        session,
        altitudes=[500.0, 600.0],
        inclinations=[97.0],
        delays=[0.0, 60.0],
        omit_coords={(600.0, 97.0, 0.0)},
    )

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    layer = data["layers"][0]
    assert layer["altitude_values_km"] == [500.0, 600.0]
    assert layer["delay_values_minutes"] == [0.0, 60.0]

    matrix = layer["values"]
    assert len(matrix) == 2
    assert len(matrix[0]) == 2
    # Row 0 (alt 500): both delays present
    assert matrix[0][0] is not None
    assert matrix[0][1] is not None
    # Row 1 (alt 600): delay 0 is missing -> must be None (null)
    assert matrix[1][0] is None
    assert matrix[1][1] is not None

    # Total candidates is 3, populated cells is 3
    assert data["total_candidates"] == 3
    assert data["populated_cells"] == 3


def test_min_max_risk_computed_from_populated_cells_only(isolated_heatmap_setup):
    """Test 9: min_risk_score and max_risk_score ignore null cells."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(
        session,
        altitudes=[500.0, 600.0],
        inclinations=[97.0],
        delays=[0.0, 60.0],
        omit_coords={(600.0, 97.0, 0.0)},
    )

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    layer = data["layers"][0]
    populated_values = [v for row in layer["values"] for v in row if v is not None]
    assert len(populated_values) == 3
    assert data["min_risk_score"] == pytest.approx(min(populated_values))
    assert data["max_risk_score"] == pytest.approx(max(populated_values))


def test_queued_or_running_run_returns_200_and_empty_heatmap(isolated_heatmap_setup):
    """Test 10: Run with status queued or running returns HTTP 200 with empty heatmap."""
    session, _, _, client = isolated_heatmap_setup
    now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    plan = Plan(
        epoch_start=now,
        altitude_min_km=500.0,
        altitude_max_km=600.0,
        altitude_step_km=50.0,
        inclination_min_deg=97.0,
        inclination_max_deg=98.0,
        inclination_step_deg=1.0,
        raan_deg=0.0,
        u0_deg=0.0,
        delay_min_minutes=0.0,
        delay_max_minutes=60.0,
        delay_step_minutes=60.0,
    )
    session.add(plan)
    session.commit()

    run = Run(
        plan_id=plan.id,
        status="running",
        progress_percent=25.0,
        current_stage="conjunction_screening",
        message="Evaluating close approaches",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    assert data["run_id"] == run.id
    assert data["status"] == "running"
    assert data["layers"] == []
    assert data["total_candidates"] == 0
    assert data["populated_cells"] == 0
    assert data["min_risk_score"] is None
    assert data["max_risk_score"] is None


def test_unknown_run_returns_404(isolated_heatmap_setup):
    """Test 11: Unknown run_id returns 404 with RUN_NOT_FOUND code."""
    _, _, _, client = isolated_heatmap_setup
    res = client.get("/api/v1/runs/non-existent-run-uuid/heatmap")
    assert res.status_code == 404
    data = res.json()
    assert data["detail"]["code"] == "RUN_NOT_FOUND"


def test_malformed_inclination_returns_422(isolated_heatmap_setup):
    """Test 12: Non-numeric inclination parameter returns 422 Unprocessable Entity."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(session)

    res = client.get(f"/api/v1/runs/{run.id}/heatmap?inclination_deg=not-a-valid-float")
    assert res.status_code == 422


def test_endpoint_does_not_trigger_new_screening_or_ranking(isolated_heatmap_setup):
    """Test 13: Endpoint is strictly read-only and does not invoke screening/ranking pipeline."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(session)

    with patch.object(PipelineService, "run_pipeline") as mock_pipeline, \
         patch.object(WorkerManager, "submit") as mock_worker:
        res = client.get(f"/api/v1/runs/{run.id}/heatmap")
        assert res.status_code == 200
        mock_pipeline.assert_not_called()
        mock_worker.assert_not_called()


def test_endpoint_makes_no_network_call(isolated_heatmap_setup):
    """Test 14: Heatmap endpoint executes completely offline without external network calls."""
    session, _, _, client = isolated_heatmap_setup
    run, _ = _seed_completed_run_and_candidates(session)

    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) and address else ""
        if host in ("127.0.0.1", "localhost", "::1"):
            return original_connect(self, address)
        raise socket.error(f"External network call forbidden in test: {address}")

    with patch.object(socket.socket, "connect", guarded_connect):
        res = client.get(f"/api/v1/runs/{run.id}/heatmap")
        assert res.status_code == 200
        assert res.json()["run_id"] == run.id


def test_conjunction_event_metadata_is_aggregated_into_cells(isolated_heatmap_setup):
    """Test 15: Conjunction event counts and min miss distance populate cells without rescreening."""
    session, _, _, client = isolated_heatmap_setup
    run, candidates = _seed_completed_run_and_candidates(
        session,
        altitudes=[500.0],
        inclinations=[97.0],
        delays=[0.0],
    )
    cand = candidates[0]

    # Add 2 conjunction events for this candidate
    evt1 = ConjunctionEvent(
        run_id=run.id,
        candidate_id=cand.id,
        tca=datetime(2026, 10, 2, 14, 0, 0, tzinfo=timezone.utc),
        miss_distance_km=4.2,
        relative_velocity_km_s=11.5,
        threshold_km=25.0,
    )
    evt2 = ConjunctionEvent(
        run_id=run.id,
        candidate_id=cand.id,
        tca=datetime(2026, 10, 2, 18, 0, 0, tzinfo=timezone.utc),
        miss_distance_km=1.8,
        relative_velocity_km_s=14.0,
        threshold_km=25.0,
    )
    session.add_all([evt1, evt2])
    session.commit()

    res = client.get(f"/api/v1/runs/{run.id}/heatmap")
    assert res.status_code == 200
    data = res.json()

    cell = data["layers"][0]["cells"][0]
    assert cell["candidate_id"] == cand.id
    assert cell["accepted_event_count"] == 2
    assert cell["minimum_miss_distance_km"] == pytest.approx(1.8)
    assert cell["uncertainty_level"] == "nominal"
