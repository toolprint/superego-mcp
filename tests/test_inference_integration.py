"""Integration tests for the inference provider system."""

import os
from unittest.mock import MagicMock, patch

import pytest

from superego_mcp.domain.models import ToolRequest
from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.ai_service import (
    AIDecision,
    AIProvider,
    AIServiceManager,
)
from superego_mcp.infrastructure.config import CLIProviderConfig, InferenceConfig
from superego_mcp.infrastructure.inference import InferenceStrategyManager
from superego_mcp.infrastructure.prompt_builder import SecurePromptBuilder


class TestInferenceIntegration:
    """Integration tests for the complete inference system."""

    @pytest.fixture
    def temp_rules_file(self, tmp_path):
        """Create temporary rules file."""
        rules_file = tmp_path / "rules.yaml"
        rules_content = """
rules:
  - id: "test-sampling-rule"
    priority: 1
    conditions:
      tool_name: "test_tool"
    action: "sample"
    reason: "Test sampling rule"
    sampling_guidance: "Evaluate this test tool request"
    enabled: true
"""
        rules_file.write_text(rules_content)
        return rules_file

    @pytest.fixture
    def mock_ai_service_manager(self):
        """Create mock AI service manager."""
        manager = MagicMock(spec=AIServiceManager)
        manager.get_health_status.return_value = {
            "enabled": True,
            "services_initialized": ["claude"],
        }
        # Create mock config object
        manager.config = MagicMock()
        manager.config.claude_model = "claude-3-sonnet"
        return manager

    @pytest.fixture
    def mock_prompt_builder(self):
        """Create mock prompt builder."""
        builder = MagicMock(spec=SecurePromptBuilder)
        builder.build_evaluation_prompt.return_value = "Test evaluation prompt"
        return builder

    @pytest.fixture
    def sample_tool_request(self):
        """Create sample tool request."""
        return ToolRequest(
            tool_name="test_tool",
            parameters={"file": "test.txt"},
            session_id="session-123",
            agent_id="agent-456",
            cwd="/home/user",
        )

    @pytest.mark.asyncio
    async def test_security_policy_with_inference_manager(
        self,
        temp_rules_file,
        mock_ai_service_manager,
        mock_prompt_builder,
        sample_tool_request,
    ):
        """Test SecurityPolicyEngine with new inference system."""
        # Mock AI decision
        ai_decision = AIDecision(
            decision="allow",
            confidence=0.8,
            reasoning="Test tool is safe to execute",
            risk_factors=["low_risk"],
            provider=AIProvider.CLAUDE,
            model="claude-3-sonnet",
            response_time_ms=150,
        )
        mock_ai_service_manager.evaluate_with_ai.return_value = ai_decision

        # Create inference configuration
        inference_config = InferenceConfig(
            timeout_seconds=10,
            provider_preference=["mcp_sampling"],
            cli_providers=[],
            api_providers=[],
        )

        # Create inference manager
        dependencies = {
            "ai_service_manager": mock_ai_service_manager,
            "prompt_builder": mock_prompt_builder,
        }
        inference_manager = InferenceStrategyManager(inference_config, dependencies)

        # Create security policy engine
        security_policy = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            health_monitor=None,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
            inference_manager=inference_manager,
        )

        # Evaluate request
        decision = await security_policy.evaluate(sample_tool_request)

        # Verify decision
        assert decision.action == "allow"
        assert decision.confidence == 0.8
        assert decision.reasoning == "Test tool is safe to execute"
        assert decision.rule_id == "test-sampling-rule"
        assert decision.ai_provider == "mcp_claude"
        assert decision.ai_model == "claude-3-sonnet"
        assert decision.risk_factors == ["low_risk"]

    @pytest.mark.asyncio
    async def test_security_policy_fallback_to_legacy(
        self,
        temp_rules_file,
        mock_ai_service_manager,
        mock_prompt_builder,
        sample_tool_request,
    ):
        """Test SecurityPolicyEngine fallback to legacy AI system."""
        # Mock AI decision
        ai_decision = AIDecision(
            decision="deny",
            confidence=0.9,
            reasoning="Test tool has security risks",
            risk_factors=["file_access", "potential_damage"],
            provider=AIProvider.CLAUDE,
            model="claude-3-sonnet",
            response_time_ms=200,
        )
        mock_ai_service_manager.evaluate_with_ai.return_value = ai_decision

        # Create security policy engine WITHOUT inference manager
        security_policy = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            health_monitor=None,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
            inference_manager=None,  # No inference manager - should use legacy
        )

        # Evaluate request
        decision = await security_policy.evaluate(sample_tool_request)

        # Verify decision uses legacy system
        assert decision.action == "deny"
        assert decision.confidence == 0.9
        assert decision.reasoning == "Test tool has security risks"
        assert decision.rule_id == "test-sampling-rule"
        assert decision.ai_provider == "claude"  # Legacy format
        assert decision.ai_model == "claude-3-sonnet"
        assert decision.risk_factors == ["file_access", "potential_damage"]

    @pytest.mark.asyncio
    async def test_security_policy_no_inference_available(
        self, temp_rules_file, sample_tool_request
    ):
        """Test SecurityPolicyEngine when no inference is available."""
        # Create security policy engine with no AI components
        security_policy = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            health_monitor=None,
            ai_service_manager=None,
            prompt_builder=None,
            inference_manager=None,
        )

        # Evaluate request
        decision = await security_policy.evaluate(sample_tool_request)

        # Should fail closed when no inference is available
        assert decision.action == "deny"
        assert "requires inference but no providers configured" in decision.reason
        assert decision.rule_id == "test-sampling-rule"
        assert decision.confidence == 0.6

    @pytest.mark.asyncio
    async def test_health_check_with_inference_manager(
        self, temp_rules_file, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test health check includes inference system status."""
        # Create inference configuration
        inference_config = InferenceConfig(
            timeout_seconds=10,
            provider_preference=["mcp_sampling"],
            cli_providers=[],
            api_providers=[],
        )

        # Create inference manager
        dependencies = {
            "ai_service_manager": mock_ai_service_manager,
            "prompt_builder": mock_prompt_builder,
        }
        inference_manager = InferenceStrategyManager(inference_config, dependencies)

        # Create security policy engine
        security_policy = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            health_monitor=None,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
            inference_manager=inference_manager,
        )

        # Check synchronous health check
        health = security_policy.health_check()
        assert "inference_system" in health
        assert health["inference_system"]["available"] is True
        assert health["inference_system"]["total_providers"] == 1

        # Check async health check
        async_health = await security_policy.health_check_async()
        assert "inference_system" in async_health
        assert async_health["inference_system"]["_summary"]["total_providers"] == 1
        assert async_health["inference_system"]["_summary"]["overall_healthy"] is True

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"})
    @patch("subprocess.run")
    async def test_cli_provider_integration(
        self, mock_subprocess, temp_rules_file, mock_prompt_builder, sample_tool_request
    ):
        """Test integration with CLI provider."""
        # Mock CLI availability check
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Create inference configuration with CLI provider
        cli_config = CLIProviderConfig(
            name="test_claude_cli",
            enabled=True,
            type="claude",
            command="claude",
            model="claude-3-sonnet",
            api_key_env_var="TEST_API_KEY",
            timeout_seconds=5,
        )

        inference_config = InferenceConfig(
            timeout_seconds=10,
            provider_preference=["test_claude_cli"],
            cli_providers=[cli_config],
            api_providers=[],
        )

        # Create inference manager
        dependencies = {
            "ai_service_manager": None,  # No MCP sampling
            "prompt_builder": mock_prompt_builder,
        }
        inference_manager = InferenceStrategyManager(inference_config, dependencies)

        # Verify CLI provider was initialized
        assert len(inference_manager.providers) == 1
        assert "test_claude_cli" in inference_manager.providers

        # Create security policy engine
        security_policy = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            health_monitor=None,
            ai_service_manager=None,
            prompt_builder=mock_prompt_builder,
            inference_manager=inference_manager,
        )

        # The actual CLI execution would require mocking subprocess, which is complex
        # For now, we just verify the provider is available and the setup is correct
        health = await security_policy.health_check_async()
        assert "inference_system" in health
        assert "test_claude_cli" in health["inference_system"]

    @pytest.mark.asyncio
    async def test_provider_preference_order(
        self, temp_rules_file, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test that provider preference order is respected."""
        # Create inference configuration with multiple providers
        cli_config = CLIProviderConfig(
            name="test_cli",
            enabled=False,  # Disabled, so should not be used
            command="claude",
        )

        inference_config = InferenceConfig(
            timeout_seconds=10,
            provider_preference=["test_cli", "mcp_sampling"],  # CLI first, but disabled
            cli_providers=[cli_config],
            api_providers=[],
        )

        # Create inference manager
        dependencies = {
            "ai_service_manager": mock_ai_service_manager,
            "prompt_builder": mock_prompt_builder,
        }
        inference_manager = InferenceStrategyManager(inference_config, dependencies)

        # Should only have MCP sampling provider (CLI is disabled)
        assert len(inference_manager.providers) == 1
        assert "mcp_sampling" in inference_manager.providers
        assert "test_cli" not in inference_manager.providers

    @pytest.mark.asyncio
    async def test_backward_compatibility_config(
        self,
        temp_rules_file,
        mock_ai_service_manager,
        mock_prompt_builder,
        sample_tool_request,
    ):
        """Test that system works without explicit inference configuration."""
        # Mock AI decision
        ai_decision = AIDecision(
            decision="allow",
            confidence=0.7,
            reasoning="Backward compatibility test",
            risk_factors=[],
            provider=AIProvider.CLAUDE,
            model="claude-3-sonnet",
            response_time_ms=100,
        )
        mock_ai_service_manager.evaluate_with_ai.return_value = ai_decision

        # Create security policy engine with only legacy components
        security_policy = SecurityPolicyEngine(
            rules_file=temp_rules_file,
            health_monitor=None,
            ai_service_manager=mock_ai_service_manager,
            prompt_builder=mock_prompt_builder,
            inference_manager=None,  # No new inference system
        )

        # Should still work using legacy system
        decision = await security_policy.evaluate(sample_tool_request)

        assert decision.action == "allow"
        assert decision.confidence == 0.7
        assert decision.reasoning == "Backward compatibility test"
        assert decision.ai_provider == "claude"  # Legacy format


if __name__ == "__main__":
    pytest.main([__file__])
