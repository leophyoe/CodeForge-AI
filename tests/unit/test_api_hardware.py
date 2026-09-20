"""Tests for the FastAPI hardware endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from codeforge.apps.server.app import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHardwareEndpoint:
    def test_get_hardware(self, client: TestClient) -> None:
        response = client.get("/v1/hardware")
        assert response.status_code == 200
        data = response.json()
        assert "os" in data
        assert "cpu" in data
        assert "ram" in data
        assert "gpu" in data
        assert "disk" in data
        assert "pytorch" in data
        assert "acceleration_backend" in data

    def test_get_hardware_os(self, client: TestClient) -> None:
        response = client.get("/v1/hardware")
        data = response.json()
        assert data["os"] in ("Linux", "Windows", "Darwin")

    def test_get_hardware_cpu(self, client: TestClient) -> None:
        response = client.get("/v1/hardware")
        data = response.json()
        assert "model" in data["cpu"]
        assert "cores_logical" in data["cpu"]

    def test_get_hardware_summary(self, client: TestClient) -> None:
        response = client.get("/v1/hardware/summary")
        assert response.status_code == 200
        data = response.json()
        assert "system" in data
        assert "cpu" in data
        assert "ram" in data

    def test_get_compatibility(self, client: TestClient) -> None:
        response = client.get("/v1/hardware/compatibility")
        assert response.status_code == 200
        data = response.json()
        assert "compatible" in data
        assert "issues" in data
        assert "warnings" in data

    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
