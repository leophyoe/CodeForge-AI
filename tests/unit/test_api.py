"""Comprehensive API endpoint tests for CodeForge AI."""

from __future__ import annotations

from starlette.testclient import TestClient

from codeforge.api import create_app
from codeforge.api.config import APIConfig, AppConfig, CORSConfig, RateLimitConfig
from codeforge.api.middleware import _WindowEntry


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
        assert "access-control-allow-origin" not in {k.lower() for k in response.headers}

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
        # Pre-fix every request to a rate-limited app returned 500; the old
        # assertion only excluded 429s, which let the 500s slip through.
        statuses = [r.status_code for r in responses]
        assert statuses == [200] * 20, f"health must stay 200, got {statuses}"


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


# ── Rate Limit Regressions (Phase 1–10 audit) ─────────────────────────────


class TestRateLimitRegression:
    """Pre-fix, RateLimitMiddleware lacked an `app` parameter and raised
    exceptions from dispatch (which bypass FastAPI's ExceptionMiddleware) —
    every request to a rate-limited app returned 500, never 429."""

    def test_default_config_app_serves_200(self) -> None:
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        for path in ("/v1/health", "/v1/models", "/v1/system", "/v1/tools"):
            response = client.get(path)
            assert response.status_code == 200, f"{path} -> {response.status_code}"

    def test_burst_returns_429_not_500(self) -> None:
        app = _make_app_with_rate_limit()
        client = TestClient(app, raise_server_exceptions=False)
        statuses = [client.get("/v1/models").status_code for _ in range(5)]
        assert statuses == [200, 200, 200, 429, 429]
        assert 500 not in statuses

    def test_429_body_and_retry_after(self) -> None:
        app = _make_app_with_rate_limit()
        client = TestClient(app, raise_server_exceptions=False)
        response = None
        for _ in range(4):
            response = client.get("/v1/models")
        assert response is not None
        assert response.status_code == 429
        body = response.json()
        assert body["error"]["code"] == "rate_limit_exceeded"
        assert "Retry-After" in response.headers
        assert int(response.headers["Retry-After"]) >= 0

    def test_429_has_request_id_and_security_headers(self) -> None:
        # RateLimit must sit innermost so its 429 passes through RequestID
        # and SecurityHeaders middlewares on the way out.
        app = _make_app_with_rate_limit()
        client = TestClient(app, raise_server_exceptions=False)
        headers = {"X-Request-ID": "rl-corr-42"}
        response = None
        for _ in range(4):
            response = client.get("/v1/models", headers=headers)
        assert response is not None
        assert response.status_code == 429
        assert response.headers["X-Request-ID"] == "rl-corr-42"
        assert response.json()["error"]["request_id"] == "rl-corr-42"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_client_table_bounded(self, monkeypatch) -> None:
        import time as time_mod
        from collections import deque

        from codeforge.api.middleware import RateLimitMiddleware

        async def _noop_app(scope, receive, send):  # noqa: ARG001
            return None

        monkeypatch.setattr(RateLimitMiddleware, "_MAX_CLIENTS", 5)
        mw = RateLimitMiddleware(_noop_app, requests_per_minute=100)
        now = time_mod.monotonic()

        # Expired windows are dropped when over the cap (X-Forwarded-For
        # is client-controlled, so the table must not grow without bound).
        for i in range(10):
            mw._clients[f"10.0.0.{i}"] = deque(  # noqa: SLF001
                [_WindowEntry(timestamp=now - 3600.0)]
            )
        mw._prune_clients(now)  # noqa: SLF001
        assert len(mw._clients) == 0  # noqa: SLF001

        # Active windows: cap enforced by dropping oldest entries.
        for i in range(10):
            mw._clients[f"10.1.0.{i}"] = deque(  # noqa: SLF001
                [_WindowEntry(timestamp=now)]
            )
        mw._prune_clients(now)  # noqa: SLF001
        assert len(mw._clients) <= 5  # noqa: SLF001


# ── Auth Regressions (Phase 1–10 audit) ───────────────────────────────────


class TestAuthRegression:
    """verify_api_key existed but was never wired into any router, and the
    old body failed open (missing key -> allow)."""

    @staticmethod
    def _make_auth_app(api_key: str = "s3cret"):
        config = AppConfig(
            api=APIConfig(docs_enabled=True, auth_required=True, api_key=api_key),
            rate_limit=RateLimitConfig(enabled=False),
        )
        return create_app(config)

    def test_missing_key_401(self) -> None:
        client = TestClient(self._make_auth_app(), raise_server_exceptions=False)
        response = client.get("/v1/models")
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["code"] == "authentication_required"
        assert body["error"]["request_id"]

    def test_wrong_key_401(self) -> None:
        client = TestClient(self._make_auth_app(), raise_server_exceptions=False)
        response = client.get("/v1/models", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "authentication_required"

    def test_correct_key_200(self) -> None:
        client = TestClient(self._make_auth_app(), raise_server_exceptions=False)
        response = client.get("/v1/models", headers={"X-API-Key": "s3cret"})
        assert response.status_code == 200

    def test_health_exempt_from_auth(self) -> None:
        client = TestClient(self._make_auth_app(), raise_server_exceptions=False)
        response = client.get("/v1/health")
        assert response.status_code == 200

    def test_fail_closed_when_no_key_configured(self, monkeypatch) -> None:
        monkeypatch.delenv("CODEFORGE_API_KEY", raising=False)
        client = TestClient(self._make_auth_app(api_key=""), raise_server_exceptions=False)
        assert client.get("/v1/models").status_code == 401
        # Health probe still works even when auth is misconfigured.
        assert client.get("/v1/health").status_code == 200

    def test_auth_off_by_default(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        assert client.get("/v1/models").status_code == 200


# ── Error Request-ID Correlation ──────────────────────────────────────────


class TestErrorCorrelation:
    def test_api_error_request_id_matches_header(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "../../etc/passwd",
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers={"X-Request-ID": "corr-99"},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "path_traversal"
        assert body["error"]["request_id"] == "corr-99"
        assert response.headers["X-Request-ID"] == "corr-99"

    def test_generated_error_request_id_is_uuid(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "../../etc/passwd",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert response.status_code == 400
        request_id = response.json()["error"]["request_id"]
        assert len(request_id) >= 16
        assert response.headers["X-Request-ID"] == request_id


# ── Models List Shape (OpenAI-compatible) ─────────────────────────────────


class TestListModelsShape:
    def test_openai_list_shape(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)
        for item in data["data"]:
            assert item["object"] == "model"
            assert "id" in item
            assert "created" in item


# ── Search Result Mapping (file_path regression) ──────────────────────────


class TestSearchMappingRegression:
    def test_search_maps_relative_path(self, monkeypatch) -> None:
        from codeforge.packages.search.hybrid import HybridSearch
        from codeforge.packages.search.models import SearchResult

        def fake_search(self, query, chunks=None, symbols=None):  # noqa: ARG001
            return [
                SearchResult(
                    chunk_id="c1",
                    content="def main():",
                    score=0.95,
                    relative_path="src/app.py",
                    symbol_name="main",
                )
            ]

        monkeypatch.setattr(HybridSearch, "search", fake_search)
        client = TestClient(_make_app(), raise_server_exceptions=False)
        response = client.post(
            "/v1/search",
            json={"workspace_id": "ws-1", "query": "main", "mode": "lexical"},
        )
        assert response.status_code == 200
        items = response.json()["results"]
        assert len(items) == 1
        assert items[0]["file_path"] == "src/app.py"
        assert items[0]["symbol_name"] == "main"
