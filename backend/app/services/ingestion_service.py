"""Debris and satellite catalog ingestion service for D-DATO.

Specification Requirements:
- Orchestrate source selection, rate-limit evaluation, caching, parsing, filtering,
  and idempotent database persistence.
- Strict fallback chain:
    ONLINE FRESH CACHE / ELIGIBLE FETCH
                    ↓
            LATEST USABLE CACHE
                    ↓
            BUNDLED DEMO DATA
                    ↓
              CLEAR FAILURE
- Result modes: 'live', 'cache', 'demo'
- CelesTrak minimum fetch interval enforcement (default 2 hours)
- Deterministic deduplication and non-destructive upserts
- Create DataSnapshot with provenance metadata
- Compute timezone-aware data_age_seconds
- Completely independent of FastAPI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.cache import FileSystemCache
from app.data.celestrak import (
    CelesTrakClient,
    CelesTrakError,
    CelesTrakFetchResult,
)
from app.data.demo_loader import get_demo_raw_payload, load_demo_records
from app.data.filter import FilterResult, apply_filters
from app.data.parser import (
    CanonicalElementRecord,
    parse_catalog_payload,
)
from app.db.models import DataSnapshot, DebrisObject, SnapshotStatus
from app.db.repositories import DataSnapshotRepository, DebrisObjectRepository
from app.utils.time import duration_seconds, ensure_utc, now_utc

logger = logging.getLogger(__name__)

IngestionModeType = Literal["live", "cache", "demo"]


class IngestionMode(str, Enum):
    """Explicit source mode indicating how data was obtained."""
    live = "live"
    cache = "cache"
    demo = "demo"


class IngestionServiceError(Exception):
    """Domain exception raised when catalog ingestion fails across all fallback options."""
    pass


@dataclass
class IngestionResult:
    """Standardized output of the catalog ingestion process."""
    source: str
    mode: IngestionModeType
    fetched_at: datetime
    data_age_seconds: float
    total_records_seen: int
    accepted_records: int
    rejected_records: int
    cache_key: Optional[str] = None
    snapshot_id: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    records: List[CanonicalElementRecord] = field(default_factory=list)


class IngestionService:
    """Service coordinating catalog data fetching, parsing, caching, and persistence."""

    def __init__(
        self,
        celestrak_client: Optional[CelesTrakClient] = None,
        cache: Optional[FileSystemCache] = None,
        min_fetch_interval_hours: float = 2.0,
    ):
        self.client = celestrak_client or CelesTrakClient()
        self.cache = cache or FileSystemCache()
        self.min_fetch_interval_hours = min_fetch_interval_hours

    def _generate_cache_key(self, source: str, group: str, fmt: str) -> str:
        """Create deterministic key for filesystem and database snapshot indexing."""
        safe_src = source.lower().strip()
        safe_grp = group.lower().replace(" ", "_").replace("=", "_").replace("?", "_").replace("&", "_")
        safe_fmt = fmt.lower().strip()
        return f"{safe_src}_{safe_grp}_{safe_fmt}"

    def ingest_catalog(
        self,
        db: Optional[Session] = None,
        source: str = "celestrak",
        group: str = "active",
        format: str = "json",
        force_refresh: bool = False,
        min_altitude_km: Optional[float] = None,
        max_altitude_km: Optional[float] = None,
        altitude_margin_km: float = 0.0,
        target_inclination_deg: Optional[float] = None,
        inclination_tolerance_deg: Optional[float] = None,
        min_inclination_deg: Optional[float] = None,
        max_inclination_deg: Optional[float] = None,
        allowed_categories: Optional[List[str]] = None,
        apply_filter: bool = True,
    ) -> IngestionResult:
        """Synchronously ingest satellite/debris catalog adhering to the offline fallback chain."""
        warnings: List[str] = []
        cache_key = self._generate_cache_key(source, group, format)
        mode: IngestionModeType = "cache"

        raw_content: Optional[str] = None
        content_format: str = format
        fetched_at: datetime = now_utc()

        # Step 1: Check cache state and rate-limiting policy
        cached_entry = self.cache.load(cache_key)
        is_fresh = self.cache.is_fresh(cache_key, max_age_hours=self.min_fetch_interval_hours)

        fetch_eligible = False
        if cached_entry is None:
            fetch_eligible = True
        elif not is_fresh:
            fetch_eligible = True
        elif force_refresh:
            # Deterministic force refresh: MUST still respect minimum interval safety policy
            age_sec = self.cache.get_age_seconds(cache_key) or 0.0
            min_sec = self.min_fetch_interval_hours * 3600.0
            if age_sec < min_sec:
                warnings.append(
                    f"Safety policy rate limit: Minimum interval of {self.min_fetch_interval_hours:.1f}h "
                    f"has not elapsed (current age: {age_sec / 60.0:.1f}m). Using cached data."
                )
                fetch_eligible = False
            else:
                fetch_eligible = True

        # Step 2: Attempt network fetch if eligible and source is celestrak
        network_succeeded = False
        if fetch_eligible and source.lower() == "celestrak":
            try:
                logger.info("Attempting live CelesTrak query for group='%s', format='%s'", group, format)
                fetch_res: CelesTrakFetchResult = self.client.fetch_gp_catalog(
                    group=group,
                    format=format,
                )
                raw_content = fetch_res.content
                content_format = fetch_res.format
                fetched_at = fetch_res.fetched_at
                mode = "live"
                network_succeeded = True
            except CelesTrakError as ce:
                logger.warning("CelesTrak live fetch failed: %s", ce)
                warnings.append(f"Network fetch failed: {ce}")

        # Step 3: Fallback logic
        if not network_succeeded:
            # 3A: Try latest usable cache (even if stale)
            if cached_entry is not None:
                raw_content, meta = cached_entry
                content_format = meta.format
                fetched_at = meta.fetched_at
                mode = "cache"
                if not is_fresh:
                    warnings.append(f"Using stale cached catalog (fetched at {meta.fetched_at.isoformat()}).")
            else:
                # 3B: Fall back to bundled offline demo data
                logger.info("No usable cache available. Falling back to bundled demo dataset.")
                try:
                    raw_content, content_format = get_demo_raw_payload(preferred_format=format)
                    fetched_at = now_utc()
                    mode = "demo"
                    warnings.append("Operating in offline demo fallback mode. Remote data unavailable.")
                except Exception as de:
                    raise IngestionServiceError(
                        f"All ingestion options failed. Remote fetch failed, no cache exists, "
                        f"and demo data load error: {de}"
                    ) from de

        if raw_content is None:
            raise IngestionServiceError("Failed to obtain catalog content from any source.")

        # Step 4: Parse records
        effective_source = "demo" if mode == "demo" else source
        try:
            parsed_records = parse_catalog_payload(
                content=raw_content,
                format_hint=content_format,
                source=effective_source,
                fetched_at=fetched_at,
            )
        except Exception as pe:
            # If parsing live response failed, try fallback
            if mode == "live" and cached_entry is not None:
                warnings.append(f"Live payload parsing failed ({pe}). Falling back to cached data.")
                raw_content, meta = cached_entry
                content_format = meta.format
                fetched_at = meta.fetched_at
                mode = "cache"
                parsed_records = parse_catalog_payload(
                    content=raw_content,
                    format_hint=content_format,
                    source=effective_source,
                    fetched_at=fetched_at,
                )
            else:
                raise IngestionServiceError(f"Catalog payload parsing failed: {pe}") from pe

        total_seen = len(parsed_records)

        # Step 5: Save to cache if live fetch succeeded
        if mode == "live" and raw_content:
            try:
                self.cache.save(
                    cache_key=cache_key,
                    content=raw_content,
                    format=content_format,
                    object_count=total_seen,
                    source=effective_source,
                    fetched_at=fetched_at,
                )
            except Exception as se:
                logger.warning("Failed to save response to filesystem cache: %s", se)
                warnings.append(f"Cache write error: {se}")

        # Step 6: Filtering and Deduplication
        if apply_filter:
            filter_res: FilterResult = apply_filters(
                records=parsed_records,
                min_altitude_km=min_altitude_km,
                max_altitude_km=max_altitude_km,
                altitude_margin_km=altitude_margin_km,
                target_inclination_deg=target_inclination_deg,
                inclination_tolerance_deg=inclination_tolerance_deg,
                min_inclination_deg=min_inclination_deg,
                max_inclination_deg=max_inclination_deg,
                allowed_categories=allowed_categories,
                deduplicate=True,
            )
            accepted_records = filter_res.accepted
            rejected_count = filter_res.rejected_count + filter_res.duplicate_count
        else:
            accepted_records = parsed_records
            rejected_count = 0

        # Step 7: Calculate data age
        data_age_sec = max(0.0, (now_utc() - fetched_at).total_seconds())

        # Update data_age_seconds on individual accepted records
        for r in accepted_records:
            r.data_age_seconds = data_age_sec

        # Step 8: Database Persistence (if session provided)
        snapshot_id: Optional[str] = None
        if db is not None:
            debris_repo = DebrisObjectRepository(db)
            snapshot_repo = DataSnapshotRepository(db)

            # Map to ORM models
            orm_objects: List[DebrisObject] = [
                DebrisObject(
                    norad_id=r.norad_id,
                    object_name=r.object_name,
                    object_id=r.object_id,
                    classification=r.classification,
                    element_format=r.element_format,
                    tle_line1=r.raw_tle_line1,
                    tle_line2=r.raw_tle_line2,
                    epoch=r.epoch,
                    inclination_deg=r.inclination_deg,
                    eccentricity=r.eccentricity,
                    raan_deg=r.raan_deg,
                    arg_perigee_deg=r.arg_perigee_deg,
                    mean_anomaly_deg=r.mean_anomaly_deg,
                    mean_motion_rev_per_day=r.mean_motion_rev_per_day,
                    bstar=r.bstar,
                    mean_motion_dot=r.mean_motion_dot,
                    mean_motion_ddot=r.mean_motion_ddot,
                    ephemeris_type=r.ephemeris_type,
                    element_set_no=r.element_set_number,
                    rev_at_epoch=r.revolution_number_at_epoch,
                    raw_source_payload=r.raw_source_record,
                    source=r.source,
                    fetched_at=r.fetched_at,
                    data_age_seconds=data_age_sec,
                )
                for r in accepted_records
            ]

            debris_repo.bulk_upsert(orm_objects)

            # Record DataSnapshot
            snapshot = DataSnapshot(
                source=effective_source,
                fetched_at=fetched_at,
                data_age_seconds=data_age_sec,
                object_count=len(accepted_records),
                cache_key=cache_key,
                status=SnapshotStatus.success.value,
                notes=(
                    f"Mode: {mode}. Seen: {total_seen}, Accepted: {len(accepted_records)}, "
                    f"Rejected: {rejected_count}"
                ),
            )
            saved_snapshot = snapshot_repo.create(snapshot)
            snapshot_id = saved_snapshot.id

        return IngestionResult(
            source=effective_source,
            mode=mode,
            fetched_at=fetched_at,
            data_age_seconds=data_age_sec,
            total_records_seen=total_seen,
            accepted_records=len(accepted_records),
            rejected_records=rejected_count,
            cache_key=cache_key,
            snapshot_id=snapshot_id,
            warnings=warnings,
            records=accepted_records,
        )

    async def ingest_catalog_async(
        self,
        db: Optional[Session] = None,
        source: str = "celestrak",
        group: str = "active",
        format: str = "json",
        force_refresh: bool = False,
        min_altitude_km: Optional[float] = None,
        max_altitude_km: Optional[float] = None,
        altitude_margin_km: float = 0.0,
        target_inclination_deg: Optional[float] = None,
        inclination_tolerance_deg: Optional[float] = None,
        min_inclination_deg: Optional[float] = None,
        max_inclination_deg: Optional[float] = None,
        allowed_categories: Optional[List[str]] = None,
        apply_filter: bool = True,
    ) -> IngestionResult:
        """Asynchronously ingest satellite/debris catalog adhering to the offline fallback chain."""
        warnings: List[str] = []
        cache_key = self._generate_cache_key(source, group, format)
        mode: IngestionModeType = "cache"

        raw_content: Optional[str] = None
        content_format: str = format
        fetched_at: datetime = now_utc()

        # Step 1: Check cache state and rate-limiting policy
        cached_entry = self.cache.load(cache_key)
        is_fresh = self.cache.is_fresh(cache_key, max_age_hours=self.min_fetch_interval_hours)

        fetch_eligible = False
        if cached_entry is None:
            fetch_eligible = True
        elif not is_fresh:
            fetch_eligible = True
        elif force_refresh:
            age_sec = self.cache.get_age_seconds(cache_key) or 0.0
            min_sec = self.min_fetch_interval_hours * 3600.0
            if age_sec < min_sec:
                warnings.append(
                    f"Safety policy rate limit: Minimum interval of {self.min_fetch_interval_hours:.1f}h "
                    f"has not elapsed (current age: {age_sec / 60.0:.1f}m). Using cached data."
                )
                fetch_eligible = False
            else:
                fetch_eligible = True

        network_succeeded = False
        if fetch_eligible and source.lower() == "celestrak":
            try:
                fetch_res = await self.client.fetch_gp_catalog_async(
                    group=group,
                    format=format,
                )
                raw_content = fetch_res.content
                content_format = fetch_res.format
                fetched_at = fetch_res.fetched_at
                mode = "live"
                network_succeeded = True
            except CelesTrakError as ce:
                warnings.append(f"Network fetch failed: {ce}")

        if not network_succeeded:
            if cached_entry is not None:
                raw_content, meta = cached_entry
                content_format = meta.format
                fetched_at = meta.fetched_at
                mode = "cache"
                if not is_fresh:
                    warnings.append(f"Using stale cached catalog (fetched at {meta.fetched_at.isoformat()}).")
            else:
                try:
                    raw_content, content_format = get_demo_raw_payload(preferred_format=format)
                    fetched_at = now_utc()
                    mode = "demo"
                    warnings.append("Operating in offline demo fallback mode. Remote data unavailable.")
                except Exception as de:
                    raise IngestionServiceError(
                        f"All ingestion options failed: {de}"
                    ) from de

        effective_source = "demo" if mode == "demo" else source
        parsed_records = parse_catalog_payload(
            content=raw_content,
            format_hint=content_format,
            source=effective_source,
            fetched_at=fetched_at,
        )
        total_seen = len(parsed_records)

        if mode == "live" and raw_content:
            try:
                self.cache.save(
                    cache_key=cache_key,
                    content=raw_content,
                    format=content_format,
                    object_count=total_seen,
                    source=effective_source,
                    fetched_at=fetched_at,
                )
            except Exception as se:
                warnings.append(f"Cache write error: {se}")

        if apply_filter:
            filter_res = apply_filters(
                records=parsed_records,
                min_altitude_km=min_altitude_km,
                max_altitude_km=max_altitude_km,
                altitude_margin_km=altitude_margin_km,
                target_inclination_deg=target_inclination_deg,
                inclination_tolerance_deg=inclination_tolerance_deg,
                min_inclination_deg=min_inclination_deg,
                max_inclination_deg=max_inclination_deg,
                allowed_categories=allowed_categories,
                deduplicate=True,
            )
            accepted_records = filter_res.accepted
            rejected_count = filter_res.rejected_count + filter_res.duplicate_count
        else:
            accepted_records = parsed_records
            rejected_count = 0

        data_age_sec = max(0.0, (now_utc() - fetched_at).total_seconds())
        for r in accepted_records:
            r.data_age_seconds = data_age_sec

        snapshot_id = None
        if db is not None:
            debris_repo = DebrisObjectRepository(db)
            snapshot_repo = DataSnapshotRepository(db)

            orm_objects = [
                DebrisObject(
                    norad_id=r.norad_id,
                    object_name=r.object_name,
                    object_id=r.object_id,
                    classification=r.classification,
                    element_format=r.element_format,
                    tle_line1=r.raw_tle_line1,
                    tle_line2=r.raw_tle_line2,
                    epoch=r.epoch,
                    inclination_deg=r.inclination_deg,
                    eccentricity=r.eccentricity,
                    raan_deg=r.raan_deg,
                    arg_perigee_deg=r.arg_perigee_deg,
                    mean_anomaly_deg=r.mean_anomaly_deg,
                    mean_motion_rev_per_day=r.mean_motion_rev_per_day,
                    bstar=r.bstar,
                    mean_motion_dot=r.mean_motion_dot,
                    mean_motion_ddot=r.mean_motion_ddot,
                    ephemeris_type=r.ephemeris_type,
                    element_set_no=r.element_set_number,
                    rev_at_epoch=r.revolution_number_at_epoch,
                    raw_source_payload=r.raw_source_record,
                    source=r.source,
                    fetched_at=r.fetched_at,
                    data_age_seconds=data_age_sec,
                )
                for r in accepted_records
            ]

            debris_repo.bulk_upsert(orm_objects)

            snapshot = DataSnapshot(
                source=effective_source,
                fetched_at=fetched_at,
                data_age_seconds=data_age_sec,
                object_count=len(accepted_records),
                cache_key=cache_key,
                status=SnapshotStatus.success.value,
                notes=(
                    f"Mode: {mode}. Seen: {total_seen}, Accepted: {len(accepted_records)}, "
                    f"Rejected: {rejected_count}"
                ),
            )
            saved_snapshot = snapshot_repo.create(snapshot)
            snapshot_id = saved_snapshot.id

        return IngestionResult(
            source=effective_source,
            mode=mode,
            fetched_at=fetched_at,
            data_age_seconds=data_age_sec,
            total_records_seen=total_seen,
            accepted_records=len(accepted_records),
            rejected_records=rejected_count,
            cache_key=cache_key,
            snapshot_id=snapshot_id,
            warnings=warnings,
            records=accepted_records,
        )
