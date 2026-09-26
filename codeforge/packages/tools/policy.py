"""Tool Policy — controls tool permissions and restrictions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import PermissionLevel


@dataclass
class ToolPolicyConfig:
    enabled: bool = True
    permission: PermissionLevel = PermissionLevel.READ_ONLY
    timeout_seconds: float = 10.0
    max_output_bytes: int = 100_000
    max_file_size_bytes: int = 2_000_000
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)
    sensitive_patterns: list[str] = field(
        default_factory=lambda: [
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            "*.p12",
            "*.pfx",
            "credentials.json",
            "secrets.json",
            "*.secret",
        ]
    )


class ToolPolicy:
    def __init__(self) -> None:
        self._configs: dict[str, ToolPolicyConfig] = {}
        self._defaults = ToolPolicyConfig()

    def set_default(self, config: ToolPolicyConfig) -> None:
        self._defaults = config

    def configure(self, tool_name: str, config: ToolPolicyConfig) -> None:
        self._configs[tool_name] = config

    def get_config(self, tool_name: str) -> ToolPolicyConfig:
        return self._configs.get(tool_name, self._defaults)

    def is_enabled(self, tool_name: str) -> bool:
        return self.get_config(tool_name).enabled

    def check_permission(self, tool_name: str, required: PermissionLevel) -> bool:
        config = self.get_config(tool_name)
        if not config.enabled:
            return False
        levels = [
            PermissionLevel.NONE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.USER_APPROVAL,
            PermissionLevel.PRIVILEGED,
        ]
        return levels.index(config.permission) >= levels.index(required)

    def is_sensitive_file(self, path: str) -> bool:
        import fnmatch

        config = self._defaults
        for pattern in config.sensitive_patterns:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.split("/")[-1], pattern):
                return True
        return False

    def validate_path(self, path: str, workspace_root: str) -> bool:
        from pathlib import Path

        try:
            resolved = Path(path).resolve()
            workspace_resolved = Path(workspace_root).resolve()
            return str(resolved).startswith(str(workspace_resolved))
        except (ValueError, OSError):
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "defaults": {
                "enabled": self._defaults.enabled,
                "permission": self._defaults.permission.value,
                "timeout_seconds": self._defaults.timeout_seconds,
                "max_output_bytes": self._defaults.max_output_bytes,
                "max_file_size_bytes": self._defaults.max_file_size_bytes,
            },
            "tools": {
                name: {
                    "enabled": cfg.enabled,
                    "permission": cfg.permission.value,
                }
                for name, cfg in self._configs.items()
            },
        }
