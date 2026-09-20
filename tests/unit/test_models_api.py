"""Tests for model API endpoints."""


from fastapi.testclient import TestClient

from codeforge.apps.server.app import app


class TestModelsAPI:
    def setup_method(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_list_models(self) -> None:
        response = self.client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "count" in data

    def test_get_model_not_found(self) -> None:
        response = self.client.get("/v1/models/nonexistent")
        assert response.status_code == 404

    def test_get_model_status_not_found(self) -> None:
        response = self.client.get("/v1/models/nonexistent/status")
        assert response.status_code == 404

    def test_load_model_not_found(self) -> None:
        response = self.client.post("/v1/models/nonexistent/load")
        assert response.status_code == 404

    def test_unload_model_not_found(self) -> None:
        response = self.client.post("/v1/models/nonexistent/unload")
        assert response.status_code == 404

    def test_health_check(self) -> None:
        response = self.client.get("/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
