"""Application configuration using pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class ServerConfig(BaseSettings):
    """Server binding and process configuration."""

    model_config = {
        "env_prefix": "CODEFORGE_SERVER_",
        "env_file": ".env",
        "extra": "ignore",
    }

    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    log_level: str = "info"


class APIConfig(BaseSettings):
    """API behavior and limits."""

    model_config = {
        "env_prefix": "CODEFORGE_API_",
        "env_file": ".env",
        "extra": "ignore",
    }

    docs_enabled: bool = True
    auth_required: bool = False
    api_key: str = ""
    max_request_bytes: int = 10_000_000
    request_timeout_seconds: float = 300


class CORSConfig(BaseSettings):
    """CORS middleware configuration."""

    model_config = {
        "env_prefix": "CODEFORGE_CORS_",
        "env_file": ".env",
        "extra": "ignore",
    }

    enabled: bool = False
    allowed_origins: list[str] = Field(default_factory=list)


class RateLimitConfig(BaseSettings):
    """Rate limiting configuration."""

    model_config = {
        "env_prefix": "CODEFORGE_RATE_LIMIT_",
        "env_file": ".env",
        "extra": "ignore",
    }

    enabled: bool = True
    requests_per_minute: int = 60


class AppConfig(BaseSettings):
    """Combined application configuration."""

    model_config = {"env_prefix": "CODEFORGE_", "env_file": ".env", "extra": "ignore"}

    server: ServerConfig = Field(default_factory=ServerConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
