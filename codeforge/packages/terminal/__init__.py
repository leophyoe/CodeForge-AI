"""Terminal package - Phase 10: Safe command execution."""

from codeforge.packages.terminal.audit import TerminalAuditLogger
from codeforge.packages.terminal.errors import (
    ApprovalRequiredError,
    CommandCancelledError,
    CommandNotFoundError,
    CommandOutputLimitError,
    CommandPermissionError,
    CommandTimeoutError,
    CommandValidationError,
    DangerousCommandError,
    PathTraversalError,
    TerminalError,
    WorkspaceAccessError,
)
from codeforge.packages.terminal.executor import ProcessExecutor
from codeforge.packages.terminal.manager import TerminalManager
from codeforge.packages.terminal.models import (
    ApprovalRequest,
    CommandClassification,
    CommandExecutionContext,
    CommandRequest,
    CommandResult,
    CommandStatus,
    current_time_ms,
)
from codeforge.packages.terminal.policy import (
    BLOCKED_COMMANDS,
    DANGEROUS_COMMANDS,
    RESTRICTED_COMMANDS,
    CommandPolicy,
    CommandPolicyConfig,
    RiskLevel,
)

__all__ = [
    "ApprovalRequiredError",
    "ApprovalRequest",
    "BLOCKED_COMMANDS",
    "CommandCancelledError",
    "CommandClassification",
    "CommandExecutionContext",
    "CommandNotFoundError",
    "CommandOutputLimitError",
    "CommandPermissionError",
    "CommandPolicy",
    "CommandPolicyConfig",
    "CommandRequest",
    "CommandResult",
    "CommandStatus",
    "CommandTimeoutError",
    "CommandValidationError",
    "DANGEROUS_COMMANDS",
    "DangerousCommandError",
    "PathTraversalError",
    "ProcessExecutor",
    "RESTRICTED_COMMANDS",
    "RiskLevel",
    "TerminalAuditLogger",
    "TerminalError",
    "TerminalManager",
    "WorkspaceAccessError",
    "current_time_ms",
]
