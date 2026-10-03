"""Unit tests for orbital element filtering and object classification (filter.py)."""

from datetime import datetime, timedelta, timezone
import pytest

from app.data.filter import (
    apply_filters,
    check_altitude_overlap,
    check_inclination_window,
    classify_object,
    deduplicate_records,
    is_valid_element_record,
)
from app.data.parser import CanonicalElementRecord
from app.utils.time import now_utc


def create_record(
    norad_id: str = "25544",
    name: str = "ISS (ZARYA)",
    inc: float = 51.64,
    ecc: float = 0.0005,
    mm: float = 15.5,
    epoch: datetime = None,
    source: str = "celestrak",
    fmt: str = "omm",
) -> CanonicalElementRecord:
    """Helper creating a test CanonicalElementRecord."""
    if epoch is None:
        epoch = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return CanonicalElementRecord(
        object_name=name,
        norad_id=norad_id,
        epoch=epoch,
        inclination_deg=inc,
        eccentricity=ecc,
        raan_deg=45.0,
        arg_perigee_deg=90.0,
        mean_anomaly_deg=180.0,
        mean_motion_rev_per_day=mm,
        source=source,
        element_format=fmt,
    )


def test_valid_record_acceptance():
    """Verify physically sound record passes validation."""
    rec = create_record()
    valid, reason = is_valid_element_record(rec)
    assert valid is True
    assert reason == "Valid"


def test_invalid_record_rejection():
    """Verify unphysical elements are rejected."""
    # Negative mean motion
    rec_neg_mm = create_record(mm=-1.0)
    valid, reason = is_valid_element_record(rec_neg_mm)
    assert valid is False
    assert "mean motion" in reason.lower()

    # Parabolic/Hyperbolic eccentricity (>= 1.0)
    rec_hyp = create_record(ecc=1.05)
    valid, reason = is_valid_element_record(rec_hyp)
    assert valid is False
    assert "eccentricity" in reason.lower()

    # Invalid inclination (> 180 deg)
    rec_inc = create_record(inc=195.0)
    valid, reason = is_valid_element_record(rec_inc)
    assert valid is False
    assert "inclination" in reason.lower()

    # Epoch too far in future (> 30 days)
    far_future = now_utc() + timedelta(days=60)
    rec_future = create_record(epoch=far_future)
    valid, reason = is_valid_element_record(rec_future)
    assert valid is False
    assert "future" in reason.lower()


def test_altitude_overlap_filter():
    """Verify orbit altitude overlap checking against a planning altitude window."""
    # LEO orbit at ~550 km (n ~ 15.064 rev/day)
    leo_sso = create_record(mm=15.064, ecc=0.001)
    # Window [500, 600] km
    assert check_altitude_overlap(leo_sso, min_altitude_km=500.0, max_altitude_km=600.0) is True

    # GEO orbit at ~35,786 km (n ~ 1.0027 rev/day)
    geo_sat = create_record(mm=1.0027, ecc=0.0002)
    assert check_altitude_overlap(geo_sat, min_altitude_km=500.0, max_altitude_km=600.0) is False

    # Low LEO orbit at ~300 km (n ~ 16.0 rev/day)
    low_leo = create_record(mm=16.0, ecc=0.001)
    assert check_altitude_overlap(low_leo, min_altitude_km=500.0, max_altitude_km=600.0) is False
    # With margin of 250 km, it should overlap
    assert check_altitude_overlap(low_leo, min_altitude_km=500.0, max_altitude_km=600.0, margin_km=250.0) is True


def test_inclination_window_filter():
    """Verify inclination tolerance and range checking."""
    sso_rec = create_record(inc=97.5)
    # Target 97.5 +/- 0.5 deg (97.0 to 98.0)
    assert check_inclination_window(sso_rec, target_inclination_deg=97.5, tolerance_deg=0.5) is True
    assert check_inclination_window(sso_rec, min_inclination_deg=97.0, max_inclination_deg=98.0) is True

    # ISS (51.64 deg) should be rejected
    iss_rec = create_record(inc=51.64)
    assert check_inclination_window(iss_rec, target_inclination_deg=97.5, tolerance_deg=0.5) is False
    assert check_inclination_window(iss_rec, min_inclination_deg=97.0, max_inclination_deg=98.0) is False


def test_object_classification_heuristics():
    """Verify conservative classification into payload, rocket_body, debris, and unknown."""
    deb_rec = create_record(name="COSMOS 2251 DEB")
    assert classify_object(deb_rec).category == "debris"

    rb_rec = create_record(name="CZ-4B R/B")
    assert classify_object(rb_rec).category == "rocket_body"

    iss_rec = create_record(name="ISS (ZARYA)")
    assert classify_object(iss_rec).category == "payload"

    unknown_rec = create_record(name="OBJECT ALPHA-99")
    assert classify_object(unknown_rec).category == "unknown"


def test_deterministic_deduplication():
    """Verify eliminating identical records based on (source, catalog_id, epoch, format)."""
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    r1 = create_record(norad_id="25544", epoch=t0, fmt="omm")
    r2 = create_record(norad_id="25544", epoch=t0, fmt="omm")  # Duplicate
    r3 = create_record(norad_id="25544", epoch=t1, fmt="omm")  # Different epoch
    r4 = create_record(norad_id="34455", epoch=t0, fmt="omm")  # Different ID

    unique, dup_count = deduplicate_records([r1, r2, r3, r4])
    assert dup_count == 1
    assert len(unique) == 3


def test_apply_filters_composite():
    """Verify running the complete filter pipeline with altitude, inclination, and validity filters."""
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Matching SSO target: 550 km, 97.5 deg
    r_target = create_record(norad_id="48000", name="SSO TARGET", inc=97.5, mm=15.064, epoch=t0)
    # 2. SSO Rocket Body: 550 km, 97.5 deg
    r_rb = create_record(norad_id="48001", name="SSO R/B", inc=97.5, mm=15.064, epoch=t0)
    # 3. ISS: 420 km, 51.64 deg (fails altitude and inclination)
    r_iss = create_record(norad_id="25544", name="ISS", inc=51.64, mm=15.5, epoch=t0)
    # 4. GEO: 35786 km, 14 deg (fails altitude)
    r_geo = create_record(norad_id="19548", name="GEO SAT", inc=14.0, mm=1.0027, epoch=t0)
    # 5. Invalid eccentricity
    r_bad = create_record(norad_id="99999", name="BAD OBJ", ecc=1.5, epoch=t0)

    records = [r_target, r_rb, r_iss, r_geo, r_bad, r_target]  # Includes 1 duplicate

    res = apply_filters(
        records=records,
        min_altitude_km=500.0,
        max_altitude_km=600.0,
        target_inclination_deg=97.5,
        inclination_tolerance_deg=1.0,
        deduplicate=True,
    )

    assert res.accepted_count == 2
    assert res.duplicate_count == 1
    # Rejected count should be 3 (ISS, GEO, BAD)
    assert res.rejected_count == 3
    accepted_ids = {r.norad_id for r in res.accepted}
    assert accepted_ids == {"48000", "48001"}
