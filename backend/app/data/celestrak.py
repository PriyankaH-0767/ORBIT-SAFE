"""CelesTrak General Perturbations (GP) element data client.

The CelesTrak GP API provides standardized orbital element datasets across:
- Modern OMM JSON (`FORMAT=json`)
- Modern OMM CSV (`FORMAT=csv`)
- Legacy TLE text (`FORMAT=tle`)

Specification Requirements:
- Base URL configurable, defaulting to https://celestrak.org/NORAD/elements/gp.php
- Explicit request timeout
- No infinite retries or aggressive retry loops
- Detect HTTP 200 success
- HTTP 301, 403, 404, 429, and 500-series responses immediately treated as failures
- Return typed result or raise clear domain-specific exceptions
- Do not log sensitive headers or credentials
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import time
from typing import Any, Dict, Optional

import httpx

from app.utils.time import now_utc

logger = logging.getLogger(__name__)

DEFAULT_CELESTRAK_BASE_URL: str = "https://celestrak.org/NORAD/elements/gp.php"
DEFAULT_TIMEOUT_SECONDS: float = 15.0
MAX_PAYLOAD_BYTES: int = 25 * 1024 * 1024  # 25 MB safety ceiling


class CelesTrakError(Exception):
    """Base exception for all CelesTrak operations."""
    pass


class CelesTrakHttpError(CelesTrakError):
    """Raised when CelesTrak responds with a non-200 status code."""

    def __init__(self, status_code: int, message: str, url: str):
        super().__init__(f"CelesTrak request to {url} failed with HTTP {status_code}: {message}")
        self.status_code = status_code
        self.url = url


class CelesTrakTimeoutError(CelesTrakError):
    """Raised when a request to CelesTrak times out."""
    pass


class CelesTrakConnectionError(CelesTrakError):
    """Raised when network connectivity fails."""
    pass


class CelesTrakPayloadTooLargeError(CelesTrakError):
    """Raised when response payload exceeds maximum allowable size."""
    pass


@dataclass(frozen=True)
class CelesTrakFetchResult:
    """Immutable result container for a successful CelesTrak API fetch."""
    content: str
    format: str
    status_code: int
    fetched_at: datetime
    duration_seconds: float
    request_url: str
    byte_size: int


class CelesTrakClient:
    """HTTP Client for querying CelesTrak General Perturbations (GP) endpoints."""

    def __init__(
        self,
        base_url: str = DEFAULT_CELESTRAK_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_payload_bytes: int = MAX_PAYLOAD_BYTES,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_payload_bytes = max_payload_bytes

    def build_query_params(
        self,
        group: Optional[str] = None,
        catnr: Optional[Union[str, int]] = None,
        name: Optional[str] = None,
        intdes: Optional[str] = None,
        format: str = "json",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Construct validated query parameters for CelesTrak GP API."""
        params: Dict[str, str] = {}
        if group:
            params["GROUP"] = str(group).strip()
        if catnr is not None:
            params["CATNR"] = str(catnr).strip()
        if name:
            params["NAME"] = str(name).strip()
        if intdes:
            params["INTDES"] = str(intdes).strip()

        # Format normalization
        fmt = format.lower().strip()
        if fmt in ("json", "csv", "tle"):
            params["FORMAT"] = fmt
        else:
            params["FORMAT"] = "json"

        if extra_params:
            for k, v in extra_params.items():
                if v is not None:
                    params[str(k).upper()] = str(v).strip()

        return params

    def fetch_gp_catalog(
        self,
        group: Optional[str] = "active",
        catnr: Optional[Union[str, int]] = None,
        format: str = "json",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> CelesTrakFetchResult:
        """Execute a synchronous HTTP GET request to CelesTrak GP endpoint with strict validation."""
        params = self.build_query_params(
            group=group,
            catnr=catnr,
            format=format,
            extra_params=extra_params,
        )

        headers = {
            "User-Agent": "D-DATO-DebrisPlanner/0.1.0 (academic/astrodynamics)",
            "Accept": "application/json, text/csv, text/plain, */*",
        }

        start_time = time.monotonic()
        fetched_at = now_utc()

        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                response = client.get(self.base_url, params=params, headers=headers)
        except httpx.TimeoutException as te:
            elapsed = time.monotonic() - start_time
            logger.error("CelesTrak request timed out after %.2fs for %s", elapsed, self.base_url)
            raise CelesTrakTimeoutError(f"CelesTrak request timed out after {elapsed:.2f}s.") from te
        except httpx.NetworkError as ne:
            elapsed = time.monotonic() - start_time
            logger.error("CelesTrak network error after %.2fs for %s: %s", elapsed, self.base_url, ne)
            raise CelesTrakConnectionError(f"CelesTrak network error: {ne}") from ne
        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error("Unexpected error contacting CelesTrak: %s", e)
            raise CelesTrakConnectionError(f"Failed to connect to CelesTrak: {e}") from e

        duration = time.monotonic() - start_time
        target_url = str(response.url)

        # Detect HTTP status
        if response.status_code != 200:
            logger.warning(
                "CelesTrak request failed. Status: %d, Elapsed: %.2fs, URL: %s",
                response.status_code,
                duration,
                target_url,
            )
            # Stop immediately without retries
            msg = response.text[:200] if response.text else "No response body"
            raise CelesTrakHttpError(status_code=response.status_code, message=msg, url=target_url)

        content = response.text
        byte_size = len(content.encode("utf-8"))

        if byte_size > self.max_payload_bytes:
            raise CelesTrakPayloadTooLargeError(
                f"Payload size ({byte_size} bytes) exceeds safety limit ({self.max_payload_bytes} bytes)."
            )

        logger.info(
            "CelesTrak fetch successful: format=%s, size=%d bytes, duration=%.2fs",
            params.get("FORMAT"),
            byte_size,
            duration,
        )

        return CelesTrakFetchResult(
            content=content,
            format=params.get("FORMAT", "json"),
            status_code=response.status_code,
            fetched_at=fetched_at,
            duration_seconds=duration,
            request_url=target_url,
            byte_size=byte_size,
        )

    async def fetch_gp_catalog_async(
        self,
        group: Optional[str] = "active",
        catnr: Optional[Union[str, int]] = None,
        format: str = "json",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> CelesTrakFetchResult:
        """Execute an asynchronous HTTP GET request to CelesTrak GP endpoint."""
        params = self.build_query_params(
            group=group,
            catnr=catnr,
            format=format,
            extra_params=extra_params,
        )

        headers = {
            "User-Agent": "D-DATO-DebrisPlanner/0.1.0 (academic/astrodynamics)",
            "Accept": "application/json, text/csv, text/plain, */*",
        }

        start_time = time.monotonic()
        fetched_at = now_utc()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=False) as client:
                response = await client.get(self.base_url, params=params, headers=headers)
        except httpx.TimeoutException as te:
            elapsed = time.monotonic() - start_time
            raise CelesTrakTimeoutError(f"CelesTrak async request timed out after {elapsed:.2f}s.") from te
        except httpx.NetworkError as ne:
            raise CelesTrakConnectionError(f"CelesTrak async network error: {ne}") from ne
        except Exception as e:
            raise CelesTrakConnectionError(f"Failed to connect to CelesTrak: {e}") from e

        duration = time.monotonic() - start_time
        target_url = str(response.url)

        if response.status_code != 200:
            msg = response.text[:200] if response.text else "No response body"
            raise CelesTrakHttpError(status_code=response.status_code, message=msg, url=target_url)

        content = response.text
        byte_size = len(content.encode("utf-8"))

        if byte_size > self.max_payload_bytes:
            raise CelesTrakPayloadTooLargeError(
                f"Payload size ({byte_size} bytes) exceeds safety limit ({self.max_payload_bytes} bytes)."
            )

        return CelesTrakFetchResult(
            content=content,
            format=params.get("FORMAT", "json"),
            status_code=response.status_code,
            fetched_at=fetched_at,
            duration_seconds=duration,
            request_url=target_url,
            byte_size=byte_size,
        )
