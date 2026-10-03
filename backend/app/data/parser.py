"""Canonical orbital element records and multi-format parsers for D-DATO.

Supports:
- Legacy 2-line TLE text
- 3-line TLE text (line 0 = object name)
- Modern CelesTrak Orbit Mean-Elements Message (OMM) JSON
- CelesTrak OMM CSV

CRITICAL SPECIFICATION REQUIREMENT:
CelesTrak's GP system supports 6-digit catalog numbers for which legacy TLE lines
are NOT available. Therefore, CanonicalElementRecord and the parsing pipeline do NOT
assume 5-digit catalog numbers or require raw TLE lines.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import io
import json
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.constants import MU, RE
from app.utils.time import ensure_utc, is_aware, now_utc, parse_iso_utc


class ParserError(ValueError):
    """Domain exception raised when element data fails parsing or validation."""
    pass


@dataclass
class CanonicalElementRecord:
    """Canonical application-level representation of an orbital element set.

    Independent of SQLAlchemy. Supports both legacy TLE and modern OMM/GP records
    with arbitrary catalog identifier lengths (including >= 6 digits).
    """

    object_name: str
    norad_id: str
    epoch: datetime
    inclination_deg: float
    eccentricity: float
    raan_deg: float
    arg_perigee_deg: float
    mean_anomaly_deg: float
    mean_motion_rev_per_day: float

    # Optional metadata / designators
    object_id: Optional[str] = None  # International designator (e.g. 1998-067A)
    classification: Optional[str] = "U"
    mean_motion_dot: Optional[float] = None
    mean_motion_ddot: Optional[float] = None
    bstar: Optional[float] = None
    ephemeris_type: Optional[int] = 0
    element_set_number: Optional[int] = None
    revolution_number_at_epoch: Optional[int] = None

    # Ingestion provenance
    source: str = "celestrak"
    element_format: str = "tle"  # "tle" or "omm"
    raw_tle_line1: Optional[str] = None
    raw_tle_line2: Optional[str] = None
    raw_source_record: Optional[str] = None
    fetched_at: datetime = field(default_factory=now_utc)
    data_age_seconds: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate timezone awareness and compute initial data age if unset."""
        if not is_aware(self.epoch):
            raise ValueError(f"Epoch must be timezone-aware UTC datetime (got {self.epoch}).")
        self.epoch = ensure_utc(self.epoch)

        if not is_aware(self.fetched_at):
            raise ValueError(f"fetched_at must be timezone-aware UTC datetime (got {self.fetched_at}).")
        self.fetched_at = ensure_utc(self.fetched_at)

        if self.data_age_seconds is None:
            self.data_age_seconds = max(0.0, (now_utc() - self.fetched_at).total_seconds())

        # Ensure norad_id is string and stripped
        self.norad_id = str(self.norad_id).strip()
        self.object_name = str(self.object_name).strip()

    @property
    def catalog_id(self) -> str:
        """Alias for norad_id to support CelesTrak GP terminology."""
        return self.norad_id

    @property
    def semi_major_axis_km(self) -> float:
        """Calculate osculating/mean semi-major axis (a) in kilometers from mean motion."""
        if self.mean_motion_rev_per_day <= 0:
            return 0.0
        # n in radians per second
        n_rad_s = self.mean_motion_rev_per_day * (2.0 * math.pi) / 86400.0
        return math.pow(MU / (n_rad_s * n_rad_s), 1.0 / 3.0)

    @property
    def perigee_altitude_km(self) -> float:
        """Calculate perigee altitude (hp = a*(1 - e) - RE) in kilometers."""
        a = self.semi_major_axis_km
        if a <= 0:
            return 0.0
        return a * (1.0 - self.eccentricity) - RE

    @property
    def apogee_altitude_km(self) -> float:
        """Calculate apogee altitude (ha = a*(1 + e) - RE) in kilometers."""
        a = self.semi_major_axis_km
        if a <= 0:
            return 0.0
        return a * (1.0 + self.eccentricity) - RE

    @property
    def orbital_period_minutes(self) -> float:
        """Calculate orbital period in minutes."""
        if self.mean_motion_rev_per_day <= 0:
            return 0.0
        return 1440.0 / self.mean_motion_rev_per_day

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary representation."""
        return {
            "object_name": self.object_name,
            "norad_id": self.norad_id,
            "catalog_id": self.catalog_id,
            "object_id": self.object_id,
            "classification": self.classification,
            "epoch": self.epoch.isoformat(),
            "inclination_deg": self.inclination_deg,
            "eccentricity": self.eccentricity,
            "raan_deg": self.raan_deg,
            "arg_perigee_deg": self.arg_perigee_deg,
            "mean_anomaly_deg": self.mean_anomaly_deg,
            "mean_motion_rev_per_day": self.mean_motion_rev_per_day,
            "semi_major_axis_km": self.semi_major_axis_km,
            "perigee_altitude_km": self.perigee_altitude_km,
            "apogee_altitude_km": self.apogee_altitude_km,
            "period_minutes": self.orbital_period_minutes,
            "mean_motion_dot": self.mean_motion_dot,
            "mean_motion_ddot": self.mean_motion_ddot,
            "bstar": self.bstar,
            "ephemeris_type": self.ephemeris_type,
            "element_set_number": self.element_set_number,
            "revolution_number_at_epoch": self.revolution_number_at_epoch,
            "source": self.source,
            "element_format": self.element_format,
            "raw_tle_line1": self.raw_tle_line1,
            "raw_tle_line2": self.raw_tle_line2,
            "fetched_at": self.fetched_at.isoformat(),
            "data_age_seconds": self.data_age_seconds,
        }


# =====================================================================
# TLE Helper Functions
# =====================================================================

def calculate_tle_checksum(line: str) -> int:
    """Calculate modulo 10 checksum for a TLE line.

    Digits add their numeric value, '-' adds 1, all others add 0.
    """
    total = 0
    # Evaluate first 68 characters (69th is the checksum itself)
    for char in line[:68]:
        if char.isdigit():
            total += int(char)
        elif char == "-":
            total += 1
    return total % 10


def _parse_tle_decimal_exponent(val_str: str) -> float:
    """Parse TLE assumed-decimal scientific notation such as '10270-3' or '-21820-4' or '00000+0'."""
    val_str = val_str.strip()
    if not val_str or val_str == "0" or val_str == "00000-0" or val_str == "00000+0":
        return 0.0

    sign = 1.0
    if val_str[0] == "-":
        sign = -1.0
        val_str = val_str[1:]
    elif val_str[0] == "+":
        val_str = val_str[1:]

    # Locate exponent sign ('+' or '-') from right
    exp_idx = -1
    for i in range(len(val_str) - 1, 0, -1):
        if val_str[i] in ("+", "-"):
            exp_idx = i
            break

    if exp_idx != -1:
        mantissa_str = val_str[:exp_idx]
        exp_str = val_str[exp_idx:]
        try:
            mantissa = float("0." + mantissa_str)
            exponent = int(exp_str)
            return sign * mantissa * math.pow(10, exponent)
        except Exception:
            return 0.0

    try:
        return sign * float("0." + val_str)
    except Exception:
        return 0.0


def parse_tle_epoch(epoch_str: str) -> datetime:
    """Parse TLE YYDDD.DDDDDDDD epoch into timezone-aware UTC datetime."""
    clean = epoch_str.strip()
    if len(clean) < 5:
        raise ParserError(f"Invalid TLE epoch string: '{epoch_str}'.")

    year_2digit = int(clean[:2])
    day_fraction = float(clean[2:])

    # Standard TLE century pivot: 57-99 -> 1957-1999; 00-56 -> 2000-2056
    full_year = 2000 + year_2digit if year_2digit < 57 else 1900 + year_2digit

    # Jan 1 00:00:00 UTC corresponds to day 1.0
    base_dt = datetime(full_year, 1, 1, tzinfo=timezone.utc)
    epoch_dt = base_dt + timedelta(days=day_fraction - 1.0)
    return epoch_dt


def parse_tle_pair(
    line1: str,
    line2: str,
    object_name: Optional[str] = None,
    source: str = "celestrak",
    fetched_at: Optional[datetime] = None,
    verify_checksum: bool = True,
) -> CanonicalElementRecord:
    """Parse a pair of TLE lines (and optional name) into a CanonicalElementRecord."""
    l1 = line1.strip()
    l2 = line2.strip()

    if len(l1) < 68 or len(l2) < 68:
        raise ParserError(f"TLE lines must be at least 68 characters (got {len(l1)} and {len(l2)}).")

    if l1[0] != "1" or l2[0] != "2":
        raise ParserError(f"TLE lines must start with '1' and '2' (got '{l1[0]}' and '{l2[0]}').")

    if verify_checksum:
        if len(l1) >= 69 and l1[68].isdigit():
            expected = int(l1[68])
            actual = calculate_tle_checksum(l1)
            if actual != expected:
                raise ParserError(f"TLE Line 1 checksum error: expected {expected}, calculated {actual}.")
        if len(l2) >= 69 and l2[68].isdigit():
            expected = int(l2[68])
            actual = calculate_tle_checksum(l2)
            if actual != expected:
                raise ParserError(f"TLE Line 2 checksum error: expected {expected}, calculated {actual}.")

    # Extract catalog ID
    norad_id_1 = l1[2:7].strip()
    norad_id_2 = l2[2:7].strip()
    if norad_id_1 != norad_id_2:
        raise ParserError(f"TLE catalog ID mismatch between Line 1 ('{norad_id_1}') and Line 2 ('{norad_id_2}').")

    classification = l1[7].strip() or "U"
    object_id = l1[9:17].strip() or None

    epoch_str = l1[18:32].strip()
    epoch = parse_tle_epoch(epoch_str)

    # Line 1 numerical fields
    mm_dot_str = l1[33:43].strip()
    mean_motion_dot = None
    if mm_dot_str:
        try:
            mean_motion_dot = float(mm_dot_str)
        except ValueError:
            pass

    mm_ddot_str = l1[44:52].strip()
    mean_motion_ddot = _parse_tle_decimal_exponent(mm_ddot_str) if mm_ddot_str else None

    bstar_str = l1[53:61].strip()
    bstar = _parse_tle_decimal_exponent(bstar_str) if bstar_str else None

    ephem_str = l1[62:63].strip()
    ephemeris_type = int(ephem_str) if ephem_str.isdigit() else 0

    elset_str = l1[64:68].strip()
    element_set_number = int(elset_str) if elset_str.isdigit() else None

    # Line 2 numerical fields
    try:
        inclination_deg = float(l2[8:16].strip())
        raan_deg = float(l2[17:25].strip())
        ecc_str = l2[26:33].strip()
        eccentricity = float("0." + ecc_str)
        arg_perigee_deg = float(l2[34:42].strip())
        mean_anomaly_deg = float(l2[43:51].strip())
        mean_motion_rev_per_day = float(l2[52:63].strip())
    except (ValueError, IndexError) as err:
        raise ParserError(f"Failed to parse Line 2 orbital fields: {err}") from err

    rev_str = l2[63:68].strip()
    revolution_number_at_epoch = int(rev_str) if rev_str.isdigit() else None

    name = object_name.strip() if object_name else f"OBJECT {norad_id_1}"
    fetch_time = ensure_utc(fetched_at) if fetched_at else now_utc()

    return CanonicalElementRecord(
        object_name=name,
        norad_id=norad_id_1,
        object_id=object_id,
        classification=classification,
        epoch=epoch,
        inclination_deg=inclination_deg,
        eccentricity=eccentricity,
        raan_deg=raan_deg,
        arg_perigee_deg=arg_perigee_deg,
        mean_anomaly_deg=mean_anomaly_deg,
        mean_motion_rev_per_day=mean_motion_rev_per_day,
        mean_motion_dot=mean_motion_dot,
        mean_motion_ddot=mean_motion_ddot,
        bstar=bstar,
        ephemeris_type=ephemeris_type,
        element_set_number=element_set_number,
        revolution_number_at_epoch=revolution_number_at_epoch,
        source=source,
        element_format="tle",
        raw_tle_line1=l1,
        raw_tle_line2=l2,
        raw_source_record=f"{name}\n{l1}\n{l2}" if object_name else f"{l1}\n{l2}",
        fetched_at=fetch_time,
    )


def parse_tle_text(
    text: str,
    source: str = "celestrak",
    fetched_at: Optional[datetime] = None,
    verify_checksum: bool = True,
) -> List[CanonicalElementRecord]:
    """Parse multi-line TLE/3LE text stream into a list of CanonicalElementRecord objects."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    records: List[CanonicalElementRecord] = []
    i = 0
    fetch_time = ensure_utc(fetched_at) if fetched_at else now_utc()

    while i < len(lines):
        curr = lines[i]
        # Check if line is line 0 of 3LE (starts with '0 ' or does not start with '1 ' or '2 ')
        if not curr.startswith("1 ") and not curr.startswith("2 "):
            # We have an object name line
            name = curr.lstrip("0 ").strip()
            if i + 2 < len(lines) and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
                rec = parse_tle_pair(
                    line1=lines[i + 1],
                    line2=lines[i + 2],
                    object_name=name,
                    source=source,
                    fetched_at=fetch_time,
                    verify_checksum=verify_checksum,
                )
                records.append(rec)
                i += 3
            else:
                # Malformed sequence
                raise ParserError(f"Malformed 3LE sequence starting at line {i}: '{curr}'")
        elif curr.startswith("1 "):
            if i + 1 < len(lines) and lines[i + 1].startswith("2 "):
                rec = parse_tle_pair(
                    line1=curr,
                    line2=lines[i + 1],
                    object_name=None,
                    source=source,
                    fetched_at=fetch_time,
                    verify_checksum=verify_checksum,
                )
                records.append(rec)
                i += 2
            else:
                raise ParserError(f"TLE Line 1 at line {i} not followed by Line 2.")
        else:
            raise ParserError(f"Unexpected TLE line format at line {i}: '{curr}'.")

    return records


