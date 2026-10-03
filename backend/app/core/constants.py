"""Astrodynamics and physical constants for D-DATO.

The original D-DATO project specification is authoritative.
These constants are numeric, immutable by convention, and must be imported
by all future orbital-mechanics modules from app.core.constants.
"""

import math

# Earth Gravitational Parameter (GM) in km^3 / s^2
MU: float = 398600.4418

# Earth Equatorial Radius in km (WGS-84 / EGM96 standard)
RE: float = 6378.137

# Earth Second Zonal Harmonic perturbation coefficient (dimensionless)
J2: float = 1.08262668e-3

# Standard acceleration due to gravity in m / s^2 (used for Isp calculations)
G0: float = 9.80665

# Angle Conversion Constants
DEG_TO_RAD: float = math.pi / 180.0
RAD_TO_DEG: float = 180.0 / math.pi

# Backward-compatibility aliases
EARTH_MU_KM3_S2: float = MU
EARTH_RADIUS_KM: float = RE
EARTH_J2: float = J2
STANDARD_GRAVITY_M_S2: float = G0
EARTH_ROTATION_RATE_RAD_S: float = 7.2921150e-5  # rad / s
DEFAULT_COLLISION_THRESHOLD_KM: float = 5.0      # km
COARSE_FILTER_THRESHOLD_KM: float = 50.0         # km
