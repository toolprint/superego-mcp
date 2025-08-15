"""
Hook integration service for converting between Claude Code and Superego models.

This service provides seamless integration between Claude Code hook inputs/outputs
and the Superego domain models, handling all schema conversions and validations.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from .claude_code_models import (
    HookEventName,
    HookInput,
    HookOutput,
    PermissionDecision,
    PostToolUseInput,
    PreToolUseInput,
    PreToolUseOutput,
    StopReason,
    create_hook_output,
    validate_hook_input,
)
from .models import Decision, ErrorCode, SuperegoError, ToolAction, ToolRequest

logger = logging.getLogger(__name__)


class HookIntegrationService:
    """Service for integrating Claude Code hooks with Superego domain models."""

    def __init__(self):
        """Initialize the hook integration service."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def parse_hook_input(self, raw_input: dict[str, Any]) -> HookInput:
        """
        Parse and validate raw hook input data.

        Args:
            raw_input: Raw input data from Claude Code hook

        Returns:
            Validated hook input model

        Raises:
            SuperegoError: If input validation fails
        """
        try:
            return validate_hook_input(raw_input)
        except ValueError as e:
            self.logger.error(f"Hook input validation failed: {e}")
            raise SuperegoError(
                code=ErrorCode.PARAMETER_VALIDATION_FAILED,
                message=f"Invalid hook input: {e}",
                user_message="The hook input data is malformed or incomplete",
                context={"raw_input": raw_input},
            ) from e

    def convert_to_tool_request(self, hook_input: HookInput) -> ToolRequest | None:
        """
        Convert Claude Code hook input to Superego ToolRequest.

        Args:
            hook_input: Validated hook input model

        Returns:
            ToolRequest model if applicable, None for non-tool events

        Raises:
            SuperegoError: If conversion fails
        """
        try:
            # Only PreToolUse and PostToolUse events contain tool information
            if isinstance(hook_input, PreToolUseInput | PostToolUseInput):
                return ToolRequest(
                    tool_name=hook_input.tool_name,
                    parameters=hook_input.tool_input.model_dump(exclude_none=True),
                    session_id=hook_input.session_id,
                    agent_id=self._extract_agent_id(hook_input),
                    cwd=hook_input.cwd,
                    timestamp=datetime.now(UTC),
                )

            # Other event types don't map to tool requests
            self.logger.debug(
                f"Event type {hook_input.hook_event_name} does not map to tool request"
            )
            return None

        except Exception as e:
            self.logger.error(f"Failed to convert hook input to tool request: {e}")
            raise SuperegoError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Hook input conversion failed: {e}",
                user_message="Failed to process the tool request",
                context={"hook_input": hook_input.model_dump()},
            ) from e

    def convert_decision_to_hook_output(
        self,
        decision: Decision,
        event_type: HookEventName,
        context: dict[str, Any] | None = None,
    ) -> HookOutput:
        """
        Convert Superego Decision to Claude Code hook output.

        Args:
            decision: Superego security decision
            event_type: Type of hook event
            context: Additional context for conversion

        Returns:
            Appropriate hook output model

        Raises:
            SuperegoError: If conversion fails
        """
        try:
            # Convert Superego action to Claude Code permission
            permission_map = {
                ToolAction.ALLOW: PermissionDecision.ALLOW,
                ToolAction.DENY: PermissionDecision.DENY,
                ToolAction.SAMPLE: PermissionDecision.ASK,  # Sample requires user approval
            }

            # Determine if execution should continue
            should_continue = decision.action in [ToolAction.ALLOW, ToolAction.SAMPLE]

            # Set stop reason if execution is blocked
            stop_reason = None
            if not should_continue:
                stop_reason = StopReason.SECURITY_VIOLATION

            # Create appropriate output based on event type
            if event_type == HookEventName.PRE_TOOL_USE:
                return create_hook_output(
                    event_type=event_type,
                    permission_decision=permission_map.get(
                        decision.action, PermissionDecision.DENY
                    ),
                    permission_decision_reason=self._format_decision_message(decision),
                    # Optional deprecated fields
                    decision="approve" if should_continue else "block",
                    reason=self._format_decision_message(decision),
                )

            elif event_type == HookEventName.POST_TOOL_USE:
                return create_hook_output(
                    event_type=event_type,
                    continue_=should_continue,
                    stop_reason=stop_reason,
                    block_output=decision.action == ToolAction.DENY,
                    message=self._format_decision_message(decision)
                    if not should_continue
                    else None,
                )

            else:
                # For other event types, create basic output
                return create_hook_output(
                    event_type=event_type,
                    continue_=should_continue,
                    stop_reason=stop_reason,
                    suppress_output=decision.action == ToolAction.DENY,
                )

        except Exception as e:
            self.logger.error(f"Failed to convert decision to hook output: {e}")
            raise SuperegoError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Decision conversion failed: {e}",
                user_message="Failed to process the security decision",
                context={
                    "decision": decision.model_dump(),
                    "event_type": event_type.value,
                },
            ) from e

    def create_error_output(
        self, event_type: HookEventName, error: Exception, fail_closed: bool = True
    ) -> HookOutput:
        """
        Create hook output for error scenarios.

        Args:
            event_type: Type of hook event
            error: The error that occurred
            fail_closed: Whether to fail securely (deny by default)

        Returns:
            Hook output representing the error state
        """
        try:
            # Determine error message
            if isinstance(error, SuperegoError):
                message = error.user_message
                stop_reason = StopReason.ERROR
            else:
                message = "Security evaluation failed - operation blocked for safety"
                stop_reason = StopReason.ERROR

            # Fail closed by default for security
            should_continue = not fail_closed

            if event_type == HookEventName.PRE_TOOL_USE:
                return create_hook_output(
                    event_type=event_type,
                    permission_decision=PermissionDecision.DENY
                    if fail_closed
                    else PermissionDecision.ALLOW,
                    permission_decision_reason=message,
                    # Optional deprecated fields
                    decision="block" if fail_closed else "approve",
                    reason=message,
                )

            elif event_type == HookEventName.POST_TOOL_USE:
                return create_hook_output(
                    event_type=event_type,
                    continue_=should_continue,
                    stop_reason=stop_reason if not should_continue else None,
                    block_output=fail_closed,
                    message=message if fail_closed else None,
                )

            else:
                return create_hook_output(
                    event_type=event_type,
                    continue_=should_continue,
                    stop_reason=stop_reason if not should_continue else None,
                    suppress_output=fail_closed,
                )

        except Exception as e:
            self.logger.error(f"Failed to create error output: {e}")
            # Ultimate fallback - return minimal error output
            from .claude_code_models import PreToolUseHookSpecificOutput

            return PreToolUseOutput(
                hookSpecificOutput=PreToolUseHookSpecificOutput(
                    permissionDecision=PermissionDecision.DENY,
                    permissionDecisionReason="Critical error in security hook"
                ),
                decision="block",
                reason="Critical error in security hook"
            )

    def _extract_agent_id(self, hook_input: HookInput) -> str:
        """
        Extract agent ID from hook input.

        Args:
            hook_input: Hook input model

        Returns:
            Agent identifier
        """
        # Use session_id as agent_id for now, but this could be enhanced
        # to extract from transcript or other context
        return f"claude_code_{hook_input.session_id}"

    def _format_decision_message(self, decision: Decision) -> str:
        """
        Format decision message for user display.

        Args:
            decision: Security decision

        Returns:
            Formatted message string
        """
        action_phrases = {
            ToolAction.ALLOW: "Security check passed",
            ToolAction.DENY: "Security check failed",
            ToolAction.SAMPLE: "Security check requires approval",
        }

        action_phrase = action_phrases.get(
            decision.action, "Security evaluation completed"
        )

        message_parts = [action_phrase]

        if decision.reason:
            message_parts.append(f": {decision.reason}")

        if decision.confidence < 1.0:
            message_parts.append(f" (confidence: {decision.confidence:.1%})")

        if decision.rule_id:
            message_parts.append(f" [Rule: {decision.rule_id}]")

        return "".join(message_parts)

    def extract_tool_context(self, hook_input: HookInput) -> dict[str, Any]:
        """
        Extract additional context from hook input for tool evaluation.

        Args:
            hook_input: Hook input model

        Returns:
            Context dictionary for tool evaluation
        """
        context = {
            "session_id": hook_input.session_id,
            "cwd": hook_input.cwd,
            "event_type": hook_input.hook_event_name.value,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Add transcript path if available
        if hook_input.transcript_path:
            context["transcript_path"] = hook_input.transcript_path

        # Add tool-specific context
        if isinstance(hook_input, PreToolUseInput | PostToolUseInput):
            context.update(
                {
                    "tool_name": hook_input.tool_name,
                    "tool_parameters": hook_input.tool_input.model_dump(
                        exclude_none=True
                    ),
                }
            )

            # Add execution results for PostToolUse
            if isinstance(hook_input, PostToolUseInput):
                context["tool_response"] = hook_input.tool_response.model_dump(
                    exclude_none=True
                )

        return context

    def should_evaluate_request(self, hook_input: HookInput) -> bool:
        """
        Determine if a hook input should be evaluated by Superego.

        Args:
            hook_input: Hook input model

        Returns:
            True if evaluation is needed, False otherwise
        """
        # Only evaluate tool-related events
        if not isinstance(hook_input, PreToolUseInput | PostToolUseInput):
            self.logger.debug(
                f"Skipping evaluation for non-tool event: {hook_input.hook_event_name}"
            )
            return False

        # Skip evaluation for certain safe tools
        safe_tools = {"mcp__debug__ping", "mcp__health__check", "mcp__version__info"}

        if hook_input.tool_name in safe_tools:
            self.logger.debug(
                f"Skipping evaluation for safe tool: {hook_input.tool_name}"
            )
            return False

        return True


# Convenience functions for direct usage


def process_hook_input(
    raw_input: dict[str, Any],
    integration_service: HookIntegrationService | None = None,
) -> tuple[HookInput, ToolRequest | None]:
    """
    Process raw hook input and convert to domain models.

    Args:
        raw_input: Raw input from Claude Code hook
        integration_service: Optional service instance

    Returns:
        Tuple of (validated hook input, tool request if applicable)

    Raises:
        SuperegoError: If processing fails
    """
    service = integration_service or HookIntegrationService()

    hook_input = service.parse_hook_input(raw_input)
    tool_request = service.convert_to_tool_request(hook_input)

    return hook_input, tool_request


def create_decision_output(
    decision: Decision,
    event_type: HookEventName,
    integration_service: HookIntegrationService | None = None,
) -> HookOutput:
    """
    Create hook output from security decision.

    Args:
        decision: Security decision from Superego
        event_type: Type of hook event
        integration_service: Optional service instance

    Returns:
        Appropriate hook output model

    Raises:
        SuperegoError: If conversion fails
    """
    service = integration_service or HookIntegrationService()
    return service.convert_decision_to_hook_output(decision, event_type)
