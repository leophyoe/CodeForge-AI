"""Comprehensive API endpoint tests for CodeForge AI."""

from __future__ import annotations

from starlette.testclient import TestClient

from codeforge.api import create_app
from codeforge.api.config import APIConfig, AppConfig, CORSConfig, RateLimitConfig


def _make_app():
    config = AppConfig(
        api=APIConfig(docs_enabled=True, auth_required=False),
        rate_limit=RateLimitConfig(enabled=False),
    )
    return create_app(config)


def _make_app_no_docs():
    config = AppConfig(
        api=APIConfig(docs_enabled=False, auth_required=False),
        rate_limit=RateLimitConfig(enabled=False),
    )
    return create_app(config)


def _make_app_with_cors():
    config = AppConfig(
        api=APIConfig(docs_enabled=True, auth_required=False),
        cors=CORSConfig(enabled=True, allowed_origins=["http://example.com"]),
        rate_limit=RateLimitConfig(enabled=False),
    )
    return create_app(config)


def _make_app_with_rate_limit():
    config = AppConfig(
        api=APIConfig(docs_enabled=True, auth_required=False),
        rate_limit=RateLimitConfig(enabled=True, requests_per_minute=3),
    )
    return create_app(config)


# ── Application Creation ──────────────────────────────────────────────────


class TestApplicationCreation:
    def test_create_app(self) -> None:
        app = _make_app()
        assert app is not None
        assert app.title == "CodeForge AI"
        assert app.version == "0.1.0"

    def test_create_app_no_docs(self) -> None:
        app = _make_app_no_docs()
        client = TestClient(app, raise_server_exceptions=False)
        assert app.docs_url is None
        assert app.redoc_url is None
        response = client.get("/docs")
        assert response.status_code == 404


