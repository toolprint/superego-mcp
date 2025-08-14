"""
Pydantic V2 models for Claude Code hooks integration.

This module defines the exact input/output schemas for Claude Code hooks
based on the official documentation. These models ensure type safety and
validation for all hook interactions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class HookEventName(str, Enum):
    """Supported Claude Code hook event types."""

    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    NOTIFICATION = "Notification"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    STOP = "Stop"
    SUBAGENT_STOP = "SubagentStop"


class StopReason(str, Enum):
    """Reasons for stopping execution."""

    SECURITY_VIOLATION = "security_violation"
    POLICY_VIOLATION = "policy_violation"
    USER_REQUEST = "user_request"
    ERROR = "error"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"


class PermissionDecision(str, Enum):
    """Permission decisions for PreToolUse hooks."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


# Base Models


class HookInputBase(BaseModel):
    """Base model for all Claude Code hook inputs."""

    session_id: str = Field(..., description="Unique session identifier")
    transcript_path: str = Field(..., description="Path to conversation JSON")
    cwd: str = Field(..., description="Current working directory")
    hook_event_name: HookEventName = Field(..., description="Type of hook event")

    model_config = {"extra": "allow"}


class HookOutputBase(BaseModel):
    """Base model for all Claude Code hook outputs."""

    continue_: bool = Field(
        alias="continue", default=True, description="Whether processing should continue"
    )
    stop_reason: StopReason | None = Field(
        default=None, description="Reason for stopping if continue is False"
    )
    suppress_output: bool = Field(
        default=False, description="Whether to hide stdout output"
    )

    model_config = {"populate_by_name": True}


# Tool Input/Output Models


class ToolInputData(BaseModel):
    """Generic tool input parameters."""

    # Common fields that might appear in tool inputs
    file_path: str | None = None
    content: str | None = None
    path: str | None = None
    command: str | None = None
    description: str | None = None
    pattern: str | None = None
    url: str | None = None

    # Allow additional fields for tool-specific parameters
    model_config = {"extra": "allow"}


class ToolResponseData(BaseModel):
    """Generic tool response data."""

    success: bool = Field(
        default=True, description="Whether the tool executed successfully"
    )
    file_path: str | None = None
    error: str | None = None
    output: str | None = None

    # Allow additional fields for tool-specific responses
    model_config = {"extra": "allow"}


# Specific Hook Input Models


class PreToolUseInput(HookInputBase):
    """Input model for PreToolUse hook events."""

    tool_name: str = Field(..., description="Name of the tool being called")
    tool_input: ToolInputData = Field(..., description="Parameters for the tool call")

    hook_event_name: Literal[HookEventName.PRE_TOOL_USE] = HookEventName.PRE_TOOL_USE


class PostToolUseInput(HookInputBase):
    """Input model for PostToolUse hook events."""

    tool_name: str = Field(..., description="Name of the tool that was called")
    tool_input: ToolInputData = Field(..., description="Parameters that were used")
    tool_response: ToolResponseData = Field(..., description="Response from the tool")

    hook_event_name: Literal[HookEventName.POST_TOOL_USE] = HookEventName.POST_TOOL_USE


class NotificationInput(HookInputBase):
    """Input model for Notification hook events."""

    message: str = Field(..., description="Notification message")

    hook_event_name: Literal[HookEventName.NOTIFICATION] = HookEventName.NOTIFICATION


class UserPromptSubmitInput(HookInputBase):
    """Input model for UserPromptSubmit hook events."""

    prompt: str = Field(..., description="User's submitted prompt")

    hook_event_name: Literal[HookEventName.USER_PROMPT_SUBMIT] = (
        HookEventName.USER_PROMPT_SUBMIT
    )


class StopInput(HookInputBase):
    """Input model for Stop hook events."""

    stop_hook_active: bool = Field(
        default=True, description="Whether the stop hook is active"
    )

    hook_event_name: Literal[HookEventName.STOP] = HookEventName.STOP


class SubagentStopInput(HookInputBase):
    """Input model for SubagentStop hook events."""

    stop_hook_active: bool = Field(
        default=True, description="Whether the subagent stop hook is active"
    )

    hook_event_name: Literal[HookEventName.SUBAGENT_STOP] = HookEventName.SUBAGENT_STOP


# Union type for all possible hook inputs
HookInput = (
    PreToolUseInput
    | PostToolUseInput
    | NotificationInput
    | UserPromptSubmitInput
    | StopInput
    | SubagentStopInput
)


# Hook Specific Output Models


class HookSpecificOutput(BaseModel):
    """Base model for hook-specific output data."""
    
    hook_event_name: HookEventName = Field(
        alias="hookEventName", 
        description="Type of hook event"
    )
    
    model_config = {"populate_by_name": True}


class PreToolUseHookSpecificOutput(HookSpecificOutput):
    """Hook-specific output for PreToolUse events."""
    
    hook_event_name: Literal["PreToolUse"] = Field(
        default="PreToolUse",
        alias="hookEventName"
    )
    permission_decision: PermissionDecision = Field(
        alias="permissionDecision",
        description="Permission decision for the tool call"
    )
    permission_decision_reason: str = Field(
        alias="permissionDecisionReason",
        description="Reason for the permission decision (shown to user)"
    )


# Specific Hook Output Models


