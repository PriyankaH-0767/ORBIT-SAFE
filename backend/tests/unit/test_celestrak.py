"""Unit tests for CelesTrakClient with mocked HTTP interactions.

Tests MUST NOT perform live network calls to CelesTrak.
"""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.data.celestrak import (
    CelesTrakClient,
    CelesTrakConnectionError,
    CelesTrakHttpError,
    CelesTrakPayloadTooLargeError,
    CelesTrakTimeoutError,
)


def test_build_query_params():
    """Verify query parameter normalization for CelesTrak GP endpoints."""
    client = CelesTrakClient()
    params = client.build_query_params(group="active", format="JSON")
    assert params["GROUP"] == "active"
    assert params["FORMAT"] == "json"

    # Specific catalog number query
    params_cat = client.build_query_params(catnr=25544, format="tle")
    assert params_cat["CATNR"] == "25544"
    assert params_cat["FORMAT"] == "tle"


def test_celestrak_http_200_success():
    """Verify successful response handling on HTTP 200."""
    client = CelesTrakClient(base_url="https://celestrak.org/NORAD/elements/gp.php")
    fake_json = '[{"OBJECT_NAME": "ISS", "NORAD_CAT_ID": 25544}]'

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.text = fake_json
    mock_resp.url = httpx.URL("https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json")

    with patch("httpx.Client.get", return_value=mock_resp):
        res = client.fetch_gp_catalog(group="active", format="json")

    assert res.status_code == 200
    assert res.content == fake_json
    assert res.format == "json"
    assert res.byte_size == len(fake_json.encode("utf-8"))
    assert res.duration_seconds >= 0.0


@pytest.mark.parametrize("status_code", [301, 403, 404, 429, 500, 503])
def test_celestrak_non_200_raises_http_error(status_code: int):
    """Verify non-200 responses immediately raise CelesTrakHttpError without retrying."""
    client = CelesTrakClient()

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.text = f"Error {status_code}"
    mock_resp.url = httpx.URL("https://celestrak.org/NORAD/elements/gp.php")

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        with pytest.raises(CelesTrakHttpError) as exc_info:
            client.fetch_gp_catalog(group="active")

        assert exc_info.value.status_code == status_code
        # Ensure only 1 attempt was made (no infinite/aggressive retry loop)
        assert mock_get.call_count == 1


def test_celestrak_timeout_handling():
    """Verify request timeouts raise CelesTrakTimeoutError."""
    client = CelesTrakClient(timeout_seconds=2.0)

    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Timed out")):
        with pytest.raises(CelesTrakTimeoutError, match="timed out"):
            client.fetch_gp_catalog(group="active")


def test_celestrak_connection_error_handling():
    """Verify network failures raise CelesTrakConnectionError."""
    client = CelesTrakClient()

    with patch("httpx.Client.get", side_effect=httpx.ConnectError("DNS resolution failed")):
        with pytest.raises(CelesTrakConnectionError, match="network error"):
            client.fetch_gp_catalog(group="active")


def test_celestrak_payload_too_large():
    """Verify exceeding max payload bytes raises CelesTrakPayloadTooLargeError."""
    client = CelesTrakClient(max_payload_bytes=100)

    huge_text = "X" * 200
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.text = huge_text
    mock_resp.url = httpx.URL("https://celestrak.org/test")

    with patch("httpx.Client.get", return_value=mock_resp):
        with pytest.raises(CelesTrakPayloadTooLargeError, match="exceeds safety limit"):
            client.fetch_gp_catalog(group="active")


@pytest.mark.anyio
async def test_celestrak_async_fetch():
    """Verify asynchronous fetch method."""
    client = CelesTrakClient()
    fake_json = '[{"OBJECT_NAME": "ISS"}]'

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.text = fake_json
    mock_resp.url = httpx.URL("https://celestrak.org/test")

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await client.fetch_gp_catalog_async(group="active")
        assert res.status_code == 200
        assert res.content == fake_json
