"""SGP4 and Circular J2 state propagation engine for D-DATO.

Specification Requirements:
- SGP4 propagation adapter for catalog debris and space objects (TEME frame)
- Circular J2 secular propagation adapter for candidate orbits
- Unified, immutable StateVector representation in km and km/s
- Strict UTC timezone-aware datetime validation (never accept naive datetimes)
- Explicit SGP4 error code translation (raise PropagationError on non-zero codes)
- 6-digit catalog ID compatibility: safe internal surrogate for SGP4 Alpha-5 limitation
  while strictly preserving canonical ID on StateVector and CanonicalElementRecord
- Distinct gravity models: SGP4 library gravity convention vs D-DATO MU/RE/J2 constants
- Independent of FastAPI and SQLAlchemy
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from typing import Any, Dict, List, Optional, Tuple

from sgp4 import omm
from sgp4.api import SGP4_ERRORS, Satrec, WGS72, WGS84, jday

from app.core.constants import RE
from app.core.orbit import CircularJ2Orbit
from app.data.parser import CanonicalElementRecord
from app.utils.time import ensure_utc, is_aware


class PropagationError(ValueError):
    """Raised when an orbital state propagation fails."""

    def __init__(
        self,
        message: str,
        object_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        error_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.message = message
        self.object_id = object_id
        self.timestamp = timestamp
        self.error_code = error_code


@dataclass(frozen=True)
class StateVector:
    """Immutable Cartesian state vector in an inertial reference frame.

    Units:
    - position_km: (x, y, z) in kilometers
    - velocity_km_s: (vx, vy, vz) in kilometers per second
    - timestamp: timezone-aware UTC datetime
    - frame: coordinate frame (e.g. "TEME")
    - model: propagation algorithm ("SGP4" or "CircularJ2")
    - object_id: catalog identifier (NORAD ID or candidate ID)
    """

    timestamp: datetime
    position_km: Tuple[float, float, float]
    velocity_km_s: Tuple[float, float, float]
    frame: str = "TEME"
    model: str = "SGP4"
    object_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate input vector sanity and coordinate types."""
        if not is_aware(self.timestamp):
            raise ValueError("StateVector timestamp must be a timezone-aware UTC datetime.")

        if len(self.position_km) != 3 or len(self.velocity_km_s) != 3:
            raise ValueError("position_km and velocity_km_s must be 3-element tuples.")

        for coord in self.position_km:
            if not math.isfinite(coord):
                raise ValueError(f"Non-finite position coordinate: {coord}")

        for vel in self.velocity_km_s:
            if not math.isfinite(vel):
                raise ValueError(f"Non-finite velocity coordinate: {vel}")

    @property
    def x(self) -> float:
        return self.position_km[0]

    @property
    def y(self) -> float:
        return self.position_km[1]

    @property
    def z(self) -> float:
        return self.position_km[2]

    @property
    def vx(self) -> float:
        return self.velocity_km_s[0]

    @property
    def vy(self) -> float:
        return self.velocity_km_s[1]

    @property
    def vz(self) -> float:
        return self.velocity_km_s[2]

    @property
    def position_norm_km(self) -> float:
        """Geocentric radius magnitude: ||r|| in kilometers."""
        x, y, z = self.position_km
        return math.sqrt(x * x + y * y + z * z)

    @property
    def speed_km_s(self) -> float:
        """Scalar orbital speed: ||v|| in kilometers per second."""
        vx, vy, vz = self.velocity_km_s
        return math.sqrt(vx * vx + vy * vy + vz * vz)

    @property
    def geocentric_altitude_km(self) -> float:
        """Spherical geocentric altitude: ||r|| - RE in kilometers."""
        return self.position_norm_km - RE


def utc_datetime_to_jd_fr(dt: datetime) -> Tuple[float, float]:
    """Convert timezone-aware UTC datetime into Julian Date whole and fractional parts.

    Uses official SGP4 jday utility with sub-second precision.
    Raises ValueError if a naive datetime is passed.
    """
    dt_utc = ensure_utc(dt)
    sec_float = dt_utc.second + (dt_utc.microsecond / 1e6)
    jd, fr = jday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour, dt_utc.minute, sec_float)
    return float(jd), float(fr)


