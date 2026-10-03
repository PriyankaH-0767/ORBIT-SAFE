"""Orbital element filtering and space object classification rules for D-DATO.

Specification Requirements:
- Separate, deterministic filtering pipeline independent of ingestion
- Valid record filtering (rejecting unphysical or corrupted element sets)
- Altitude overlap filtering based on perigee and apogee altitudes
- Inclination window filtering
- Conservative category classification:
  - 'payload'
  - 'rocket_body'
  - 'debris'
  - 'unknown'
  (Never assume all non-active objects are debris)
- Deterministic deduplication using (source, catalog_id, epoch, element_format)
- Configurable thresholds
- Detailed rejection diagnostics (never silently discard objects)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from app.data.parser import CanonicalElementRecord
from app.utils.time import now_utc


@dataclass(frozen=True)
class ObjectClassification:
    """Classification outcome and confidence assessment."""
    category: str  # "payload", "rocket_body", "debris", "unknown"
    confidence: float  # 0.0 to 1.0
    rationale: str


@dataclass
class FilterResult:
    """Result of running catalog filters on a dataset."""
    accepted: List[CanonicalElementRecord]
    rejected: List[Tuple[CanonicalElementRecord, str]]  # (record, rejection_reason)
    duplicate_count: int = 0

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def total_count(self) -> int:
        return self.accepted_count + self.rejected_count + self.duplicate_count


# =====================================================================
# Object Classification
# =====================================================================

# Common patterns for rocket bodies and debris
ROCKET_BODY_PATTERNS = (
    "R/B",
    "ROCKET BODY",
    "STAGE",
    "CENTAUR",
    "FALCON",
    "DELTA",
    "ARIANE",
    "TITAN",
    "BREEZE",
    "FREGAT",
    "UPPER STAGE",
    "AKM",
    "BOOSTER",
)

DEBRIS_PATTERNS = (
    "DEB",
    "DEBRIS",
    "FRAGMENT",
    "COOLANT",
    "SHROUD",
    "COVER",
    "PANEL",
    "CLAMP",
    "SPRING",
    "PLUME",
)

PAYLOAD_PATTERNS = (
    "ISS",
    "TIANGONG",
    "STARLINK",
    "ONEWEB",
    "GPS",
    "GLONASS",
    "GALILEO",
    "BEIDOU",
    "IRIDIUM",
    "COSMOS",
    "NOAA",
    "METOP",
    "LANDSAT",
    "SENTINEL",
    "TERRA",
    "AQUA",
    "HUBBLE",
    "SATELLITE",
    "SAT",
)


def classify_object(record: CanonicalElementRecord) -> ObjectClassification:
    """Classify space object into payload, rocket_body, debris, or unknown.

    Uses conservative heuristic rules based on standard naming conventions
    and international designator / metadata when available.
    """
    name_upper = record.object_name.upper().strip()

    # 1. Check for explicit debris patterns
    for pat in DEBRIS_PATTERNS:
        if pat in name_upper:
            return ObjectClassification(
                category="debris",
                confidence=0.9,
                rationale=f"Object name contains debris indicator '{pat}'",
            )

    # 2. Check for rocket body patterns
    for pat in ROCKET_BODY_PATTERNS:
        if pat in name_upper:
            return ObjectClassification(
                category="rocket_body",
                confidence=0.85,
                rationale=f"Object name contains rocket body indicator '{pat}'",
            )

    # 3. Check for payload patterns
    for pat in PAYLOAD_PATTERNS:
        if pat in name_upper and not any(d in name_upper for d in ("DEB", "R/B")):
            return ObjectClassification(
                category="payload",
                confidence=0.75,
                rationale=f"Object name matches standard spacecraft pattern '{pat}'",
            )

    # 4. Fallback to unknown if source does not establish type
    return ObjectClassification(
        category="unknown",
        confidence=0.3,
        rationale="Insufficient metadata to determine object type conclusively",
    )


# =====================================================================
# Individual Deterministic Filter Checks
# =====================================================================

def is_valid_element_record(record: CanonicalElementRecord, max_future_days: float = 30.0) -> Tuple[bool, str]:
    """Validate physical plausibility of an orbital element record."""
    if not record.norad_id:
        return False, "Missing catalog/NORAD identifier"

    if not record.object_name:
        return False, "Missing object name"

    # Eccentricity must be non-negative and sub-parabolic for bounded orbits
    if record.eccentricity < 0.0 or record.eccentricity >= 1.0:
        return False, f"Invalid eccentricity {record.eccentricity} (must be in [0, 1))"

    # Inclination must be between 0 and 180 degrees
    if not (0.0 <= record.inclination_deg <= 180.0):
        return False, f"Invalid inclination {record.inclination_deg} (must be in [0, 180] deg)"

    # Mean motion must be strictly positive (rev / day)
    if record.mean_motion_rev_per_day <= 0.0:
        return False, f"Non-positive mean motion {record.mean_motion_rev_per_day}"

    # Orbit must not decay deep into the center of the Earth
    if record.perigee_altitude_km < -500.0:
        return False, f"Unphysical perigee altitude {record.perigee_altitude_km:.1f} km"

    # Epoch check: reject timestamps far in the future
    cutoff = now_utc() + timedelta(days=max_future_days)
    if record.epoch > cutoff:
        return False, f"Epoch {record.epoch} is unreasonably far in the future (> {max_future_days} days)"

    return True, "Valid"


def check_altitude_overlap(
    record: CanonicalElementRecord,
    min_altitude_km: float,
    max_altitude_km: float,
    margin_km: float = 0.0,
) -> bool:
    """Check if an object's orbit altitude span [perigee, apogee] overlaps the target window."""
    eff_min = min_altitude_km - margin_km
    eff_max = max_altitude_km + margin_km

    # Overlap condition: orbit apogee >= window min AND orbit perigee <= window max
    return (record.apogee_altitude_km >= eff_min) and (record.perigee_altitude_km <= eff_max)


