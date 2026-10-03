"""Local filesystem raw payload cache for CelesTrak and external catalog data.

Specification Requirements:
- Persist raw downloaded catalog payloads to local filesystem
- Save accompanying metadata:
  source, cache_key, fetched_at, format, byte_size, object_count, sha256, status
- Enforce cache freshness policy (e.g., default minimum fetch interval = 2 hours)
- Provide fallback to cached payload when remote service is unavailable
- Do not store secrets in cache metadata
- Directory structure:
  demo_data/cache/celestrak/<cache_key>/payload.<ext> and metadata.json
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from app.utils.time import ensure_utc, format_iso_utc, is_aware, now_utc, parse_iso_utc

logger = logging.getLogger(__name__)

# Default base directory: <repo_root>/demo_data/cache/celestrak
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "demo_data" / "cache" / "celestrak"


@dataclass
class CacheMetadata:
    """Metadata tracking raw cache file state and ingestion provenance."""
    source: str
    cache_key: str
    fetched_at: datetime
    format: str
    byte_size: int
    object_count: int
    sha256: str
    status: str = "success"

    def to_dict(self) -> dict:
        """Serialize metadata for storage in metadata.json."""
        return {
            "source": self.source,
            "cache_key": self.cache_key,
            "fetched_at": format_iso_utc(self.fetched_at),
            "format": self.format,
            "byte_size": self.byte_size,
            "object_count": self.object_count,
            "sha256": self.sha256,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CacheMetadata:
        """Deserialize metadata from dictionary representation."""
        fetched_at_str = data.get("fetched_at", "")
        dt = parse_iso_utc(fetched_at_str)
        return cls(
            source=str(data.get("source", "celestrak")),
            cache_key=str(data.get("cache_key", "default")),
            fetched_at=dt,
            format=str(data.get("format", "json")),
            byte_size=int(data.get("byte_size", 0)),
            object_count=int(data.get("object_count", 0)),
            sha256=str(data.get("sha256", "")),
            status=str(data.get("status", "success")),
        )


class FileSystemCache:
    """Manages raw catalog payloads and metadata stored on the local filesystem."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_CACHE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_key(self, key: str) -> str:
        """Sanitize cache key for safe filesystem path representation."""
        return "".join(c if (c.isalnum() or c in ("-", "_", ".")) else "_" for c in key).strip("_")

    def _get_entry_dir(self, cache_key: str) -> Path:
        """Return the directory path for a specific cache entry."""
        sanitized = self._sanitize_key(cache_key) or "default"
        return self.base_dir / sanitized

    def _get_payload_file(self, entry_dir: Path, fmt: str) -> Path:
        """Return payload file path based on data format."""
        ext = fmt.lower().strip()
        if ext == "json":
            return entry_dir / "payload.json"
        elif ext == "csv":
            return entry_dir / "payload.csv"
        elif ext in ("tle", "3le", "txt"):
            return entry_dir / "payload.tle"
        return entry_dir / "payload.dat"

    def save(
        self,
        cache_key: str,
        content: str,
        format: str,
        object_count: int,
        source: str = "celestrak",
        fetched_at: Optional[datetime] = None,
    ) -> CacheMetadata:
        """Persist payload text and metadata.json to disk."""
        entry_dir = self._get_entry_dir(cache_key)
        entry_dir.mkdir(parents=True, exist_ok=True)

        payload_bytes = content.encode("utf-8")
        byte_size = len(payload_bytes)
        sha256_hash = hashlib.sha256(payload_bytes).hexdigest()
        dt_fetched = ensure_utc(fetched_at) if fetched_at else now_utc()

        metadata = CacheMetadata(
            source=source,
            cache_key=cache_key,
            fetched_at=dt_fetched,
            format=format.lower().strip(),
            byte_size=byte_size,
            object_count=object_count,
            sha256=sha256_hash,
            status="success",
        )

        # Write payload
        payload_path = self._get_payload_file(entry_dir, format)
        payload_path.write_text(content, encoding="utf-8")

        # Write metadata
        metadata_path = entry_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")

        logger.info(
            "Saved cache for '%s': %d objects (%d bytes, sha256: %s)",
            cache_key,
            object_count,
            byte_size,
            sha256_hash[:8],
        )
        return metadata

    def load(self, cache_key: str) -> Optional[Tuple[str, CacheMetadata]]:
        """Load raw payload content and metadata if present and uncorrupted.

        Returns:
            Tuple of (payload_str, metadata) or None if missing/corrupt.
        """
        entry_dir = self._get_entry_dir(cache_key)
        metadata_path = entry_dir / "metadata.json"

        if not metadata_path.is_file():
            return None

        try:
            meta_dict = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata = CacheMetadata.from_dict(meta_dict)
        except Exception as e:
            logger.warning("Corrupt metadata in cache '%s': %s", cache_key, e)
            return None

        payload_path = self._get_payload_file(entry_dir, metadata.format)
        if not payload_path.is_file():
            # Try alternate fallback extensions
            for alt in entry_dir.glob("payload.*"):
                payload_path = alt
                break

        if not payload_path.is_file():
            logger.warning("Payload file missing in cache '%s'", cache_key)
            return None

        try:
            content = payload_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read payload from '%s': %s", payload_path, e)
            return None

        return content, metadata

    def get_metadata(self, cache_key: str) -> Optional[CacheMetadata]:
        """Retrieve only the metadata for a cache entry without reading full payload."""
        entry_dir = self._get_entry_dir(cache_key)
        metadata_path = entry_dir / "metadata.json"
        if not metadata_path.is_file():
            return None
        try:
            meta_dict = json.loads(metadata_path.read_text(encoding="utf-8"))
            return CacheMetadata.from_dict(meta_dict)
        except Exception:
            return None

    def get_age_seconds(self, cache_key: str) -> Optional[float]:
        """Compute the elapsed age in seconds since the cache was fetched."""
        meta = self.get_metadata(cache_key)
        if meta is None:
            return None
        now = now_utc()
        age = (now - meta.fetched_at).total_seconds()
        return max(0.0, age)

    def is_fresh(self, cache_key: str, max_age_hours: float = 2.0) -> bool:
        """Check whether the cached entry exists and is within the freshness interval."""
        age_seconds = self.get_age_seconds(cache_key)
        if age_seconds is None:
            return False
        max_age_seconds = max_age_hours * 3600.0
        return age_seconds <= max_age_seconds

    def clear(self, cache_key: Optional[str] = None) -> None:
        """Delete cache entries for a specific key, or entire cache directory."""
        if cache_key is not None:
            entry_dir = self._get_entry_dir(cache_key)
            if entry_dir.is_dir():
                for f in entry_dir.iterdir():
                    f.unlink()
                entry_dir.rmdir()
        else:
            if self.base_dir.is_dir():
                for sub in self.base_dir.iterdir():
                    if sub.is_dir():
                        for f in sub.iterdir():
                            f.unlink()
                        sub.rmdir()
                    elif sub.is_file():
                        sub.unlink()
