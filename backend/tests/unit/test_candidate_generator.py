"""Unit tests for Candidate Orbit and Deployment Window Generator.

Phase P6: Deterministic candidate orbit generation, inclusive grids,
RAAN-delay coupling, maximum candidate limits, and ordering.
The original D-DATO project specification is authoritative.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import pytest

from app.core.candidate_generator import (
    CandidateGenerationConfig,
    CandidateGenerationError,
    CandidateOrbit,
    candidate_to_model_data,
    generate_candidate_id,
    generate_candidates,
    generate_grid,
    normalize_angle_360,
)
from app.core.config import settings


@pytest.fixture
def fixed_utc_epoch():
    """Fixed reference epoch in timezone-aware UTC."""
    return datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)


def test_default_altitude_grid():
    """Default altitude grid produces [500, 525, 550, 575, 600] km."""
    grid = generate_grid(
        settings.ALTITUDE_MIN_KM,
        settings.ALTITUDE_MAX_KM,
        settings.ALTITUDE_STEP_KM,
    )
    assert grid == [500.0, 525.0, 550.0, 575.0, 600.0]
    assert len(grid) == 5


def test_default_inclination_grid():
    """Default inclination grid produces [97.0, 97.5, 98.0] degrees."""
    grid = generate_grid(
        settings.INCLINATION_MIN_DEG,
        settings.INCLINATION_MAX_DEG,
        settings.INCLINATION_STEP_DEG,
    )
    assert grid == [97.0, 97.5, 98.0]
    assert len(grid) == 3


def test_default_delay_grid():
    """Default delay grid produces 13 values from 0 to 720 minutes in 60-min steps."""
    grid = generate_grid(
        settings.DELAY_MIN_MINUTES,
        settings.DELAY_MAX_MINUTES,
        settings.DELAY_STEP_MINUTES,
    )
    expected = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0, 360.0, 420.0, 480.0, 540.0, 600.0, 660.0, 720.0]
    assert grid == expected
    assert len(grid) == 13


def test_default_candidate_count_and_reference_candidates(fixed_utc_epoch):
    """Default candidate generation produces exactly 195 candidates and reference candidates."""
    candidates = generate_candidates(epoch_start=fixed_utc_epoch)
    # 5 altitudes * 3 inclinations * 13 delays = 195
    assert len(candidates) == 195

    # Find reference candidate: 550 km, 97.5 deg, 0 min delay
    ref_cand = next(
        c for c in candidates
        if c.altitude_km == 550.0 and c.inclination_deg == 97.5 and c.deployment_delay_minutes == 0.0
    )
    assert ref_cand.raan_deg == 0.0
    assert ref_cand.predicted_raan_deg == 0.0
    assert ref_cand.base_raan_deg == 0.0
    assert ref_cand.candidate_id == "ALT550_INC97.5_DELAY000"

    # Find 60-minute delay candidate: 550 km, 97.5 deg, 60 min delay
    cand_60 = next(
        c for c in candidates
        if c.altitude_km == 550.0 and c.inclination_deg == 97.5 and c.deployment_delay_minutes == 60.0
    )
    assert cand_60.raan_deg == 15.0408
    assert cand_60.predicted_raan_deg == 15.0408
    assert cand_60.base_raan_deg == 0.0
    assert cand_60.candidate_id == "ALT550_INC97.5_DELAY060"

    # Find 720-minute delay candidate: 550 km, 97.5 deg, 720 min delay
    cand_720 = next(
        c for c in candidates
        if c.altitude_km == 550.0 and c.inclination_deg == 97.5 and c.deployment_delay_minutes == 720.0
    )
    assert cand_720.raan_deg == 180.4896
    assert cand_720.predicted_raan_deg == 180.4896
    assert cand_720.candidate_id == "ALT550_INC97.5_DELAY720"


def test_default_first_and_last_candidates(fixed_utc_epoch):
    """First and last candidates follow strict deterministic ordering bounds."""
    candidates = generate_candidates(epoch_start=fixed_utc_epoch)

    # First candidate: lowest altitude, lowest inclination, lowest delay
    first = candidates[0]
    assert first.altitude_km == 500.0
    assert first.inclination_deg == 97.0
    assert first.deployment_delay_minutes == 0.0
    assert first.candidate_id == "ALT500_INC97.0_DELAY000"
    assert first.generated_index == 0

    # Last candidate: highest altitude, highest inclination, highest delay
    last = candidates[-1]
    assert last.altitude_km == 600.0
    assert last.inclination_deg == 98.0
    assert last.deployment_delay_minutes == 720.0
    assert last.candidate_id == "ALT600_INC98.0_DELAY720"
    assert last.generated_index == 194


def test_deterministic_ordering(fixed_utc_epoch):
    """Candidates are strictly ordered: altitude -> inclination -> deployment delay."""
    candidates = generate_candidates(epoch_start=fixed_utc_epoch)

    # Verify sequential monotonic ordering across all 195 candidates
    for i in range(len(candidates) - 1):
        c1 = candidates[i]
        c2 = candidates[i + 1]
        key1 = (c1.altitude_km, c1.inclination_deg, c1.deployment_delay_minutes)
        key2 = (c2.altitude_km, c2.inclination_deg, c2.deployment_delay_minutes)
        assert key1 < key2, f"Ordering violation at index {i}: {key1} vs {key2}"

    # Verify the first 14 candidates specific sequence:
    # First 13 have alt=500, inc=97.0, delays 0 to 720
    for i in range(13):
        assert candidates[i].altitude_km == 500.0
        assert candidates[i].inclination_deg == 97.0
        assert candidates[i].deployment_delay_minutes == i * 60.0

    # 14th candidate (index 13) advances inclination to 97.5, delay returns to 0
    assert candidates[13].altitude_km == 500.0
    assert candidates[13].inclination_deg == 97.5
    assert candidates[13].deployment_delay_minutes == 0.0


def test_deterministic_candidate_ids(fixed_utc_epoch):
    """Candidate IDs are unique, deterministic, and identifiable."""
    candidates = generate_candidates(epoch_start=fixed_utc_epoch)
    ids = [c.candidate_id for c in candidates]

    # All 195 IDs must be unique
    assert len(set(ids)) == len(candidates)

    # Specific format verification
    assert generate_candidate_id(500.0, 97.0, 0.0) == "ALT500_INC97.0_DELAY000"
    assert generate_candidate_id(550.0, 97.5, 60.0) == "ALT550_INC97.5_DELAY060"
    assert generate_candidate_id(600.0, 98.0, 720.0) == "ALT600_INC98.0_DELAY720"


def test_raan_delay_coupling_exact_values(fixed_utc_epoch):
    """Coupling parameter 0.25068 deg/min is applied deterministically to delay."""
    # coupling * delay:
    # 0.25068 * 0 = 0.0
    # 0.25068 * 60 = 15.0408
    # 0.25068 * 120 = 30.0816
    # 0.25068 * 720 = 180.4896
    candidates = generate_candidates(
        epoch_start=fixed_utc_epoch,
        altitude_min_km=500.0,
        altitude_max_km=500.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.0,
        inclination_max_deg=97.0,
        inclination_step_deg=0.5,
        delay_min_minutes=0.0,
        delay_max_minutes=120.0,
        delay_step_minutes=60.0,
        base_raan_deg=0.0,
    )
    assert len(candidates) == 3
    assert candidates[0].raan_deg == 0.0
    assert candidates[1].raan_deg == 15.0408
    assert candidates[2].raan_deg == 30.0816


def test_raan_normalization_and_wrapping(fixed_utc_epoch):
    """RAAN is normalized strictly into [0.0, 360.0) degrees."""
    # Base RAAN = 350 deg, delay = 60 min -> 350 + 15.0408 = 365.0408 -> 5.0408 deg
    candidates = generate_candidates(
        epoch_start=fixed_utc_epoch,
        altitude_min_km=500.0,
        altitude_max_km=500.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.0,
        inclination_max_deg=97.0,
        inclination_step_deg=0.5,
        delay_min_minutes=60.0,
        delay_max_minutes=60.0,
        delay_step_minutes=60.0,
        base_raan_deg=350.0,
    )
    assert len(candidates) == 1
    assert candidates[0].base_raan_deg == 350.0
    assert candidates[0].raan_deg == 5.0408

    # Negative base RAAN normalization
    assert normalize_angle_360(-30.0) == 330.0
    assert normalize_angle_360(360.0) == 0.0
    assert normalize_angle_360(0.0) == 0.0
    assert normalize_angle_360(-0.0) == 0.0


def test_deployment_epoch_calculation(fixed_utc_epoch):
    """Deployment epoch strictly equals epoch_start + delay minutes in UTC."""
    candidates = generate_candidates(
        epoch_start=fixed_utc_epoch,
        altitude_min_km=500.0,
        altitude_max_km=500.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.0,
        inclination_max_deg=97.0,
        inclination_step_deg=0.5,
        delay_min_minutes=0.0,
        delay_max_minutes=120.0,
        delay_step_minutes=60.0,
    )
    assert len(candidates) == 3
    assert candidates[0].deployment_epoch == datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
    assert candidates[1].deployment_epoch == datetime(2026, 10, 2, 1, 0, 0, tzinfo=timezone.utc)
    assert candidates[2].deployment_epoch == datetime(2026, 10, 2, 2, 0, 0, tzinfo=timezone.utc)


def test_u0_preservation(fixed_utc_epoch):
    """u0_deg is preserved from planning inputs without arbitrary delay modification."""
    candidates = generate_candidates(
        epoch_start=fixed_utc_epoch,
        altitude_min_km=500.0,
        altitude_max_km=500.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.0,
        inclination_max_deg=97.0,
        inclination_step_deg=0.5,
        delay_min_minutes=0.0,
        delay_max_minutes=120.0,
        delay_step_minutes=60.0,
        u0_deg=45.0,
    )
    for c in candidates:
        assert c.u0_deg == 45.0


def test_range_edge_cases():
    """Test boundary edge cases for discrete grid generation."""
    # A. min == max produces 1 value
    grid_single = generate_grid(500.0, 500.0, 25.0)
    assert grid_single == [500.0]

    # B. step larger than range produces 1 value (min only, does not force max)
    grid_large_step = generate_grid(500.0, 600.0, 250.0)
    assert grid_large_step == [500.0]

    # C. step exactly divides range includes max
    grid_exact = generate_grid(500.0, 600.0, 25.0)
    assert grid_exact == [500.0, 525.0, 550.0, 575.0, 600.0]

    # D. step equal to range produces min and max
    grid_two = generate_grid(500.0, 550.0, 50.0)
    assert grid_two == [500.0, 550.0]


def test_floating_point_step_behavior():
    """Decimal-based grid generation avoids floating-point accumulation drift."""
    grid = generate_grid(97.0, 98.0, 0.1)
    assert len(grid) == 11
    expected = [97.0, 97.1, 97.2, 97.3, 97.4, 97.5, 97.6, 97.7, 97.8, 97.9, 98.0]
    assert grid == expected
    # Verify no drift like 97.4999999997
    for val in grid:
        assert round(val, 1) == val


def test_invalid_range_rejections(fixed_utc_epoch):
    """Invalid parameter ranges raise CandidateGenerationError or ValueError."""
    # Descending altitude range
    with pytest.raises(CandidateGenerationError, match="cannot exceed max"):
        generate_grid(600.0, 500.0, 25.0)

    # Step <= 0
    with pytest.raises(CandidateGenerationError, match="strictly positive"):
        generate_grid(500.0, 600.0, 0.0)

    # Non-finite values
    with pytest.raises(CandidateGenerationError, match="finite numbers"):
        generate_grid(float("nan"), 600.0, 25.0)

    # In generate_candidates: negative altitude
    with pytest.raises(CandidateGenerationError, match="positive numbers"):
        generate_candidates(epoch_start=fixed_utc_epoch, altitude_min_km=-100.0)

    # Inclination out of bounds
    with pytest.raises(CandidateGenerationError, match="between 0.0 and 180.0"):
        generate_candidates(epoch_start=fixed_utc_epoch, inclination_max_deg=185.0)

    # Negative delay
    with pytest.raises(CandidateGenerationError, match="non-negative"):
        generate_candidates(epoch_start=fixed_utc_epoch, delay_min_minutes=-10.0)

    # Naive epoch (lacking timezone)
    naive_epoch = datetime(2026, 10, 2, 0, 0, 0)
    with pytest.raises(ValueError, match="[Nn]aive"):
        generate_candidates(epoch_start=naive_epoch)


def test_candidate_count_boundary_exactly_300_accepted(fixed_utc_epoch):
    """Grid producing exactly 300 candidates is accepted without truncation."""
    # 1 altitude * 1 inclination * 300 delays = 300 candidates
    candidates = generate_candidates(
        epoch_start=fixed_utc_epoch,
        altitude_min_km=500.0,
        altitude_max_km=500.0,
        altitude_step_km=25.0,
        inclination_min_deg=97.0,
        inclination_max_deg=97.0,
        inclination_step_deg=0.5,
        delay_min_minutes=0.0,
        delay_max_minutes=299.0,
        delay_step_minutes=1.0,
        max_candidates=300,
    )
    assert len(candidates) == 300
    assert candidates[0].generated_index == 0
    assert candidates[-1].generated_index == 299


def test_candidate_count_boundary_301_rejected(fixed_utc_epoch):
    """Grid producing 301 candidates is explicitly rejected with CandidateGenerationError."""
    # 1 altitude * 1 inclination * 301 delays = 301 candidates
    with pytest.raises(CandidateGenerationError) as exc_info:
        generate_candidates(
            epoch_start=fixed_utc_epoch,
            altitude_min_km=500.0,
            altitude_max_km=500.0,
            altitude_step_km=25.0,
            inclination_min_deg=97.0,
            inclination_max_deg=97.0,
            inclination_step_deg=0.5,
            delay_min_minutes=0.0,
            delay_max_minutes=300.0,
            delay_step_minutes=1.0,
            max_candidates=300,
        )

    msg = str(exc_info.value)
    assert "requested grid produces 301 candidates" in msg
    assert "maximum is 300" in msg


def test_repeated_generation_identical_and_stable(fixed_utc_epoch):
    """Repeated generation produces identical, deterministic candidate lists."""
    run1 = generate_candidates(epoch_start=fixed_utc_epoch)
    run2 = generate_candidates(epoch_start=fixed_utc_epoch)

    assert len(run1) == len(run2) == 195
    for c1, c2 in zip(run1, run2):
        assert c1.candidate_id == c2.candidate_id
        assert c1.altitude_km == c2.altitude_km
        assert c1.inclination_deg == c2.inclination_deg
        assert c1.raan_deg == c2.raan_deg
        assert c1.u0_deg == c2.u0_deg
        assert c1.deployment_delay_minutes == c2.deployment_delay_minutes
        assert c1.deployment_epoch == c2.deployment_epoch
        assert c1.generated_index == c2.generated_index


def test_candidate_orbit_immutability(fixed_utc_epoch):
    """CandidateOrbit is a frozen dataclass and cannot be mutated."""
    candidates = generate_candidates(epoch_start=fixed_utc_epoch)
    c = candidates[0]
    with pytest.raises(FrozenInstanceError):
        c.altitude_km = 600.0  # type: ignore


def test_candidate_to_model_data_helper(fixed_utc_epoch):
    """Mapping helper converts CandidateOrbit to dict for ORM persistence without DB side-effects."""
    candidates = generate_candidates(epoch_start=fixed_utc_epoch)
    c = candidates[1]  # 500 km, 97.0 deg, 60 min delay
    data = candidate_to_model_data(c, run_id="run-uuid-1234")

    assert data["run_id"] == "run-uuid-1234"
    assert data["altitude_km"] == c.altitude_km
    assert data["inclination_deg"] == c.inclination_deg
    assert data["raan_deg"] == c.raan_deg
    assert data["u0_deg"] == c.u0_deg
    assert data["deployment_delay_minutes"] == c.deployment_delay_minutes
    assert data["predicted_raan_deg"] == c.raan_deg