# ── Health Endpoint ───────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_ok(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_has_version(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/health")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_has_timestamp(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/health")
        data = response.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    def test_health_has_request_id(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0


# ── Readiness Endpoint ────────────────────────────────────────────────────


class TestReadinessEndpoint:
    def test_ready_returns_not_ready(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_ready"

    def test_ready_has_model_count(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/ready")
        data = response.json()
        assert "loaded_models" in data
        assert isinstance(data["loaded_models"], int)
        assert data["loaded_models"] == 0


# ── System Endpoint ───────────────────────────────────────────────────────


class TestSystemEndpoint:
    def test_system_returns_info(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/system")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "platform" in data
        assert "architecture" in data
        assert "python_version" in data

    def test_system_no_secrets(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/system")
        data = response.json()
        full_text = str(data)
        assert "/home/" not in full_text
        assert "~/" not in full_text
        assert "root" not in full_text.lower() or "root" not in full_text


# ── Hardware Endpoint ─────────────────────────────────────────────────────


class TestHardwareEndpoint:
    def test_hardware_returns_info(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/hardware")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "os" in data or "cpu" in data

    def test_hardware_summary(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/hardware/summary")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_hardware_compatibility(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/hardware/compatibility")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


# ── Runtime Endpoint ──────────────────────────────────────────────────────


class TestRuntimeEndpoint:
    def test_runtime_returns_info(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/runtime")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


# ── Models Endpoint ───────────────────────────────────────────────────────


class TestModelsEndpoint:
    def test_list_models(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    def test_get_model_not_found(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/models/nonexistent")
        assert response.status_code == 404

    def test_model_status(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/models/nonexistent/status")
        assert response.status_code == 200
        data = response.json()
        assert "model_id" in data
        assert "status" in data


# ── Model Load / Unload ──────────────────────────────────────────────────


class TestModelLoadUnload:
    def test_load_model_not_found(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/models/nonexistent/load",
            json={"device": "auto", "dtype": "auto", "force": False},
        )
        assert response.status_code in (404, 500)

    def test_unload_model_not_found(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post("/v1/models/nonexistent/unload")
        assert response.status_code in (404, 500)

    def test_load_model_path_traversal(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/models/../../etc/passwd/load",
            json={"device": "auto", "dtype": "auto", "force": False},
        )
        assert response.status_code in (400, 404, 422)


# ── Generation Endpoint ──────────────────────────────────────────────────


class TestGenerationEndpoint:
    def test_chat_model_not_loaded(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat",
            json={
                "model": "nonexistent-model",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 409

    def test_chat_empty_messages(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat",
            json={"model": "nonexistent-model", "messages": []},
        )
        assert response.status_code == 422

    def test_chat_invalid_model_id(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat",
            json={
                "model": "../etc/passwd",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 422

    def test_completions_model_not_loaded(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/completions",
            json={"model": "nonexistent-model", "prompt": "hello"},
        )
        assert response.status_code == 409

    def test_completions_empty_prompt(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/completions",
            json={"model": "nonexistent-model", "prompt": ""},
        )
        assert response.status_code == 422

    def test_chat_validation_temperature(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 5.0,
            },
        )
        assert response.status_code == 422

    def test_chat_validation_max_tokens(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hello"}],
                "max_new_tokens": 0,
            },
        )
        assert response.status_code == 422


# ── Embeddings Endpoint ──────────────────────────────────────────────────


class TestEmbeddingsEndpoint:
    def test_embeddings_returns_embedding(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/embeddings",
            json={"text": "hello", "model": "test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "embedding" in data
        assert "dimension" in data

    def test_embeddings_batch(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/embeddings/batch",
            json={"texts": ["hello", "world"], "model": "test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "embeddings" in data
        assert data["count"] == 2

    def test_embeddings_health(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/embeddings/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_embeddings_config(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/embeddings/config")
        assert response.status_code == 200
        data = response.json()
        assert "provider" in data
        assert "dimension" in data


# ── OpenAI Compatible Endpoints ──────────────────────────────────────────


class TestOpenAICompatEndpoints:
    def test_oai_chat_completions(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "nonexistent-model",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 409

    def test_oai_chat_completions_model_not_loaded(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "nonexistent-model",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

    def test_oai_completions(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/completions",
            json={"model": "nonexistent-model", "prompt": "hello"},
        )
        assert response.status_code == 409

    def test_oai_list_models(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))


# ── Request ID ────────────────────────────────────────────────────────────


class TestRequestID:
    def test_request_id_generated(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    def test_request_id_passed_through(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        custom_id = "test-req-id-12345"
        response = client.get("/v1/health", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id


# ── Security Headers ─────────────────────────────────────────────────────


class TestSecurityHeaders:
    def test_security_headers(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ── CORS ──────────────────────────────────────────────────────────────────


class TestCORS:
    def test_cors_disabled_by_default(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get(
            "/v1/health",
            headers={"Origin": "http://example.com"},
        )
        assert "access-control-allow-origin" not in {
            k.lower() for k in response.headers
        }

    def test_cors_enabled(self) -> None:
        client = TestClient(_make_app_with_cors(), raise_server_exceptions=False)
        response = client.options(
            "/v1/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://example.com"


# ── Rate Limiting ─────────────────────────────────────────────────────────


class TestRateLimiting:
    def test_rate_limit_skips_health(self) -> None:
        app = _make_app_with_rate_limit()
        client = TestClient(app, raise_server_exceptions=False)
        responses = [client.get("/v1/health") for _ in range(20)]
        non_200 = [r for r in responses if r.status_code != 200]
        rate_limited = [r for r in responses if r.status_code == 429]
        assert len(rate_limited) == 0, (
            f"Health endpoint should not be rate limited, got {len(rate_limited)} 429s"
        )
        for r in non_200:
            assert r.status_code != 429


# ── Path Traversal ────────────────────────────────────────────────────────


class TestPathTraversal:
    def test_path_traversal_models(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/models/..%2F..%2Fetc/passwd")
        assert response.status_code in (400, 404)

    def test_absolute_path_model_id(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/models/%2Fetc%2Fpasswd")
        assert response.status_code in (400, 404)


# ── Error Format ──────────────────────────────────────────────────────────


class TestErrorFormat:
    def test_error_response_format(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/models/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
