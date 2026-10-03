"""Fuel and Delta-V budget calculations for D-DATO.

Phase P7: Early-stage conservative screening estimation of altitude-transfer delta-v,
inclination-plane-change delta-v, total delta-v, propellant mass, and budget checks.

The original D-DATO project specification is authoritative.

IMPORTANT DISTINCTION:
This module provides an early-stage conservative screening estimator.
It is NOT:
- an operational maneuver plan
- a flight-certified delta-v budget
- a high-fidelity finite-burn simulation
- a true mission design trajectory optimizer

The P7 total delta-v is the conservative scalar sum of independent altitude-transfer
and plane-change estimates; burns are not vector-combined or optimized.
Spacecraft mass is treated as initial/wet mass (m0).
"""

from dataclasses import dataclass
import math
from typing import Any, Optional

from app.core.config import settings
from app.core.constants import DEG_TO_RAD, G0, MU, RE


class FuelEstimationError(ValueError):
    """Raised when fuel or delta-v estimation inputs violate physical or domain constraints."""
    pass


@dataclass(frozen=True)
class DeltaVEstimate:
    """Pure domain-level result model for candidate delta-v and propellant estimation.

    Completely decoupled from database persistence and HTTP schemas.
    """
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


def calculate_circular_velocity(radius_km: float) -> float:
    """Calculate the circular orbit velocity at radius r in km/s.

    v = sqrt(MU / r)
    """
    if not math.isfinite(radius_km):
        raise FuelEstimationError(f"Radius must be a finite number, got {radius_km}")
    if radius_km <= RE:
        raise FuelEstimationError(
            f"Orbit radius ({radius_km} km) must be strictly greater than Earth radius ({RE} km)."
        )
    return math.sqrt(MU / radius_km)


def calculate_hohmann_transfer_delta_v(
    r1_km: float,
    r2_km: float,
) -> float:
    """Calculate total delta-v required for a coplanar Hohmann transfer between two circular orbits.

    For radii r1 and r2:
      dv1 = sqrt(MU / r1) * (sqrt(2*r2 / (r1+r2)) - 1)
      dv2 = sqrt(MU / r2) * (1 - sqrt(2*r1 / (r1+r2)))
      transfer_dv = abs(dv1) + abs(dv2)

    For r1 == r2: returns 0.0 without calculating transfer maneuvers.

    Returns:
        Transfer delta-v in km/s.
    """
    if not (math.isfinite(r1_km) and math.isfinite(r2_km)):
        raise FuelEstimationError(f"Radii must be finite numbers, got r1={r1_km}, r2={r2_km}")
    if r1_km <= RE or r2_km <= RE:
        raise FuelEstimationError(
            f"Orbital radii must exceed Earth radius ({RE} km), got r1={r1_km}, r2={r2_km}"
        )
    if math.isclose(r1_km, r2_km, abs_tol=1e-12):
        return 0.0

    dv1 = math.sqrt(MU / r1_km) * (math.sqrt(2.0 * r2_km / (r1_km + r2_km)) - 1.0)
    dv2 = math.sqrt(MU / r2_km) * (1.0 - math.sqrt(2.0 * r1_km / (r1_km + r2_km)))
    return abs(dv1) + abs(dv2)


def calculate_plane_change_delta_v(
    velocity_km_s: float,
    delta_inclination_deg: float,
) -> float:
    """Calculate delta-v required for a pure circular orbital plane change maneuver.

    Conservative formula at reference velocity:
      dv_plane = 2 * velocity * sin(abs(delta_i) / 2)

    For delta_i == 0: returns 0.0.

    Returns:
        Plane change delta-v in km/s.
    """
    if not (math.isfinite(velocity_km_s) and math.isfinite(delta_inclination_deg)):
        raise FuelEstimationError(
            f"Velocity and delta inclination must be finite, got v={velocity_km_s}, di={delta_inclination_deg}"
        )
    if velocity_km_s < 0:
        raise FuelEstimationError(f"Velocity must be non-negative, got {velocity_km_s}")

    delta_i = abs(delta_inclination_deg)
    if delta_i < 1e-12:
        return 0.0

    delta_i_rad = delta_i * DEG_TO_RAD
    return 2.0 * velocity_km_s * math.sin(delta_i_rad / 2.0)


