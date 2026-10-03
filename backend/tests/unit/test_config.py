"""Unit tests for configuration system, planning defaults, and validation rules."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_default_settings_p1():
    """Verify default configuration attributes from Phase P1 are preserved."""
    cfg = Settings()
    assert cfg.APP_NAME == "D-DATO"
    assert cfg.APP_VERSION == "0.1.0"
    assert cfg.ENVIRONMENT == "development"
    assert cfg.DEBUG is True
    assert cfg.HOST == "127.0.0.1"
    assert cfg.PORT == 8000
    assert cfg.LOG_LEVEL == "INFO"
    assert cfg.DEMO_MODE is True
    assert cfg.DATABASE_URL == "sqlite:///./d_dato.db"


def test_default_settings_p2_planning_defaults():
    """Verify authoritative Phase P2 planning defaults from D-DATO specification."""
    cfg = Settings()

    # Epoch start offset
    assert cfg.EPOCH_START_OFFSET_DAYS == 1

    # Altitude grid
    assert cfg.ALTITUDE_MIN_KM == 500.0
    assert cfg.ALTITUDE_MAX_KM == 600.0
    assert cfg.ALTITUDE_STEP_KM == 25.0
    assert cfg.REFERENCE_ALTITUDE_KM == 550.0

    # Inclination grid
    assert cfg.INCLINATION_MIN_DEG == 97.0
    assert cfg.INCLINATION_MAX_DEG == 98.0
    assert cfg.INCLINATION_STEP_DEG == 0.5
    assert cfg.REFERENCE_INCLINATION_DEG == 97.5

    # Angles & delay
    assert cfg.RAAN_DEG == 0.0
    assert cfg.U0_DEG == 0.0
    assert cfg.DELAY_MIN_MINUTES == 0.0
    assert cfg.DELAY_MAX_MINUTES == 720.0
    assert cfg.DELAY_STEP_MINUTES == 60.0
    assert cfg.RAAN_DELAY_COUPLING_DEG_PER_MIN == 0.25068

    # Screening duration bounds
    assert cfg.SCREENING_DAYS == 3
    assert cfg.SCREENING_MIN_DAYS == 1
    assert cfg.SCREENING_MAX_DAYS == 7

    # Propulsion and spacecraft parameters
    assert cfg.DV_BUDGET_M_S == 100.0
    assert cfg.SPACECRAFT_MASS_KG == 3.0
    assert cfg.ISP_SECONDS == 60.0

    # Multi-objective weights
    assert cfg.FUEL_WEIGHT == 0.4
    assert cfg.RISK_WEIGHT == 0.6
    assert cfg.FUEL_WEIGHT + cfg.RISK_WEIGHT == 1.0

    # Data source and etiquette
    assert cfg.DATA_SOURCE == "celestrak"
    assert cfg.CELESTRAK_MIN_FETCH_INTERVAL_HOURS == 2.0
    assert cfg.SPACETRACK_MIN_FETCH_INTERVAL_HOURS == 1.0


def test_settings_override():
    """Verify settings can be overridden with custom valid parameters."""
    cfg = Settings(
        APP_NAME="D-DATO-Custom",
        PORT=9000,
        DEBUG=False,
        ENVIRONMENT="production",
        ALTITUDE_MIN_KM=450.0,
        ALTITUDE_MAX_KM=550.0,
        FUEL_WEIGHT=0.5,
        RISK_WEIGHT=0.5,
        DATA_SOURCE="spacetrack",
    )
    assert cfg.APP_NAME == "D-DATO-Custom"
    assert cfg.PORT == 9000
    assert cfg.DEBUG is False
    assert cfg.ENVIRONMENT == "production"
    assert cfg.ALTITUDE_MIN_KM == 450.0
    assert cfg.DATA_SOURCE == "spacetrack"


def test_cached_singleton():
    """Verify get_settings returns the singleton cached settings instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_altitude_validation():
    """Verify altitude validation rules (positive values, min <= max, step > 0)."""
    # min > max
    with pytest.raises(ValidationError):
        Settings(ALTITUDE_MIN_KM=700.0, ALTITUDE_MAX_KM=600.0)

    # negative altitude
    with pytest.raises(ValidationError):
        Settings(ALTITUDE_MIN_KM=-100.0)

    # non-positive step
    with pytest.raises(ValidationError):
        Settings(ALTITUDE_STEP_KM=0.0)

    # non-positive reference altitude
    with pytest.raises(ValidationError):
        Settings(REFERENCE_ALTITUDE_KM=0.0)


