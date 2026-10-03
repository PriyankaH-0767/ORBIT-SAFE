"""Unit tests for authoritative D-DATO astrodynamics constants."""

import math
from app.core import constants


def test_authoritative_constants():
    """Verify exact values and numeric types of authoritative physical constants."""
    # Earth gravitational parameter (GM in km^3 / s^2)
    assert constants.MU == 398600.4418
    assert isinstance(constants.MU, float)

    # Earth equatorial radius (km)
    assert constants.RE == 6378.137
    assert isinstance(constants.RE, float)

    # Second zonal harmonic coefficient J2
    assert constants.J2 == 1.08262668e-3
    assert isinstance(constants.J2, float)

    # Standard gravity for Isp (m / s^2)
    assert constants.G0 == 9.80665
    assert isinstance(constants.G0, float)


def test_angle_conversion_constants():
    """Verify angle conversion factor values and reciprocity."""
    assert math.isclose(constants.DEG_TO_RAD, math.pi / 180.0, rel_tol=1e-12)
    assert math.isclose(constants.RAD_TO_DEG, 180.0 / math.pi, rel_tol=1e-12)
    assert math.isclose(constants.DEG_TO_RAD * constants.RAD_TO_DEG, 1.0, rel_tol=1e-12)


def test_backward_compatibility_aliases():
    """Verify legacy aliases reference the authoritative constants."""
    assert constants.EARTH_MU_KM3_S2 == constants.MU
    assert constants.EARTH_RADIUS_KM == constants.RE
    assert constants.EARTH_J2 == constants.J2
    assert constants.STANDARD_GRAVITY_M_S2 == constants.G0