def calculate_propellant_mass(
    initial_mass_kg: float,
    delta_v_m_s: float,
    isp_seconds: float,
) -> float:
    """Compute required propellant mass via the Tsiolkovsky rocket equation.

    delta_v = Isp * G0 * ln(m0 / mf)
    mf = m0 * exp(-delta_v / (Isp * G0))
    m_propellant = m0 - mf

    For delta_v <= 0: returns 0.0.

    Returns:
        Propellant mass in kg.
    """
    if not (math.isfinite(initial_mass_kg) and math.isfinite(delta_v_m_s) and math.isfinite(isp_seconds)):
        raise FuelEstimationError("Mass, delta-v, and Isp must be finite numbers.")
    if initial_mass_kg <= 0:
        raise FuelEstimationError(f"Initial mass must be strictly positive, got {initial_mass_kg}")
    if isp_seconds <= 0:
        raise FuelEstimationError(f"Isp must be strictly positive, got {isp_seconds}")
    if delta_v_m_s <= 0.0:
        return 0.0

    # Numerically stable calculation using -expm1(-x) = 1 - exp(-x)
    fuel_fraction = -math.expm1(-delta_v_m_s / (isp_seconds * G0))
    propellant_mass = initial_mass_kg * fuel_fraction
    return max(0.0, float(propellant_mass))


