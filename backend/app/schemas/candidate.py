"""Pydantic schemas for Candidate Deployment Orbits.

The original D-DATO project specification is authoritative.
Semantics:
- `raan_deg`: The candidate's actual derived RAAN after applying delay coupling.
- `base_raan_deg`: The reference plan RAAN before delay coupling.
- `predicted_raan_deg`: Explicit alias/compatibility field equal to `raan_deg`.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CandidateOrbitSchema(BaseModel):
    """Pydantic representation of a domain CandidateOrbit configuration."""
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str = Field(..., description="Deterministic candidate identifier")
    altitude_km: float = Field(..., description="Circular orbit altitude in km")
    inclination_deg: float = Field(..., description="Orbital inclination in degrees")
    raan_deg: float = Field(..., description="Derived Right Ascension of Ascending Node in degrees")
    u0_deg: float = Field(default=0.0, description="Initial argument of latitude in degrees")
    deployment_delay_minutes: float = Field(..., description="Deployment delay from epoch start in minutes")
    base_raan_deg: float = Field(..., description="Reference plan RAAN before delay coupling in degrees")
    raan_delay_coupling_deg_per_min: float = Field(..., description="RAAN delay coupling constant in deg/min")
    epoch_start: datetime = Field(..., description="Base planning epoch in UTC")
    deployment_epoch: datetime = Field(..., description="Deployment epoch in UTC")
    generated_index: int = Field(default=0, description="Sequential generation index")
    predicted_raan_deg: Optional[float] = Field(default=None, description="Alias for derived raan_deg")


class CandidateOrbitResponse(BaseModel):
    """Database-backed Candidate response schema for evaluated candidates."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    deployment_epoch: datetime
    altitude_km: Optional[float] = None
    semi_major_axis_km: Optional[float] = None
    eccentricity: Optional[float] = 0.0
    inclination_deg: float
    raan_deg: float
    u0_deg: Optional[float] = 0.0
    deployment_delay_minutes: Optional[float] = 0.0
    base_raan_deg: Optional[float] = None
    predicted_raan_deg: Optional[float] = None
    candidate_id: Optional[str] = None
    delta_v_m_s: Optional[float] = None
    fuel_mass_kg: Optional[float] = None
    propellant_mass_kg: Optional[float] = None
    fuel_fraction: Optional[float] = None
    within_dv_budget: Optional[bool] = None
    risk_score: Optional[float] = None
    proximity_score: Optional[float] = None
    event_count_score: Optional[float] = None
    accepted_event_count: Optional[int] = None
    minimum_miss_distance_km: Optional[float] = None
    minimum_relative_velocity_km_s: Optional[float] = None
    maximum_relative_velocity_km_s: Optional[float] = None
    uncertainty_level: Optional[str] = None
    scoring_method: Optional[str] = None
    composite_rank: Optional[int] = None
    rank: Optional[int] = None
    composite_score: Optional[float] = None
    ranking_score: Optional[float] = None
    normalized_fuel_cost: Optional[float] = None
    normalized_risk_cost: Optional[float] = None
    ranking_method: Optional[str] = None


class RankedCandidateSchema(BaseModel):
    """Pydantic representation of a domain RankedCandidate."""
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    altitude_km: float
    inclination_deg: float
    raan_deg: float
    u0_deg: float
    deployment_delay_minutes: float
    deployment_epoch: Optional[datetime] = None

    # Fuel metrics
    delta_v_m_s: float
    propellant_mass_kg: float
    fuel_fraction: float
    within_dv_budget: bool

    # Risk metrics
    risk_score: float
    accepted_event_count: int
    minimum_miss_distance_km: Optional[float] = None
    uncertainty_level: str

    # Ranking metrics
    normalized_fuel_cost: float
    normalized_risk_cost: float
    composite_score: float
    rank: int
    ranking_method: str = "fallback_ranking_v1"


class RiskAssessmentSchema(BaseModel):
    """Pydantic representation of a domain RiskAssessment."""
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    risk_score: float
    proximity_score: float
    event_count_score: float
    accepted_event_count: int
    minimum_miss_distance_km: Optional[float] = None
    minimum_relative_velocity_km_s: Optional[float] = None
    maximum_relative_velocity_km_s: Optional[float] = None
    data_age_seconds: Optional[float] = None
    uncertainty_level: str = "nominal"
    uncertainty_notes: str = ""
    scoring_method: str = "fallback_heuristic_v1"


class DeltaVEstimateSchema(BaseModel):
    """Pydantic representation of a domain DeltaVEstimate."""
    model_config = ConfigDict(from_attributes=True)

    reference_altitude_km: float
    candidate_altitude_km: float
    reference_inclination_deg: float
    candidate_inclination_deg: float
    reference_radius_km: float
    candidate_radius_km: float
    transfer_dv_m_s: float
    plane_change_dv_m_s: float
    total_dv_m_s: float
    spacecraft_mass_kg: float
    isp_seconds: float
    propellant_mass_kg: float
    final_mass_kg: float
    fuel_fraction: float
    within_dv_budget: bool
    dv_budget_m_s: float
    method: str = "hohmann_plus_plane_change_conservative"


class CandidateResultItem(BaseModel):
    """Pydantic model representing an evaluated and ranked candidate deployment orbit."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: str = Field(..., description="Unique candidate identifier")
    altitude_km: float = Field(..., description="Circular orbit altitude in km")
    inclination_deg: float = Field(..., description="Orbital inclination in degrees")
    raan_deg: float = Field(..., description="Right Ascension of Ascending Node in degrees")
    u0_deg: float = Field(default=0.0, description="Initial argument of latitude in degrees")
    deployment_delay_minutes: float = Field(..., description="Deployment delay from epoch start in minutes")
    deployment_epoch: Optional[datetime] = Field(default=None, description="Deployment epoch in UTC")

    # Fuel metrics
    delta_v_m_s: float = Field(..., description="Total required delta-v in m/s")
    propellant_mass_kg: float = Field(..., description="Required propellant mass in kg")
    fuel_fraction: float = Field(..., description="Propellant mass fraction")
    within_dv_budget: bool = Field(..., description="Whether total delta-v is within budget")

    # Risk metrics
    risk_score: float = Field(..., description="Screening risk score (0 to 100)")
    accepted_event_count: Optional[int] = Field(default=0, description="Number of close-approach events detected")
    minimum_miss_distance_km: Optional[float] = Field(default=None, description="Closest approach distance in km")
    uncertainty_level: Optional[str] = Field(default="nominal", description="Assessment data uncertainty level")

    # Ranking metrics
    normalized_fuel_cost: Optional[float] = Field(default=None, description="Normalized fuel cost [0, 1]")
    normalized_risk_cost: Optional[float] = Field(default=None, description="Normalized risk cost [0, 1]")
    composite_score: Optional[float] = Field(default=None, description="Weighted composite score [0, 1]")
    rank: Optional[int] = Field(default=None, description="Final rank (1 = best)")


class CandidateResultsResponse(BaseModel):
    """Paginated response containing ranked candidates for a screening run."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(..., description="Unique screening run identifier")
    total: int = Field(..., description="Total candidate count for this run")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")
    candidate_count: Optional[int] = Field(default=None, description="Count of candidate items returned or total")
    status: Optional[str] = Field(default=None, description="Run lifecycle state")
    candidates: list[CandidateResultItem] = Field(default_factory=list, description="Ranked candidates ordered by rank ASC")
