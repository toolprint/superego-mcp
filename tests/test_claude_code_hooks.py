"""
Comprehensive tests for Claude Code hooks integration.

This test suite covers all aspects of the Claude Code hooks schema validation,
integration services, and error handling scenarios.
"""

import pytest

from src.superego_mcp.domain.claude_code_models import (
    HookEventName,
    NotificationInput,
    PermissionDecision,
    PostToolUseInput,
    PostToolUseOutput,
    PreToolUseHookSpecificOutput,
    PreToolUseInput,
    PreToolUseOutput,
    StopReason,
    ToolInputData,
    create_hook_output,
    validate_hook_input,
)
from src.superego_mcp.domain.hook_integration import (
    HookIntegrationService,
    create_decision_output,
    process_hook_input,
)
from src.superego_mcp.domain.models import (
    Decision,
    ErrorCode,
    SuperegoError,
    ToolAction,
)


class TestClaudeCodeModels:
    """Test Claude Code Pydantic models."""

    def test_pre_tool_use_input_validation(self):
        """Test PreToolUseInput model validation."""
        valid_data = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/home/user/project/test.py",
                "content": "print('hello')",
            },
        }

        input_model = PreToolUseInput.model_validate(valid_data)
        assert input_model.session_id == "test-session-123"
        assert input_model.tool_name == "Edit"
        assert input_model.tool_input.file_path == "/home/user/project/test.py"
        assert input_model.hook_event_name == HookEventName.PRE_TOOL_USE

    def test_post_tool_use_input_validation(self):
        """Test PostToolUseInput model validation."""
        valid_data = {
            "session_id": "test-session-456",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {
                "success": True,
                "output": "total 16\ndrwxr-xr-x  4 user user 4096 Jan 1 12:00 .",
            },
        }

        input_model = PostToolUseInput.model_validate(valid_data)
        assert input_model.session_id == "test-session-456"
        assert input_model.tool_name == "Bash"
        assert input_model.tool_response.success is True
        assert input_model.hook_event_name == HookEventName.POST_TOOL_USE

    def test_notification_input_validation(self):
        """Test NotificationInput model validation."""
        valid_data = {
            "session_id": "test-session-789",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "Notification",
            "message": "File saved successfully",
        }

        input_model = NotificationInput.model_validate(valid_data)
        assert input_model.message == "File saved successfully"
        assert input_model.hook_event_name == HookEventName.NOTIFICATION

    def test_pre_tool_use_output_creation(self):
        """Test PreToolUseOutput model creation."""
        # Create hook-specific output
        hook_specific_output = PreToolUseHookSpecificOutput(
            permissionDecision=PermissionDecision.DENY,
            permissionDecisionReason="File access denied",
        )

        output = PreToolUseOutput(
            hookSpecificOutput=hook_specific_output,
            decision="block",
            reason="File access denied",
        )

        assert (
            output.hook_specific_output.permission_decision == PermissionDecision.DENY
        )
        assert (
            output.hook_specific_output.permission_decision_reason
            == "File access denied"
        )
        assert output.decision == "block"
        assert output.reason == "File access denied"

    def test_tool_input_data_extra_fields(self):
        """Test that ToolInputData accepts extra fields for tool-specific parameters."""
        data = {
            "file_path": "/test/file.py",
            "content": "test content",
            "custom_param": "custom_value",
            "nested_param": {"key": "value"},
        }

        tool_input = ToolInputData.model_validate(data)
        assert tool_input.file_path == "/test/file.py"
        assert tool_input.content == "test content"
        # Extra fields should be preserved
        model_dict = tool_input.model_dump()
        assert model_dict["custom_param"] == "custom_value"
        assert model_dict["nested_param"] == {"key": "value"}

    def test_validate_hook_input_function(self):
        """Test the validate_hook_input utility function."""
        valid_data = {
            "session_id": "test-session",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user",
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/test.txt"},
        }

        hook_input = validate_hook_input(valid_data)
        assert isinstance(hook_input, PreToolUseInput)
        assert hook_input.tool_name == "Read"

    def test_validate_hook_input_invalid_event(self):
        """Test validate_hook_input with invalid event type."""
        invalid_data = {
            "session_id": "test-session",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user",
            "hook_event_name": "InvalidEvent",
            "tool_name": "Read",
            "tool_input": {"file_path": "/test.txt"},
        }

        with pytest.raises(ValueError, match="Unsupported hook event type"):
            validate_hook_input(invalid_data)

    def test_create_hook_output_function(self):
        """Test the create_hook_output utility function."""
        output = create_hook_output(
            event_type=HookEventName.PRE_TOOL_USE,
            permission_decision=PermissionDecision.ALLOW,
            permission_decision_reason="Tool allowed",
        )

        assert isinstance(output, PreToolUseOutput)
        assert (
            output.hook_specific_output.permission_decision == PermissionDecision.ALLOW
        )
        assert output.hook_specific_output.permission_decision_reason == "Tool allowed"


