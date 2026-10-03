"""Deterministic offline demo data loader for D-DATO.

Specification Requirements:
- Load bundled demo datasets without any external network dependency
- Realistic-looking, clearly labeled test records:
  - At least one payload
  - At least one rocket body
  - At least one debris object
  - At least one object outside target altitude/inclination window
  - At least one modern 6-digit catalog ID (verifying non-5-digit compatibility)
- Explicitly mark all records: source = "demo"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.data.parser import CanonicalElementRecord, parse_catalog_payload
from app.utils.time import now_utc

import os

def _resolve_demo_dir() -> Path:
    env_dir = os.environ.get("DEMO_DATA_DIR")
    if env_dir:
        p = Path(env_dir).resolve()
        if p.exists():
            return p

    candidates = [
        Path(__file__).resolve().parents[3] / "demo_data",
        Path(__file__).resolve().parents[2] / "demo_data",
        Path(__file__).resolve().parents[1] / "demo_data",
        Path.cwd() / "demo_data",
        Path.cwd() / "backend" / "demo_data",
        Path("/app/demo_data"),
        Path("/app/backend/demo_data"),
    ]
    for c in candidates:
        if c.exists() and ((c / "demo_catalog.json").is_file() or (c / "tle" / "demo_catalog.tle").is_file()):
            return c
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


DEMO_DIR = _resolve_demo_dir()
DEMO_TLE_PATH = DEMO_DIR / "tle" / "demo_catalog.tle"
DEMO_JSON_PATH = DEMO_DIR / "demo_catalog.json"


def get_demo_raw_payload(preferred_format: str = "json") -> Tuple[str, str]:
    """Retrieve raw demo dataset content and format identifier ('json' or 'tle')."""
    fmt = preferred_format.lower().strip()
    if fmt == "json" and DEMO_JSON_PATH.is_file():
        return DEMO_JSON_PATH.read_text(encoding="utf-8"), "json"
    elif DEMO_TLE_PATH.is_file():
        return DEMO_TLE_PATH.read_text(encoding="utf-8"), "tle"
    elif DEMO_JSON_PATH.is_file():
        return DEMO_JSON_PATH.read_text(encoding="utf-8"), "json"
    raise FileNotFoundError(f"No demo data fixtures found in {DEMO_DIR}")


def load_demo_records(preferred_format: str = "json") -> List[CanonicalElementRecord]:
    """Load and parse the bundled offline demo catalog as CanonicalElementRecords.

    All records are deterministically tagged with source='demo'.
    """
    content, fmt = get_demo_raw_payload(preferred_format=preferred_format)
    fetched_at = now_utc()
    records = parse_catalog_payload(
        content=content,
        format_hint=fmt,
        source="demo",
        fetched_at=fetched_at,
    )
    # Ensure source is strictly 'demo'
    for r in records:
        r.source = "demo"
    return records


def load_demo_tles() -> List[str]:
    """Load sample TLE lines from demo_catalog.tle for legacy callers."""
    if not DEMO_TLE_PATH.is_file():
        raise FileNotFoundError(f"Demo TLE fixture missing at {DEMO_TLE_PATH}")
    return [line.strip() for line in DEMO_TLE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_demo_plan() -> Dict[str, Any]:
    """Load standard reference mission plan envelope for demo testing."""
    return {
        "epoch_start": "2026-10-02T12:00:00Z",
        "altitude_min_km": 500.0,
        "altitude_max_km": 600.0,
        "altitude_step_km": 25.0,
        "inclination_min_deg": 97.0,
        "inclination_max_deg": 98.0,
        "inclination_step_deg": 0.5,
        "raan_deg": 0.0,
        "u0_deg": 0.0,
        "delay_min_minutes": 0.0,
        "delay_max_minutes": 720.0,
        "delay_step_minutes": 60.0,
        "screening_days": 3,
        "reference_altitude_km": 550.0,
        "reference_inclination_deg": 97.5,
        "dv_budget_m_s": 100.0,
        "spacecraft_mass_kg": 3.0,
        "isp_seconds": 60.0,
        "fuel_weight": 0.4,
        "risk_weight": 0.6,
        "data_source": "celestrak",
        "demo_mode": True,
    }
