"""SOCRATES validation reference data adapter (Phase P16).

Non-Operational Disclaimer:
SOCRATES comparison data is external reference evidence only.
It does NOT represent certified flight safety, operational conjunction assessment,
true collision probability, CDM generation, maneuver planning, or launch COLA.

Offline-first architecture:
- Live SOCRATES connection is disabled by default (SOCRATES_ENABLED=False).
- When disabled or offline, falls back to local filesystem cache.
- When cache is absent, falls back to bundled deterministic fixture (demo_mode=True).
- Strictly preserves source provenance: 'socrates_live', 'socrates_cache', 'socrates_demo_fixture'.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.data.cache import FileSystemCache
from app.schemas.validation import ValidationReferenceEvent
from app.utils.time import ensure_utc, format_iso_utc, now_utc, parse_iso_utc

logger = logging.getLogger(__name__)

_ROOT_DEMO_DIR = Path(__file__).resolve().parents[3] / "demo_data"
_APP_DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_data"
_DEMO_BASE = _ROOT_DEMO_DIR if _ROOT_DEMO_DIR.exists() else _APP_DEMO_DIR

# Default paths
_DEFAULT_CACHE_DIR = _DEMO_BASE / "cache" / "socrates"
_DEFAULT_FIXTURE_PATH = _DEMO_BASE / "validation" / "socrates_fixture.json"



class ValidationSourceUnavailableError(Exception):
    """Raised when the requested external validation source is unavailable and no cache/fixture exists."""
    pass


class ValidationSourceError(Exception):
    """Raised when validation data fails parsing or contains invalid structure."""
    pass


class SocratesAdapter:
    """Adapter for retrieving and normalizing external SOCRATES conjunction reference events."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        fixture_path: Optional[Path] = None,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self.fixture_path = Path(fixture_path) if fixture_path else _DEFAULT_FIXTURE_PATH
        self.cache = FileSystemCache(base_dir=self.cache_dir)

    def get_reference_events(
        self,
        demo_mode: Optional[bool] = None,
        cache_key: str = "default",
    ) -> Tuple[List[ValidationReferenceEvent], str, Optional[datetime]]:
        """Retrieve and normalize external reference events according to provenance hierarchy.

        Hierarchy:
        1. If demo_mode is True -> Bundled deterministic fixture ('socrates_demo_fixture')
        2. If SOCRATES_ENABLED is True and SOCRATES_BASE_URL set -> Live fetch ('socrates_live')
        3. If cached payload exists in cache_dir -> Local cache ('socrates_cache')
        4. If settings.DEMO_MODE is True (and demo_mode is not explicitly False) -> Bundled fixture ('socrates_demo_fixture')
        5. Otherwise -> ValidationSourceUnavailableError

        Returns:
            Tuple of (normalized_events, provenance_string, source_fetched_at)
        """
        # Case 1: Explicit demo mode requested
        if demo_mode is True:
            logger.info("Explicit demo_mode=True requested; loading bundled SOCRATES fixture.")
            return self._load_from_fixture()

        # Case 2: Live source explicitly enabled
        if settings.SOCRATES_ENABLED and settings.SOCRATES_BASE_URL:
            logger.info("SOCRATES_ENABLED=True; attempting live fetch from %s", settings.SOCRATES_BASE_URL)
            try:
                events, fetched_at = self._fetch_live(cache_key=cache_key)
                return events, "socrates_live", fetched_at
            except Exception as live_err:
                logger.warning("Live SOCRATES fetch failed (%s); checking cache fallback.", live_err)
                cached = self._load_from_cache(cache_key=cache_key)
                if cached is not None:
                    return cached
                if demo_mode is not False and settings.DEMO_MODE:
                    logger.info("Falling back to bundled SOCRATES fixture after live failure.")
                    return self._load_from_fixture()
                raise ValidationSourceUnavailableError(
                    f"Live SOCRATES validation source is unavailable ({live_err}) and no cached fallback exists."
                ) from live_err

        # Case 3: Live source disabled, check cached reference payload
        cached = self._load_from_cache(cache_key=cache_key)
        if cached is not None:
            return cached

        # Case 4: Default demo mode fallback if enabled in settings
        is_demo = demo_mode if demo_mode is not None else settings.DEMO_MODE
        if is_demo:
            logger.info("SOCRATES live access disabled; loading bundled deterministic fixture in demo mode.")
            return self._load_from_fixture()

        # Case 5: Offline and no cache or fixture permitted
        raise ValidationSourceUnavailableError(
            "SOCRATES validation source is not enabled (SOCRATES_ENABLED=False) "
            "and no cached validation reference data is available."
        )

    def _fetch_live(self, cache_key: str) -> Tuple[List[ValidationReferenceEvent], datetime]:
        """Perform a bounded HTTP request to the configured SOCRATES endpoint and cache raw payload."""
        url = settings.SOCRATES_BASE_URL
        timeout = settings.SOCRATES_TIMEOUT_SECONDS
        fetched_at = now_utc()

        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content = resp.text

        # Parse JSON
        try:
            data = resp.json()
        except Exception as exc:
            raise ValidationSourceError(f"Failed to parse SOCRATES response as JSON: {exc}") from exc

        # Save to filesystem cache
        raw_events = data.get("events", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        self.cache.save(
            cache_key=cache_key,
            content=content,
            format="json",
            object_count=len(raw_events),
            source="socrates",
            fetched_at=fetched_at,
        )

        events = self._normalize_records(data, provenance="socrates_live", fetched_at=fetched_at)
        return events, fetched_at

    def _load_from_cache(
        self, cache_key: str
    ) -> Optional[Tuple[List[ValidationReferenceEvent], str, Optional[datetime]]]:
        """Attempt loading raw payload and metadata from filesystem cache."""
        loaded = self.cache.load(cache_key)
        if loaded is None:
            return None

        content, meta = loaded
        try:
            data = json.loads(content)
        except Exception as exc:
            logger.warning("Corrupt cached SOCRATES JSON in key '%s': %s", cache_key, exc)
            return None

        fetched_at = meta.fetched_at
        events = self._normalize_records(data, provenance="socrates_cache", fetched_at=fetched_at)
        return events, "socrates_cache", fetched_at

    def _load_from_fixture(
        self,
    ) -> Tuple[List[ValidationReferenceEvent], str, Optional[datetime]]:
        """Load deterministic bundled fixture data from disk."""
        if not self.fixture_path.is_file():
            raise ValidationSourceUnavailableError(
                f"Bundled SOCRATES fixture not found at path: {self.fixture_path}"
            )

        try:
            content = self.fixture_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception as exc:
            raise ValidationSourceError(f"Failed to load bundled SOCRATES fixture: {exc}") from exc

        meta = data.get("_metadata", {}) if isinstance(data, dict) else {}
        fetched_at_str = meta.get("fetched_at")
        fetched_at = parse_iso_utc(fetched_at_str) if fetched_at_str else datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)
        provenance = meta.get("provenance", "socrates_demo_fixture")

        events = self._normalize_records(data, provenance=provenance, fetched_at=fetched_at)
        return events, provenance, fetched_at

    def _normalize_records(
        self,
        data: Any,
        provenance: str,
        fetched_at: Optional[datetime],
    ) -> List[ValidationReferenceEvent]:
        """Transform diverse raw external representations into canonical ValidationReferenceEvent records."""
        items: List[dict] = []
        if isinstance(data, dict):
            if "events" in data and isinstance(data["events"], list):
                items = data["events"]
            elif "records" in data and isinstance(data["records"], list):
                items = data["records"]
            else:
                items = [data]
        elif isinstance(data, list):
            items = data

        normalized: List[ValidationReferenceEvent] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            external_id = str(
                item.get("external_id")
                or item.get("id")
                or item.get("report_id")
                or f"SOC-EV-{idx+1:04d}"
            ).strip()

            candidate_identifier = item.get("candidate_identifier") or item.get("primary_satellite")
            if candidate_identifier is not None:
                candidate_identifier = str(candidate_identifier).strip()

            debris_norad = (
                item.get("debris_norad_id")
                or item.get("norad_id")
                or item.get("secondary_norad")
                or item.get("norad_cat_id")
            )
            debris_norad_id = str(debris_norad).strip() if debris_norad is not None else None

            # Parse TCA
            tca: Optional[datetime] = None
            tca_raw = item.get("tca") or item.get("event_time") or item.get("time_of_closest_approach")
            if tca_raw:
                try:
                    if isinstance(tca_raw, datetime):
                        tca = ensure_utc(tca_raw)
                    else:
                        tca = parse_iso_utc(str(tca_raw))
                except Exception:
                    logger.warning("Unparseable TCA '%s' in external event '%s'", tca_raw, external_id)

            # Parse miss distance (km)
            miss_km: Optional[float] = None
            miss_raw = item.get("miss_distance_km")
            if miss_raw is None:
                miss_raw = item.get("min_range_km")
            if miss_raw is None:
                miss_raw = item.get("miss_distance")
            if miss_raw is not None:
                try:
                    miss_km = float(miss_raw)
                except (ValueError, TypeError):
                    miss_km = None

            # Parse relative velocity (km/s)
            rel_vel: Optional[float] = None
            vel_raw = item.get("relative_velocity_km_s")
            if vel_raw is None:
                vel_raw = item.get("rel_vel_km_s")
            if vel_raw is None:
                vel_raw = item.get("relative_velocity")
            if vel_raw is not None:
                try:
                    rel_vel = float(vel_raw)
                except (ValueError, TypeError):
                    rel_vel = None

            raw_reference = item.get("raw_reference") or item

            normalized.append(
                ValidationReferenceEvent(
                    external_id=external_id,
                    candidate_identifier=candidate_identifier,
                    debris_norad_id=debris_norad_id,
                    tca=tca,
                    miss_distance_km=miss_km,
                    relative_velocity_km_s=rel_vel,
                    source=provenance,
                    source_fetched_at=fetched_at,
                    raw_reference=raw_reference,
                )
            )

        return normalized
