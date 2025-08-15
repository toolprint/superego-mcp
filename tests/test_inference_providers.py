"""Tests for the new inference provider system."""

import asyncio
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from superego_mcp.domain.models import (
    ErrorCode,
    SecurityRule,
    SuperegoError,
    ToolAction,
    ToolRequest,
)
from superego_mcp.infrastructure.ai_service import (
    AIDecision,
    AIProvider,
    AIServiceManager,
)
from superego_mcp.infrastructure.inference import (
    APIProvider,
    CLIProvider,
    CLIProviderConfig,
    InferenceConfig,
    InferenceDecision,
    InferenceRequest,
    InferenceStrategyManager,
    MCPSamplingProvider,
)
from superego_mcp.infrastructure.prompt_builder import SecurePromptBuilder


class TestInferenceModels:
    """Test the basic inference data models."""

    def test_inference_request_validation(self):
        """Test InferenceRequest model validation."""
        rule = SecurityRule(
            id="test-rule",
            priority=1,
            conditions={"tool_name": "test_tool"},
            action=ToolAction.SAMPLE,
        )

        request = ToolRequest(
            tool_name="test_tool",
            parameters={"arg": "value"},
            session_id="session-123",
            agent_id="agent-456",
            cwd="/home/user",
        )

        inference_request = InferenceRequest(
            prompt="Test prompt",
            tool_request=request,
            rule=rule,
            cache_key="test-cache-key",
            timeout_seconds=10,
        )

        assert inference_request.prompt == "Test prompt"
        assert inference_request.tool_request == request
        assert inference_request.rule == rule
        assert inference_request.cache_key == "test-cache-key"
        assert inference_request.timeout_seconds == 10

    def test_inference_decision_validation(self):
        """Test InferenceDecision model validation."""
        # Valid decision
        decision = InferenceDecision(
            decision="allow",
            confidence=0.8,
            reasoning="Test reasoning",
            risk_factors=["risk1", "risk2"],
            provider="test_provider",
            model="test_model",
            response_time_ms=100,
        )

        assert decision.decision == "allow"
        assert decision.confidence == 0.8
        assert decision.reasoning == "Test reasoning"
        assert decision.risk_factors == ["risk1", "risk2"]
        assert decision.provider == "test_provider"
        assert decision.model == "test_model"
        assert decision.response_time_ms == 100

    def test_inference_decision_invalid_decision(self):
        """Test InferenceDecision with invalid decision value."""
        with pytest.raises(ValidationError):
            InferenceDecision(
                decision="maybe",  # Invalid - should be allow or deny
                confidence=0.8,
                reasoning="Test reasoning",
                provider="test_provider",
                model="test_model",
                response_time_ms=100,
            )

    def test_inference_decision_invalid_confidence(self):
        """Test InferenceDecision with invalid confidence value."""
        with pytest.raises(ValidationError):
            InferenceDecision(
                decision="allow",
                confidence=1.5,  # Invalid - should be 0.0-1.0
                reasoning="Test reasoning",
                provider="test_provider",
                model="test_model",
                response_time_ms=100,
            )

    def test_cli_provider_config_validation(self):
        """Test CLIProviderConfig model validation."""
        config = CLIProviderConfig(
            name="test_cli",
            enabled=True,
            type="claude",
            command="claude",
            model="claude-3-sonnet",
            system_prompt="Test system prompt",
            api_key_env_var="TEST_API_KEY",
            max_retries=3,
            retry_delay_ms=500,
            timeout_seconds=15,
        )

        assert config.name == "test_cli"
        assert config.enabled is True
        assert config.type == "claude"
        assert config.command == "claude"
        assert config.model == "claude-3-sonnet"
        assert config.system_prompt == "Test system prompt"
        assert config.api_key_env_var == "TEST_API_KEY"
        assert config.max_retries == 3
        assert config.retry_delay_ms == 500
        assert config.timeout_seconds == 15


