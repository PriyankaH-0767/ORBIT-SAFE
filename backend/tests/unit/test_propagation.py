"""Unit tests for SGP4 orbital propagation, 6-digit ID handling, and circular J2 propagation (propagation.py)."""

from datetime import datetime, timedelta, timezone
import math
import pytest

from app.core.orbit import create_circular_j2_orbit
from app.core.propagation import (
    PropagationError,
    Sgp4Propagator,
    StateVector,
    propagate_circular_j2,
    propagate_circular_j2_many,
    propagate_many,
    propagate_sgp4,
    utc_datetime_to_jd_fr,
)
from app.data.demo_loader import load_demo_records
from app.data.parser import CanonicalElementRecord, parse_tle_pair

# Valid ISS TLE Fixture
ISS_LINE1 = "1 25544U 98067A   26001.50000000  .00016717  00000+0  10270-3 0  9998"
ISS_LINE2 = "2 25544  51.6400 208.1000 0005000 120.0000 240.0000 15.50000000400008"


@pytest.fixture
def iss_record() -> CanonicalElementRecord:
    """Fixture providing a parsed ISS CanonicalElementRecord."""
    return parse_tle_pair(ISS_LINE1, ISS_LINE2, object_name="ISS (ZARYA)")


def test_utc_to_jd_fr_conversion():
    """Verify Julian date conversion and rejection of naive datetimes."""
    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    jd, fr = utc_datetime_to_jd_fr(dt)
    assert jd == pytest.approx(2461041.5)
    assert fr == pytest.approx(0.5)

    # Sub-second precision test
    dt_micro = datetime(2026, 1, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)
    jd2, fr2 = utc_datetime_to_jd_fr(dt_micro)
    # 0.5s difference is 0.5 / 86400 days
    assert (fr2 - fr) == pytest.approx(0.5 / 86400.0, rel=1e-8)

    # Rejection of naive datetime
    naive_dt = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.raises(ValueError, match=r"(?i)naive"):
        utc_datetime_to_jd_fr(naive_dt)


def test_state_vector_properties():
    """Verify StateVector attributes and derived physical properties."""
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    sv = StateVector(
        timestamp=t0,
        position_km=(4000.0, 3000.0, 0.0),
        velocity_km_s=(0.0, 6.0, 4.0),
        frame="TEME",
        model="SGP4",
        object_id="25544",
    )
    # Radius = sqrt(4000^2 + 3000^2) = 5000 km
    assert sv.position_norm_km == pytest.approx(5000.0)
    # Speed = sqrt(6^2 + 4^2) = sqrt(52) approx 7.211 km/s
    assert sv.speed_km_s == pytest.approx(math.sqrt(52.0))
    # Geocentric altitude = 5000 - 6378.137 = -1378.137 km
    assert sv.geocentric_altitude_km == pytest.approx(5000.0 - 6378.137)
    assert sv.object_id == "25544"


def test_sgp4_tle_epoch_propagation(iss_record: CanonicalElementRecord):
    """Verify SGP4 propagation exactly at TLE epoch returns valid TEME state."""
    state = propagate_sgp4(iss_record, iss_record.epoch)

    assert state.frame == "TEME"
    assert state.model == "SGP4"
    assert state.object_id == "25544"
    assert state.timestamp == iss_record.epoch

    # Position in km
    assert len(state.position_km) == 3
    for c in state.position_km:
        assert math.isfinite(c)

    # Velocity in km/s
    assert len(state.velocity_km_s) == 3
    for v in state.velocity_km_s:
        assert math.isfinite(v)

    # ISS LEO radius: ~6700 - 6900 km, altitude ~400 - 430 km
    r_mag = state.position_norm_km
    assert 6700.0 < r_mag < 6900.0
    assert 380.0 < state.geocentric_altitude_km < 440.0

    # Speed: ~7.6 - 7.7 km/s
    assert 7.5 < state.speed_km_s < 7.8


def test_sgp4_future_propagation(iss_record: CanonicalElementRecord):
    """Verify propagating forward by 1 minute and 1 hour."""
    t_1min = iss_record.epoch + timedelta(minutes=1)
    state_1min = propagate_sgp4(iss_record, t_1min)
    assert state_1min.timestamp == t_1min
    assert 6700.0 < state_1min.position_norm_km < 6900.0

    t_1hr = iss_record.epoch + timedelta(hours=1)
    state_1hr = propagate_sgp4(iss_record, t_1hr)
    assert state_1hr.timestamp == t_1hr
    assert 6700.0 < state_1hr.position_norm_km < 6900.0


def test_sgp4_utc_awareness_validation(iss_record: CanonicalElementRecord):
    """Verify SGP4 propagator rejects naive datetimes."""
    naive_dt = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.raises(ValueError, match=r"(?i)naive"):
        propagate_sgp4(iss_record, naive_dt)


def test_sgp4_batch_propagation(iss_record: CanonicalElementRecord):
    """Verify propagate_many preserves timestamp order and returns expected count."""
    times = [
        iss_record.epoch + timedelta(minutes=i * 5)
        for i in range(5)
    ]
    states = propagate_many(iss_record, times)
    assert len(states) == 5
    for i, st in enumerate(states):
        assert st.timestamp == times[i]
        assert st.object_id == "25544"
        assert math.isfinite(st.speed_km_s)


