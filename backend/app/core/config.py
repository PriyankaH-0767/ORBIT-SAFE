"""Application settings and environment configuration using Pydantic Settings.

The original D-DATO project specification is authoritative.
Configuration rules, planning defaults, and validation constraints
defined here govern all downstream services and algorithms.
"""

from functools import lru_cache
import math
from typing import Literal, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DataSourceType = Literal["celestrak", "spacetrack"]


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables and .env file."""

    # Core Application Settings (Phase P1)
    APP_NAME: str = "D-DATO"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    DEMO_MODE: bool = True

    # Database & Routing
    DATABASE_URL: str = "sqlite:///./d_dato.db"
    API_V1_PREFIX: str = "/api/v1"

    # Planning Defaults (Phase P2)
    EPOCH_START_OFFSET_DAYS: int = 1

    ALTITUDE_MIN_KM: float = 500.0
    ALTITUDE_MAX_KM: float = 600.0
    ALTITUDE_STEP_KM: float = 25.0

    INCLINATION_MIN_DEG: float = 97.0
    INCLINATION_MAX_DEG: float = 98.0
    INCLINATION_STEP_DEG: float = 0.5

    RAAN_DEG: float = 0.0
    U0_DEG: float = 0.0

    DELAY_MIN_MINUTES: float = 0.0
    DELAY_MAX_MINUTES: float = 720.0
    DELAY_STEP_MINUTES: float = 60.0

    RAAN_DELAY_COUPLING_DEG_PER_MIN: float = 0.25068

    MAX_CANDIDATES: int = 300

    SCREENING_DAYS: int = 3
    SCREENING_MIN_DAYS: int = 1
    SCREENING_MAX_DAYS: int = 7

    # Conjunction Screening & TCA Refinement (Phase P8)
    SCREENING_COARSE_STEP_SECONDS: float = 30.0
    SCREENING_COARSE_THRESHOLD_KM: float = 260.0
    SCREENING_EVENT_THRESHOLD_KM: float = 25.0
    SCREENING_TCA_XTOL_SECONDS: float = 0.01
    SCREENING_TCA_MAX_ITERATIONS: int = 100
    SCREENING_MAX_EVENTS_PER_CANDIDATE: int = 1000
    SCREENING_DEBRIS_BATCH_SIZE: int = 256
    SCREENING_TIME_CHUNK_SECONDS: int = 3600
    SCREENING_PREFILTER_ALTITUDE_MARGIN_KM: float = 300.0
    SCREENING_INCLUDE_UNKNOWN_OBJECTS: bool = True

    # Screening Risk Scoring (Phase P9 Fallback Heuristic)
    RISK_PROXIMITY_WEIGHT: float = 0.8
    RISK_EVENT_COUNT_WEIGHT: float = 0.2
    RISK_EVENT_SATURATION_COUNT: int = 5
    RISK_DATA_AGE_ELEVATED_SECONDS: float = 259200.0  # 3 days

    REFERENCE_ALTITUDE_KM: float = 550.0
    REFERENCE_INCLINATION_DEG: float = 97.5

    DV_BUDGET_M_S: float = 100.0

    SPACECRAFT_MASS_KG: float = 3.0
    ISP_SECONDS: float = 60.0

    FUEL_WEIGHT: float = 0.4
    RISK_WEIGHT: float = 0.6

    DATA_SOURCE: DataSourceType = "celestrak"

    # Data Etiquette & Ingestion Intervals (hours)
    CELESTRAK_MIN_FETCH_INTERVAL_HOURS: float = 2.0
    SPACETRACK_MIN_FETCH_INTERVAL_HOURS: float = 1.0

    # Asynchronous Execution & Worker (Phase P12)
    WORKER_MAX_CONCURRENCY: int = 1

    # External Validation & SOCRATES Settings (Phase P16)
    SOCRATES_ENABLED: bool = False
    SOCRATES_BASE_URL: Optional[str] = None
    SOCRATES_TIMEOUT_SECONDS: float = 10.0
    VALIDATION_DEFAULT_TCA_TOLERANCE_SECONDS: float = 300.0
    VALIDATION_DEFAULT_MISS_DISTANCE_TOLERANCE_KM: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        """Validate physical and operational consistency of configuration parameters."""
        # 1. Altitude bounds and steps
        if self.ALTITUDE_MIN_KM <= 0 or self.ALTITUDE_MAX_KM <= 0:
            raise ValueError(
                f"Altitude limits must be positive numbers (got min={self.ALTITUDE_MIN_KM}, max={self.ALTITUDE_MAX_KM})."
            )
        if self.ALTITUDE_MIN_KM > self.ALTITUDE_MAX_KM:
            raise ValueError(
                f"ALTITUDE_MIN_KM ({self.ALTITUDE_MIN_KM}) cannot exceed ALTITUDE_MAX_KM ({self.ALTITUDE_MAX_KM})."
            )
        if self.ALTITUDE_STEP_KM <= 0:
            raise ValueError(f"ALTITUDE_STEP_KM ({self.ALTITUDE_STEP_KM}) must be > 0.")
        if self.REFERENCE_ALTITUDE_KM <= 0:
            raise ValueError(
                f"REFERENCE_ALTITUDE_KM ({self.REFERENCE_ALTITUDE_KM}) must be a positive number."
            )

        # 2. Inclination bounds and steps (0 to 180 degrees)
        for name, val in [
            ("INCLINATION_MIN_DEG", self.INCLINATION_MIN_DEG),
            ("INCLINATION_MAX_DEG", self.INCLINATION_MAX_DEG),
            ("REFERENCE_INCLINATION_DEG", self.REFERENCE_INCLINATION_DEG),
        ]:
            if not (0.0 <= val <= 180.0):
                raise ValueError(f"{name} ({val}) must be between 0.0 and 180.0 degrees.")
        if self.INCLINATION_MIN_DEG > self.INCLINATION_MAX_DEG:
            raise ValueError(
                f"INCLINATION_MIN_DEG ({self.INCLINATION_MIN_DEG}) cannot exceed INCLINATION_MAX_DEG ({self.INCLINATION_MAX_DEG})."
            )
        if self.INCLINATION_STEP_DEG <= 0:
            raise ValueError(f"INCLINATION_STEP_DEG ({self.INCLINATION_STEP_DEG}) must be > 0.")

        # 3. Delay bounds and steps
        if self.DELAY_MIN_MINUTES < 0 or self.DELAY_MAX_MINUTES < 0:
            raise ValueError("Delay values (DELAY_MIN_MINUTES, DELAY_MAX_MINUTES) must be non-negative.")
        if self.DELAY_MIN_MINUTES > self.DELAY_MAX_MINUTES:
            raise ValueError(
                f"DELAY_MIN_MINUTES ({self.DELAY_MIN_MINUTES}) cannot exceed DELAY_MAX_MINUTES ({self.DELAY_MAX_MINUTES})."
            )
        if self.DELAY_STEP_MINUTES <= 0:
            raise ValueError(f"DELAY_STEP_MINUTES ({self.DELAY_STEP_MINUTES}) must be > 0.")

        # 4. RAAN delay coupling & candidate limits
        if not math.isfinite(self.RAAN_DELAY_COUPLING_DEG_PER_MIN):
            raise ValueError("RAAN_DELAY_COUPLING_DEG_PER_MIN must be a finite numeric value.")
        if self.MAX_CANDIDATES <= 0:
            raise ValueError(f"MAX_CANDIDATES ({self.MAX_CANDIDATES}) must be > 0.")

        # 5. Screening days bounds
        if self.SCREENING_MIN_DAYS <= 0:
            raise ValueError(f"SCREENING_MIN_DAYS ({self.SCREENING_MIN_DAYS}) must be > 0.")
        if self.SCREENING_MIN_DAYS > self.SCREENING_MAX_DAYS:
            raise ValueError(
                f"SCREENING_MIN_DAYS ({self.SCREENING_MIN_DAYS}) cannot exceed SCREENING_MAX_DAYS ({self.SCREENING_MAX_DAYS})."
            )
        if not (self.SCREENING_MIN_DAYS <= self.SCREENING_DAYS <= self.SCREENING_MAX_DAYS):
            raise ValueError(
                f"SCREENING_DAYS ({self.SCREENING_DAYS}) must be between "
                f"SCREENING_MIN_DAYS ({self.SCREENING_MIN_DAYS}) and SCREENING_MAX_DAYS ({self.SCREENING_MAX_DAYS})."
            )

        # 5b. Conjunction Screening & TCA Refinement (Phase P8)
        if self.SCREENING_COARSE_STEP_SECONDS <= 0:
            raise ValueError(f"SCREENING_COARSE_STEP_SECONDS ({self.SCREENING_COARSE_STEP_SECONDS}) must be > 0.")
        if self.SCREENING_EVENT_THRESHOLD_KM <= 0:
            raise ValueError(f"SCREENING_EVENT_THRESHOLD_KM ({self.SCREENING_EVENT_THRESHOLD_KM}) must be > 0.")
        if self.SCREENING_COARSE_THRESHOLD_KM <= self.SCREENING_EVENT_THRESHOLD_KM:
            raise ValueError(
                f"SCREENING_COARSE_THRESHOLD_KM ({self.SCREENING_COARSE_THRESHOLD_KM}) must be strictly greater than "
                f"SCREENING_EVENT_THRESHOLD_KM ({self.SCREENING_EVENT_THRESHOLD_KM})."
            )
        if self.SCREENING_TCA_XTOL_SECONDS <= 0:
            raise ValueError(f"SCREENING_TCA_XTOL_SECONDS ({self.SCREENING_TCA_XTOL_SECONDS}) must be > 0.")
        if self.SCREENING_TCA_MAX_ITERATIONS <= 0:
            raise ValueError(f"SCREENING_TCA_MAX_ITERATIONS ({self.SCREENING_TCA_MAX_ITERATIONS}) must be > 0.")
        if self.SCREENING_MAX_EVENTS_PER_CANDIDATE <= 0:
            raise ValueError(f"SCREENING_MAX_EVENTS_PER_CANDIDATE ({self.SCREENING_MAX_EVENTS_PER_CANDIDATE}) must be > 0.")
        if self.SCREENING_DEBRIS_BATCH_SIZE <= 0:
            raise ValueError(f"SCREENING_DEBRIS_BATCH_SIZE ({self.SCREENING_DEBRIS_BATCH_SIZE}) must be > 0.")
        if self.SCREENING_TIME_CHUNK_SECONDS <= 0:
            raise ValueError(f"SCREENING_TIME_CHUNK_SECONDS ({self.SCREENING_TIME_CHUNK_SECONDS}) must be > 0.")
        if self.SCREENING_PREFILTER_ALTITUDE_MARGIN_KM <= 0:
            raise ValueError(f"SCREENING_PREFILTER_ALTITUDE_MARGIN_KM ({self.SCREENING_PREFILTER_ALTITUDE_MARGIN_KM}) must be > 0.")

        # 6. Spacecraft & Propulsion
        if self.SPACECRAFT_MASS_KG <= 0:
            raise ValueError(f"SPACECRAFT_MASS_KG ({self.SPACECRAFT_MASS_KG}) must be > 0.")
        if self.ISP_SECONDS <= 0:
            raise ValueError(f"ISP_SECONDS ({self.ISP_SECONDS}) must be > 0.")
        if self.DV_BUDGET_M_S < 0:
            raise ValueError(f"DV_BUDGET_M_S ({self.DV_BUDGET_M_S}) must be >= 0.")

        # 7. Multi-objective weights
        if self.FUEL_WEIGHT < 0 or self.RISK_WEIGHT < 0:
            raise ValueError("FUEL_WEIGHT and RISK_WEIGHT must be non-negative (>= 0).")
        if not math.isclose(self.FUEL_WEIGHT + self.RISK_WEIGHT, 1.0, abs_tol=1e-6):
            raise ValueError(
                f"FUEL_WEIGHT ({self.FUEL_WEIGHT}) and RISK_WEIGHT ({self.RISK_WEIGHT}) "
                f"must sum to 1.0 (actual sum: {self.FUEL_WEIGHT + self.RISK_WEIGHT:.6f})."
            )

        # 8. Ingestion etiquette fetch intervals
        if self.CELESTRAK_MIN_FETCH_INTERVAL_HOURS <= 0:
            raise ValueError("CELESTRAK_MIN_FETCH_INTERVAL_HOURS must be > 0.")
        if self.SPACETRACK_MIN_FETCH_INTERVAL_HOURS <= 0:
            raise ValueError("SPACETRACK_MIN_FETCH_INTERVAL_HOURS must be > 0.")

        # 9. Risk scoring parameters (Phase P9)
        if self.RISK_PROXIMITY_WEIGHT < 0.0 or self.RISK_EVENT_COUNT_WEIGHT < 0.0:
            raise ValueError("RISK_PROXIMITY_WEIGHT and RISK_EVENT_COUNT_WEIGHT must be non-negative (>= 0).")
        if not math.isclose(self.RISK_PROXIMITY_WEIGHT + self.RISK_EVENT_COUNT_WEIGHT, 1.0, abs_tol=1e-6):
            raise ValueError(
                f"RISK_PROXIMITY_WEIGHT ({self.RISK_PROXIMITY_WEIGHT}) and "
                f"RISK_EVENT_COUNT_WEIGHT ({self.RISK_EVENT_COUNT_WEIGHT}) must sum to 1.0."
            )
        if self.RISK_EVENT_SATURATION_COUNT <= 0:
            raise ValueError(f"RISK_EVENT_SATURATION_COUNT ({self.RISK_EVENT_SATURATION_COUNT}) must be > 0.")
        if self.RISK_DATA_AGE_ELEVATED_SECONDS <= 0:
            raise ValueError(f"RISK_DATA_AGE_ELEVATED_SECONDS ({self.RISK_DATA_AGE_ELEVATED_SECONDS}) must be > 0.")

        # 10. Worker concurrency (Phase P12)
        if self.WORKER_MAX_CONCURRENCY < 1:
            raise ValueError(f"WORKER_MAX_CONCURRENCY must be at least 1 (got {self.WORKER_MAX_CONCURRENCY}).")

        # 11. External validation parameters (Phase P16)
        if self.SOCRATES_TIMEOUT_SECONDS <= 0:
            raise ValueError(f"SOCRATES_TIMEOUT_SECONDS must be > 0 (got {self.SOCRATES_TIMEOUT_SECONDS}).")
        if self.VALIDATION_DEFAULT_TCA_TOLERANCE_SECONDS <= 0:
            raise ValueError(
                f"VALIDATION_DEFAULT_TCA_TOLERANCE_SECONDS must be > 0 (got {self.VALIDATION_DEFAULT_TCA_TOLERANCE_SECONDS})."
            )
        if self.VALIDATION_DEFAULT_MISS_DISTANCE_TOLERANCE_KM <= 0:
            raise ValueError(
                f"VALIDATION_DEFAULT_MISS_DISTANCE_TOLERANCE_KM must be > 0 (got {self.VALIDATION_DEFAULT_MISS_DISTANCE_TOLERANCE_KM})."
            )

        return self

    # Convenience properties
    @property
    def app_name(self) -> str:
        return self.APP_NAME

    @property
    def app_version(self) -> str:
        return self.APP_VERSION

    @property
    def environment(self) -> str:
        return self.ENVIRONMENT

    @property
    def debug(self) -> bool:
        return self.DEBUG

    @property
    def log_level(self) -> str:
        return self.LOG_LEVEL


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()


settings = get_settings()