def test_inclination_validation():
    """Verify inclination validation rules (0..180 range, min <= max, step > 0)."""
    # min > max
    with pytest.raises(ValidationError):
        Settings(INCLINATION_MIN_DEG=100.0, INCLINATION_MAX_DEG=90.0)

    # out of bounds (> 180 or < 0)
    with pytest.raises(ValidationError):
        Settings(INCLINATION_MAX_DEG=185.0)

    with pytest.raises(ValidationError):
        Settings(INCLINATION_MIN_DEG=-5.0)

    # non-positive step
    with pytest.raises(ValidationError):
        Settings(INCLINATION_STEP_DEG=0.0)


def test_delay_and_coupling_validation():
    """Verify deployment delay and RAAN coupling validation."""
    # min > max
    with pytest.raises(ValidationError):
        Settings(DELAY_MIN_MINUTES=800.0, DELAY_MAX_MINUTES=720.0)

    # negative delay
    with pytest.raises(ValidationError):
        Settings(DELAY_MIN_MINUTES=-10.0)

    # step <= 0
    with pytest.raises(ValidationError):
        Settings(DELAY_STEP_MINUTES=0.0)

    # non-finite coupling
    with pytest.raises(ValidationError):
        Settings(RAAN_DELAY_COUPLING_DEG_PER_MIN=float("nan"))


def test_screening_days_validation():
    """Verify screening duration bounds validation."""
    # days < min
    with pytest.raises(ValidationError):
        Settings(SCREENING_DAYS=0, SCREENING_MIN_DAYS=1, SCREENING_MAX_DAYS=7)

    # days > max
    with pytest.raises(ValidationError):
        Settings(SCREENING_DAYS=10, SCREENING_MIN_DAYS=1, SCREENING_MAX_DAYS=7)

    # min > max
    with pytest.raises(ValidationError):
        Settings(SCREENING_MIN_DAYS=10, SCREENING_MAX_DAYS=5)


def test_spacecraft_and_propulsion_validation():
    """Verify spacecraft mass, Isp, and delta-v budget validation."""
    with pytest.raises(ValidationError):
        Settings(SPACECRAFT_MASS_KG=0.0)

    with pytest.raises(ValidationError):
        Settings(ISP_SECONDS=0.0)

    with pytest.raises(ValidationError):
        Settings(DV_BUDGET_M_S=-1.0)


def test_weights_validation():
    """Verify fuel and risk weight validation rules."""
    # Valid custom weights summing to 1.0
    cfg = Settings(FUEL_WEIGHT=0.2, RISK_WEIGHT=0.8)
    assert cfg.FUEL_WEIGHT == 0.2
    assert cfg.RISK_WEIGHT == 0.8

    # Weights not summing to 1.0
    with pytest.raises(ValidationError):
        Settings(FUEL_WEIGHT=0.5, RISK_WEIGHT=0.6)

    # Negative weight
    with pytest.raises(ValidationError):
        Settings(FUEL_WEIGHT=-0.1, RISK_WEIGHT=1.1)


def test_data_source_and_fetch_interval_validation():
    """Verify data source literals and etiquette fetch interval rules."""
    # Valid source
    cfg_spacetrack = Settings(DATA_SOURCE="spacetrack")
    assert cfg_spacetrack.DATA_SOURCE == "spacetrack"

    # Invalid source
    with pytest.raises(ValidationError):
        Settings(DATA_SOURCE="unsupported_source")

    # Non-positive fetch intervals
    with pytest.raises(ValidationError):
        Settings(CELESTRAK_MIN_FETCH_INTERVAL_HOURS=0.0)

    with pytest.raises(ValidationError):
        Settings(SPACETRACK_MIN_FETCH_INTERVAL_HOURS=-1.0)
