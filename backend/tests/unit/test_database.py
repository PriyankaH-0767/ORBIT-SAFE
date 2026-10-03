"""Unit tests for D-DATO database engine, ORM models, relationships, and repository CRUD."""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base, init_db
from app.db.models import (
    Plan,
    Run,
    Candidate,
    DebrisObject,
    DataSnapshot,
    ConjunctionEvent,
    ValidationRecord,
    RunStatus,
    SnapshotStatus,
)
from app.db.repositories import (
    PlanRepository,
    RunRepository,
    CandidateRepository,
    DebrisObjectRepository,
    ConjunctionEventRepository,
    DataSnapshotRepository,
    ValidationRecordRepository,
)
from app.utils.time import now_utc


@pytest.fixture
def db_session() -> Session:
    """Create an isolated, in-memory SQLite database session for unit testing."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_engine_and_metadata_creation():
    """Verify table creation from Base metadata on an in-memory test engine."""
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(target_engine=test_engine)

    inspector = inspect(test_engine)
    table_names = inspector.get_table_names()

    expected_tables = {
        "plans",
        "runs",
        "candidates",
        "debris_objects",
        "data_snapshots",
        "conjunction_events",
        "validation_records",
    }
    assert expected_tables.issubset(set(table_names))
    test_engine.dispose()


def test_plan_persistence_and_repo(db_session: Session):
    """Verify Plan creation, persistence, and retrieval via PlanRepository."""
    repo = PlanRepository(db_session)
    epoch = datetime(2026, 10, 15, 0, 0, 0, tzinfo=timezone.utc)

    plan = Plan(
        epoch_start=epoch,
        altitude_min_km=500.0,
        altitude_max_km=600.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.0,
        inclination_max_deg=98.0,
        inclination_step_deg=0.5,
        raan_deg=0.0,
        u0_deg=0.0,
        delay_min_minutes=0.0,
        delay_max_minutes=720.0,
        delay_step_minutes=60.0,
        raan_delay_coupling_deg_per_min=0.25068,
        screening_days=3,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
        dv_budget_m_s=100.0,
        spacecraft_mass_kg=3.0,
        isp_seconds=60.0,
        fuel_weight=0.4,
        risk_weight=0.6,
        data_source="celestrak",
        demo_mode=True,
    )

    created = repo.create(plan)
    assert created.id is not None
    assert created.created_at is not None

    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.reference_altitude_km == 550.0
    assert fetched.fuel_weight == 0.4
    assert fetched.demo_mode is True


def test_run_persistence_and_relationship(db_session: Session):
    """Verify Run creation, Plan -> Run relationship, and status lifecycle."""
    plan_repo = PlanRepository(db_session)
    run_repo = RunRepository(db_session)

    plan = plan_repo.create(
        Plan(
            epoch_start=now_utc(),
            altitude_min_km=500.0,
            altitude_max_km=600.0,
            altitude_step_km=25.0,
            inclination_min_deg=97.0,
            inclination_max_deg=98.0,
            inclination_step_deg=0.5,
            reference_altitude_km=550.0,
            reference_inclination_deg=97.5,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
            fuel_weight=0.4,
            risk_weight=0.6,
        )
    )

    run = Run(
        plan_id=plan.id,
        status=RunStatus.queued.value,
        progress_percent=0.0,
        current_stage="initialization",
    )
    created_run = run_repo.create(run)
    assert created_run.id is not None
    assert created_run.status == "queued"

    # Verify bidirectional relationship
    assert created_run.plan.id == plan.id
    assert len(plan.runs) == 1
    assert plan.runs[0].id == created_run.id

    # Test update_status to running
    updated_run = run_repo.update_status(
        created_run.id,
        status=RunStatus.running,
        progress_percent=45.0,
        current_stage="propagation",
        message="Propagating orbits",
    )
    assert updated_run is not None
    assert updated_run.status == "running"
    assert updated_run.started_at is not None
    assert updated_run.progress_percent == 45.0

    # Test update_status to completed
    completed_run = run_repo.update_status(
        created_run.id,
        status=RunStatus.completed,
        progress_percent=100.0,
        current_stage="complete",
        message="Screening finished",
    )
    assert completed_run.status == "completed"
    assert completed_run.completed_at is not None

    # Test list_by_plan
    runs = run_repo.list_by_plan(plan.id)
    assert len(runs) == 1


def test_candidate_persistence_and_repo(db_session: Session):
    """Verify Candidate persistence, bulk creation, and query ordering."""
    plan_repo = PlanRepository(db_session)
    run_repo = RunRepository(db_session)
    cand_repo = CandidateRepository(db_session)

    plan = plan_repo.create(
        Plan(
            epoch_start=now_utc(),
            altitude_min_km=500.0,
            altitude_max_km=600.0,
            altitude_step_km=25.0,
            inclination_min_deg=97.0,
            inclination_max_deg=98.0,
            inclination_step_deg=0.5,
            reference_altitude_km=550.0,
            reference_inclination_deg=97.5,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
            fuel_weight=0.4,
            risk_weight=0.6,
        )
    )
    run = run_repo.create(Run(plan_id=plan.id))

    candidates = [
        Candidate(
            run_id=run.id,
            altitude_km=500.0,
            inclination_deg=97.0,
            raan_deg=0.0,
            u0_deg=0.0,
            deployment_delay_minutes=0.0,
            predicted_raan_deg=0.0,
            delta_v_m_s=25.0,
            propellant_mass_kg=0.12,
            fuel_fraction=0.04,
            within_dv_budget=True,
            risk_score=0.15,
            rank=2,
        ),
        Candidate(
            run_id=run.id,
            altitude_km=550.0,
            inclination_deg=97.5,
            raan_deg=15.0,
            u0_deg=0.0,
            deployment_delay_minutes=60.0,
            predicted_raan_deg=15.04,
            delta_v_m_s=12.0,
            propellant_mass_kg=0.06,
            fuel_fraction=0.02,
            within_dv_budget=True,
            risk_score=0.05,
            rank=1,
        ),
    ]

    bulk_created = cand_repo.bulk_create(candidates)
    assert len(bulk_created) == 2

    # Query by run (should be ordered by rank)
    listed = cand_repo.list_by_run(run.id)
    assert len(listed) == 2
    assert listed[0].rank == 1
    assert listed[0].altitude_km == 550.0
    assert listed[1].rank == 2


def test_debris_object_persistence_and_upsert(db_session: Session):
    """Verify DebrisObject creation, retrieval, and bulk upsert."""
    repo = DebrisObjectRepository(db_session)
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    fetch_time = now_utc()

    debris = DebrisObject(
        norad_id="25544",
        object_name="ISS (ZARYA)",
        classification="U",
        tle_line1="1 25544U 98067A   26001.50000000  .00016717  00000+0  10270-3 0  9993",
        tle_line2="2 25544  51.6400 208.1000 0005000 120.0000 240.0000 15.50000000400001",
        epoch=epoch,
        inclination_deg=51.64,
        eccentricity=0.0005,
        mean_motion_rev_per_day=15.5,
        source="celestrak",
        fetched_at=fetch_time,
        data_age_seconds=120.0,
    )

    created = repo.create_or_update(debris)
    assert created.id is not None

    fetched = repo.get_by_norad_id("25544", source="celestrak")
    assert fetched is not None
    assert fetched.object_name == "ISS (ZARYA)"

    # Test update via create_or_update
    debris_update = DebrisObject(
        norad_id="25544",
        object_name="ISS (ZARYA) UPDATED",
        tle_line1=debris.tle_line1,
        tle_line2=debris.tle_line2,
        epoch=epoch,
        source="celestrak",
        fetched_at=now_utc(),
    )
    updated = repo.create_or_update(debris_update)
    assert updated.object_name == "ISS (ZARYA) UPDATED"
    assert updated.id == created.id

    # Test bulk_upsert
    bulk_list = [
        DebrisObject(
            norad_id="34455",
            object_name="COSMOS 2251 DEB",
            tle_line1="1 34455U...",
            tle_line2="2 34455...",
            epoch=epoch,
            source="celestrak",
            fetched_at=fetch_time,
        ),
        DebrisObject(
            norad_id="25544",
            object_name="ISS (ZARYA) REFRESHED",
            tle_line1=debris.tle_line1,
            tle_line2=debris.tle_line2,
            epoch=epoch,
            source="celestrak",
            fetched_at=fetch_time,
        ),
    ]
    upsert_count = repo.bulk_upsert(bulk_list)
    assert upsert_count == 2

    # Verify both records
    iss = repo.get_by_norad_id("25544", source="celestrak")
    assert iss.object_name == "ISS (ZARYA) REFRESHED"
    cosmos = repo.get_by_norad_id("34455", source="celestrak")
    assert cosmos is not None


def test_data_snapshot_persistence(db_session: Session):
    """Verify DataSnapshot persistence and latest snapshot lookup."""
    repo = DataSnapshotRepository(db_session)
    t1 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 1, 14, 0, 0, tzinfo=timezone.utc)

    s1 = DataSnapshot(
        source="celestrak",
        fetched_at=t1,
        data_age_seconds=3600.0,
        object_count=15000,
        cache_key="celestrak_active_t1",
        status=SnapshotStatus.success.value,
    )
    s2 = DataSnapshot(
        source="celestrak",
        fetched_at=t2,
        data_age_seconds=1800.0,
        object_count=15050,
        cache_key="celestrak_active_t2",
        status=SnapshotStatus.success.value,
    )
    repo.create(s1)
    repo.create(s2)

    latest = repo.get_latest_by_source("celestrak")
    assert latest is not None
    assert latest.fetched_at == t2
    assert latest.object_count == 15050


def test_conjunction_event_persistence_and_relationships(db_session: Session):
    """Verify ConjunctionEvent bulk creation and relationship linking."""
    plan_repo = PlanRepository(db_session)
    run_repo = RunRepository(db_session)
    cand_repo = CandidateRepository(db_session)
    deb_repo = DebrisObjectRepository(db_session)
    event_repo = ConjunctionEventRepository(db_session)

    plan = plan_repo.create(
        Plan(
            epoch_start=now_utc(),
            altitude_min_km=500.0,
            altitude_max_km=600.0,
            altitude_step_km=25.0,
            inclination_min_deg=97.0,
            inclination_max_deg=98.0,
            inclination_step_deg=0.5,
            reference_altitude_km=550.0,
            reference_inclination_deg=97.5,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
            fuel_weight=0.4,
            risk_weight=0.6,
        )
    )
    run = run_repo.create(Run(plan_id=plan.id))
    cand = cand_repo.create(
        Candidate(
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
            risk_score=0.2,
        )
    )
    deb = deb_repo.create_or_update(
        DebrisObject(
            norad_id="99999",
            object_name="DEBRIS 99999",
            tle_line1="1 99999U...",
            tle_line2="2 99999...",
            epoch=now_utc(),
            source="celestrak",
            fetched_at=now_utc(),
        )
    )

    tca_time = now_utc() + timedelta(days=1)
    event = ConjunctionEvent(
        run_id=run.id,
        candidate_id=cand.id,
        debris_object_id=deb.id,
        tca=tca_time,
        miss_distance_km=2.45,
        relative_velocity_km_s=14.2,
        threshold_km=5.0,
        screening_source="ddato",
    )
    event_repo.bulk_create([event])

    events_by_run = event_repo.list_by_run(run.id)
    assert len(events_by_run) == 1
    assert events_by_run[0].miss_distance_km == 2.45
    assert events_by_run[0].debris_object.object_name == "DEBRIS 99999"

    events_by_cand = event_repo.list_by_candidate(cand.id)
    assert len(events_by_cand) == 1
    assert events_by_cand[0].candidate.altitude_km == 550.0


def test_validation_record_persistence(db_session: Session):
    """Verify ValidationRecord persistence and lookup."""
    plan_repo = PlanRepository(db_session)
    run_repo = RunRepository(db_session)
    val_repo = ValidationRecordRepository(db_session)

    plan = plan_repo.create(
        Plan(
            epoch_start=now_utc(),
            altitude_min_km=500.0,
            altitude_max_km=600.0,
            altitude_step_km=25.0,
            inclination_min_deg=97.0,
            inclination_max_deg=98.0,
            inclination_step_deg=0.5,
            reference_altitude_km=550.0,
            reference_inclination_deg=97.5,
            dv_budget_m_s=100.0,
            spacecraft_mass_kg=3.0,
            isp_seconds=60.0,
            fuel_weight=0.4,
            risk_weight=0.6,
        )
    )
    run = run_repo.create(Run(plan_id=plan.id))

    record = ValidationRecord(
        run_id=run.id,
        source="SOCRATES",
        external_event_id="SOC-2026-1001",
        event_time=now_utc(),
        measured_or_reference_miss_distance_km=3.5,
        ddato_miss_distance_km=3.42,
        absolute_error_km=0.08,
        relative_error_percent=2.28,
        notes="High confidence alignment with SOCRATES report.",
    )
    val_repo.create(record)

    records = val_repo.list_by_run(run.id)
    assert len(records) == 1
    assert records[0].source == "SOCRATES"
    assert records[0].absolute_error_km == 0.08


def test_repository_rollback_on_failure(db_session: Session):
    """Verify explicit rollback behavior upon transaction constraint failure."""
    plan_repo = PlanRepository(db_session)

    # Attempt to persist an invalid entity missing required fields
    bad_plan = Plan(id="invalid_plan")  # Missing non-nullable fields like epoch_start, altitude_min_km
    with pytest.raises(Exception):
        plan_repo.create(bad_plan)

    # Confirm session is not corrupted and rollback succeeded
    assert plan_repo.get_by_id("invalid_plan") is None


def test_naive_datetime_rejected_by_orm(db_session: Session):
    """Verify that passing a naive datetime to ORM models raises ValueError."""
    plan_repo = PlanRepository(db_session)
    naive_epoch = datetime(2026, 10, 15, 0, 0, 0)  # naive datetime without timezone

    bad_plan = Plan(
        epoch_start=naive_epoch,
        altitude_min_km=500.0,
        altitude_max_km=600.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.0,
        inclination_max_deg=98.0,
        inclination_step_deg=0.5,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
        dv_budget_m_s=100.0,
        spacecraft_mass_kg=3.0,
        isp_seconds=60.0,
        fuel_weight=0.4,
        risk_weight=0.6,
    )
    with pytest.raises(Exception, match="Naive datetime.*passed to database layer"):
        plan_repo.create(bad_plan)

