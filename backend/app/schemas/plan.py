"""Pydantic schemas for Mission Plans (Phase P13).

The original D-DATO specification is authoritative.
"""

from datetime import datetime, timezone
import math
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import DataSourceType, settings
from app.schemas.run import RunStatusResponse
from app.utils.time import now_utc


class PlanCreateRequest(BaseModel):
    """Request schema for creating a mission plan and submitting an asynchronous screening run."""

    epoch_start: Optional[datetime] = Field(
        default_factory=now_utc,
        description="Deployment planning epoch start in UTC",
    )
    altitude_min_km: float = Field(
        default=settings.ALTITUDE_MIN_KM,
        gt=0.0,
        description="Minimum search altitude (km)",
    )
    altitude_max_km: float = Field(
        default=settings.ALTITUDE_MAX_KM,
        gt=0.0,
        description="Maximum search altitude (km)",
    )
    altitude_step_km: float = Field(
        default=settings.ALTITUDE_STEP_KM,
        gt=0.0,
        description="Altitude grid step size (km)",
    )
    inclination_min_deg: float = Field(
        default=settings.INCLINATION_MIN_DEG,
        ge=0.0,
        le=180.0,
        description="Minimum orbital inclination (degrees)",
    )
    inclination_max_deg: float = Field(
        default=settings.INCLINATION_MAX_DEG,
        ge=0.0,
        le=180.0,
        description="Maximum orbital inclination (degrees)",
    )
    inclination_step_deg: float = Field(
        default=settings.INCLINATION_STEP_DEG,
        gt=0.0,
        description="Inclination grid step size (degrees)",
    )
    raan_deg: float = Field(
        default=settings.RAAN_DEG,
        ge=0.0,
        le=360.0,
        description="Base Right Ascension of Ascending Node (degrees)",
    )
    u0_deg: float = Field(
        default=settings.U0_DEG,
        ge=0.0,
        le=360.0,
        description="Initial argument of latitude (degrees)",
    )
    delay_min_minutes: float = Field(
        default=settings.DELAY_MIN_MINUTES,
        ge=0.0,
        description="Minimum deployment delay (minutes)",
    )
    delay_max_minutes: float = Field(
        default=settings.DELAY_MAX_MINUTES,
        ge=0.0,
        description="Maximum deployment delay (minutes)",
    )
    delay_step_minutes: float = Field(
        default=settings.DELAY_STEP_MINUTES,
        gt=0.0,
        description="Deployment delay step size (minutes)",
    )
    raan_delay_coupling_deg_per_min: float = Field(
        default=settings.RAAN_DELAY_COUPLING_DEG_PER_MIN,
        description="RAAN delay coupling constant (deg/min)",
    )
    screening_days: int = Field(
        default=settings.SCREENING_DAYS,
        ge=settings.SCREENING_MIN_DAYS,
        le=settings.SCREENING_MAX_DAYS,
        description="Screening duration in days (1 to 7)",
    )
    reference_altitude_km: float = Field(
        default=settings.REFERENCE_ALTITUDE_KM,
        gt=0.0,
        description="Reference circular orbit altitude (km)",
    )
    reference_inclination_deg: float = Field(
        default=settings.REFERENCE_INCLINATION_DEG,
        ge=0.0,
        le=180.0,
        description="Reference orbital inclination (degrees)",
    )
    dv_budget_m_s: float = Field(
        default=settings.DV_BUDGET_M_S,
        ge=0.0,
        description="Total delta-v budget (m/s)",
    )
    spacecraft_mass_kg: float = Field(
        default=settings.SPACECRAFT_MASS_KG,
        gt=0.0,
        description="Spacecraft wet/dry mass (kg)",
    )
    isp_seconds: float = Field(
        default=settings.ISP_SECONDS,
        gt=0.0,
        description="Propulsion specific impulse (seconds)",
    )
    fuel_weight: float = Field(
        default=settings.FUEL_WEIGHT,
        ge=0.0,
        le=1.0,
        description="Multi-objective fuel weight [0, 1]",
    )
    risk_weight: float = Field(
        default=settings.RISK_WEIGHT,
        ge=0.0,
        le=1.0,
        description="Multi-objective risk weight [0, 1]",
    )
    data_source: DataSourceType = Field(
        default=settings.DATA_SOURCE,
        description="Catalog data source ('celestrak' or 'spacetrack')",
    )
    demo_mode: bool = Field(
        default=True,
        description="Enable offline demo mode using local fixture catalogs",
    )

    @model_validator(mode="after")
    def validate_plan_envelope(self) -> "PlanCreateRequest":
        """Validate logical parameter consistency, bounds, and candidate limits."""
        if self.altitude_min_km > self.altitude_max_km:
            raise ValueError(
                f"altitude_min_km ({self.altitude_min_km}) cannot exceed altitude_max_km ({self.altitude_max_km})."
            )
        if self.inclination_min_deg > self.inclination_max_deg:
            raise ValueError(
                f"inclination_min_deg ({self.inclination_min_deg}) cannot exceed inclination_max_deg ({self.inclination_max_deg})."
            )
        if self.delay_min_minutes > self.delay_max_minutes:
            raise ValueError(
                f"delay_min_minutes ({self.delay_min_minutes}) cannot exceed delay_max_minutes ({self.delay_max_minutes})."
            )
        if not math.isclose(self.fuel_weight + self.risk_weight, 1.0, abs_tol=1e-4):
            raise ValueError(
                f"fuel_weight ({self.fuel_weight}) and risk_weight ({self.risk_weight}) must sum to 1.0."
            )

        # Estimate candidate grid size to reject oversized search grids
        n_alt = math.floor((self.altitude_max_km - self.altitude_min_km) / self.altitude_step_km + 1e-9) + 1
        n_inc = math.floor((self.inclination_max_deg - self.inclination_min_deg) / self.inclination_step_deg + 1e-9) + 1
        n_delay = math.floor((self.delay_max_minutes - self.delay_min_minutes) / self.delay_step_minutes + 1e-9) + 1
        total_candidates = n_alt * n_inc * n_delay

        if total_candidates <= 0:
            raise ValueError("Candidate configuration produces 0 candidates.")
        if total_candidates > settings.MAX_CANDIDATES:
            raise ValueError(
                f"Candidate configuration produces {total_candidates} candidates, exceeding maximum limit of {settings.MAX_CANDIDATES}."
            )

        # Normalize naive timestamp to UTC
        if self.epoch_start is not None and self.epoch_start.tzinfo is None:
            object.__setattr__(self, "epoch_start", self.epoch_start.replace(tzinfo=timezone.utc))

        return self


