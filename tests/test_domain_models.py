"""Tests for domain models."""

import uuid
from datetime import datetime

from superego_mcp.domain.models import (
    AuditEntry,
    Decision,
    ErrorCode,
    SecurityRule,
    SuperegoError,
    ToolAction,
    ToolRequest,
)


class TestToolAction:
    """Test ToolAction enum."""

    def test_values(self):
        """Test enum values."""
        assert ToolAction.ALLOW == "allow"
        assert ToolAction.DENY == "deny"
        assert ToolAction.SAMPLE == "sample"


class TestErrorCode:
    """Test ErrorCode enum."""

    def test_values(self):
        """Test error code values."""
        assert ErrorCode.RULE_EVALUATION_FAILED == "RULE_EVAL_001"
        assert ErrorCode.AI_SERVICE_UNAVAILABLE == "AI_SVC_001"
        assert ErrorCode.INVALID_CONFIGURATION == "CONFIG_001"
        assert ErrorCode.PARAMETER_VALIDATION_FAILED == "PARAM_001"
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_001"


class TestSuperegoError:
    """Test SuperegoError exception."""

    def test_create_error(self):
        """Test creating a SuperegoError."""
        error = SuperegoError(
            code=ErrorCode.RULE_EVALUATION_FAILED,
            message="Rule evaluation failed",
            user_message="Unable to process request",
            context={"rule_id": "test-rule"},
        )

        assert error.code == ErrorCode.RULE_EVALUATION_FAILED
        assert error.message == "Rule evaluation failed"
        assert error.user_message == "Unable to process request"
        assert error.context["rule_id"] == "test-rule"
        assert str(error) == "Rule evaluation failed"

    def test_create_error_no_context(self):
        """Test creating error without context."""
        error = SuperegoError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Internal error",
            user_message="Something went wrong",
        )

        assert error.context == {}


class TestToolRequest:
    """Test ToolRequest model."""

    def test_create_tool_request(self):
        """Test creating a tool request."""
        request = ToolRequest(
            tool_name="test_tool",
            parameters={"arg1": "value1"},
            agent_id="agent-123",
            session_id="session-456",
            cwd="/test/dir",
        )

        assert request.tool_name == "test_tool"
        assert request.parameters["arg1"] == "value1"
        assert request.agent_id == "agent-123"
        assert request.session_id == "session-456"
        assert request.cwd == "/test/dir"
        assert isinstance(request.timestamp, datetime)

    def test_tool_name_validation(self):
        """Test tool name validation."""
        # Valid tool names
        request = ToolRequest(
            tool_name="valid_tool_name123",
            parameters={},
            agent_id="agent-123",
            session_id="session-456",
            cwd="/test/dir",
        )
        assert request.tool_name == "valid_tool_name123"

    def test_parameter_sanitization(self):
        """Test parameter sanitization."""
        request = ToolRequest(
            tool_name="test_tool",
            parameters={
                "safe_param": "value",
                "../malicious": "path",
                "null_byte\x00": "bad\r\nvalue",
                "nested": {"inner/../bad": "value", "list": ["item\x00", "clean_item"]},
            },
            agent_id="agent-123",
            session_id="session-456",
            cwd="/test/dir",
        )

        # Check sanitization worked
        assert "safe_param" in request.parameters
        assert "malicious" in request.parameters  # .. removed
        assert "null_byte" in request.parameters  # null byte removed
        assert "\x00" not in str(request.parameters)  # no null bytes
        assert "\r" not in str(request.parameters)  # carriage returns removed


class TestSecurityRule:
    """Test SecurityRule model."""

    def test_create_security_rule(self):
        """Test creating a security rule."""
        rule = SecurityRule(
            id="test-rule",
            priority=10,
            conditions={"tool_name": "dangerous.*"},
            action=ToolAction.DENY,
            reason="Tool is potentially dangerous",
        )

        assert rule.id == "test-rule"
        assert rule.priority == 10
        assert rule.action == ToolAction.DENY
        assert rule.reason == "Tool is potentially dangerous"
        assert rule.conditions["tool_name"] == "dangerous.*"

    def test_priority_validation(self):
        """Test priority validation."""
        # Valid priority
        rule = SecurityRule(
            id="test-rule",
            priority=500,
            conditions={"tool_name": {"equals": "test"}},
            action=ToolAction.ALLOW,
        )
        assert rule.priority == 500

    def test_immutable_rule(self):
        """Test that rules are immutable."""
        rule = SecurityRule(
            id="test-rule",
            priority=10,
            conditions={"tool_name": {"equals": "test"}},
            action=ToolAction.ALLOW,
        )

        # Rules should be frozen (immutable)
        try:
            rule.priority = 20
            raise AssertionError("Should not be able to modify frozen model")
        except (AttributeError, ValueError):
            pass  # Expected behavior for frozen model


class TestDecision:
    """Test Decision model."""

    def test_create_allow_decision(self):
        """Test creating an allow decision."""
        decision = Decision(
            action="allow",
            reason="Request looks safe",
            rule_id="rule-123",
            confidence=0.95,
            processing_time_ms=50,
        )

        assert decision.action == "allow"
        assert decision.reason == "Request looks safe"
        assert decision.rule_id == "rule-123"
        assert decision.confidence == 0.95
        assert decision.processing_time_ms == 50

    def test_create_deny_decision(self):
        """Test creating a deny decision."""
        decision = Decision(
            action="deny",
            reason="Request violates security policy",
            rule_id="deny-rule",
            confidence=1.0,
            processing_time_ms=25,
        )

        assert decision.action == "deny"
        assert decision.reason == "Request violates security policy"
        assert decision.confidence == 1.0

    def test_confidence_validation(self):
        """Test confidence validation."""
        decision = Decision(
            action="allow", reason="Test", confidence=0.5, processing_time_ms=10
        )
        assert decision.confidence == 0.5


class TestAuditEntry:
    """Test AuditEntry model."""

    def test_create_audit_entry(self):
        """Test creating an audit entry."""
        request = ToolRequest(
            tool_name="test_tool",
            parameters={"arg1": "value1"},
            agent_id="agent-123",
            session_id="session-456",
            cwd="/test/dir",
        )

        decision = Decision(
            action="allow",
            reason="Request approved",
            confidence=0.9,
            processing_time_ms=30,
        )

        audit_entry = AuditEntry(
            request=request, decision=decision, rule_matches=["rule-1", "rule-2"]
        )

        assert audit_entry.request == request
        assert audit_entry.decision == decision
        assert audit_entry.rule_matches == ["rule-1", "rule-2"]
        assert isinstance(audit_entry.id, str)
        assert isinstance(audit_entry.timestamp, datetime)
        assert len(audit_entry.id) > 0  # UUID should be generated

    def test_auto_generated_fields(self):
        """Test auto-generated ID and timestamp."""
        request = ToolRequest(
            tool_name="test_tool",
            parameters={},
            agent_id="agent-123",
            session_id="session-456",
            cwd="/test/dir",
        )

        decision = Decision(
            action="deny", reason="Test", confidence=1.0, processing_time_ms=10
        )

        entry1 = AuditEntry(request=request, decision=decision, rule_matches=[])
        entry2 = AuditEntry(request=request, decision=decision, rule_matches=[])

        # IDs should be different
        assert entry1.id != entry2.id
        # Both should be valid UUIDs
        uuid.UUID(entry1.id)
        uuid.UUID(entry2.id)
