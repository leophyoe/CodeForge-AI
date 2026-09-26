"""Command policy — classify and validate commands."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from codeforge.packages.terminal.models import CommandRequest


class RiskLevel(Enum):
    SAFE = "safe"
    RESTRICTED = "restricted"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"


BLOCKED_COMMANDS = {
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "mkfs",
    "mkfs.ext4",
    "mkfs.xfs",
    "dd",
    "mount",
    "umount",
    "systemctl",
    "sudo",
    "su",
    "doas",
    "passwd",
    "chpasswd",
    "usermod",
    "groupmod",
    "iptables",
}

DANGEROUS_COMMANDS = {
    "rm",
    "rmdir",
    "mv",
    "cp",
    "chmod",
    "chown",
    "tar",
    "curl",
    "wget",
    "nc",
    "ncat",
    "ssh",
    "scp",
    "rsync",
    "openssl",
    "gpg",
    "xargs",
    "truncate",
    "shred",
    "ln",
    "fdisk",
    "parted",
}

RESTRICTED_COMMANDS = {
    "find",
    "grep",
    "awk",
    "sed",
    "perl",
    "python",
    "python3",
    "node",
    "npm",
    "pip",
    "gem",
    "bundle",
    "make",
    "cmake",
    "gcc",
    "g++",
    "clang",
    "rustc",
    "cargo",
    "go",
    "docker",
    "containerd",
    "kubectl",
    "helm",
    "vagrant",
    "virt-manager",
    "chpasswd2",
    "useradd",
    "groupadd",
    "adduser",
    "iptables-nft",
    "ip",
    "ifconfig",
    "netstat",
    "ss",
    "ps",
    "top",
    "htop",
    "kill",
    "pkill",
    "killall",
    "cron",
    "at",
    "systemd",
    "journalctl",
    "logrotate",
}

SHELL_INTERPRETERS = {
    "sh",
    "bash",
    "zsh",
    "dash",
    "ksh",
    "csh",
    "tcsh",
    "fish",
    "ash",
}

SHELL_STRING_FLAGS = {"-c", "/c", "-Command", "--command"}

WRAPPER_COMMANDS = {"env", "nohup", "setsid", "nice", "timeout", "time", "busybox"}

_VALUE_FLAGS = {"-n", "--nice", "-u", "--adjustment", "-s", "--signal"}

_GIT_WRITE_SUBCOMMANDS = {
    "push",
    "commit",
    "reset",
    "clean",
    "rebase",
    "merge",
    "revert",
    "cherry-pick",
    "rm",
    "mv",
    "tag",
    "config",
    "am",
    "apply",
    "fetch",
    "pull",
    "clone",
    "init",
    "checkout",
    "switch",
    "restore",
}

_CODE_EXEC_FLAGS: dict[str, set[str]] = {
    "python": {"-c"},
    "python3": {"-c"},
    "perl": {"-e", "-E"},
    "ruby": {"-e"},
    "node": {"-e", "--eval"},
    "php": {"-r"},
}

_FIND_MUTATING_FLAGS = {"-exec", "-execdir", "-ok", "-okdir", "-delete"}

_COMMAND_TOKEN_RE = re.compile(r"^[A-Za-z0-9_+./\\:@%=-]+$")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")

_MAX_UNWRAP_DEPTH = 3


@dataclass
class CommandPolicyConfig:
    enabled: bool = True
    default_timeout: float = 30.0
    max_timeout: float = 300.0
    max_output_bytes: int = 100_000
    max_total_output_bytes: int = 400_000
    approval_required: bool = True
    max_args: int = 50
    max_command_length: int = 1024


class CommandPolicy:
    def __init__(self, config: CommandPolicyConfig | None = None) -> None:
        self.config = config or CommandPolicyConfig()
        self._allowed_env_vars: list[str] = [
            "PATH",
            "HOME",
            "USER",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "TERM",
            "SHELL",
            "PWD",
            "TMPDIR",
        ]
        if os.name == "nt":
            self._allowed_env_vars += [
                "SYSTEMROOT",
                "SYSTEMDRIVE",
                "COMSPEC",
                "TEMP",
                "TMP",
                "USERPROFILE",
                "PATHEXT",
                "WINDIR",
            ]
        self._denied_env_patterns: list[str] = [
            "KEY",
            "SECRET",
            "TOKEN",
            "PASSWORD",
            "CREDENTIAL",
            "API_KEY",
            "AWS_",
            "GCP_",
            "AZURE_",
        ]

    @property
    def allowed_env_vars(self) -> list[str]:
        return list(self._allowed_env_vars)

    @staticmethod
    def _basename(command: str) -> str:
        token = command.strip().split()[0] if command.strip() else ""
        base = token.replace("\\", "/").split("/")[-1]
        if os.name == "nt" and base.lower().endswith(".exe"):
            base = base[:-4]
        return base.lower()

    @staticmethod
    def _strip_options(args: list[str]) -> list[str]:
        index = 0
        while index < len(args) and args[index].startswith("-"):
            if args[index] in _VALUE_FLAGS and index + 1 < len(args):
                index += 2
            else:
                index += 1
        return args[index:]

    def _effective_command(self, command: str, args: list[str]) -> tuple[str, list[str]]:
        base = self._basename(command)
        tokens = command.strip().split()
        remaining = tokens[1:] + list(args)
        depth = 0
        while base in WRAPPER_COMMANDS and depth < _MAX_UNWRAP_DEPTH:
            depth += 1
            if base == "env":
                while remaining and (
                    _ENV_ASSIGN_RE.match(remaining[0]) or remaining[0].startswith("-")
                ):
                    remaining = remaining[1:]
            elif base == "timeout":
                if remaining and not remaining[0].startswith("-"):
                    remaining = remaining[1:]
                remaining = self._strip_options(remaining)
            else:
                remaining = self._strip_options(remaining)
            if not remaining:
                break
            base = self._basename(remaining[0])
            remaining = remaining[1:]
        return base, remaining

    def classify(self, command: str, args: list[str] | None = None) -> RiskLevel:
        base, remaining = self._effective_command(command, args or [])
        if not base:
            return RiskLevel.SAFE
        if base in BLOCKED_COMMANDS:
            return RiskLevel.BLOCKED
        if base in SHELL_INTERPRETERS and any(flag in SHELL_STRING_FLAGS for flag in remaining):
            return RiskLevel.BLOCKED
        if base in DANGEROUS_COMMANDS:
            return RiskLevel.DANGEROUS
        remaining_set = set(remaining)
        if base in _CODE_EXEC_FLAGS and _CODE_EXEC_FLAGS[base] & remaining_set:
            return RiskLevel.DANGEROUS
        if base.startswith("python") and "-c" in remaining_set:
            return RiskLevel.DANGEROUS
        if base == "find" and _FIND_MUTATING_FLAGS & remaining_set:
            return RiskLevel.DANGEROUS
        if base == "git":
            subcommand = next((tok for tok in remaining if not tok.startswith("-")), "")
            if subcommand in _GIT_WRITE_SUBCOMMANDS:
                return RiskLevel.DANGEROUS
            return RiskLevel.SAFE
        if base in RESTRICTED_COMMANDS:
            return RiskLevel.RESTRICTED
        return RiskLevel.SAFE

    def is_dangerous(self, command: str, args: list[str] | None = None) -> bool:
        return self.classify(command, args) == RiskLevel.DANGEROUS

    def is_restricted(self, command: str, args: list[str] | None = None) -> bool:
        return self.classify(command, args) == RiskLevel.RESTRICTED

    def is_blocked(self, command: str, args: list[str] | None = None) -> bool:
        return self.classify(command, args) == RiskLevel.BLOCKED

    def validate(self, request: CommandRequest) -> list[str]:
        errors: list[str] = []
        command = request.command or ""
        if not command.strip():
            errors.append("Command is required")
            return errors
        if "\x00" in command:
            errors.append("Command contains a null byte")
        elif len(command) > self.config.max_command_length:
            errors.append("Command too long")
        elif not _COMMAND_TOKEN_RE.match(command.strip()):
            errors.append("Command must be a single token without shell metacharacters")
        if len(request.arguments) > self.config.max_args:
            errors.append("Too many arguments")
        if any("\x00" in arg for arg in request.arguments):
            errors.append("Arguments contain a null byte")
        if request.timeout_seconds <= 0:
            errors.append("Timeout must be positive")
        elif request.timeout_seconds > self.config.max_timeout:
            errors.append("Timeout exceeds maximum")
        if request.max_output_bytes <= 0:
            errors.append("max_output_bytes must be positive")
        if request.max_total_output_bytes < 0:
            errors.append("max_total_output_bytes cannot be negative")
        return errors

    def sanitize_environment(
        self,
        env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        source_env = dict(os.environ) if env is None else env
        clean: dict[str, str] = {}
        for key in self._allowed_env_vars:
            if key in source_env:
                clean[key] = source_env[key]
        clean.setdefault("PATH", os.defpath)
        return {key: value for key, value in clean.items() if self._is_allowed_env_name(key)}

    def _is_allowed_env_name(self, key: str) -> bool:
        return not any(pattern.lower() in key.lower() for pattern in self._denied_env_patterns)

    def is_safe_environment(self, env: dict[str, str]) -> bool:
        for key in env:
            for pattern in self._denied_env_patterns:
                if pattern.lower() in key.lower():
                    return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "default_timeout": self.config.default_timeout,
            "max_timeout": self.config.max_timeout,
            "max_output_bytes": self.config.max_output_bytes,
            "max_total_output_bytes": self.config.max_total_output_bytes,
            "approval_required": self.config.approval_required,
            "max_args": self.config.max_args,
            "max_command_length": self.config.max_command_length,
            "dangerous_commands": sorted(DANGEROUS_COMMANDS),
            "restricted_commands": sorted(RESTRICTED_COMMANDS),
            "blocked_commands": sorted(BLOCKED_COMMANDS),
            "shell_interpreters": sorted(SHELL_INTERPRETERS),
            "safe_commands": "any command not listed above",
            "environment_allowed_variables": list(self._allowed_env_vars),
        }