def estimate_delta_v_and_propellant(
    candidate_altitude_km: float,
    candidate_inclination_deg: float,
    reference_altitude_km: float = settings.REFERENCE_ALTITUDE_KM,
    reference_inclination_deg: float = settings.REFERENCE_INCLINATION_DEG,
    spacecraft_mass_kg: float = settings.SPACECRAFT_MASS_KG,
    isp_seconds: float = settings.ISP_SECONDS,
    dv_budget_m_s: float = settings.DV_BUDGET_M_S,
) -> DeltaVEstimate:
    """Estimate conservative delta-v and propellant for an insertion/transfer candidate.

    Calculates:
      1. r_ref = RE + reference_altitude_km, r_cand = RE + candidate_altitude_km
      2. Hohmann transfer delta-v (m/s)
      3. Simple circular plane-change delta-v at reference speed (m/s)
      4. Total delta-v = transfer_dv + plane_change_dv (scalar sum, m/s)
      5. Tsiolkovsky propellant mass and fuel fraction
      6. Budget compliance: total_dv_m_s <= dv_budget_m_s

    Does NOT access database, network, or external services.
    """
    # 1. Validate numeric finiteness
    for name, val in [
        ("candidate_altitude_km", candidate_altitude_km),
        ("candidate_inclination_deg", candidate_inclination_deg),
        ("reference_altitude_km", reference_altitude_km),
        ("reference_inclination_deg", reference_inclination_deg),
        ("spacecraft_mass_kg", spacecraft_mass_kg),
        ("isp_seconds", isp_seconds),
        ("dv_budget_m_s", dv_budget_m_s),
    ]:
        if not math.isfinite(val):
            raise FuelEstimationError(f"{name} must be a finite number, got {val}")

    # 2. Validate domain ranges
    if candidate_altitude_km <= 0:
        raise FuelEstimationError(f"candidate_altitude_km must be > 0, got {candidate_altitude_km}")
    if reference_altitude_km <= 0:
        raise FuelEstimationError(f"reference_altitude_km must be > 0, got {reference_altitude_km}")

    for name, inc in [
        ("candidate_inclination_deg", candidate_inclination_deg),
        ("reference_inclination_deg", reference_inclination_deg),
    ]:
        if not (0.0 <= inc <= 180.0):
            raise FuelEstimationError(f"{name} ({inc}) must be between 0.0 and 180.0 degrees.")

    if spacecraft_mass_kg <= 0:
        raise FuelEstimationError(f"spacecraft_mass_kg must be > 0, got {spacecraft_mass_kg}")
    if isp_seconds <= 0:
        raise FuelEstimationError(f"isp_seconds must be > 0, got {isp_seconds}")
    if dv_budget_m_s < 0:
        raise FuelEstimationError(f"dv_budget_m_s must be >= 0, got {dv_budget_m_s}")

    # 3. Calculate radii and velocities in km and km/s
    r_ref_km = RE + reference_altitude_km
    r_cand_km = RE + candidate_altitude_km
    v_ref_km_s = calculate_circular_velocity(r_ref_km)

    # 4. Hohmann transfer delta-v
    transfer_dv_km_s = calculate_hohmann_transfer_delta_v(r_ref_km, r_cand_km)

    # 5. Plane-change delta-v
    delta_i_deg = abs(candidate_inclination_deg - reference_inclination_deg)
    plane_change_dv_km_s = calculate_plane_change_delta_v(v_ref_km_s, delta_i_deg)

    # 6. Conservative scalar sum total delta-v
    total_dv_km_s = transfer_dv_km_s + plane_change_dv_km_s

    # Convert km/s to m/s at boundary
    transfer_dv_m_s = transfer_dv_km_s * 1000.0
    plane_change_dv_m_s = plane_change_dv_km_s * 1000.0
    total_dv_m_s = total_dv_km_s * 1000.0

    # 7. Rocket equation for propellant and mass
    if total_dv_m_s <= 0.0:
        propellant_mass_kg = 0.0
        final_mass_kg = float(spacecraft_mass_kg)
        fuel_fraction = 0.0
    else:
        propellant_mass_kg = calculate_propellant_mass(spacecraft_mass_kg, total_dv_m_s, isp_seconds)
        final_mass_kg = max(0.0, spacecraft_mass_kg - propellant_mass_kg)
        fuel_fraction = propellant_mass_kg / spacecraft_mass_kg

    # 8. Budget evaluation (exact equality is considered within budget)
    within_budget = total_dv_m_s <= dv_budget_m_s

    return DeltaVEstimate(
        reference_altitude_km=reference_altitude_km,
        candidate_altitude_km=candidate_altitude_km,
        reference_inclination_deg=reference_inclination_deg,
        candidate_inclination_deg=candidate_inclination_deg,
        reference_radius_km=r_ref_km,
        candidate_radius_km=r_cand_km,
        transfer_dv_m_s=transfer_dv_m_s,
        plane_change_dv_m_s=plane_change_dv_m_s,
        total_dv_m_s=total_dv_m_s,
        spacecraft_mass_kg=spacecraft_mass_kg,
        isp_seconds=isp_seconds,
        propellant_mass_kg=propellant_mass_kg,
        final_mass_kg=final_mass_kg,
        fuel_fraction=fuel_fraction,
        within_dv_budget=within_budget,
        dv_budget_m_s=dv_budget_m_s,
        method="hohmann_plus_plane_change_conservative",
    )


def evaluate_candidate_fuel(
    candidate: Any,
    reference_altitude_km: float = settings.REFERENCE_ALTITUDE_KM,
    reference_inclination_deg: float = settings.REFERENCE_INCLINATION_DEG,
    spacecraft_mass_kg: float = settings.SPACECRAFT_MASS_KG,
    isp_seconds: float = settings.ISP_SECONDS,
    dv_budget_m_s: float = settings.DV_BUDGET_M_S,
) -> DeltaVEstimate:
    """Evaluate fuel and delta-v for a candidate orbit object (e.g. CandidateOrbit).

    Extracts altitude_km and inclination_deg from the candidate.
    """
    alt = getattr(candidate, "altitude_km", None)
    inc = getattr(candidate, "inclination_deg", None)
    if alt is None or inc is None:
        raise FuelEstimationError("Candidate must have altitude_km and inclination_deg attributes.")

    return estimate_delta_v_and_propellant(
        candidate_altitude_km=alt,
        candidate_inclination_deg=inc,
        reference_altitude_km=reference_altitude_km,
        reference_inclination_deg=reference_inclination_deg,
        spacecraft_mass_kg=spacecraft_mass_kg,
        isp_seconds=isp_seconds,
        dv_budget_m_s=dv_budget_m_s,
    )