class PlanRunAcceptedResponse(BaseModel):
    """Response returned upon successful acceptance and queuing of a planning run (HTTP 202)."""

    plan_id: str = Field(..., description="Unique mission plan identifier")
    run_id: str = Field(..., description="Unique screening run identifier")
    status: str = Field(default="queued", description="Initial lifecycle state ('queued' or 'running')")
    message: str = Field(default="Screening run queued for execution", description="Informational message")
    created_at: datetime = Field(..., description="Creation epoch (UTC)")


class PlanResponse(BaseModel):
    """Full detail response schema for a persisted mission plan."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: str = Field(..., description="Unique mission plan identifier")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")
    epoch_start: datetime = Field(..., description="Deployment planning epoch start (UTC)")
    altitude_min_km: float = Field(..., description="Minimum search altitude (km)")
    altitude_max_km: float = Field(..., description="Maximum search altitude (km)")
    altitude_step_km: float = Field(..., description="Altitude step size (km)")
    inclination_min_deg: float = Field(..., description="Minimum inclination (deg)")
    inclination_max_deg: float = Field(..., description="Maximum inclination (deg)")
    inclination_step_deg: float = Field(..., description="Inclination step size (deg)")
    raan_deg: float = Field(..., description="Base RAAN (deg)")
    u0_deg: float = Field(..., description="Initial argument of latitude (deg)")
    delay_min_minutes: float = Field(..., description="Minimum deployment delay (minutes)")
    delay_max_minutes: float = Field(..., description="Maximum deployment delay (minutes)")
    delay_step_minutes: float = Field(..., description="Deployment delay step size (minutes)")
    raan_delay_coupling_deg_per_min: float = Field(..., description="RAAN delay coupling constant (deg/min)")
    screening_days: int = Field(..., description="Screening duration in days")
    reference_altitude_km: float = Field(..., description="Reference altitude (km)")
    reference_inclination_deg: float = Field(..., description="Reference inclination (deg)")
    dv_budget_m_s: float = Field(..., description="Delta-v budget (m/s)")
    spacecraft_mass_kg: float = Field(..., description="Spacecraft mass (kg)")
    isp_seconds: float = Field(..., description="Specific impulse (seconds)")
    fuel_weight: float = Field(..., description="Fuel weighting [0, 1]")
    risk_weight: float = Field(..., description="Risk weighting [0, 1]")
    data_source: str = Field(..., description="Catalog data source")
    demo_mode: bool = Field(..., description="Offline demo mode flag")


class PlanRunListResponse(BaseModel):
    """Response schema listing all screening runs associated with a mission plan."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: str = Field(..., description="Mission plan identifier")
    total: int = Field(..., description="Total runs associated with plan")
    runs: List[RunStatusResponse] = Field(default_factory=list, description="Screening runs ordered newest first")


# Legacy compatibility models
class MissionPlanBase(BaseModel):
    name: str = Field(..., description="Descriptive mission plan name")
    target_altitude_km: float = Field(..., ge=100.0, le=2000.0, description="Target circular orbit altitude (km)")
    target_inclination_deg: float = Field(..., ge=0.0, le=180.0, description="Target orbital inclination (degrees)")
    target_eccentricity: float = Field(default=0.0, ge=0.0, le=0.2, description="Target orbital eccentricity")
    target_raan_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0, description="Right Ascension of Ascending Node")
    satellite_mass_kg: float = Field(..., gt=0.0, description="Dry or wet mass of payload (kg)")
    propulsion_isp_s: Optional[float] = Field(default=220.0, gt=0.0, description="Propulsion specific impulse (seconds)")
    window_start: datetime = Field(..., description="Deployment window start epoch")
    window_end: datetime = Field(..., description="Deployment window end epoch")


class MissionPlanCreate(MissionPlanBase):
    pass


class MissionPlanUpdate(BaseModel):
    name: Optional[str] = None
    target_altitude_km: Optional[float] = None
    target_inclination_deg: Optional[float] = None
    satellite_mass_kg: Optional[float] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


class MissionPlanResponse(MissionPlanBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
