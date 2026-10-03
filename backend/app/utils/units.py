"""Astrodynamics and engineering unit conversion utilities for D-DATO.

Authoritative external/API unit conventions:
- Distance: kilometers (km)
- Velocity: kilometers per second (km/s)
- Time duration: seconds (s)
- Angles: degrees (deg)
- Mass: kilograms (kg)
- Specific impulse: seconds (s)
- Delta-v budget: meters per second (m/s)

Internal orbital calculation conventions:
- Angles: radians (rad) for mathematical/orbital formulation
- Distance: kilometers (km)
- Velocity: kilometers per second (km/s)
- Time: seconds (s)
"""

import math
from typing import Union

from app.core.constants import DEG_TO_RAD, RAD_TO_DEG

Numeric = Union[int, float]


def _validate_numeric(val: Numeric, name: str = "value") -> float:
    """Validate that input is a finite numeric value."""
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise TypeError(f"Expected numeric type for {name}, got {type(val).__name__}.")
    if not math.isfinite(val):
        raise ValueError(f"Input {name} must be a finite number, got {val}.")
    return float(val)


def deg_to_rad(degrees: Numeric) -> float:
    """Convert angle from degrees to radians.

    Intended for translating degrees from API/user boundaries into radians
    for internal astrodynamics and trigonometric calculations.
    """
    deg = _validate_numeric(degrees, "degrees")
    return deg * DEG_TO_RAD


def rad_to_deg(radians: Numeric) -> float:
    """Convert angle from radians to degrees.

    Intended for translating radians from internal orbital models back to
    degrees for reporting, persistence, and API responses.
    """
    rad = _validate_numeric(radians, "radians")
    return rad * RAD_TO_DEG


def m_s_to_km_s(v_m_s: Numeric) -> float:
    """Convert velocity from meters per second (m/s) to kilometers per second (km/s).

    Intended for converting delta-v budgets or impulse values into orbital velocity units.
    """
    v = _validate_numeric(v_m_s, "velocity (m/s)")
    return v / 1000.0


def km_s_to_m_s(v_km_s: Numeric) -> float:
    """Convert velocity from kilometers per second (km/s) to meters per second (m/s).

    Intended for converting orbital velocities to delta-v budget units.
    """
    v = _validate_numeric(v_km_s, "velocity (km/s)")
    return v * 1000.0


def minutes_to_seconds(minutes: Numeric) -> float:
    """Convert duration or delay from minutes to seconds."""
    m = _validate_numeric(minutes, "minutes")
    return m * 60.0


def seconds_to_minutes(seconds: Numeric) -> float:
    """Convert duration or delay from seconds to minutes."""
    s = _validate_numeric(seconds, "seconds")
    return s / 60.0


def km_to_m(km: Numeric) -> float:
    """Convert distance from kilometers (km) to meters (m)."""
    val = _validate_numeric(km, "distance (km)")
    return val * 1000.0


def m_to_km(m: Numeric) -> float:
    """Convert distance from meters (m) to kilometers (km)."""
    val = _validate_numeric(m, "distance (m)")
    return val / 1000.0
