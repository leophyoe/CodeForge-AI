"""Tests for runtime API endpoints and CLI commands."""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from codeforge.apps.server.app import app
from codeforge.cli import main


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestRuntimeAPI:
    def test_get_runtime(self, client: TestClient) -> None:
        response = client.get("/v1/runtime")
        assert response.status_code == 200
        data = response.json()
        assert "python" in data
        assert "pytorch" in data
        assert "backend_status" in data

    def test_get_runtime_has_python(self, client: TestClient) -> None:
        response = client.get("/v1/runtime")
        data = response.json()
        assert "version" in data["python"]
        assert "executable" in data["python"]

    def test_get_devices(self, client: TestClient) -> None:
        response = client.get("/v1/device")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "default_device" in data
        assert len(data["devices"]) >= 1

    def test_get_devices_has_cpu(self, client: TestClient) -> None:
        response = client.get("/v1/device")
        data = response.json()
        types = [d["type"] for d in data["devices"]]
        assert "cpu" in types

    def test_get_environment(self, client: TestClient) -> None:
        response = client.get("/v1/environment")
        assert response.status_code == 200
        data = response.json()
        assert "python" in data
        assert "environment" in data
        assert "packages" in data

    def test_get_environment_has_packages(self, client: TestClient) -> None:
        response = client.get("/v1/environment")
        data = response.json()
        assert "torch" in data["packages"]
        assert "numpy" in data["packages"]

    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestRuntimeCLI:
    def test_runtime_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["runtime"])
        assert result.exit_code == 0
        assert "Runtime" in result.output

    def test_device_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["device"])
        assert result.exit_code == 0
        assert "Devices" in result.output

    def test_doctor_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0
        assert "Diagnostics" in result.output
