"""Unit tests for CanonicalElementRecord and multi-format parsers (TLE, OMM JSON, OMM CSV)."""

from datetime import datetime, timezone
import json
import pytest

from app.data.parser import (
    CanonicalElementRecord,
    ParserError,
    _parse_tle_decimal_exponent,
    calculate_tle_checksum,
    parse_catalog_payload,
    parse_omm_csv,
    parse_omm_dict,
    parse_omm_json,
    parse_tle_epoch,
    parse_tle_pair,
    parse_tle_text,
)

# Test Fixtures: Standard ISS TLE (5-digit)
ISS_NAME = "ISS (ZARYA)"
ISS_LINE1 = "1 25544U 98067A   26001.50000000  .00016717  00000+0  10270-3 0  9998"
ISS_LINE2 = "2 25544  51.6400 208.1000 0005000 120.0000 240.0000 15.50000000400008"

# 6-Digit OMM JSON fixture (modern CelesTrak GP format)
OMM_6DIGIT_JSON = """
[
  {
    "OBJECT_NAME": "MODERN DEBRIS 6-DIGIT",
    "OBJECT_ID": "2026-999A",
    "NORAD_CAT_ID": 700001,
    "CLASSIFICATION_TYPE": "U",
    "EPOCH": "2026-02-15T08:30:00.000000Z",
    "MEAN_MOTION": 15.10000000,
    "ECCENTRICITY": 0.0008000,
    "INCLINATION": 97.4000,
    "RA_OF_ASC_NODE": 50.0000,
    "ARG_OF_PERICENTER": 95.0000,
    "MEAN_ANOMALY": 200.0000,
    "EPHEMERIS_TYPE": 0,
    "ELEMENT_SET_NO": 1,
    "REV_AT_EPOCH": 500,
    "BSTAR": 0.0000250,
    "MEAN_MOTION_DOT": 0.00001000,
    "MEAN_MOTION_DDOT": 0.0
  }
]
"""

# OMM CSV fixture
OMM_CSV_DATA = """OBJECT_NAME,OBJECT_ID,NORAD_CAT_ID,EPOCH,MEAN_MOTION,ECCENTRICITY,INCLINATION,RA_OF_ASC_NODE,ARG_OF_PERICENTER,MEAN_ANOMALY,EPHEMERIS_TYPE,CLASSIFICATION_TYPE,BSTAR,MEAN_MOTION_DOT,MEAN_MOTION_DDOT
COSMOS 2251 DEB,1993-036SX,34455,2026-01-01T12:00:00Z,14.30000000,0.0025000,74.0300,62.1500,190.2000,169.8000,0,U,0.0001542,0.00000850,0.0
"""


def test_tle_checksum_calculation():
    """Verify standard modulo 10 checksum calculation for TLE lines."""
    assert calculate_tle_checksum(ISS_LINE1) == 8
    assert calculate_tle_checksum(ISS_LINE2) == 8


def test_tle_decimal_exponent_parsing():
    """Verify TLE assumed-decimal float parsing."""
    assert _parse_tle_decimal_exponent("10270-3") == pytest.approx(0.10270e-3)
    assert _parse_tle_decimal_exponent("-21820-4") == pytest.approx(-0.21820e-4)
    assert _parse_tle_decimal_exponent("00000+0") == 0.0
    assert _parse_tle_decimal_exponent("00000-0") == 0.0
    assert _parse_tle_decimal_exponent("") == 0.0


def test_tle_epoch_parsing():
    """Verify TLE YYDDD.DDDDDDDD epoch conversion to timezone-aware UTC datetime."""
    # 26001.5 -> Year 2026, Day 1.5 -> 2026-01-01 12:00:00 UTC
    dt = parse_tle_epoch("26001.50000000")
    assert dt.year == 2026
    assert dt.month == 1
    assert dt.day == 1
    assert dt.hour == 12
    assert dt.minute == 0
    assert dt.second == 0
    assert dt.tzinfo == timezone.utc

    # 98001.0 -> Year 1998, Day 1.0 -> 1998-01-01 00:00:00 UTC
    dt_98 = parse_tle_epoch("98001.00000000")
    assert dt_98.year == 1998
    assert dt_98.month == 1
    assert dt_98.day == 1
    assert dt_98.tzinfo == timezone.utc


def test_parse_valid_2line_tle():
    """Verify parsing a valid 2-line TLE into CanonicalElementRecord."""
    record = parse_tle_pair(ISS_LINE1, ISS_LINE2)
    assert record.norad_id == "25544"
    assert record.classification == "U"
    assert record.object_id == "98067A"
    assert record.inclination_deg == 51.64
    assert record.raan_deg == 208.1
    assert record.eccentricity == pytest.approx(0.0005)
    assert record.arg_perigee_deg == 120.0
    assert record.mean_anomaly_deg == 240.0
    assert record.mean_motion_rev_per_day == 15.5
    assert record.element_format == "tle"
    assert record.raw_tle_line1 == ISS_LINE1
    assert record.raw_tle_line2 == ISS_LINE2
    assert record.epoch.tzinfo == timezone.utc


