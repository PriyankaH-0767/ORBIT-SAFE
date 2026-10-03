"""Pydantic schemas for Risk Heatmap data (Phase P14).

The original D-DATO specification is authoritative.
Exposes 2D risk density matrices over the candidate grid:
- X axis: delay_minutes
- Y axis: altitude_km
- Slice dimension: inclination_deg
Values represent persisted Candidate.risk_score (0-100 scale).
Missing grid positions are represented by null (None).
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HeatmapCell(BaseModel):
    """Detailed metadata for a candidate deployment orbit within a heatmap grid cell."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: str = Field(..., description="Unique candidate identifier")
    altitude_km: float = Field(..., description="Circular orbit altitude in km")
    inclination_deg: float = Field(..., description="Orbital inclination in degrees")
    delay_minutes: float = Field(..., description="Deployment delay from epoch start in minutes")
    risk_score: Optional[float] = Field(default=None, description="Screening risk score on 0 to 100 scale")
    rank: Optional[int] = Field(default=None, description="Multi-objective rank (1 is best)")
    delta_v_m_s: Optional[float] = Field(default=None, description="Required delta-v maneuver cost in m/s")
    within_dv_budget: Optional[bool] = Field(default=None, description="Whether required delta-v is within budget")
    accepted_event_count: Optional[int] = Field(default=None, description="Count of close-approach events detected")
    minimum_miss_distance_km: Optional[float] = Field(default=None, description="Closest approach distance in km")
    uncertainty_level: Optional[str] = Field(default=None, description="Screening uncertainty level")


class HeatmapLayer(BaseModel):
    """2D risk heatmap slice for a specific orbital inclination."""

    model_config = ConfigDict(from_attributes=True)

    inclination_deg: float = Field(..., description="Orbital inclination slice in degrees")
    altitude_values_km: List[float] = Field(
        ...,
        description="Sorted altitude grid coordinates for Y-axis in ascending order (km)",
    )
    delay_values_minutes: List[float] = Field(
        ...,
        description="Sorted delay grid coordinates for X-axis in ascending order (minutes)",
    )
    values: List[List[Optional[float]]] = Field(
        ...,
        description="2D risk matrix [rows=altitudes][cols=delays]. values[r][c] corresponds to altitude_values_km[r] and delay_values_minutes[c]. Missing cells are null.",
    )
    cells: List[HeatmapCell] = Field(
        default_factory=list,
        description="Detailed cell metadata records for candidates in this inclination layer",
    )


class HeatmapResponse(BaseModel):
    """Risk heatmap response payload containing 2D slices across inclination dimensions."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(..., description="Unique screening run identifier")
    status: str = Field(..., description="Lifecycle status of the screening run")
    metric: str = Field(default="risk_score", description="Metric displayed in the heatmap matrix")
    x_axis: str = Field(default="delay_minutes", description="Dimension represented along the X axis")
    y_axis: str = Field(default="altitude_km", description="Dimension represented along the Y axis")
    inclination_values_deg: List[float] = Field(
        default_factory=list,
        description="List of inclination slices present in this heatmap response",
    )
    layers: List[HeatmapLayer] = Field(
        default_factory=list,
        description="Heatmap layers partitioned by orbital inclination",
    )
    total_candidates: int = Field(default=0, description="Total number of candidates in run or layer")
    populated_cells: int = Field(default=0, description="Total number of non-null cells populated with risk scores")
    min_risk_score: Optional[float] = Field(default=None, description="Minimum risk score among populated cells")
    max_risk_score: Optional[float] = Field(default=None, description="Maximum risk score among populated cells")


# Backwards compatibility placeholders (deprecated)
class HeatmapPoint(BaseModel):
    """Deprecated: Legacy single point schema."""

    model_config = ConfigDict(from_attributes=True)
    x_epoch_or_altitude: float
    y_raan_or_inclination: float
    risk_value: float


class HeatmapDataResponse(BaseModel):
    """Deprecated: Legacy heatmap response schema."""

    model_config = ConfigDict(from_attributes=True)
    run_id: str
    x_axis_label: str
    y_axis_label: str
    points: List[HeatmapPoint]