class TestHookIntegrationService:
    """Test the HookIntegrationService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = HookIntegrationService()

    def test_parse_hook_input_valid(self):
        """Test parsing valid hook input."""
        raw_input = {
            "session_id": "test-session",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user",
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/test.py", "content": "print('test')"},
        }

        hook_input = self.service.parse_hook_input(raw_input)
        assert isinstance(hook_input, PreToolUseInput)
        assert hook_input.tool_name == "Write"

    def test_parse_hook_input_invalid(self):
        """Test parsing invalid hook input."""
        invalid_input = {
            "session_id": "test-session",
            # Missing required fields
        }

        with pytest.raises(SuperegoError) as exc_info:
            self.service.parse_hook_input(invalid_input)

        assert exc_info.value.code == ErrorCode.PARAMETER_VALIDATION_FAILED

    def test_convert_to_tool_request_pre_tool_use(self):
        """Test converting PreToolUseInput to ToolRequest."""
        hook_input = PreToolUseInput(
            session_id="test-session",
            transcript_path="/tmp/transcript.json",
            cwd="/home/user/project",
            hook_event_name=HookEventName.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input=ToolInputData(file_path="/test.py", content="print('hello')"),
        )

        tool_request = self.service.convert_to_tool_request(hook_input)
        assert tool_request is not None
        assert tool_request.tool_name == "Edit"
        assert tool_request.session_id == "test-session"
        assert tool_request.cwd == "/home/user/project"
        assert "file_path" in tool_request.parameters
        assert tool_request.parameters["file_path"] == "/test.py"

    def test_convert_to_tool_request_notification(self):
        """Test converting non-tool event returns None."""
        hook_input = NotificationInput(
            session_id="test-session",
            transcript_path="/tmp/transcript.json",
            cwd="/home/user",
            hook_event_name=HookEventName.NOTIFICATION,
            message="Test notification",
        )

        tool_request = self.service.convert_to_tool_request(hook_input)
        assert tool_request is None

    def test_convert_decision_to_hook_output_allow(self):
        """Test converting ALLOW decision to hook output."""
        decision = Decision(
            action=ToolAction.ALLOW,
            reason="Safe operation detected",
            confidence=0.95,
            processing_time_ms=150,
        )

        output = self.service.convert_decision_to_hook_output(
            decision, HookEventName.PRE_TOOL_USE
        )

        assert isinstance(output, PreToolUseOutput)
        assert (
            output.hook_specific_output.permission_decision == PermissionDecision.ALLOW
        )
        assert output.decision == "approve"
        assert "Safe operation detected" in output.reason

    def test_convert_decision_to_hook_output_deny(self):
        """Test converting DENY decision to hook output."""
        decision = Decision(
            action=ToolAction.DENY,
            reason="Dangerous file operation",
            confidence=0.98,
            processing_time_ms=200,
            rule_id="rule-001",
        )

        output = self.service.convert_decision_to_hook_output(
            decision, HookEventName.PRE_TOOL_USE
        )

        assert isinstance(output, PreToolUseOutput)
        assert (
            output.hook_specific_output.permission_decision == PermissionDecision.DENY
        )
        assert output.decision == "block"
        assert "Dangerous file operation" in output.reason
        assert "rule-001" in output.reason

    def test_convert_decision_to_hook_output_sample(self):
        """Test converting SAMPLE decision to hook output."""
        decision = Decision(
            action=ToolAction.SAMPLE,
            reason="Requires user approval",
            confidence=0.75,
            processing_time_ms=300,
        )

        output = self.service.convert_decision_to_hook_output(
            decision, HookEventName.PRE_TOOL_USE
        )

        assert isinstance(output, PreToolUseOutput)
        assert output.hook_specific_output.permission_decision == PermissionDecision.ASK
        assert (
            output.decision == "approve"
        )  # Sample maps to approve for Claude Code compatibility

    def test_convert_decision_post_tool_use(self):
        """Test converting decision for PostToolUse event."""
        decision = Decision(
            action=ToolAction.DENY,
            reason="Output contains sensitive data",
            confidence=0.90,
            processing_time_ms=180,
        )

        output = self.service.convert_decision_to_hook_output(
            decision, HookEventName.POST_TOOL_USE
        )

        assert isinstance(output, PostToolUseOutput)
        assert output.block_output is True
        assert output.continue_ is False
        assert output.stop_reason == StopReason.SECURITY_VIOLATION

    def test_create_error_output_fail_closed(self):
        """Test creating error output with fail-closed behavior."""
        error = SuperegoError(
            code=ErrorCode.AI_SERVICE_UNAVAILABLE,
            message="AI service timeout",
            user_message="Security evaluation temporarily unavailable",
        )

        output = self.service.create_error_output(
            HookEventName.PRE_TOOL_USE, error, fail_closed=True
        )

        assert isinstance(output, PreToolUseOutput)
        assert (
            output.hook_specific_output.permission_decision == PermissionDecision.DENY
        )
        assert output.decision == "block"

    def test_create_error_output_fail_open(self):
        """Test creating error output with fail-open behavior."""
        error = Exception("Generic error")

        output = self.service.create_error_output(
            HookEventName.PRE_TOOL_USE, error, fail_closed=False
        )

        assert isinstance(output, PreToolUseOutput)
        assert (
            output.hook_specific_output.permission_decision == PermissionDecision.ALLOW
        )
        assert output.decision == "approve"

    def test_should_evaluate_request_tool_events(self):
        """Test should_evaluate_request for tool events."""
        pre_tool_input = PreToolUseInput(
            session_id="test",
            transcript_path="/tmp/transcript.json",
            cwd="/home/user",
            hook_event_name=HookEventName.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input=ToolInputData(file_path="/test.py"),
        )

        assert self.service.should_evaluate_request(pre_tool_input) is True

    def test_should_evaluate_request_safe_tools(self):
        """Test should_evaluate_request skips safe tools."""
        safe_tool_input = PreToolUseInput(
            session_id="test",
            transcript_path="/tmp/transcript.json",
            cwd="/home/user",
            hook_event_name=HookEventName.PRE_TOOL_USE,
            tool_name="mcp__debug__ping",
            tool_input=ToolInputData(),
        )

        assert self.service.should_evaluate_request(safe_tool_input) is False

    def test_should_evaluate_request_non_tool_events(self):
        """Test should_evaluate_request for non-tool events."""
        notification_input = NotificationInput(
            session_id="test",
            transcript_path="/tmp/transcript.json",
            cwd="/home/user",
            hook_event_name=HookEventName.NOTIFICATION,
            message="Test message",
        )

        assert self.service.should_evaluate_request(notification_input) is False

    def test_extract_tool_context(self):
        """Test extracting context from hook input."""
        hook_input = PreToolUseInput(
            session_id="test-session",
            transcript_path="/tmp/transcript.json",
            cwd="/home/user/project",
            hook_event_name=HookEventName.PRE_TOOL_USE,
            tool_name="Bash",
            tool_input=ToolInputData(command="rm -rf /"),
        )

        context = self.service.extract_tool_context(hook_input)

        assert context["session_id"] == "test-session"
        assert context["cwd"] == "/home/user/project"
        assert context["event_type"] == "PreToolUse"
        assert context["tool_name"] == "Bash"
        assert "tool_parameters" in context
        assert context["tool_parameters"]["command"] == "rm -rf /"

    def test_format_decision_message(self):
        """Test decision message formatting."""
        decision = Decision(
            action=ToolAction.DENY,
            reason="Dangerous command detected",
            confidence=0.95,
            processing_time_ms=100,
            rule_id="dangerous-commands",
        )

        message = self.service._format_decision_message(decision)

        assert "Security check failed" in message
        assert "Dangerous command detected" in message
        assert "95.0%" in message
        assert "dangerous-commands" in message


class TestConvenienceFunctions:
    """Test convenience functions for hook processing."""

    def test_process_hook_input_valid(self):
        """Test process_hook_input with valid data."""
        raw_input = {
            "session_id": "test-session",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user",
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/test.py", "content": "test"},
        }

        hook_input, tool_request = process_hook_input(raw_input)

        assert isinstance(hook_input, PreToolUseInput)
        assert tool_request is not None
        assert tool_request.tool_name == "Write"

    def test_process_hook_input_notification(self):
        """Test process_hook_input with notification event."""
        raw_input = {
            "session_id": "test-session",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user",
            "hook_event_name": "Notification",
            "message": "Test notification",
        }

        hook_input, tool_request = process_hook_input(raw_input)

        assert isinstance(hook_input, NotificationInput)
        assert tool_request is None

    def test_create_decision_output(self):
        """Test create_decision_output convenience function."""
        decision = Decision(
            action=ToolAction.ALLOW,
            reason="Safe operation",
            confidence=0.9,
            processing_time_ms=100,
        )

        output = create_decision_output(decision, HookEventName.PRE_TOOL_USE)

        assert isinstance(output, PreToolUseOutput)
        assert (
            output.hook_specific_output.permission_decision == PermissionDecision.ALLOW
        )


class TestIntegrationScenarios:
    """Test end-to-end integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = HookIntegrationService()

    def test_complete_pre_tool_use_flow(self):
        """Test complete flow from hook input to output."""
        # 1. Raw input from Claude Code
        raw_input = {
            "session_id": "integration-test",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": "/etc/passwd", "content": "malicious content"},
        }

        # 2. Parse and convert to domain models
        hook_input = self.service.parse_hook_input(raw_input)
        tool_request = self.service.convert_to_tool_request(hook_input)

        assert tool_request is not None
        assert tool_request.tool_name == "Edit"

        # 3. Simulate security decision (would come from Superego service)
        decision = Decision(
            action=ToolAction.DENY,
            reason="Attempt to modify system file",
            confidence=0.99,
            processing_time_ms=250,
            rule_id="system-file-protection",
        )

        # 4. Convert back to hook output
        output = self.service.convert_decision_to_hook_output(
            decision, hook_input.hook_event_name
        )

        assert isinstance(output, PreToolUseOutput)
        assert (
            output.hook_specific_output.permission_decision == PermissionDecision.DENY
        )
        assert output.decision == "block"
        assert "system file" in output.reason.lower()

    def test_post_tool_use_flow_with_blocking(self):
        """Test PostToolUse flow with output blocking."""
        raw_input = {
            "session_id": "integration-test",
            "transcript_path": "/tmp/transcript.json",
            "cwd": "/home/user",
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "cat ~/.ssh/id_rsa"},
            "tool_response": {
                "success": True,
                "output": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG...",
            },
        }

        hook_input = self.service.parse_hook_input(raw_input)

        # Simulate decision to block sensitive output
        decision = Decision(
            action=ToolAction.DENY,
            reason="Output contains private key data",
            confidence=0.97,
            processing_time_ms=180,
        )

        output = self.service.convert_decision_to_hook_output(
            decision, hook_input.hook_event_name
        )

        assert isinstance(output, PostToolUseOutput)
        assert output.block_output is True
        assert output.continue_ is False
        assert "private key" in output.message.lower()

    def test_error_handling_flow(self):
        """Test error handling throughout the flow."""
        # Invalid input data
        invalid_input = {"invalid": "data"}

        with pytest.raises(SuperegoError) as exc_info:
            self.service.parse_hook_input(invalid_input)

        error = exc_info.value
        assert error.code == ErrorCode.PARAMETER_VALIDATION_FAILED

        # Test error output creation
        error_output = self.service.create_error_output(
            HookEventName.PRE_TOOL_USE, error
        )

        assert isinstance(error_output, PreToolUseOutput)
        assert (
            error_output.hook_specific_output.permission_decision
            == PermissionDecision.DENY
        )
        assert error_output.decision == "block"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
