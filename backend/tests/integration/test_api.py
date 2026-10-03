"""Integration tests for FastAPI application entrypoint, health, and documentation endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


@pytest.fixture(scope="module")
def client():
    """Create a TestClient instance for testing API endpoints."""
    with TestClient(app) as test_client:
        yield test_client


def test_app_imports_successfully():
    """Test 1: FastAPI application imports successfully and has expected metadata."""
    assert app is not None
    assert app.title == "D-DATO API"
    assert app.version == "0.1.0"


def test_health_endpoint_returns_200_and_expected_payload(client: TestClient):
    """Test 2-5: GET /api/v1/health returns HTTP 200 with required keys and values."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    expected_payload = {
        "status": "ok",
        "service": "D-DATO",
        "version": "0.1.0",
        "environment": "development",
    }
    assert response.json() == expected_payload


def test_openapi_json_available(client: TestClient):
    """Test 6a: OpenAPI JSON schema endpoint is available and valid."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    assert "openapi" in schema
    assert schema["info"]["title"] == "D-DATO API"
    assert schema["info"]["version"] == "0.1.0"
    assert "/api/v1/health" in schema["paths"]


def test_docs_endpoints_available(client: TestClient):
    """Test 6b: Swagger UI /docs and ReDoc /redoc endpoints are accessible."""
    docs_res = client.get("/docs")
    assert docs_res.status_code == 200

    redoc_res = client.get("/redoc")
    assert redoc_res.status_code == 200


def test_root_endpoint(client: TestClient):
    """Test root endpoint provides service status and docs links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "D-DATO"
    assert data["status"] == "operational"
    assert data["health_url"] == "/api/v1/health"
