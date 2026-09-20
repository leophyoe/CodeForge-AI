"""Application configuration using pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class ServerConfig(BaseSettings):
    """Server binding and process configuration."""

    model_config = {"env_prefix": "CODEFORGE_SERVER_"}

    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    log_level: str = "info"


class APIConfig(BaseSettings):
    """API behavior and limits."""

    model_config = {"env_prefix": "CODEFORGE_API_"}

    docs_enabled: bool = True
    auth_required: bool = False
    api_key: str = ""
    max_request_bytes: int = 10_000_000
    request_timeout_seconds: float = 300


class CORSConfig(BaseSettings):
    """CORS middleware configuration."""

    model_config = {"env_prefix": "CODEFORGE_CORS_"}

    enabled: bool = False
    allowed_origins: list[str] = Field(default_factory=list)


class RateLimitConfig(BaseSettings):
    """Rate limiting configuration."""

    model_config = {"env_prefix": "CODEFORGE_RATE_LIMIT_"}

    enabled: bool = True
    requests_per_minute: int = 60


class AppConfig(BaseSettings):
    """Combined application configuration."""

    model_config = {"env_prefix": "CODEFORGE_"}

    server: ServerConfig = Field(default_factory=ServerConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