# =====================================================================
# OMM JSON Parser
# =====================================================================

def _normalize_iso_epoch(epoch_raw: Any) -> datetime:
    """Normalize OMM ISO-8601 epoch string into timezone-aware UTC datetime."""
    if isinstance(epoch_raw, datetime):
        return ensure_utc(epoch_raw)
    if not isinstance(epoch_raw, str):
        raise ParserError(f"OMM epoch must be string or datetime, got {type(epoch_raw).__name__}")

    epoch_str = epoch_raw.strip()
    # If lacks timezone, append Z for UTC
    if not epoch_str.endswith("Z") and "+" not in epoch_str and "-" not in epoch_str[10:]:
        epoch_str = epoch_str + "Z"
    return parse_iso_utc(epoch_str)


def parse_omm_dict(
    entry: Dict[str, Any],
    source: str = "celestrak",
    fetched_at: Optional[datetime] = None,
) -> CanonicalElementRecord:
    """Normalize a single OMM data dictionary into a CanonicalElementRecord."""
    # Field mapping supporting both CCSDS OMM standard and CelesTrak variations
    name = str(entry.get("OBJECT_NAME") or entry.get("object_name") or "UNKNOWN").strip()
    cat_id = str(
        entry.get("NORAD_CAT_ID")
        or entry.get("norad_cat_id")
        or entry.get("CATALOG_NUMBER")
        or entry.get("catalog_id")
        or ""
    ).strip()
    if not cat_id:
        raise ParserError("OMM record missing NORAD_CAT_ID or catalog number.")

    epoch_raw = entry.get("EPOCH") or entry.get("epoch")
    if not epoch_raw:
        raise ParserError(f"OMM record for {cat_id} missing EPOCH field.")
    epoch = _normalize_iso_epoch(epoch_raw)

    try:
        inc = float(entry.get("INCLINATION") or entry.get("inclination") or 0.0)
        ecc = float(entry.get("ECCENTRICITY") or entry.get("eccentricity") or 0.0)
        raan = float(entry.get("RA_OF_ASC_NODE") or entry.get("ra_of_asc_node") or entry.get("RAAN") or 0.0)
        arg_p = float(entry.get("ARG_OF_PERICENTER") or entry.get("arg_of_pericenter") or entry.get("ARG_PERIGEE") or 0.0)
        ma = float(entry.get("MEAN_ANOMALY") or entry.get("mean_anomaly") or 0.0)
        mm = float(entry.get("MEAN_MOTION") or entry.get("mean_motion") or 0.0)
    except (ValueError, TypeError) as err:
        raise ParserError(f"Failed to parse OMM orbital elements for object {cat_id}: {err}") from err

    obj_id = entry.get("OBJECT_ID") or entry.get("object_id")
    classification = entry.get("CLASSIFICATION_TYPE") or entry.get("classification_type") or "U"

    def _opt_float(key: str) -> Optional[float]:
        val = entry.get(key)
        if val is not None and val != "":
            try:
                return float(val)
            except ValueError:
                return None
        return None

    def _opt_int(key: str) -> Optional[int]:
        val = entry.get(key)
        if val is not None and val != "":
            try:
                return int(val)
            except ValueError:
                return None
        return None

    bstar = _opt_float("BSTAR") or _opt_float("bstar")
    mm_dot = _opt_float("MEAN_MOTION_DOT") or _opt_float("mean_motion_dot")
    mm_ddot = _opt_float("MEAN_MOTION_DDOT") or _opt_float("mean_motion_ddot")
    ephem_type = _opt_int("EPHEMERIS_TYPE") or _opt_int("ephemeris_type") or 0
    elset_no = _opt_int("ELEMENT_SET_NO") or _opt_int("element_set_no")
    rev_at_epoch = _opt_int("REV_AT_EPOCH") or _opt_int("rev_at_epoch")

    line1 = entry.get("TLE_LINE1") or entry.get("tle_line1")
    line2 = entry.get("TLE_LINE2") or entry.get("tle_line2")

    fetch_time = ensure_utc(fetched_at) if fetched_at else now_utc()

    return CanonicalElementRecord(
        object_name=name,
        norad_id=cat_id,
        object_id=str(obj_id).strip() if obj_id else None,
        classification=str(classification).strip() if classification else "U",
        epoch=epoch,
        inclination_deg=inc,
        eccentricity=ecc,
        raan_deg=raan,
        arg_perigee_deg=arg_p,
        mean_anomaly_deg=ma,
        mean_motion_rev_per_day=mm,
        mean_motion_dot=mm_dot,
        mean_motion_ddot=mm_ddot,
        bstar=bstar,
        ephemeris_type=ephem_type,
        element_set_number=elset_no,
        revolution_number_at_epoch=rev_at_epoch,
        source=source,
        element_format="omm",
        raw_tle_line1=str(line1) if line1 else None,
        raw_tle_line2=str(line2) if line2 else None,
        raw_source_record=json.dumps(entry, default=str),
        fetched_at=fetch_time,
    )


