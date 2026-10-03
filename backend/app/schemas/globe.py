"""Pydantic schemas for Phase P15 3D globe visualization data.

Frame: TEME (True Equator Mean Equinox).
Position units: km.
Velocity units: km/s.
Time: UTC ISO 8601 with timezone.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GlobeStatePoint(BaseModel):
    """Single sampled orbital state in the TEME inertial frame."""

    t: datetime = Field(..., description="UTC sample timestamp (ISO 8601)")
    x_km: float = Field(..., description="TEME X position in km")
    y_km: float = Field(..., description="TEME Y position in km")
    z_km: float = Field(..., description="TEME Z position in km")
    vx_km_s: float = Field(..., description="TEME X velocity in km/s")
    vy_km_s: float = Field(..., description="TEME Y velocity in km/s")
    vz_km_s: float = Field(..., description="TEME Z velocity in km/s")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @property
    def x(self) -> float:
        return self.x_km

    @property
    def y(self) -> float:
        return self.y_km

    @property
    def z(self) -> float:
        return self.z_km

    @property
    def vx(self) -> float:
        return self.vx_km_s

    @property
    def vy(self) -> float:
        return self.vy_km_s

    @property
    def vz(self) -> float:
        return self.vz_km_s

    @model_validator(mode="before")
    @classmethod
    def remap_short_names(cls, data):
        if isinstance(data, dict):
            for short_k, full_k in [
                ("x", "x_km"),
                ("y", "y_km"),
                ("z", "z_km"),
                ("vx", "vx_km_s"),
                ("vy", "vy_km_s"),
                ("vz", "vz_km_s"),
            ]:
                if short_k in data and full_k not in data:
                    data[full_k] = data[short_k]
        return data


class GlobeCandidateTrack(BaseModel):
    """TEME-frame orbital trajectory for one ranked candidate deployment orbit."""

    candidate_id: str = Field(..., description="Candidate database identifier")
    rank: Optional[int] = Field(default=None, description="Candidate rank (lower is better)")
    altitude_km: float = Field(..., description="Target circular orbit altitude in km")
    inclination_deg: float = Field(..., description="Target orbit inclination in degrees")
    raan_deg: float = Field(..., description="Initial RAAN at plan epoch in degrees")
    risk_score: float = Field(..., description="Persisted screening risk score (0-100)")
    within_dv_budget: bool = Field(..., description="Whether this candidate is within delta-v budget")
    deployment_delay_minutes: float = Field(..., description="Deployment delay from plan epoch in minutes")
    deployment_epoch: datetime = Field(..., description="Deployment epoch when candidate orbit begins (UTC)")
    trajectory_start: datetime = Field(..., description="First sample timestamp in trajectory (= deployment_epoch)")
    trajectory_end: datetime = Field(..., description="Last sample timestamp in trajectory (= deployment_epoch + screening_days)")
    point_count: int = Field(..., description="Number of sampled trajectory points")
    trajectory: List[GlobeStatePoint] = Field(
        default_factory=list,
        description="Ordered TEME-frame Cartesian state samples starting at deployment_epoch",
    )

    model_config = ConfigDict(from_attributes=True)


class GlobeDebrisTrack(BaseModel):
    """TEME-frame orbital trajectory for a cataloged debris or space object."""

    norad_id: str = Field(..., description="NORAD catalog identifier")
    object_name: str = Field(..., description="Catalog object name")
    debris_db_id: Optional[str] = Field(default=None, description="Internal database ID")
    point_count: int = Field(..., description="Number of sampled trajectory points")
    trajectory: List[GlobeStatePoint] = Field(
        default_factory=list,
        description="Ordered TEME-frame Cartesian state samples propagated via SGP4",
    )

    model_config = ConfigDict(from_attributes=True)

    @property
    def trajectory_start(self) -> Optional[datetime]:
        return self.trajectory[0].t if self.trajectory else None

    @property
    def trajectory_end(self) -> Optional[datetime]:
        return self.trajectory[-1].t if self.trajectory else None


class GlobeEventMarker(BaseModel):
    """Conjunction event marker for globe visualization overlay."""

    event_id: str = Field(..., description="Conjunction event database identifier")
    candidate_id: Optional[str] = Field(default=None, description="Associated candidate identifier")
    debris_object_id: Optional[str] = Field(default=None, description="Associated debris object database identifier")
    debris_norad_id: Optional[str] = Field(default=None, description="NORAD ID of the threatening object")
    tca: datetime = Field(..., description="Time of Closest Approach in UTC")
    miss_distance_km: float = Field(..., description="Estimated miss distance in km")
    relative_velocity_km_s: float = Field(..., description="Relative encounter velocity in km/s")
    x_km: float = Field(..., description="TEME X position of debris at TCA in km")
    y_km: float = Field(..., description="TEME Y position of debris at TCA in km")
    z_km: float = Field(..., description="TEME Z position of debris at TCA in km")

    model_config = ConfigDict(from_attributes=True)


class GlobeResponse(BaseModel):
    """Complete 3D globe visualization payload for a D-DATO screening run.

    Contains TEME-frame trajectories for ranked candidate orbits and
    associated debris objects, plus conjunction event markers.
    Coordinate frame: TEME. Position: km. Velocity: km/s.
    """

    run_id: str = Field(..., description="Screening run identifier")
    status: str = Field(..., description="Run lifecycle status")
    frame: str = Field(default="TEME", description="Inertial coordinate frame")
    time_scale: str = Field(default="UTC", description="Time scale (UTC)")
    sample_step_seconds: int = Field(..., description="Sampling interval in seconds")
    epoch_start: datetime = Field(..., description="Visualization window start (UTC)")
    epoch_end: datetime = Field(..., description="Visualization window end (UTC)")
    candidate_count: int = Field(..., description="Number of candidate tracks returned")
    debris_count: int = Field(..., description="Number of debris tracks returned")
    event_count: int = Field(..., description="Number of conjunction event markers")
    candidates: List[GlobeCandidateTrack] = Field(
        default_factory=list,
        description="Candidate orbital trajectory tracks",
    )
    debris: List[GlobeDebrisTrack] = Field(
        default_factory=list,
        description="Debris orbital trajectory tracks propagated via SGP4",
    )
    events: List[GlobeEventMarker] = Field(
        default_factory=list,
        description="Conjunction event markers ordered by TCA ASC",
    )

    model_config = ConfigDict(from_attributes=True)
