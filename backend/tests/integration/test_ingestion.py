"""Integration tests for catalog IngestionService and fallback pipeline.

Requirements:
- Tests MUST NOT perform live network requests.
- Verify fallback chain: LIVE -> CACHE -> DEMO -> FAILURE.
- Verify database idempotence and DataSnapshot creation.
- Verify 2-hour minimum fetch rate-limit policy.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.cache import FileSystemCache
from app.data.celestrak import (
    CelesTrakClient,
    CelesTrakConnectionError,
    CelesTrakFetchResult,
)
from app.db.models import DataSnapshot, DebrisObject
from app.db.repositories import DataSnapshotRepository, DebrisObjectRepository
from app.services.ingestion_service import IngestionResult, IngestionService
from app.utils.time import now_utc

SAMPLE_OMM_JSON = """[
  {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "NORAD_CAT_ID": 25544,
    "CLASSIFICATION_TYPE": "U",
    "EPOCH": "2026-01-01T12:00:00.000000Z",
    "MEAN_MOTION": 15.50000000,
    "ECCENTRICITY": 0.0005000,
    "INCLINATION": 51.6400,
    "RA_OF_ASC_NODE": 208.1000,
    "ARG_OF_PERICENTER": 120.0000,
    "MEAN_ANOMALY": 240.0000
  },
  {
    "OBJECT_NAME": "MODERN DEBRIS 6-DIGIT",
    "OBJECT_ID": "2026-999A",
    "NORAD_CAT_ID": 700001,
    "CLASSIFICATION_TYPE": "U",
    "EPOCH": "2026-01-01T12:00:00.000000Z",
    "MEAN_MOTION": 15.10000000,
    "ECCENTRICITY": 0.0008000,
    "INCLINATION": 97.4000,
    "RA_OF_ASC_NODE": 50.0000,
    "ARG_OF_PERICENTER": 95.0000,
    "MEAN_ANOMALY": 200.0000
  }
]"""


@pytest.fixture
def isolated_cache(tmp_path: Path) -> FileSystemCache:
    """Fixture providing an isolated filesystem cache."""
    return FileSystemCache(base_dir=tmp_path / "test_ingestion_cache")


def test_successful_live_fetch_populates_cache_and_db(
    db_session: Session,
    isolated_cache: FileSystemCache,
):
    """Verify live fetch writes to cache and idempotently persists records to database."""
    client = CelesTrakClient()
    fetch_time = now_utc()
    mock_res = CelesTrakFetchResult(
        content=SAMPLE_OMM_JSON,
        format="json",
        status_code=200,
        fetched_at=fetch_time,
        duration_seconds=0.25,
        request_url="https://celestrak.org/NORAD/elements/gp.php",
        byte_size=len(SAMPLE_OMM_JSON.encode("utf-8")),
    )

    with patch.object(client, "fetch_gp_catalog", return_value=mock_res) as mock_fetch:
        service = IngestionService(celestrak_client=client, cache=isolated_cache)
        result: IngestionResult = service.ingest_catalog(
            db=db_session,
            source="celestrak",
            group="active",
            format="json",
            apply_filter=False,
        )

        assert mock_fetch.call_count == 1
        assert result.mode == "live"
        assert result.total_records_seen == 2
        assert result.accepted_records == 2
        assert result.snapshot_id is not None

        # Verify DB records
        debris_repo = DebrisObjectRepository(db_session)
        iss = debris_repo.get_by_norad_id("25544", source="celestrak")
        assert iss is not None
        assert iss.object_name == "ISS (ZARYA)"

        deb6 = debris_repo.get_by_norad_id("700001", source="celestrak")
        assert deb6 is not None
        assert deb6.norad_id == "700001"
        assert deb6.element_format == "omm"

        # Verify DataSnapshot
        snapshot_repo = DataSnapshotRepository(db_session)
        snap = snapshot_repo.get_latest_by_source("celestrak")
        assert snap is not None
        assert snap.id == result.snapshot_id
        assert snap.object_count == 2
        assert snap.status == "success"

        # Verify filesystem cache was populated
        cached = isolated_cache.load(result.cache_key)
        assert cached is not None


def test_fresh_cache_avoids_network(
    db_session: Session,
    isolated_cache: FileSystemCache,
):
    """Verify when fresh cache exists, network is never called."""
    client = CelesTrakClient()
    service = IngestionService(celestrak_client=client, cache=isolated_cache)
    cache_key = service._generate_cache_key("celestrak", "active", "json")

    # Seed fresh cache (fetched 5 minutes ago)
    isolated_cache.save(
        cache_key=cache_key,
        content=SAMPLE_OMM_JSON,
        format="json",
        object_count=2,
        source="celestrak",
        fetched_at=now_utc() - timedelta(minutes=5),
    )

    with patch.object(client, "fetch_gp_catalog") as mock_fetch:
        res = service.ingest_catalog(
            db=db_session,
            source="celestrak",
            group="active",
            format="json",
            apply_filter=False,
        )

        # Network MUST NOT be called
        mock_fetch.assert_not_called()
        assert res.mode == "cache"
        assert res.accepted_records == 2


def test_force_refresh_respects_minimum_fetch_interval(
    db_session: Session,
    isolated_cache: FileSystemCache,
):
    """Verify force_refresh cannot bypass the 2-hour minimum fetch interval safety policy."""
    client = CelesTrakClient()
    service = IngestionService(celestrak_client=client, cache=isolated_cache, min_fetch_interval_hours=2.0)
    cache_key = service._generate_cache_key("celestrak", "active", "json")

    # Seed recent cache (10 minutes old)
    isolated_cache.save(
        cache_key=cache_key,
        content=SAMPLE_OMM_JSON,
        format="json",
        object_count=2,
        source="celestrak",
        fetched_at=now_utc() - timedelta(minutes=10),
    )

    with patch.object(client, "fetch_gp_catalog") as mock_fetch:
        res = service.ingest_catalog(
            db=db_session,
            source="celestrak",
            group="active",
            format="json",
            force_refresh=True,
            apply_filter=False,
        )

        # Should NOT make network call because 2 hours have not passed
        mock_fetch.assert_not_called()
        assert res.mode == "cache"
        assert any("rate limit" in w.lower() for w in res.warnings)


def test_network_failure_falls_back_to_cache(
    db_session: Session,
    isolated_cache: FileSystemCache,
):
    """Verify network exception falls back to available cache with warning."""
    client = CelesTrakClient()
    service = IngestionService(celestrak_client=client, cache=isolated_cache)
    cache_key = service._generate_cache_key("celestrak", "active", "json")

    # Seed stale cache (3 hours old)
    isolated_cache.save(
        cache_key=cache_key,
        content=SAMPLE_OMM_JSON,
        format="json",
        object_count=2,
        source="celestrak",
        fetched_at=now_utc() - timedelta(hours=3),
    )

    with patch.object(client, "fetch_gp_catalog", side_effect=CelesTrakConnectionError("Connection lost")):
        res = service.ingest_catalog(
            db=db_session,
            source="celestrak",
            group="active",
            format="json",
            apply_filter=False,
        )

        assert res.mode == "cache"
        assert res.accepted_records == 2
        assert any("Network fetch failed" in w for w in res.warnings)


def test_offline_mode_no_cache_falls_back_to_demo_data(
    db_session: Session,
    isolated_cache: FileSystemCache,
):
    """Verify that when remote service is unavailable and no cache exists, bundled demo data is loaded."""
    client = CelesTrakClient()
    service = IngestionService(celestrak_client=client, cache=isolated_cache)

    with patch.object(client, "fetch_gp_catalog", side_effect=CelesTrakConnectionError("Network down")):
        res = service.ingest_catalog(
            db=db_session,
            source="celestrak",
            group="active",
            format="json",
            apply_filter=False,
        )

        assert res.mode == "demo"
        assert res.source == "demo"
        assert res.accepted_records >= 4
        assert any("offline demo" in w.lower() for w in res.warnings)

        # Verify demo objects in DB
        debris_repo = DebrisObjectRepository(db_session)
        demo_objs = db_session.scalars(select(DebrisObject).where(DebrisObject.source == "demo")).all()
        assert len(list(demo_objs)) >= 4


def test_ingestion_idempotence(
    db_session: Session,
    isolated_cache: FileSystemCache,
):
    """Verify repeated ingestion of same data updates existing rows without duplicating."""
    client = CelesTrakClient()
    service = IngestionService(celestrak_client=client, cache=isolated_cache)
    cache_key = service._generate_cache_key("celestrak", "active", "json")

    isolated_cache.save(
        cache_key=cache_key,
        content=SAMPLE_OMM_JSON,
        format="json",
        object_count=2,
        source="celestrak",
    )

    # First ingestion
    service.ingest_catalog(db=db_session, source="celestrak", group="active", format="json", apply_filter=False)
    count_1 = len(list(db_session.scalars(select(DebrisObject)).all()))
    assert count_1 == 2

    # Second ingestion
    service.ingest_catalog(db=db_session, source="celestrak", group="active", format="json", apply_filter=False)
    count_2 = len(list(db_session.scalars(select(DebrisObject)).all()))
    # Idempotent: must still be exactly 2 rows
    assert count_2 == 2
