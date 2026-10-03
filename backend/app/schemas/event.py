"""Pydantic schemas for Conjunction Events and Screening Results."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ConjunctionEventResultSchema(BaseModel):
    """Schema representing a pure domain close-approach screening event."""
    candidate_id: str
    debris_object_id: Optional[str] = None
    debris_norad_id: str
    tca: datetime
    miss_distance_km: float
    relative_velocity_km_s: float
    coarse_min_distance_km: float
    coarse_time: datetime
    screening_start: datetime
    screening_end: datetime
    coarse_step_seconds: float
    coarse_threshold_km: float
    acceptance_threshold_km: float
    propagation_model_candidate: str = "CircularJ2"
    propagation_model_debris: str = "SGP4"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConjunctionEventResponse(BaseModel):
    """Schema representing persisted ConjunctionEvent database entity."""
    id: str
    run_id: str
    candidate_id: Optional[str] = None
    debris_object_id: Optional[str] = None
    debris_norad_id: Optional[str] = None
    debris_name: Optional[str] = None
    tca: datetime
    miss_distance_km: float
    relative_velocity_km_s: float
    threshold_km: float = 25.0
    screening_source: str = "ddato"
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ScreeningReportSchema(BaseModel):
    """Schema for screening run summary and audit report."""
    candidate_id: str
    screening_start: datetime
    screening_end: datetime
    coarse_step_seconds: float
    coarse_threshold_km: float
    event_threshold_km: float
    debris_objects_considered: int
    debris_objects_skipped: int
    coarse_pair_hits: int
    refined_event_count: int
    events: List[ConjunctionEventResultSchema] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EventResultItem(BaseModel):
    """Pydantic model representing a single conjunction event in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = Field(default=None, description="Conjunction event database identifier")
    candidate_id: Optional[str] = Field(default=None, description="Associated candidate orbit identifier")
    debris_object_id: Optional[str] = Field(default=None, description="Database ID of cataloged debris object")
    debris_norad_id: Optional[str] = Field(default=None, description="NORAD catalog identifier")
    tca: datetime = Field(..., description="Time of Closest Approach in UTC")
    miss_distance_km: float = Field(..., description="Estimated miss distance in km")
    relative_velocity_km_s: float = Field(..., description="Relative encounter velocity in km/s")
    threshold_km: float = Field(default=25.0, description="Encounter threshold in km")
    screening_source: str = Field(default="ddato", description="Screening source provenance")


class EventResultsResponse(BaseModel):
    """Paginated response containing close-approach conjunction events for a screening run."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(..., description="Unique screening run identifier")
    total: int = Field(..., description="Total event count for this run")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")
    event_count: Optional[int] = Field(default=None, description="Count of event items returned or total")
    status: Optional[str] = Field(default=None, description="Run lifecycle state")
    events: List[EventResultItem] = Field(default_factory=list, description="Conjunction events ordered by TCA ASC")