class PreToolUseOutput(BaseModel):
    """Output model for PreToolUse hook responses matching Claude Code specification."""
    
    hook_specific_output: PreToolUseHookSpecificOutput = Field(
        alias="hookSpecificOutput",
        description="Hook-specific output data"
    )
    
    # Deprecated fields for backward compatibility
    decision: Literal["approve", "block"] | None = Field(
        default=None,
        description="Deprecated: Use hookSpecificOutput.permissionDecision instead"
    )
    reason: str | None = Field(
        default=None,
        description="Deprecated: Use hookSpecificOutput.permissionDecisionReason instead"
    )
    
    model_config = {"populate_by_name": True}


class PostToolUseOutput(HookOutputBase):
    """Output model for PostToolUse hook responses."""

    block_output: bool = Field(
        default=False,
        description="Whether to block the tool output from being displayed",
    )
    message: str | None = Field(
        default=None, description="Optional message to display instead of tool output"
    )


class NotificationOutput(HookOutputBase):
    """Output model for Notification hook responses."""

    acknowledge: bool = Field(
        default=True, description="Whether the notification was acknowledged"
    )
    response_message: str | None = Field(
        default=None, description="Optional response to the notification"
    )


class UserPromptSubmitOutput(HookOutputBase):
    """Output model for UserPromptSubmit hook responses."""

    block_prompt: bool = Field(
        default=False, description="Whether to block the user prompt"
    )
    additional_context: str | None = Field(
        default=None, description="Additional context to add to the prompt"
    )
    modified_prompt: str | None = Field(
        default=None, description="Modified version of the user prompt"
    )


class StopOutput(HookOutputBase):
    """Output model for Stop hook responses."""

    allow_stop: bool = Field(
        default=True, description="Whether to allow the stop operation"
    )
    message: str | None = Field(
        default=None, description="Optional message about the stop decision"
    )


class SubagentStopOutput(HookOutputBase):
    """Output model for SubagentStop hook responses."""

    allow_stop: bool = Field(
        default=True, description="Whether to allow the subagent stop operation"
    )
    message: str | None = Field(
        default=None, description="Optional message about the stop decision"
    )


# Union type for all possible hook outputs
HookOutput = (
    PreToolUseOutput
    | PostToolUseOutput
    | NotificationOutput
    | UserPromptSubmitOutput
    | StopOutput
    | SubagentStopOutput
)


# Utility Models


class HookContext(BaseModel):
    """Additional context information for hook processing."""

    request_id: str = Field(..., description="Unique request identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Hook processing timestamp",
    )
    source: str = Field(default="claude_code", description="Source of the hook call")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class HookError(BaseModel):
    """Error information for hook processing failures."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Error occurrence timestamp",
    )


# Validation utilities


def validate_hook_input(data: dict[str, Any]) -> HookInput:
    """
    Validate and parse hook input data into the appropriate model.

    Args:
        data: Raw hook input data

    Returns:
        Parsed and validated hook input model

    Raises:
        ValueError: If the input data is invalid or event type is unsupported
    """
    if not isinstance(data, dict):
        raise ValueError("Hook input must be a dictionary")

    event_name = data.get("hook_event_name")
    if not event_name:
        raise ValueError("Missing hook_event_name in input data")

    try:
        event_type = HookEventName(event_name)
    except ValueError:
        raise ValueError(f"Unsupported hook event type: {event_name}") from None

    # Map event types to their corresponding input models
    model_map = {
        HookEventName.PRE_TOOL_USE: PreToolUseInput,
        HookEventName.POST_TOOL_USE: PostToolUseInput,
        HookEventName.NOTIFICATION: NotificationInput,
        HookEventName.USER_PROMPT_SUBMIT: UserPromptSubmitInput,
        HookEventName.STOP: StopInput,
        HookEventName.SUBAGENT_STOP: SubagentStopInput,
    }

    model_class = model_map[event_type]
    return model_class.model_validate(data)


def create_hook_output(event_type: HookEventName, **kwargs) -> HookOutput:
    """
    Create appropriate hook output model based on event type.

    Args:
        event_type: Type of hook event
        **kwargs: Output model parameters

    Returns:
        Initialized hook output model

    Raises:
        ValueError: If event type is unsupported
    """
    # Special handling for PreToolUse to construct the nested structure
    if event_type == HookEventName.PRE_TOOL_USE:
        # Extract hook-specific parameters
        permission_decision = kwargs.pop("permission_decision", PermissionDecision.ALLOW)
        permission_decision_reason = kwargs.pop("permission_decision_reason", "")
        
        # Extract deprecated parameters if provided
        decision = kwargs.pop("decision", None)
        reason = kwargs.pop("reason", None)
        
        # Create the hook-specific output
        hook_specific_output = PreToolUseHookSpecificOutput(
            permissionDecision=permission_decision,
            permissionDecisionReason=permission_decision_reason
        )
        
        return PreToolUseOutput(
            hookSpecificOutput=hook_specific_output,
            decision=decision,
            reason=reason,
            **kwargs
        )
    
    model_map = {
        HookEventName.POST_TOOL_USE: PostToolUseOutput,
        HookEventName.NOTIFICATION: NotificationOutput,
        HookEventName.USER_PROMPT_SUBMIT: UserPromptSubmitOutput,
        HookEventName.STOP: StopOutput,
        HookEventName.SUBAGENT_STOP: SubagentStopOutput,
    }

    if event_type not in model_map:
        raise ValueError(f"Unsupported hook event type: {event_type}")

    model_class = model_map[event_type]
    return model_class(**kwargs)
