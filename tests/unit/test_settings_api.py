"""Tests for provider settings API (API key management for the web UI)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codeforge.api.config import APIConfig, AppConfig, RateLimitConfig
from codeforge.packages.models.remote import (
    clear_remote_settings_cache,
    list_remote_models,
    reset_remote_providers,
)

_ENV_KEYS = (
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_BASE_URL",
    "GEMINI_BASE_URL",
    "CODEFORGE_OPENAI_API_KEY",
    "CODEFORGE_GEMINI_API_KEY",
)


@pytest.fixture(autouse=True)
def _settings_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from codeforge.api.dependencies import reset_singletons

    monkeypatch.chdir(tmp_path)
    saved = {key: os.environ.get(key) for key in _ENV_KEYS}
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    clear_remote_settings_cache()
    reset_remote_providers()
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    clear_remote_settings_cache()
    reset_remote_providers()
    reset_singletons()


def _client() -> TestClient:
    from codeforge.api.app import create_app

    config = AppConfig(
        api=APIConfig(docs_enabled=True, auth_required=False),
        rate_limit=RateLimitConfig(enabled=False),
    )
    return TestClient(create_app(config))


class TestGetProviderSettings:
    def test_default_not_configured(self) -> None:
        response = _client().get("/v1/settings/providers")
        assert response.status_code == 200
        providers = response.json()["providers"]
        assert [p["provider"] for p in providers] == ["openai", "gemini"]
        for p in providers:
            assert p["configured"] is False
            assert p["key_masked"] == ""
            assert p["key_env"].endswith("_API_KEY")

    def test_env_key_detected_masked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abcd1234efgh5678")
        clear_remote_settings_cache()
        providers = _client().get("/v1/settings/providers").json()["providers"]
        openai = next(p for p in providers if p["provider"] == "openai")
        assert openai["configured"] is True
        assert openai["key_masked"] == "sk-...5678"
        assert "sk-abcd1234efgh5678" not in str(providers)


class TestUpdateProviderSettings:
    def test_save_openai_key_persists_and_lists(self) -> None:
        client = _client()
        response = client.put(
            "/v1/settings/providers",
            json={"provider": "openai", "api_key": "sk-supersecret123456"},
        )
        assert response.status_code == 200
        body_text = response.text
        assert "sk-supersecret123456" not in body_text

        env_file = Path(".env")
        assert env_file.exists()
        assert "OPENAI_API_KEY=sk-supersecret123456" in env_file.read_text()
        assert env_file.stat().st_mode & 0o777 == 0o600

        providers = client.get("/v1/settings/providers").json()["providers"]
        openai = next(p for p in providers if p["provider"] == "openai")
        assert openai["configured"] is True
        assert openai["key_masked"] == "sk-...3456"

        ids = [m["model_id"] for m in list_remote_models()]
        assert ids == ["openai:gpt-4o-mini", "openai:gpt-4o"]

    def test_save_gemini_key(self) -> None:
        client = _client()
        response = client.put(
            "/v1/settings/providers",
            json={"provider": "gemini", "api_key": "AIzaFakeKey1234567"},
        )
        assert response.status_code == 200
        providers = response.json()["providers"]
        gemini = next(p for p in providers if p["provider"] == "gemini")
        assert gemini["configured"] is True
        assert "AIzaFakeKey1234567" not in response.text
        ids = [m["model_id"] for m in list_remote_models()]
        assert any(i.startswith("gemini:") for i in ids)

    def test_save_base_url(self) -> None:
        client = _client()
        response = client.put(
            "/v1/settings/providers",
            json={
                "provider": "openai",
                "base_url": "http://127.0.0.1:9000/v1",
            },
        )
        assert response.status_code == 200
        openai = next(p for p in response.json()["providers"] if p["provider"] == "openai")
        assert openai["base_url"] == "http://127.0.0.1:9000/v1"
        assert os.environ["OPENAI_BASE_URL"] == "http://127.0.0.1:9000/v1"
        assert "OPENAI_BASE_URL=http://127.0.0.1:9000/v1" in Path(".env").read_text()

    def test_clear_key(self) -> None:
        client = _client()
        client.put(
            "/v1/settings/providers",
            json={"provider": "openai", "api_key": "sk-toberemoved1234"},
        )
        assert Path(".env").exists()
        response = client.put(
            "/v1/settings/providers",
            json={"provider": "openai", "clear": True},
        )
        assert response.status_code == 200
        openai = next(p for p in response.json()["providers"] if p["provider"] == "openai")
        assert openai["configured"] is False
        assert "OPENAI_API_KEY" not in Path(".env").read_text()
        assert "OPENAI_API_KEY" not in os.environ
        assert list_remote_models() == []

    def test_clear_preserves_other_lines(self) -> None:
        Path(".env").write_text("OTHER_VAR=keep-me\nOPENAI_API_KEY=sk-old\n")
        client = _client()
        client.put(
            "/v1/settings/providers",
            json={"provider": "openai", "clear": True},
        )
        content = Path(".env").read_text()
        assert "OTHER_VAR=keep-me" in content
        assert "OPENAI_API_KEY" not in content

    def test_invalid_provider(self) -> None:
        response = _client().put(
            "/v1/settings/providers",
            json={"provider": "mistral", "api_key": "x" * 8},
        )
        assert response.status_code == 422
        assert "unknown provider" in str(response.json()["detail"])

    def test_short_key_rejected(self) -> None:
        response = _client().put(
            "/v1/settings/providers",
            json={"provider": "openai", "api_key": "short"},
        )
        assert response.status_code == 422

    def test_newline_in_key_rejected(self) -> None:
        response = _client().put(
            "/v1/settings/providers",
            json={"provider": "openai", "api_key": "validkey\nEVIL=1"},
        )
        assert response.status_code == 422
        assert not Path(".env").exists() or "EVIL" not in Path(".env").read_text()

    def test_bad_base_url_rejected(self) -> None:
        response = _client().put(
            "/v1/settings/providers",
            json={"provider": "openai", "base_url": "ftp://bad"},
        )
        assert response.status_code == 422

    def test_clear_with_fields_conflicts(self) -> None:
        response = _client().put(
            "/v1/settings/providers",
            json={"provider": "openai", "clear": True, "api_key": "x" * 10},
        )
        assert response.status_code == 422

    def test_empty_update_rejected(self) -> None:
        response = _client().put("/v1/settings/providers", json={"provider": "openai"})
        assert response.status_code == 422


class TestEnvHints:
    def test_env_hints(self) -> None:
        response = _client().get("/v1/settings/env")
        assert response.status_code == 200
        data = response.json()
        assert "OPENAI_API_KEY" in data["env_vars"]
        assert data["cwd_env_file"].endswith(".env")


class TestConfigResilience:
    def test_app_starts_with_provider_keys_in_env_file(self) -> None:
        """Regression: .env with API keys must not break AppConfig loading."""
        Path(".env").write_text("OPENAI_API_KEY=sk-test123456\nGEMINI_API_KEY=gm-test123456\n")
        clear_remote_settings_cache()
        client = _client()
        assert client.get("/v1/health").status_code == 200
        assert client.get("/v1/settings/providers").status_code == 200
        assert client.get("/v1/models").status_code == 200


class TestWebUI:
    def test_index_served(self) -> None:
        response = _client().get("/ui/")
        assert response.status_code == 200
        assert "CodeForge AI" in response.text
        assert "Provider API Keys" in response.text

    def test_root_redirects_to_ui(self) -> None:
        client = _client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code in (301, 302, 307, 308)
        assert response.headers["location"] == "/ui/"