def test_sgp4_decay_error_handling():
    """Verify SGP4 non-zero error codes raise a descriptive PropagationError."""
    # Construct an unphysical / decaying element record
    decayed_rec = CanonicalElementRecord(
        object_name="DECAYED TEST",
        norad_id="99999",
        epoch=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        inclination_deg=51.64,
        eccentricity=0.0001,
        raan_deg=0.0,
        arg_perigee_deg=0.0,
        mean_anomaly_deg=0.0,
        mean_motion_rev_per_day=17.5,  # Very high mean motion (~100 km altitude, rapidly decaying)
        bstar=0.05,  # Massive drag
        element_format="omm",
    )
    propagator = Sgp4Propagator(decayed_rec)

    # Propagating far into future must trigger decay error (code 6)
    future_time = decayed_rec.epoch + timedelta(days=20)
    with pytest.raises(PropagationError) as exc_info:
        propagator.propagate(future_time)

    assert exc_info.value.object_id == "99999"
    assert exc_info.value.error_code is not None


def test_omm_propagation_without_tle():
    """Verify OMM record initializes and propagates without raw TLE lines."""
    omm_rec = CanonicalElementRecord(
        object_name="OMM ACTIVE SAT",
        norad_id="46984",
        epoch=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        inclination_deg=97.5,
        eccentricity=0.00015,
        raan_deg=45.0,
        arg_perigee_deg=110.0,
        mean_anomaly_deg=250.0,
        mean_motion_rev_per_day=15.064,
        bstar=0.00005,
        element_format="omm",
    )
    assert omm_rec.raw_tle_line1 is None

    state = propagate_sgp4(omm_rec, omm_rec.epoch)
    assert state.object_id == "46984"
    assert state.model == "SGP4"
    # Radius around 6928 km (~550 km altitude)
    assert 6900.0 < state.position_norm_km < 6950.0
    assert 520.0 < state.geocentric_altitude_km < 580.0


def test_6digit_catalog_id_sgp4_compatibility():
    """CRITICAL: Verify 6-digit catalog ID (e.g. 700001) propagates with surrogate while preserving ID."""
    demo_records = load_demo_records(preferred_format="json")
    obj_700001 = next(r for r in demo_records if r.norad_id == "700001")

    assert obj_700001.norad_id == "700001"
    assert obj_700001.element_format == "omm"

    propagator = Sgp4Propagator(obj_700001)
    # SGP4 satnum must have used surrogate 0 to avoid Alpha-5 crash
    assert propagator.surrogate_used is True
    assert propagator.satrec.satnum == 0
    # Canonical ID MUST strictly remain '700001'
    assert propagator.canonical_id == "700001"

    # Propagate at epoch
    state = propagator.propagate(obj_700001.epoch)
    assert state.object_id == "700001"
    assert state.frame == "TEME"
    assert state.model == "SGP4"
    assert math.isfinite(state.speed_km_s)
    # Speed is reasonable for LEO orbit (~7.5 km/s)
    assert 7.4 < state.speed_km_s < 7.8


def test_candidate_circular_j2_propagation():
    """Verify propagating a candidate orbit using propagate_circular_j2."""
    epoch = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    orbit = create_circular_j2_orbit(
        altitude_km=550.0,
        inclination_deg=97.5,
        raan_deg=0.0,
        u0_deg=0.0,
        epoch=epoch,
    )

    t_eval = epoch + timedelta(minutes=15)
    state = propagate_circular_j2(orbit, t_eval, candidate_id="cand_opt_01")

    assert state.object_id == "cand_opt_01"
    assert state.model == "CircularJ2"
    assert state.frame == "TEME"
    assert state.timestamp == t_eval
    assert state.position_norm_km == pytest.approx(orbit.semi_major_axis_km, abs=1e-8)
    assert state.geocentric_altitude_km == pytest.approx(550.0, abs=1e-8)

    # Batch test
    times = [epoch + timedelta(minutes=i * 10) for i in range(4)]
    states = propagate_circular_j2_many(orbit, times, candidate_id="cand_opt_01")
    assert len(states) == 4
    for i, st in enumerate(states):
        assert st.timestamp == times[i]
        assert st.object_id == "cand_opt_01"


def test_cross_model_separation():
    """Verify clear model separation between SGP4 catalog propagation and analytical Circular J2."""
    # 1. Propagate catalog object with SGP4
    demo_records = load_demo_records(preferred_format="json")
    deb_rec = next(r for r in demo_records if "DEB" in r.object_name)

    t_now = deb_rec.epoch + timedelta(minutes=30)
    sgp4_state = propagate_sgp4(deb_rec, t_now)

    assert sgp4_state.model == "SGP4"
    assert sgp4_state.frame == "TEME"
    assert math.isfinite(sgp4_state.speed_km_s)

    # 2. Propagate analytical candidate orbit with Circular J2
    cand_orbit = create_circular_j2_orbit(
        altitude_km=deb_rec.perigee_altitude_km,
        inclination_deg=deb_rec.inclination_deg,
        epoch=deb_rec.epoch,
    )
    j2_state = propagate_circular_j2(cand_orbit, t_now, candidate_id="cand_ref")

    assert j2_state.model == "CircularJ2"
    assert j2_state.frame == "TEME"
    assert math.isfinite(j2_state.speed_km_s)

    # Both states are in TEME with units km and km/s, but distinctly labeled models
    assert sgp4_state.model != j2_state.model