class Sgp4Propagator:
    """Encapsulates SGP4 satellite state initialization and propagation.

    Supports both legacy Two-Line Elements (TLE) and modern OMM records.
    Handles >= 6-digit catalog numbers (such as 700001) by using an internal
    surrogate satellite number for the SGP4 Alpha-5 numerical encoding without
    modifying or compromising the canonical record's identity.
    """

    def __init__(
        self,
        record: CanonicalElementRecord,
        gravity_model: int = WGS72,
    ):
        self.record = record
        self.canonical_id = str(record.norad_id)
        self.gravity_model = gravity_model
        self.surrogate_used = False
        self.satrec = Satrec()

        self._initialize_satrec()

    def _initialize_satrec(self) -> None:
        """Initialize underlying SGP4 Satrec instance from TLE or OMM record."""
        fmt = self.record.element_format.lower().strip()

        if fmt == "tle":
            if not self.record.raw_tle_line1 or not self.record.raw_tle_line2:
                raise PropagationError(
                    f"TLE record for object '{self.canonical_id}' lacks raw TLE lines.",
                    object_id=self.canonical_id,
                )
            try:
                self.satrec = Satrec.twoline2rv(
                    self.record.raw_tle_line1,
                    self.record.raw_tle_line2,
                    self.gravity_model,
                )
            except Exception as e:
                raise PropagationError(
                    f"Failed to initialize Satrec from TLE for '{self.canonical_id}': {e}",
                    object_id=self.canonical_id,
                ) from e

        elif fmt == "omm":
            # Build OMM field dictionary required by sgp4.omm.initialize
            omm_fields: Dict[str, Any] = {}
            if self.record.raw_source_record:
                try:
                    loaded = json.loads(self.record.raw_source_record)
                    if isinstance(loaded, dict):
                        omm_fields = dict(loaded)
                except Exception:
                    pass

            # Fallback/override with canonical record fields
            omm_fields.setdefault("OBJECT_NAME", self.record.object_name)
            omm_fields.setdefault("OBJECT_ID", self.record.object_id or "00-000A")
            cls_code = (self.record.classification or "U")[0].upper() if self.record.classification else "U"
            omm_fields.setdefault("CLASSIFICATION_TYPE", cls_code)
            omm_fields.setdefault("EPHEMERIS_TYPE", self.record.ephemeris_type or 0)
            omm_fields.setdefault("ELEMENT_SET_NO", self.record.element_set_number or 1)
            omm_fields.setdefault("REV_AT_EPOCH", self.record.revolution_number_at_epoch or 0)
            omm_fields.setdefault("MEAN_MOTION", self.record.mean_motion_rev_per_day)
            omm_fields.setdefault("ECCENTRICITY", self.record.eccentricity)
            omm_fields.setdefault("INCLINATION", self.record.inclination_deg)
            omm_fields.setdefault("RA_OF_ASC_NODE", self.record.raan_deg)
            omm_fields.setdefault("ARG_OF_PERICENTER", self.record.arg_perigee_deg)
            omm_fields.setdefault("MEAN_ANOMALY", self.record.mean_anomaly_deg)
            omm_fields.setdefault("BSTAR", self.record.bstar or 0.0)
            omm_fields.setdefault("MEAN_MOTION_DOT", self.record.mean_motion_dot or 0.0)
            omm_fields.setdefault("MEAN_MOTION_DDOT", self.record.mean_motion_ddot or 0.0)

            # sgp4.omm.initialize strictly expects '%Y-%m-%dT%H:%M:%S.%f' without trailing 'Z'
            omm_fields["EPOCH"] = self.record.epoch.strftime("%Y-%m-%dT%H:%M:%S.%f")

            # SGP4 Alpha-5 Catalog ID handling:
            # SGP4 library's satnum must be <= 339999 (Alpha-5 limit 'Z9999').
            # If canonical catalog ID is > 339999, use safe surrogate 0 strictly
            # for SGP4 internal numerical initialization. The canonical ID remains intact.
            cat_int = int(self.canonical_id) if self.canonical_id.isdigit() else 0
            if cat_int > 339999:
                omm_fields["NORAD_CAT_ID"] = 0
                self.surrogate_used = True
            else:
                omm_fields["NORAD_CAT_ID"] = cat_int

            try:
                omm.initialize(self.satrec, omm_fields, gravconst=self.gravity_model)
            except Exception as e:
                raise PropagationError(
                    f"Failed to initialize Satrec from OMM for '{self.canonical_id}': {e}",
                    object_id=self.canonical_id,
                ) from e
        else:
            raise PropagationError(
                f"Unsupported element_format '{fmt}' for object '{self.canonical_id}'",
                object_id=self.canonical_id,
            )

    def propagate(self, timestamp: datetime) -> StateVector:
        """Propagate to a single timezone-aware UTC timestamp and return TEME StateVector."""
        dt_utc = ensure_utc(timestamp)
        jd, fr = utc_datetime_to_jd_fr(dt_utc)

        error_code, r, v = self.satrec.sgp4(jd, fr)

        if error_code != 0:
            error_desc = SGP4_ERRORS.get(error_code, f"Unrecognized SGP4 error code {error_code}")
            raise PropagationError(
                f"SGP4 propagation failed for object '{self.canonical_id}' at {dt_utc.isoformat()} "
                f"(error {error_code}: {error_desc})",
                object_id=self.canonical_id,
                timestamp=dt_utc,
                error_code=error_code,
            )

        return StateVector(
            timestamp=dt_utc,
            position_km=(r[0], r[1], r[2]),
            velocity_km_s=(v[0], v[1], v[2]),
            frame="TEME",
            model="SGP4",
            object_id=self.canonical_id,
        )

    def propagate_many(self, timestamps: List[datetime]) -> List[StateVector]:
        """Propagate across a series of UTC timestamps, preserving request order."""
        return [self.propagate(ts) for ts in timestamps]