def test_parse_valid_3line_tle():
    """Verify parsing 3-line element text with object name."""
    tle_text = f"{ISS_NAME}\n{ISS_LINE1}\n{ISS_LINE2}"
    records = parse_tle_text(tle_text)
    assert len(records) == 1
    rec = records[0]
    assert rec.object_name == ISS_NAME
    assert rec.norad_id == "25544"
    assert rec.inclination_deg == 51.64


def test_parse_tle_rejections():
    """Verify malformed TLE lines are rejected with descriptive ParserError."""
    # Line 1 wrong start char
    with pytest.raises(ParserError, match="must start with '1' and '2'"):
        parse_tle_pair("X" + ISS_LINE1[1:], ISS_LINE2)

    # Line 2 wrong start char
    with pytest.raises(ParserError, match="must start with '1' and '2'"):
        parse_tle_pair(ISS_LINE1, "X" + ISS_LINE2[1:])

    # NORAD mismatch
    bad_line2 = ISS_LINE2[:2] + "99999" + ISS_LINE2[7:]
    with pytest.raises(ParserError, match="mismatch"):
        parse_tle_pair(ISS_LINE1, bad_line2, verify_checksum=False)

    # Checksum failure
    bad_chk = ISS_LINE1[:-1] + "0"
    with pytest.raises(ParserError, match="checksum error"):
        parse_tle_pair(bad_chk, ISS_LINE2, verify_checksum=True)


def test_parse_omm_json_with_6digit_catalog_id():
    """Verify modern CelesTrak OMM JSON parsing supports > 5 digit catalog numbers."""
    records = parse_omm_json(OMM_6DIGIT_JSON)
    assert len(records) == 1
    rec = records[0]
    assert rec.norad_id == "700001"
    assert rec.catalog_id == "700001"
    assert rec.object_name == "MODERN DEBRIS 6-DIGIT"
    assert rec.element_format == "omm"
    assert rec.raw_tle_line1 is None
    assert rec.raw_tle_line2 is None
    assert rec.inclination_deg == 97.4
    assert rec.eccentricity == 0.0008
    assert rec.mean_motion_rev_per_day == 15.1
    assert rec.epoch.tzinfo == timezone.utc
    assert rec.epoch == datetime(2026, 2, 15, 8, 30, 0, tzinfo=timezone.utc)


def test_parse_omm_csv():
    """Verify parsing CelesTrak OMM CSV content."""
    records = parse_omm_csv(OMM_CSV_DATA)
    assert len(records) == 1
    rec = records[0]
    assert rec.object_name == "COSMOS 2251 DEB"
    assert rec.norad_id == "34455"
    assert rec.inclination_deg == 74.03
    assert rec.eccentricity == 0.0025
    assert rec.mean_motion_rev_per_day == 14.3
    assert rec.epoch == datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_canonical_record_derived_properties():
    """Verify physical orbital geometry properties derived from mean motion and eccentricity."""
    # Near circular LEO orbit at ~550 km
    # n = 15.064 rev/day
    rec = CanonicalElementRecord(
        object_name="TEST SATELLITE",
        norad_id="48000",
        epoch=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        inclination_deg=97.5,
        eccentricity=0.001,
        raan_deg=45.0,
        arg_perigee_deg=100.0,
        mean_anomaly_deg=200.0,
        mean_motion_rev_per_day=15.064,
        source="test",
        element_format="omm",
    )
    # semi-major axis should be approximately 6928 km
    assert 6920.0 < rec.semi_major_axis_km < 6935.0
    # perigee altitude around 543 km, apogee around 557 km
    assert 530.0 < rec.perigee_altitude_km < 560.0
    assert 540.0 < rec.apogee_altitude_km < 570.0
    # Period around 95.6 minutes
    assert 94.0 < rec.orbital_period_minutes < 97.0


def test_auto_detect_parser():
    """Verify parse_catalog_payload automatically routes JSON, CSV, and TLE formats."""
    # JSON test
    json_recs = parse_catalog_payload(OMM_6DIGIT_JSON)
    assert len(json_recs) == 1
    assert json_recs[0].norad_id == "700001"

    # CSV test
    csv_recs = parse_catalog_payload(OMM_CSV_DATA)
    assert len(csv_recs) == 1
    assert csv_recs[0].norad_id == "34455"

    # TLE test
    tle_text = f"{ISS_NAME}\n{ISS_LINE1}\n{ISS_LINE2}"
    tle_recs = parse_catalog_payload(tle_text)
    assert len(tle_recs) == 1
    assert tle_recs[0].norad_id == "25544"