def parse_omm_json(
    json_content: Union[str, List[Dict[str, Any]], Dict[str, Any]],
    source: str = "celestrak",
    fetched_at: Optional[datetime] = None,
) -> List[CanonicalElementRecord]:
    """Parse CelesTrak OMM JSON content into a list of CanonicalElementRecords."""
    if isinstance(json_content, str):
        try:
            data = json.loads(json_content)
        except Exception as e:
            raise ParserError(f"Invalid JSON string passed to parse_omm_json: {e}") from e
    else:
        data = json_content

    if isinstance(data, dict):
        entries = [data]
    elif isinstance(data, list):
        entries = data
    else:
        raise ParserError(f"Expected JSON object or array, got {type(data).__name__}")

    records: List[CanonicalElementRecord] = []
    for entry in entries:
        if isinstance(entry, dict):
            records.append(parse_omm_dict(entry, source=source, fetched_at=fetched_at))

    return records


# =====================================================================
# OMM CSV Parser
# =====================================================================

def parse_omm_csv(
    csv_content: str,
    source: str = "celestrak",
    fetched_at: Optional[datetime] = None,
) -> List[CanonicalElementRecord]:
    """Parse CelesTrak OMM CSV content into a list of CanonicalElementRecords."""
    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    records: List[CanonicalElementRecord] = []
    for row in reader:
        # Strip all keys and values
        clean_row = {k.strip(): v.strip() for k, v in row.items() if k is not None}
        records.append(parse_omm_dict(clean_row, source=source, fetched_at=fetched_at))
    return records


# =====================================================================
# Universal Auto-Detect Parser
# =====================================================================

def parse_catalog_payload(
    content: str,
    format_hint: Optional[str] = None,
    source: str = "celestrak",
    fetched_at: Optional[datetime] = None,
) -> List[CanonicalElementRecord]:
    """Auto-detect format (JSON, CSV, or TLE) and parse payload into CanonicalElementRecords."""
    raw = content.strip()
    if not raw:
        return []

    hint = format_hint.lower().strip() if format_hint else None

    if hint == "json" or (hint is None and (raw.startswith("{") or raw.startswith("["))):
        return parse_omm_json(raw, source=source, fetched_at=fetched_at)

    if hint == "csv" or (hint is None and ("OBJECT_NAME" in raw and "," in raw.splitlines()[0])):
        return parse_omm_csv(raw, source=source, fetched_at=fetched_at)

    # Default to TLE text
    return parse_tle_text(raw, source=source, fetched_at=fetched_at)