# =====================================================================
# SGP4 Convenience Interfaces
# =====================================================================

def propagate_sgp4(
    record: CanonicalElementRecord,
    timestamp: datetime,
    gravity_model: int = WGS72,
) -> StateVector:
    """Propagate a CanonicalElementRecord to a UTC timestamp using SGP4."""
    propagator = Sgp4Propagator(record, gravity_model=gravity_model)
    return propagator.propagate(timestamp)


def propagate_many(
    record: CanonicalElementRecord,
    timestamps: List[datetime],
    gravity_model: int = WGS72,
) -> List[StateVector]:
    """Batch-propagate a CanonicalElementRecord across multiple UTC timestamps."""
    propagator = Sgp4Propagator(record, gravity_model=gravity_model)
    return propagator.propagate_many(timestamps)


# =====================================================================
# Candidate Orbit Propagation (Circular J2 Secular Model)
# =====================================================================

def propagate_circular_j2(
    orbit: CircularJ2Orbit,
    timestamp: datetime,
    candidate_id: Optional[str] = None,
) -> StateVector:
    """Propagate a CircularJ2Orbit model to a UTC timestamp in the TEME frame."""
    dt_utc = ensure_utc(timestamp)
    delta_t = (dt_utc - orbit.epoch).total_seconds()

    pos = orbit.position_at(delta_t)
    vel = orbit.velocity_at(delta_t)

    return StateVector(
        timestamp=dt_utc,
        position_km=pos,
        velocity_km_s=vel,
        frame="TEME",
        model="CircularJ2",
        object_id=candidate_id,
    )


def propagate_circular_j2_many(
    orbit: CircularJ2Orbit,
    timestamps: List[datetime],
    candidate_id: Optional[str] = None,
) -> List[StateVector]:
    """Batch-propagate a CircularJ2Orbit candidate across multiple UTC timestamps."""
    return [propagate_circular_j2(orbit, ts, candidate_id=candidate_id) for ts in timestamps]
