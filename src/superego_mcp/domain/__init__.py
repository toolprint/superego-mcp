"""Domain models and business logic for Superego MCP Server.

This module contains the core domain models, value objects, and business logic
for the tool request interception system.
"""

# Claude Code integration
from .claude_code_models import (
    HookEventName,
    HookInput,
    HookOutput,
    PermissionDecision,
    PostToolUseInput,
    PostToolUseOutput,
    PreToolUseInput,
    PreToolUseOutput,
    PreToolUseHookSpecificOutput,
    create_hook_output,
    validate_hook_input,
)
from .hook_integration import HookIntegrationService
from .models import (
    AuditEntry,
    Decision,
    ErrorCode,
    SecurityRule,
    SuperegoError,
    ToolAction,
    ToolRequest,
)
from .repositories import RuleRepository
from .services import InterceptionService, RuleEngine

__all__ = [
    "AuditEntry",
    "Decision",
    "ErrorCode",
    "SecurityRule",
    "SuperegoError",
    "ToolAction",
    "ToolRequest",
    "InterceptionService",
    "RuleEngine",
    "RuleRepository",
    # Claude Code integration
    "HookEventName",
    "HookInput",
    "HookOutput",
    "PermissionDecision",
    "PreToolUseInput",
    "PreToolUseOutput",
    "PreToolUseHookSpecificOutput",
    "PostToolUseInput",
    "PostToolUseOutput",
    "validate_hook_input",
    "create_hook_output",
    "HookIntegrationService",
]
