"""Unit tests for Fuel and Delta-V budget calculations.

Phase P7: Hohmann transfer, circular plane change, scalar total delta-v,
Tsiolkovsky rocket equation, mass semantics, and budget compliance.
The original D-DATO project specification is authoritative.
"""

import math
import pytest

from app.core.candidate_generator import CandidateOrbit
from app.core.config import settings
from app.core.constants import DEG_TO_RAD, G0, MU, RE
from app.core.fuel import (
    DeltaVEstimate,
    FuelEstimationError,
    calculate_circular_velocity,
    calculate_hohmann_transfer_delta_v,
    calculate_plane_change_delta_v,
    calculate_propellant_mass,
    estimate_delta_v_and_propellant,
    evaluate_candidate_fuel,
)
from app.utils.time import now_utc


def test_circular_velocity_reference_orbit():
    """Reference orbit at 550 km produces approximately 7.584 km/s circular velocity."""
    r_ref = RE + 550.0  # 6928.137 km
    v_circ = calculate_circular_velocity(r_ref)
    assert math.isclose(v_circ, 7.58444, abs_tol=1e-3)

    # Sub-surface or negative radius rejected
    with pytest.raises(FuelEstimationError, match="greater than Earth radius"):
        calculate_circular_velocity(RE)
    with pytest.raises(FuelEstimationError, match="greater than Earth radius"):
        calculate_circular_velocity(100.0)


def test_reference_identical_orbit_zero_maneuver():
    """Candidate identical to reference orbit requires zero delta-v and zero propellant."""
    est = estimate_delta_v_and_propellant(
        candidate_altitude_km=550.0,
        candidate_inclination_deg=97.5,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
        spacecraft_mass_kg=3.0,
        isp_seconds=60.0,
        dv_budget_m_s=100.0,
    )
    assert est.transfer_dv_m_s == 0.0
    assert est.plane_change_dv_m_s == 0.0
    assert est.total_dv_m_s == 0.0
    assert est.propellant_mass_kg == 0.0
    assert est.final_mass_kg == 3.0
    assert est.fuel_fraction == 0.0
    assert est.within_dv_budget is True


def test_same_altitude_inclination_change_pure_plane_change():
    """Identical altitude with inclination change produces pure plane change delta-v."""
    # 550 km, 98.0 deg vs 550 km, 97.5 deg -> delta_i = 0.5 deg
    est = estimate_delta_v_and_propellant(
        candidate_altitude_km=550.0,
        candidate_inclination_deg=98.0,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
    )
    assert est.transfer_dv_m_s == 0.0
    assert est.plane_change_dv_m_s > 0.0
    assert est.total_dv_m_s == est.plane_change_dv_m_s

    # Exact plane-change formula verification: 2 * v_ref * sin(delta_i / 2)
    r_ref = RE + 550.0
    v_ref = math.sqrt(MU / r_ref)
    expected_plane_dv_m_s = 2.0 * v_ref * math.sin(0.5 * DEG_TO_RAD / 2.0) * 1000.0
    assert math.isclose(est.plane_change_dv_m_s, expected_plane_dv_m_s, rel_tol=1e-9)


def test_same_inclination_altitude_change_pure_transfer():
    """Identical inclination with altitude change produces pure transfer delta-v."""
    # 600 km, 97.5 deg vs 550 km, 97.5 deg
    est = estimate_delta_v_and_propellant(
        candidate_altitude_km=600.0,
        candidate_inclination_deg=97.5,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
    )
    assert est.plane_change_dv_m_s == 0.0
    assert est.transfer_dv_m_s > 0.0
    assert est.total_dv_m_s == est.transfer_dv_m_s


def test_higher_orbit_transfer():
    """Transfer to a higher orbit produces positive transfer delta-v."""
    est = estimate_delta_v_and_propellant(
        candidate_altitude_km=600.0,
        candidate_inclination_deg=97.5,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
    )
    assert est.candidate_radius_km > est.reference_radius_km
    assert est.transfer_dv_m_s > 0.0
    assert 20.0 < est.transfer_dv_m_s < 35.0  # Approx 27.2 m/s


def test_lower_orbit_transfer():
    """Transfer to a lower orbit produces positive transfer delta-v."""
    est = estimate_delta_v_and_propellant(
        candidate_altitude_km=500.0,
        candidate_inclination_deg=97.5,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
    )
    assert est.candidate_radius_km < est.reference_radius_km
    assert est.transfer_dv_m_s > 0.0
    assert 20.0 < est.transfer_dv_m_s < 35.0  # Approx 27.4 m/s


