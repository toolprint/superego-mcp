"""Integration tests for security policy engine with AI sampling."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from superego_mcp.domain.models import (
    SuperegoError,
    ToolRequest,
)
from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.ai_service import (
    AIDecision,
    AIProvider,
    AIServiceManager,
)
from superego_mcp.infrastructure.prompt_builder import SecurePromptBuilder


@pytest.fixture
def temp_rules_file(tmp_path):
    """Create temporary rules file."""
    rules_file = tmp_path / "test_rules.yaml"
    rules_data = {
        "rules": [
            {
                "id": "rule-ai-sample",
                "priority": 10,
                "conditions": {"tool_name": "dangerous_tool"},
                "action": "sample",
                "reason": "Requires AI evaluation",
                "sampling_guidance": "Evaluate for potential system damage",
            },
            {
                "id": "rule-deny",
                "priority": 20,
                "conditions": {"tool_name": "blocked_tool"},
                "action": "deny",
                "reason": "Explicitly blocked",
            },
            {
                "id": "rule-allow",
                "priority": 30,
                "conditions": {"tool_name": "safe_tool"},
                "action": "allow",
                "reason": "Known safe operation",
            },
        ]
    }

    with open(rules_file, "w") as f:
        yaml.dump(rules_data, f)

    return rules_file


@pytest.fixture
def mock_ai_service_manager():
    """Create mock AI service manager."""
    manager = MagicMock(spec=AIServiceManager)
    return manager


@pytest.fixture
def mock_prompt_builder():
    """Create mock prompt builder."""
    builder = MagicMock(spec=SecurePromptBuilder)
    builder.build_evaluation_prompt.return_value = "Test evaluation prompt"
    return builder


class TestSecurityPolicyWithAI:
    """Test security policy engine with AI sampling integration."""

    @pytest.mark.asyncio
    async def test_ai_sampling_allow_decision(
        self, temp_rules_file, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test AI sampling that results in allow decision."""
        # Setup AI response
        ai_decision = AIDecision(
            decision="allow",
            confidence=0.9,
            reasoning="Operation appears safe",
            risk_factors=[],
            provider=AIProvider.CLAUDE,
            model="claude-3",
            response_time_ms=150,
        )
        mock_ai_service_manager.evaluate_with_ai = AsyncMock(return_value=ai_decision)

        # Create engine with AI components
        engine = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
        )

        # Create request that triggers sampling
        request = ToolRequest(
            tool_name="dangerous_tool",
            parameters={"action": "test"},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/dir",
        )

        # Evaluate
        decision = await engine.evaluate(request)

        # Verify decision
        assert decision.action == "allow"
        assert decision.reason == "Operation appears safe"
        assert decision.confidence == 0.9
        assert decision.ai_provider == "claude"
        assert decision.ai_model == "claude-3"
        assert decision.risk_factors == []

        # Verify AI service was called
        mock_ai_service_manager.evaluate_with_ai.assert_called_once()
        mock_prompt_builder.build_evaluation_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_sampling_deny_decision(
        self, temp_rules_file, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test AI sampling that results in deny decision."""
        # Setup AI response
        ai_decision = AIDecision(
            decision="deny",
            confidence=0.95,
            reasoning="High risk of data exposure",
            risk_factors=["data_exposure", "privilege_escalation"],
            provider=AIProvider.OPENAI,
            model="gpt-4",
            response_time_ms=200,
        )
        mock_ai_service_manager.evaluate_with_ai = AsyncMock(return_value=ai_decision)

        # Create engine
        engine = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
        )

        # Create request
        request = ToolRequest(
            tool_name="dangerous_tool",
            parameters={"target": "/etc/passwd"},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/dir",
        )

        # Evaluate
        decision = await engine.evaluate(request)

        # Verify decision
        assert decision.action == "deny"
        assert decision.reason == "High risk of data exposure"
        assert decision.confidence == 0.95
        assert decision.ai_provider == "openai"
        assert "data_exposure" in decision.risk_factors
        assert "privilege_escalation" in decision.risk_factors

    @pytest.mark.asyncio
    async def test_ai_sampling_with_cache_key(
        self, temp_rules_file, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test that AI sampling uses cache keys correctly."""
        # Setup
        ai_decision = AIDecision(
            decision="allow",
            confidence=0.8,
            reasoning="Cached decision",
            risk_factors=[],
            provider=AIProvider.CLAUDE,
            model="claude-3",
            response_time_ms=100,
        )
        mock_ai_service_manager.evaluate_with_ai = AsyncMock(return_value=ai_decision)

        # Create engine
        engine = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
        )

        # Create identical requests
        request1 = ToolRequest(
            tool_name="dangerous_tool",
            parameters={"action": "test"},
            session_id="session-1",
            agent_id="agent-1",
            cwd="/test/dir",
        )

        request2 = ToolRequest(
            tool_name="dangerous_tool",
            parameters={"action": "test"},
            session_id="session-2",
            agent_id="agent-2",
            cwd="/test/dir",
        )

        # Evaluate both
        decision1 = await engine.evaluate(request1)
        decision2 = await engine.evaluate(request2)

        # Both should get same result
        assert decision1.action == decision2.action

        # Verify cache key was used
        calls = mock_ai_service_manager.evaluate_with_ai.call_args_list
        assert len(calls) == 2

        # Cache keys should be the same (same tool, params, rule)
        cache_key1 = calls[0][1]["cache_key"]
        cache_key2 = calls[1][1]["cache_key"]
        assert cache_key1 == cache_key2

    @pytest.mark.asyncio
    async def test_ai_service_failure_fallback(
        self, temp_rules_file, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test fallback behavior when AI service fails."""
        # Setup AI to fail
        mock_ai_service_manager.evaluate_with_ai = AsyncMock(
            side_effect=SuperegoError(
                code="AI_SERVICE_UNAVAILABLE",
                message="AI service error",
                user_message="Service unavailable",
            )
        )

        # Create engine
        engine = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
        )

        # Create request
        request = ToolRequest(
            tool_name="dangerous_tool",
            parameters={"action": "test"},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/dir",
        )

        # Evaluate - should fallback to deny
        decision = await engine.evaluate(request)

        assert decision.action == "deny"
        assert "AI evaluation failed" in decision.reason
        assert decision.confidence == 0.5

    @pytest.mark.asyncio
    async def test_no_ai_service_fallback(self, temp_rules_file):
        """Test behavior when AI service is not configured."""
        # Create engine without AI components
        engine = SecurityPolicyEngine(
            rules_file=temp_rules_file, ai_service_manager=None, prompt_builder=None
        )

        # Create request that would trigger sampling
        request = ToolRequest(
            tool_name="dangerous_tool",
            parameters={"action": "test"},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/dir",
        )

        # Evaluate - should deny due to missing AI
        decision = await engine.evaluate(request)

        assert decision.action == "deny"
        assert (
            "Rule rule-ai-sample requires inference but no providers configured"
            in decision.reason
        )

    @pytest.mark.asyncio
    async def test_regular_rules_bypass_ai(
        self, temp_rules_file, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test that non-sampling rules don't invoke AI."""
        # Create engine with AI
        engine = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
        )

        # Test allow rule
        request_allow = ToolRequest(
            tool_name="safe_tool",
            parameters={},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/dir",
        )

        decision_allow = await engine.evaluate(request_allow)
        assert decision_allow.action == "allow"
        assert decision_allow.ai_provider is None

        # Test deny rule
        request_deny = ToolRequest(
            tool_name="blocked_tool",
            parameters={},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/dir",
        )

        decision_deny = await engine.evaluate(request_deny)
        assert decision_deny.action == "deny"
        assert decision_deny.ai_provider is None

        # Verify AI was never called
        mock_ai_service_manager.evaluate_with_ai.assert_not_called()

    @pytest.mark.asyncio
    async def test_prompt_builder_integration(
        self, temp_rules_file, mock_ai_service_manager
    ):
        """Test real prompt builder integration."""
        # Use real prompt builder
        prompt_builder = SecurePromptBuilder()

        # Setup AI response
        ai_decision = AIDecision(
            decision="allow",
            confidence=0.85,
            reasoning="Test decision",
            risk_factors=[],
            provider=AIProvider.CLAUDE,
            model="claude-3",
            response_time_ms=100,
        )
        mock_ai_service_manager.evaluate_with_ai = AsyncMock(return_value=ai_decision)

        # Create engine
        engine = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=prompt_builder,
        )

        # Create request with potentially dangerous parameters
        request = ToolRequest(
            tool_name="dangerous_tool",
            parameters={
                "path": "../../etc/passwd",
                "command": "rm -rf /*",
                "script": "<script>alert('xss')</script>",
            },
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/dir",
        )

        # Evaluate
        await engine.evaluate(request)

        # Verify prompt was built and sanitized
        call_args = mock_ai_service_manager.evaluate_with_ai.call_args
        prompt = call_args[1]["prompt"]

        # Verify sanitization
        assert "../.." not in prompt  # Path traversal removed
        assert (
            "&amp;lt;script&amp;gt;" in prompt
        )  # HTML escaped (double-escaped by Jinja2)
        assert "dangerous_tool" in prompt
        assert "Evaluate for potential system damage" in prompt  # Sampling guidance

    def test_health_check_with_ai(
        self, temp_rules_file, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test health check includes AI service status."""
        # Mock AI health status
        mock_ai_service_manager.get_health_status.return_value = {
            "enabled": True,
            "primary_provider": "claude",
            "cache_size": 5,
        }

        # Create engine
        engine = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
        )

        # Get health status
        health = engine.health_check()

        assert health["status"] == "healthy"
        assert health["rules_count"] == 3
        assert "ai_service" in health
        assert health["ai_service"]["enabled"] is True
        assert health["ai_service"]["cache_size"] == 5
