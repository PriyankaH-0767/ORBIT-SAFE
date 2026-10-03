"""Unit tests for local filesystem cache (FileSystemCache)."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest

from app.data.cache import CacheMetadata, FileSystemCache
from app.utils.time import now_utc


@pytest.fixture
def temp_cache(tmp_path: Path) -> FileSystemCache:
    """Fixture providing an isolated temporary FileSystemCache."""
    return FileSystemCache(base_dir=tmp_path / "cache_test")


def test_save_and_load_cache(temp_cache: FileSystemCache):
    """Verify persisting and retrieving payload with metadata."""
    payload = '{"test": "content", "objects": [1, 2, 3]}'
    key = "active_satellites_json"
    fetch_time = now_utc()

    meta = temp_cache.save(
        cache_key=key,
        content=payload,
        format="json",
        object_count=3,
        source="celestrak",
        fetched_at=fetch_time,
    )

    assert meta.cache_key == key
    assert meta.object_count == 3
    assert meta.byte_size == len(payload.encode("utf-8"))
    assert meta.format == "json"

    # Load back
    loaded = temp_cache.load(key)
    assert loaded is not None
    loaded_content, loaded_meta = loaded
    assert loaded_content == payload
    assert loaded_meta.object_count == 3
    assert loaded_meta.sha256 == meta.sha256


def test_cache_freshness_and_age(temp_cache: FileSystemCache):
    """Verify is_fresh check based on age threshold."""
    key = "fresh_test"
    now = now_utc()
    # Recently fetched (10 seconds ago)
    temp_cache.save(
        cache_key=key,
        content="data",
        format="tle",
        object_count=1,
        fetched_at=now - timedelta(seconds=10),
    )

    assert temp_cache.is_fresh(key, max_age_hours=2.0) is True

    # Stale entry (fetched 3 hours ago)
    stale_key = "stale_test"
    temp_cache.save(
        cache_key=stale_key,
        content="data",
        format="tle",
        object_count=1,
        fetched_at=now - timedelta(hours=3),
    )

    assert temp_cache.is_fresh(stale_key, max_age_hours=2.0) is False
    age_sec = temp_cache.get_age_seconds(stale_key)
    assert age_sec is not None
    assert age_sec >= 3 * 3600.0


def test_nonexistent_cache_entry(temp_cache: FileSystemCache):
    """Verify loading non-existent entry returns None."""
    assert temp_cache.load("nonexistent") is None
    assert temp_cache.get_metadata("nonexistent") is None
    assert temp_cache.get_age_seconds("nonexistent") is None
    assert temp_cache.is_fresh("nonexistent") is False


def test_corrupt_cache_metadata(temp_cache: FileSystemCache):
    """Verify gracefully handling corrupt metadata.json."""
    key = "corrupt_test"
    temp_cache.save(
        cache_key=key,
        content="data",
        format="json",
        object_count=1,
    )

    # Overwrite metadata.json with invalid JSON
    meta_path = temp_cache._get_entry_dir(key) / "metadata.json"
    meta_path.write_text("{corrupted_json", encoding="utf-8")

    assert temp_cache.load(key) is None
    assert temp_cache.get_metadata(key) is None


def test_missing_payload_file(temp_cache: FileSystemCache):
    """Verify handling when metadata exists but payload file is deleted."""
    key = "missing_payload"
    temp_cache.save(
        cache_key=key,
        content="data",
        format="json",
        object_count=1,
    )

    # Delete payload.json
    payload_path = temp_cache._get_entry_dir(key) / "payload.json"
    payload_path.unlink()

    assert temp_cache.load(key) is None


def test_cache_clear(temp_cache: FileSystemCache):
    """Verify clearing a specific cache key and clearing entire cache."""
    temp_cache.save("k1", "data1", "json", 1)
    temp_cache.save("k2", "data2", "json", 2)

    temp_cache.clear("k1")
    assert temp_cache.load("k1") is None
    assert temp_cache.load("k2") is not None

    temp_cache.clear()
    assert temp_cache.load("k2") is None