class TestCLIProvider:
    """Test the CLI provider implementation."""

    @pytest.fixture
    def cli_config(self):
        """Create test CLI configuration."""
        return CLIProviderConfig(
            name="test_claude_cli",
            enabled=True,
            type="claude",
            command="claude",
            model="claude-3-sonnet",
            system_prompt="Test system prompt",
            api_key_env_var="TEST_API_KEY",
            max_retries=2,
            retry_delay_ms=100,
            timeout_seconds=5,
        )

    @pytest.fixture
    def sample_request(self):
        """Create sample inference request."""
        rule = SecurityRule(
            id="test-rule",
            priority=1,
            conditions={"tool_name": "test_tool"},
            action=ToolAction.SAMPLE,
        )

        tool_request = ToolRequest(
            tool_name="test_tool",
            parameters={"file": "test.txt"},
            session_id="session-123",
            agent_id="agent-456",
            cwd="/home/user",
        )

        return InferenceRequest(
            prompt="Evaluate this request",
            tool_request=tool_request,
            rule=rule,
            cache_key="test-cache",
            timeout_seconds=5,
        )

    @patch("subprocess.run")
    def test_cli_provider_initialization_success(self, mock_subprocess, cli_config):
        """Test successful CLI provider initialization."""
        # Mock successful version check
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="claude 1.0.0")

        provider = CLIProvider(cli_config)

        assert provider.config == cli_config
        mock_subprocess.assert_called_once_with(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )

    @patch("subprocess.run")
    def test_cli_provider_initialization_failure(self, mock_subprocess, cli_config):
        """Test CLI provider initialization failure."""
        # Mock failed version check
        mock_subprocess.side_effect = FileNotFoundError()

        with pytest.raises(RuntimeError, match="claude CLI not found in PATH"):
            CLIProvider(cli_config)

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"})
    @patch("subprocess.run")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_cli_provider_evaluate_success(
        self, mock_subprocess_exec, mock_subprocess, cli_config, sample_request
    ):
        """Test successful CLI evaluation."""
        # Mock version check
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Mock CLI execution
        mock_proc = MagicMock()
        mock_proc.returncode = 0

        async def mock_communicate(input=None):
            return (
                json.dumps(
                    {
                        "content": json.dumps(
                            {
                                "decision": "allow",
                                "confidence": 0.8,
                                "reasoning": "File read is safe",
                                "risk_factors": [],
                            }
                        )
                    }
                ).encode(),
                b"",
            )

        mock_proc.communicate = mock_communicate
        mock_subprocess_exec.return_value = mock_proc

        provider = CLIProvider(cli_config)
        decision = await provider.evaluate(sample_request)

        assert decision.decision == "allow"
        assert decision.confidence == 0.8
        assert decision.reasoning == "File read is safe"
        assert decision.risk_factors == []
        assert decision.provider == "claude_cli"
        assert decision.model == "claude-3-sonnet"
        assert decision.response_time_ms >= 0

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"})
    @patch("subprocess.run")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_cli_provider_evaluate_timeout(
        self, mock_subprocess_exec, mock_subprocess, cli_config, sample_request
    ):
        """Test CLI evaluation timeout."""
        # Mock version check
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Mock timeout
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = TimeoutError()
        mock_subprocess_exec.return_value = mock_proc

        provider = CLIProvider(cli_config)

        with pytest.raises(SuperegoError) as exc_info:
            await provider.evaluate(sample_request)

        assert exc_info.value.code == ErrorCode.AI_SERVICE_TIMEOUT

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"})
    @patch("subprocess.run")
    @patch("asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_cli_provider_evaluate_cli_error(
        self, mock_subprocess_exec, mock_subprocess, cli_config, sample_request
    ):
        """Test CLI evaluation with CLI error."""
        # Mock version check
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Mock CLI error
        mock_proc = MagicMock()
        mock_proc.returncode = 1

        async def mock_communicate_error(input=None):
            return (b"", b"CLI error occurred")

        mock_proc.communicate = mock_communicate_error
        mock_subprocess_exec.return_value = mock_proc

        provider = CLIProvider(cli_config)

        with pytest.raises(SuperegoError) as exc_info:
            await provider.evaluate(sample_request)

        assert exc_info.value.code == ErrorCode.AI_SERVICE_UNAVAILABLE

    @patch("subprocess.run")
    def test_cli_provider_sanitize_prompt(self, mock_subprocess, cli_config):
        """Test prompt sanitization."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        provider = CLIProvider(cli_config)

        # Test normal prompt
        normal_prompt = "Evaluate this tool request"
        sanitized = provider._sanitize_prompt(normal_prompt)
        assert sanitized == normal_prompt

        # Test prompt with control characters
        malicious_prompt = "Evaluate\x00this\x1ftool\x7frequest"
        sanitized = provider._sanitize_prompt(malicious_prompt)
        assert "\x00" not in sanitized
        assert "\x1f" not in sanitized
        assert "\x7f" not in sanitized

        # Test very long prompt
        long_prompt = "x" * 15000
        sanitized = provider._sanitize_prompt(long_prompt)
        assert len(sanitized) <= 10000 + len("... [truncated for security]")

    @patch("subprocess.run")
    def test_cli_provider_is_valid_model_name(self, mock_subprocess, cli_config):
        """Test model name validation."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        provider = CLIProvider(cli_config)

        # Valid model names
        assert provider._is_valid_model_name("claude-3-sonnet")
        assert provider._is_valid_model_name("gpt-4")
        assert provider._is_valid_model_name("model.v1.0")
        assert provider._is_valid_model_name("test_model")

        # Invalid model names
        assert not provider._is_valid_model_name("model; rm -rf /")
        assert not provider._is_valid_model_name("model && malicious")
        assert not provider._is_valid_model_name("model|cat /etc/passwd")
        assert not provider._is_valid_model_name("x" * 200)  # Too long

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"})
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_cli_provider_health_check_success(self, mock_subprocess, cli_config):
        """Test successful health check."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        provider = CLIProvider(cli_config)

        health = await provider.health_check()

        assert health.healthy is True
        assert "CLI available" in health.message

    @patch.dict(os.environ, {})  # No API key
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_cli_provider_health_check_no_api_key(
        self, mock_subprocess, cli_config
    ):
        """Test health check with missing API key."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        provider = CLIProvider(cli_config)

        health = await provider.health_check()

        assert health.healthy is True
        assert "OAuth/CLI auth" in health.message

    @patch("subprocess.run")
    def test_cli_provider_get_provider_info(self, mock_subprocess, cli_config):
        """Test getting provider information."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        provider = CLIProvider(cli_config)

        info = provider.get_provider_info()

        assert info.name == "test_claude_cli"
        assert info.type == "cli"
        assert "claude-3-sonnet" in info.models
        assert info.capabilities["non_interactive"] is True
        assert info.capabilities["json_output"] is True
        assert info.capabilities["security_restricted"] is True


class TestMCPSamplingProvider:
    """Test the MCP sampling provider wrapper."""

    @pytest.fixture
    def mock_ai_service_manager(self):
        """Create mock AI service manager."""
        manager = MagicMock(spec=AIServiceManager)
        manager.get_health_status.return_value = {
            "enabled": True,
            "services_initialized": ["claude", "openai"],
            "circuit_breaker_state": "closed",
        }
        # Create mock config object
        manager.config = MagicMock()
        manager.config.claude_model = "claude-3-sonnet"
        manager.config.openai_model = "gpt-4"
        return manager

    @pytest.fixture
    def mock_prompt_builder(self):
        """Create mock prompt builder."""
        return MagicMock(spec=SecurePromptBuilder)

    @pytest.fixture
    def sample_request(self):
        """Create sample inference request."""
        rule = SecurityRule(
            id="test-rule",
            priority=1,
            conditions={"tool_name": "test_tool"},
            action=ToolAction.SAMPLE,
        )

        tool_request = ToolRequest(
            tool_name="test_tool",
            parameters={"file": "test.txt"},
            session_id="session-123",
            agent_id="agent-456",
            cwd="/home/user",
        )

        return InferenceRequest(
            prompt="Evaluate this request",
            tool_request=tool_request,
            rule=rule,
            cache_key="test-cache",
            timeout_seconds=5,
        )

    @pytest.mark.asyncio
    async def test_mcp_sampling_provider_evaluate_success(
        self, mock_ai_service_manager, mock_prompt_builder, sample_request
    ):
        """Test successful MCP sampling evaluation."""
        # Mock AI decision
        ai_decision = AIDecision(
            decision="allow",
            confidence=0.8,
            reasoning="File read is safe",
            risk_factors=["minor_risk"],
            provider=AIProvider.CLAUDE,
            model="claude-3-sonnet",
            response_time_ms=150,
        )
        mock_ai_service_manager.evaluate_with_ai.return_value = ai_decision

        provider = MCPSamplingProvider(mock_ai_service_manager, mock_prompt_builder)
        decision = await provider.evaluate(sample_request)

        assert decision.decision == "allow"
        assert decision.confidence == 0.8
        assert decision.reasoning == "File read is safe"
        assert decision.risk_factors == ["minor_risk"]
        assert decision.provider == "mcp_claude"
        assert decision.model == "claude-3-sonnet"
        assert decision.response_time_ms == 150

    @pytest.mark.asyncio
    async def test_mcp_sampling_provider_evaluate_failure(
        self, mock_ai_service_manager, mock_prompt_builder, sample_request
    ):
        """Test MCP sampling evaluation failure."""
        # Mock AI service failure
        mock_ai_service_manager.evaluate_with_ai.side_effect = SuperegoError(
            ErrorCode.AI_SERVICE_UNAVAILABLE,
            "AI service failed",
            "Service temporarily unavailable",
        )

        provider = MCPSamplingProvider(mock_ai_service_manager, mock_prompt_builder)

        with pytest.raises(SuperegoError):
            await provider.evaluate(sample_request)

    def test_mcp_sampling_provider_get_provider_info(
        self, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test getting MCP sampling provider information."""
        provider = MCPSamplingProvider(mock_ai_service_manager, mock_prompt_builder)

        info = provider.get_provider_info()

        assert info.name == "mcp_sampling"
        assert info.type == "mcp_sampling"
        assert "claude-3-sonnet" in info.models
        assert "gpt-4" in info.models
        assert info.capabilities["caching"] is True
        assert info.capabilities["fallback"] is True

    @pytest.mark.asyncio
    async def test_mcp_sampling_provider_health_check_healthy(
        self, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test health check when MCP sampling is healthy."""
        provider = MCPSamplingProvider(mock_ai_service_manager, mock_prompt_builder)

        health = await provider.health_check()

        assert health.healthy is True
        assert "MCP sampling available" in health.message

    @pytest.mark.asyncio
    async def test_mcp_sampling_provider_health_check_disabled(
        self, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test health check when MCP sampling is disabled."""
        mock_ai_service_manager.get_health_status.return_value = {
            "enabled": False,
            "services_initialized": [],
        }

        provider = MCPSamplingProvider(mock_ai_service_manager, mock_prompt_builder)

        health = await provider.health_check()

        assert health.healthy is False
        assert "MCP sampling is disabled" in health.message


class TestAPIProvider:
    """Test the API provider placeholder."""

    def test_api_provider_not_implemented(self):
        """Test that API provider raises NotImplementedError."""
        config = {"name": "test_api", "enabled": True}
        provider = APIProvider(config)

        # Create dummy request
        rule = SecurityRule(
            id="test-rule",
            priority=1,
            conditions={"tool_name": "test_tool"},
            action=ToolAction.SAMPLE,
        )

        tool_request = ToolRequest(
            tool_name="test_tool",
            parameters={},
            session_id="session-123",
            agent_id="agent-456",
            cwd="/home/user",
        )

        request = InferenceRequest(
            prompt="Test prompt",
            tool_request=tool_request,
            rule=rule,
            cache_key="test-cache",
            timeout_seconds=5,
        )

        with pytest.raises(NotImplementedError):
            asyncio.run(provider.evaluate(request))

    def test_api_provider_get_provider_info(self):
        """Test API provider information indicates placeholder status."""
        config = {"name": "test_api", "enabled": True}
        provider = APIProvider(config)

        info = provider.get_provider_info()

        assert info.name == "api_placeholder"
        assert info.type == "api"
        assert info.capabilities["implemented"] is False
        assert info.capabilities["planned"] is True

    @pytest.mark.asyncio
    async def test_api_provider_health_check(self):
        """Test API provider health check indicates not implemented."""
        config = {"name": "test_api", "enabled": True}
        provider = APIProvider(config)

        health = await provider.health_check()

        assert health.healthy is False
        assert "not yet implemented" in health.message


class TestInferenceStrategyManager:
    """Test the inference strategy manager."""

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
        return MagicMock(spec=SecurePromptBuilder)

    @pytest.fixture
    def inference_config(self):
        """Create inference configuration."""
        return InferenceConfig(
            timeout_seconds=10,
            provider_preference=["mcp_sampling"],
            cli_providers=[],
            api_providers=[],
        )

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

    @pytest.fixture
    def sample_rule(self):
        """Create sample security rule."""
        return SecurityRule(
            id="test-rule",
            priority=1,
            conditions={"tool_name": "test_tool"},
            action=ToolAction.SAMPLE,
        )

    def test_inference_strategy_manager_initialization(
        self, inference_config, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test strategy manager initialization."""
        dependencies = {
            "ai_service_manager": mock_ai_service_manager,
            "prompt_builder": mock_prompt_builder,
        }

        manager = InferenceStrategyManager(inference_config, dependencies)

        assert len(manager.providers) == 1
        assert "mcp_sampling" in manager.providers
        assert isinstance(manager.providers["mcp_sampling"], MCPSamplingProvider)

    @pytest.mark.asyncio
    async def test_inference_strategy_manager_evaluate_success(
        self,
        inference_config,
        mock_ai_service_manager,
        mock_prompt_builder,
        sample_tool_request,
        sample_rule,
    ):
        """Test successful evaluation through strategy manager."""
        # Mock AI decision
        ai_decision = AIDecision(
            decision="allow",
            confidence=0.8,
            reasoning="File read is safe",
            risk_factors=[],
            provider=AIProvider.CLAUDE,
            model="claude-3-sonnet",
            response_time_ms=150,
        )
        mock_ai_service_manager.evaluate_with_ai.return_value = ai_decision

        dependencies = {
            "ai_service_manager": mock_ai_service_manager,
            "prompt_builder": mock_prompt_builder,
        }

        manager = InferenceStrategyManager(inference_config, dependencies)

        decision = await manager.evaluate(
            request=sample_tool_request,
            rule=sample_rule,
            prompt="Test prompt",
            cache_key="test-cache",
        )

        assert decision.decision == "allow"
        assert decision.confidence == 0.8
        assert decision.reasoning == "File read is safe"
        assert decision.provider == "mcp_claude"

    @pytest.mark.asyncio
    async def test_inference_strategy_manager_no_providers(
        self, sample_tool_request, sample_rule
    ):
        """Test evaluation with no providers configured."""
        config = InferenceConfig(
            timeout_seconds=10,
            provider_preference=[],
            cli_providers=[],
            api_providers=[],
        )

        dependencies = {}  # No dependencies

        manager = InferenceStrategyManager(config, dependencies)

        with pytest.raises(SuperegoError) as exc_info:
            await manager.evaluate(
                request=sample_tool_request,
                rule=sample_rule,
                prompt="Test prompt",
                cache_key="test-cache",
            )

        assert exc_info.value.code == ErrorCode.INVALID_CONFIGURATION

    @pytest.mark.asyncio
    async def test_inference_strategy_manager_all_providers_fail(
        self,
        inference_config,
        mock_ai_service_manager,
        mock_prompt_builder,
        sample_tool_request,
        sample_rule,
    ):
        """Test evaluation when all providers fail."""
        # Mock AI service failure
        mock_ai_service_manager.evaluate_with_ai.side_effect = SuperegoError(
            ErrorCode.AI_SERVICE_UNAVAILABLE,
            "AI service failed",
            "Service temporarily unavailable",
        )

        dependencies = {
            "ai_service_manager": mock_ai_service_manager,
            "prompt_builder": mock_prompt_builder,
        }

        manager = InferenceStrategyManager(inference_config, dependencies)

        with pytest.raises(SuperegoError) as exc_info:
            await manager.evaluate(
                request=sample_tool_request,
                rule=sample_rule,
                prompt="Test prompt",
                cache_key="test-cache",
            )

        assert exc_info.value.code == ErrorCode.AI_SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_inference_strategy_manager_health_check(
        self, inference_config, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test strategy manager health check."""
        dependencies = {
            "ai_service_manager": mock_ai_service_manager,
            "prompt_builder": mock_prompt_builder,
        }

        manager = InferenceStrategyManager(inference_config, dependencies)

        health = await manager.health_check()

        assert "_summary" in health
        assert health["_summary"]["total_providers"] == 1
        assert health["_summary"]["overall_healthy"] is True
        assert "mcp_sampling" in health

    @pytest.mark.asyncio
    async def test_inference_strategy_manager_cleanup(
        self, inference_config, mock_ai_service_manager, mock_prompt_builder
    ):
        """Test strategy manager cleanup."""
        dependencies = {
            "ai_service_manager": mock_ai_service_manager,
            "prompt_builder": mock_prompt_builder,
        }

        manager = InferenceStrategyManager(inference_config, dependencies)

        # Should not raise any exceptions
        await manager.cleanup()


class TestInferenceConfig:
    """Test inference configuration model."""

    def test_inference_config_defaults(self):
        """Test default inference configuration."""
        config = InferenceConfig()

        assert config.timeout_seconds == 30
        assert config.provider_preference == ["mcp_sampling"]
        assert config.cli_providers == []
        assert config.api_providers == []

    def test_inference_config_with_cli_providers(self):
        """Test inference configuration with CLI providers."""
        cli_config = CLIProviderConfig(name="test_cli", command="claude")

        config = InferenceConfig(
            timeout_seconds=15,
            provider_preference=["test_cli", "mcp_sampling"],
            cli_providers=[cli_config],
        )

        assert config.timeout_seconds == 15
        assert config.provider_preference == ["test_cli", "mcp_sampling"]
        assert len(config.cli_providers) == 1
        assert config.cli_providers[0].name == "test_cli"


if __name__ == "__main__":
    pytest.main([__file__])