def check_inclination_window(
    record: CanonicalElementRecord,
    target_inclination_deg: Optional[float] = None,
    tolerance_deg: Optional[float] = None,
    min_inclination_deg: Optional[float] = None,
    max_inclination_deg: Optional[float] = None,
) -> bool:
    """Check if an object's inclination falls within a specified window or target tolerance."""
    inc = record.inclination_deg

    if target_inclination_deg is not None and tolerance_deg is not None:
        low = target_inclination_deg - tolerance_deg
        high = target_inclination_deg + tolerance_deg
        if not (low <= inc <= high):
            return False

    if min_inclination_deg is not None and inc < min_inclination_deg:
        return False

    if max_inclination_deg is not None and inc > max_inclination_deg:
        return False

    return True


# =====================================================================
# Deduplication
# =====================================================================

def deduplicate_records(
    records: List[CanonicalElementRecord],
) -> Tuple[List[CanonicalElementRecord], int]:
    """Deterministically eliminate duplicate element records.

    Preferred identity tuple: (source, catalog_id, epoch, element_format)
    Returns:
        (unique_records, duplicate_count)
    """
    seen: Set[Tuple[str, str, str, str]] = set()
    unique: List[CanonicalElementRecord] = []
    duplicates = 0

    for rec in records:
        # Standardize epoch representation to microsecond ISO string
        epoch_str = rec.epoch.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        identity = (rec.source, rec.norad_id, epoch_str, rec.element_format)

        if identity in seen:
            duplicates += 1
            continue

        seen.add(identity)
        unique.append(rec)

    return unique, duplicates


# =====================================================================
# Filtering Pipeline
# =====================================================================

def apply_filters(
    records: List[CanonicalElementRecord],
    min_altitude_km: Optional[float] = None,
    max_altitude_km: Optional[float] = None,
    altitude_margin_km: float = 0.0,
    target_inclination_deg: Optional[float] = None,
    inclination_tolerance_deg: Optional[float] = None,
    min_inclination_deg: Optional[float] = None,
    max_inclination_deg: Optional[float] = None,
    allowed_categories: Optional[List[str]] = None,
    deduplicate: bool = True,
) -> FilterResult:
    """Apply configured filtering suite to a list of CanonicalElementRecords."""
    input_records = records
    duplicate_count = 0

    if deduplicate:
        input_records, duplicate_count = deduplicate_records(records)

    accepted: List[CanonicalElementRecord] = []
    rejected: List[Tuple[CanonicalElementRecord, str]] = []

    for rec in input_records:
        # 1. Validity check
        is_valid, reason = is_valid_element_record(rec)
        if not is_valid:
            rejected.append((rec, f"Validity: {reason}"))
            continue

        # 2. Altitude window check
        if min_altitude_km is not None and max_altitude_km is not None:
            if not check_altitude_overlap(rec, min_altitude_km, max_altitude_km, margin_km=altitude_margin_km):
                rejected.append(
                    (
                        rec,
                        f"Altitude: Orbit [{rec.perigee_altitude_km:.1f}, {rec.apogee_altitude_km:.1f}] km "
                        f"does not overlap window [{min_altitude_km}, {max_altitude_km}] km",
                    )
                )
                continue

        # 3. Inclination window check
        if (
            target_inclination_deg is not None
            or min_inclination_deg is not None
            or max_inclination_deg is not None
        ):
            if not check_inclination_window(
                rec,
                target_inclination_deg=target_inclination_deg,
                tolerance_deg=inclination_tolerance_deg,
                min_inclination_deg=min_inclination_deg,
                max_inclination_deg=max_inclination_deg,
            ):
                rejected.append(
                    (rec, f"Inclination: {rec.inclination_deg:.2f} deg outside target window")
                )
                continue

        # 4. Category filter
        if allowed_categories is not None:
            classification = classify_object(rec)
            if classification.category not in allowed_categories:
                rejected.append(
                    (
                        rec,
                        f"Category: Classified as '{classification.category}' "
                        f"(allowed: {allowed_categories})",
                    )
                )
                continue

        # Passed all filters
        accepted.append(rec)

    return FilterResult(
        accepted=accepted,
        rejected=rejected,
        duplicate_count=duplicate_count,
    )
