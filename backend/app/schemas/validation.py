"""Pydantic v2 schemas for External Conjunction Validation (Phase P16).

Non-Operational Disclaimer:
D-DATO validation comparison is external reference evidence only.
It does NOT represent certified flight safety, operational conjunction assessment,
true collision probability, CDM generation, maneuver planning, or launch COLA.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValidationReferenceEvent(BaseModel):
    """Canonical normalized external reference conjunction event (e.g., from SOCRATES)."""

    external_id: str = Field(..., description="Unique external reference identifier")
    candidate_identifier: Optional[str] = Field(
        default=None, description="External primary candidate/satellite identifier if available"
    )
    debris_norad_id: Optional[str] = Field(
        default=None, description="Cataloged NORAD identifier of the threatening debris object"
    )
    tca: Optional[datetime] = Field(
        default=None, description="Time of closest approach in UTC"
    )
    miss_distance_km: Optional[float] = Field(
        default=None, description="Reported external miss distance in kilometers"
    )
    relative_velocity_km_s: Optional[float] = Field(
        default=None, description="Reported external relative encounter velocity in km/s"
    )
    source: str = Field(
        default="socrates", description="External validation data source name"
    )
    source_fetched_at: Optional[datetime] = Field(
        default=None, description="Timestamp when reference source data was fetched or generated"
    )
    raw_reference: Optional[Dict[str, Any]] = Field(
        default=None, description="Verbatim raw external reference payload for auditing"
    )

    model_config = ConfigDict(from_attributes=True)


class ValidationMatch(BaseModel):
    """Paired match between a D-DATO conjunction event and an external validation event."""

    d_dato_event_id: Optional[str] = Field(
        default=None, description="ID of the persisted D-DATO ConjunctionEvent record"
    )
    external_event_id: Optional[str] = Field(
        default=None, description="ID of the matched external reference event"
    )
    candidate_id: Optional[str] = Field(
        default=None, description="D-DATO candidate identifier"
    )
    debris_norad_id: Optional[str] = Field(
        default=None, description="Normalized NORAD catalog identifier of the debris object"
    )
    tca_d_dato: Optional[datetime] = Field(
        default=None, description="D-DATO calculated TCA in UTC"
    )
    tca_external: Optional[datetime] = Field(
        default=None, description="External reference TCA in UTC"
    )
    tca_error_seconds: Optional[float] = Field(
        default=None, description="TCA difference in seconds (tca_d_dato - tca_external)"
    )
    miss_distance_d_dato_km: Optional[float] = Field(
        default=None, description="D-DATO calculated miss distance in kilometers"
    )
    miss_distance_external_km: Optional[float] = Field(
        default=None, description="External reference miss distance in kilometers"
    )
    miss_distance_difference_km: Optional[float] = Field(
        default=None,
        description="Miss distance difference in kilometers (d_dato - external)",
    )
    match_criteria: List[str] = Field(
        default_factory=list,
        description="Explicit criteria satisfied for pairing (e.g. ['norad_id', 'tca_tolerance', 'miss_distance_tolerance'])",
    )

    model_config = ConfigDict(from_attributes=True)


class ValidationDdatoOnlyEvent(BaseModel):
    """Conjunction event detected by D-DATO with no corresponding external match."""

    d_dato_event_id: str = Field(..., description="ID of the unmatched D-DATO ConjunctionEvent")
    candidate_id: Optional[str] = Field(default=None, description="Associated candidate orbit ID")
    debris_norad_id: Optional[str] = Field(default=None, description="NORAD catalog identifier of debris")
    tca: Optional[datetime] = Field(default=None, description="D-DATO TCA in UTC")
    miss_distance_km: Optional[float] = Field(default=None, description="D-DATO miss distance in km")
    relative_velocity_km_s: Optional[float] = Field(default=None, description="Relative velocity in km/s")
    notes: Optional[str] = Field(
        default=None, description="Descriptive explanation for unmatched status"
    )

    model_config = ConfigDict(from_attributes=True)


class ValidationExternalOnlyEvent(BaseModel):
    """External reference conjunction event with no corresponding D-DATO match."""

    external_event_id: str = Field(..., description="ID of the unmatched external event")
    debris_norad_id: Optional[str] = Field(default=None, description="NORAD catalog identifier of debris")
    tca: Optional[datetime] = Field(default=None, description="External reference TCA in UTC")
    miss_distance_km: Optional[float] = Field(default=None, description="External miss distance in km")
    relative_velocity_km_s: Optional[float] = Field(default=None, description="External relative velocity in km/s")
    candidate_identifier: Optional[str] = Field(
        default=None, description="External primary candidate/satellite identifier if available"
    )
    notes: Optional[str] = Field(
        default=None, description="Descriptive explanation for unmatched status"
    )

    model_config = ConfigDict(from_attributes=True)


class ValidationSummary(BaseModel):
    """Aggregate comparison metrics between D-DATO and external reference source."""

    d_dato_event_count: int = Field(..., description="Total D-DATO conjunction events evaluated")
    external_event_count: int = Field(..., description="Total external reference events considered")
    matched_event_count: int = Field(..., description="Number of successfully paired conjunction events")
    d_dato_only_count: int = Field(..., description="Number of events found only by D-DATO")
    external_only_count: int = Field(..., description="Number of events found only in external reference")
    external_coverage_percent: Optional[float] = Field(
        default=None,
        description="Matched / external * 100 (null if external_event_count is 0)",
    )
    d_dato_match_rate_percent: Optional[float] = Field(
        default=None,
        description="Matched / d_dato * 100 (null if d_dato_event_count is 0)",
    )
    mean_abs_tca_error_seconds: Optional[float] = Field(
        default=None,
        description="Mean absolute TCA error across matched events in seconds",
    )
    max_abs_tca_error_seconds: Optional[float] = Field(
        default=None,
        description="Maximum absolute TCA error across matched events in seconds",
    )
    mean_abs_miss_distance_difference_km: Optional[float] = Field(
        default=None,
        description="Mean absolute miss distance difference across matched events in km",
    )
    max_abs_miss_distance_difference_km: Optional[float] = Field(
        default=None,
        description="Maximum absolute miss distance difference across matched events in km",
    )

    model_config = ConfigDict(from_attributes=True)


class ValidationResponse(BaseModel):
    """Full read-only validation report comparing D-DATO run results against external source."""

    validation_id: str = Field(..., description="Unique validation report identifier")
    run_id: str = Field(..., description="Associated D-DATO screening run identifier")
    status: str = Field(..., description="Validation operation status (completed, failed)")
    source: str = Field(..., description="Validation source name and provenance (e.g. socrates_demo_fixture)")
    source_fetched_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the external reference data snapshot"
    )
    validation_created_at: datetime = Field(..., description="Validation report creation timestamp in UTC")
    summary: ValidationSummary = Field(..., description="Aggregate descriptive comparison metrics")
    matches: List[ValidationMatch] = Field(
        default_factory=list, description="List of paired D-DATO and external reference matches"
    )
    d_dato_only: List[ValidationDdatoOnlyEvent] = Field(
        default_factory=list, description="List of events detected only by D-DATO"
    )
    external_only: List[ValidationExternalOnlyEvent] = Field(
        default_factory=list, description="List of events present only in external reference"
    )
    notes: List[str] = Field(
        default_factory=list, description="Provenance, matching criteria, and non-operational disclaimers"
    )

    model_config = ConfigDict(from_attributes=True)


class ValidationExecutionRequest(BaseModel):
    """Request payload to trigger an external validation comparison for a screening run."""

    source: str = Field(
        default="socrates",
        description="External validation source name (currently supported: 'socrates')",
    )
    tca_tolerance_seconds: float = Field(
        default=300.0,
        description="Maximum allowable absolute TCA difference for event pairing in seconds",
    )
    miss_distance_tolerance_km: float = Field(
        default=5.0,
        description="Maximum allowable absolute miss-distance difference for event pairing in km",
    )
    demo_mode: Optional[bool] = Field(
        default=None,
        description="Optional override to force offline demo fixture usage without external network calls",
    )

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        canonical = v.strip().lower()
        if canonical != "socrates":
            raise ValueError(
                f"Unsupported validation source '{v}'. Currently supported validation source is 'socrates'."
            )
        return canonical

    @field_validator("tca_tolerance_seconds")
    @classmethod
    def validate_tca_tolerance(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"tca_tolerance_seconds must be positive (> 0), got {v}.")
        return v

    @field_validator("miss_distance_tolerance_km")
    @classmethod
    def validate_miss_distance_tolerance(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"miss_distance_tolerance_km must be positive (> 0), got {v}.")
        return v


# Legacy parameter validation stubs retained for backward compatibility
class ValidationRequest(BaseModel):
    target_altitude_km: float
    target_inclination_deg: float
    satellite_mass_kg: float
    propulsion_isp_s: float
    window_duration_hours: float


class ValidationIssue(BaseModel):
    field: str
    severity: str
    message: str


class ValidationResult(BaseModel):
    valid: bool
    issues: List[ValidationIssue]