def test_altitude_transfer_symmetry_sanity():
    """Upward (+50 km) and downward (-50 km) transfers have positive, comparable magnitudes."""
    up = estimate_delta_v_and_propellant(
        candidate_altitude_km=600.0,
        candidate_inclination_deg=97.5,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
    )
    down = estimate_delta_v_and_propellant(
        candidate_altitude_km=500.0,
        candidate_inclination_deg=97.5,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
    )
    assert up.transfer_dv_m_s > 0.0
    assert down.transfer_dv_m_s > 0.0
    # Both are ~27 m/s, differing by less than 2% due to gravity gradient
    rel_diff = abs(up.transfer_dv_m_s - down.transfer_dv_m_s) / up.transfer_dv_m_s
    assert rel_diff < 0.02


def test_plane_change_formula_against_exact():
    """Verify calculate_plane_change_delta_v against 2 * v * sin(delta_i / 2)."""
    v = 7.58444
    for delta_i in [0.1, 0.5, 1.0, 5.0, 10.0]:
        expected = 2.0 * v * math.sin(math.radians(delta_i) / 2.0)
        calc = calculate_plane_change_delta_v(v, delta_i)
        assert math.isclose(calc, expected, rel_tol=1e-12)

    # Negative delta inclination handles absolute angle
    assert calculate_plane_change_delta_v(v, -1.0) == calculate_plane_change_delta_v(v, 1.0)
    # Zero inclination change produces 0.0
    assert calculate_plane_change_delta_v(v, 0.0) == 0.0


def test_tsiolkovsky_rocket_equation_exact():
    """Verify propellant calculation matches Tsiolkovsky: mp = m0 * (1 - exp(-dv / (Isp * G0)))."""
    m0 = 3.0
    isp = 60.0
    dv = 75.0  # m/s

    expected_mf = m0 * math.exp(-dv / (isp * G0))
    expected_mp = m0 - expected_mf
    calc_mp = calculate_propellant_mass(m0, dv, isp)

    assert math.isclose(calc_mp, expected_mp, rel_tol=1e-10)


def test_fuel_fraction_definition():
    """Fuel fraction strictly equals propellant mass divided by initial mass."""
    est = estimate_delta_v_and_propellant(
        candidate_altitude_km=575.0,
        candidate_inclination_deg=98.0,
        spacecraft_mass_kg=3.0,
    )
    assert math.isclose(est.fuel_fraction, est.propellant_mass_kg / est.spacecraft_mass_kg, rel_tol=1e-12)
    assert 0.0 < est.fuel_fraction < 1.0
    assert math.isclose(est.final_mass_kg + est.propellant_mass_kg, est.spacecraft_mass_kg, rel_tol=1e-12)


def test_zero_dv_rocket_equation():
    """Zero delta-v yields exactly zero propellant and unchanged final mass."""
    mp = calculate_propellant_mass(3.0, 0.0, 60.0)
    assert mp == 0.0

    mp_neg = calculate_propellant_mass(3.0, -10.0, 60.0)
    assert mp_neg == 0.0


def test_dv_budget_evaluation():
    """Verify within_dv_budget boolean for below, equal, and above budget conditions."""
    # 1. Total dv below budget
    est_below = estimate_delta_v_and_propellant(
        candidate_altitude_km=555.0,
        candidate_inclination_deg=97.5,
        dv_budget_m_s=100.0,
    )
    assert est_below.total_dv_m_s < 100.0
    assert est_below.within_dv_budget is True

    # 2. Total dv exactly equal to budget
    est_exact = estimate_delta_v_and_propellant(
        candidate_altitude_km=575.0,
        candidate_inclination_deg=98.0,
        dv_budget_m_s=est_below.total_dv_m_s,
    )
    # Force budget to match total dv
    est_match = estimate_delta_v_and_propellant(
        candidate_altitude_km=575.0,
        candidate_inclination_deg=98.0,
        dv_budget_m_s=est_exact.total_dv_m_s,
    )
    assert est_match.within_dv_budget is True

    # 3. Total dv above budget
    est_above = estimate_delta_v_and_propellant(
        candidate_altitude_km=550.0,
        candidate_inclination_deg=99.0,  # 1.5 deg plane change -> ~198 m/s
        dv_budget_m_s=100.0,
    )
    assert est_above.total_dv_m_s > 100.0
    assert est_above.within_dv_budget is False


def test_invalid_altitude_rejected():
    """Negative or zero altitude raises FuelEstimationError."""
    with pytest.raises(FuelEstimationError, match="candidate_altitude_km must be > 0"):
        estimate_delta_v_and_propellant(candidate_altitude_km=0.0, candidate_inclination_deg=97.5)

    with pytest.raises(FuelEstimationError, match="candidate_altitude_km must be > 0"):
        estimate_delta_v_and_propellant(candidate_altitude_km=-50.0, candidate_inclination_deg=97.5)

    with pytest.raises(FuelEstimationError, match="reference_altitude_km must be > 0"):
        estimate_delta_v_and_propellant(
            candidate_altitude_km=550.0,
            candidate_inclination_deg=97.5,
            reference_altitude_km=-10.0,
        )


def test_invalid_inclination_rejected():
    """Inclination outside [0, 180] raises FuelEstimationError."""
    with pytest.raises(FuelEstimationError, match="between 0.0 and 180.0"):
        estimate_delta_v_and_propellant(candidate_altitude_km=550.0, candidate_inclination_deg=-1.0)

    with pytest.raises(FuelEstimationError, match="between 0.0 and 180.0"):
        estimate_delta_v_and_propellant(candidate_altitude_km=550.0, candidate_inclination_deg=181.0)

    with pytest.raises(FuelEstimationError, match="between 0.0 and 180.0"):
        estimate_delta_v_and_propellant(
            candidate_altitude_km=550.0,
            candidate_inclination_deg=97.5,
            reference_inclination_deg=190.0,
        )


def test_invalid_mass_and_isp_rejected():
    """Non-positive mass or Isp raises FuelEstimationError."""
    with pytest.raises(FuelEstimationError, match="spacecraft_mass_kg must be > 0"):
        estimate_delta_v_and_propellant(
            candidate_altitude_km=550.0,
            candidate_inclination_deg=97.5,
            spacecraft_mass_kg=0.0,
        )

    with pytest.raises(FuelEstimationError, match="isp_seconds must be > 0"):
        estimate_delta_v_and_propellant(
            candidate_altitude_km=550.0,
            candidate_inclination_deg=97.5,
            isp_seconds=-10.0,
        )


def test_invalid_budget_rejected():
    """Negative delta-v budget raises FuelEstimationError."""
    with pytest.raises(FuelEstimationError, match="dv_budget_m_s must be >= 0"):
        estimate_delta_v_and_propellant(
            candidate_altitude_km=550.0,
            candidate_inclination_deg=97.5,
            dv_budget_m_s=-1.0,
        )


def test_non_finite_inputs_rejected():
    """NaN or Inf values raise FuelEstimationError."""
    with pytest.raises(FuelEstimationError, match="finite number"):
        estimate_delta_v_and_propellant(candidate_altitude_km=float("nan"), candidate_inclination_deg=97.5)

    with pytest.raises(FuelEstimationError, match="finite number"):
        estimate_delta_v_and_propellant(candidate_altitude_km=550.0, candidate_inclination_deg=float("inf"))

    with pytest.raises(FuelEstimationError, match="finite number"):
        estimate_delta_v_and_propellant(
            candidate_altitude_km=550.0, candidate_inclination_deg=97.5, spacecraft_mass_kg=float("nan")
        )


def test_units_consistency_and_scalar_sum():
    """Ensure internal values use km/s while reported values use m/s, strictly summing components."""
    est = estimate_delta_v_and_propellant(
        candidate_altitude_km=600.0,
        candidate_inclination_deg=98.0,
        reference_altitude_km=550.0,
        reference_inclination_deg=97.5,
    )
    # Scalar sum must be exact
    assert math.isclose(est.total_dv_m_s, est.transfer_dv_m_s + est.plane_change_dv_m_s, rel_tol=1e-12)

    # Assert reasonable magnitudes in m/s
    assert 20.0 < est.transfer_dv_m_s < 35.0      # ~27.2 m/s
    assert 60.0 < est.plane_change_dv_m_s < 75.0  # ~66.2 m/s
    assert 85.0 < est.total_dv_m_s < 105.0        # ~93.4 m/s


def test_evaluate_candidate_fuel_convenience():
    """Convenience helper extracts CandidateOrbit attributes and produces identical DeltaVEstimate."""
    candidate = CandidateOrbit(
        candidate_id="ALT600_INC98.0_DELAY060",
        altitude_km=600.0,
        inclination_deg=98.0,
        raan_deg=15.0408,
        u0_deg=0.0,
        deployment_delay_minutes=60.0,
        base_raan_deg=0.0,
        raan_delay_coupling_deg_per_min=0.25068,
        epoch_start=now_utc(),
        deployment_epoch=now_utc(),
        generated_index=1,
    )
    est = evaluate_candidate_fuel(candidate)
    direct_est = estimate_delta_v_and_propellant(
        candidate_altitude_km=600.0,
        candidate_inclination_deg=98.0,
    )
    assert est.total_dv_m_s == direct_est.total_dv_m_s
    assert est.propellant_mass_kg == direct_est.propellant_mass_kg
    assert est.within_dv_budget == direct_est.within_dv_budget
