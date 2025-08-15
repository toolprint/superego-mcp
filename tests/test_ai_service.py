"""Tests for AI service integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from superego_mcp.domain.models import ErrorCode, SuperegoError
from superego_mcp.infrastructure.ai_service import (
    AIDecision,
    AIProvider,
    AIServiceManager,
    ClaudeService,
    OpenAIService,
    SamplingConfig,
)


@pytest.fixture
def sampling_config():
    """Create test sampling configuration."""
    return SamplingConfig(
        enabled=True,
        primary_provider=AIProvider.CLAUDE,
        fallback_provider=AIProvider.OPENAI,
        timeout_seconds=5,
        cache_ttl_seconds=60,
        max_concurrent_requests=5,
        temperature=0.0,
    )


@pytest.fixture
def mock_httpx_client():
    """Create mock httpx client."""
    client = MagicMock(spec=httpx.AsyncClient)
    return client


class TestClaudeService:
    """Test Claude AI service implementation."""

    @pytest.mark.asyncio
    async def test_successful_evaluation(self, sampling_config, mock_httpx_client):
        """Test successful Claude evaluation."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {
                    "text": '{"decision": "allow", "confidence": 0.9, "reasoning": "Safe operation", "risk_factors": []}'
                }
            ]
        }
        mock_response.status_code = 200

        # Setup mock client
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        # Create service
        service = ClaudeService(sampling_config, "test-api-key")
        service.client = mock_httpx_client

        # Test evaluation
        result = await service.evaluate("Test prompt")

        assert result.decision == "allow"
        assert result.confidence == 0.9
        assert result.reasoning == "Safe operation"
        assert result.provider == AIProvider.CLAUDE
        assert result.risk_factors == []

    @pytest.mark.asyncio
    async def test_parse_non_json_response(self, sampling_config, mock_httpx_client):
        """Test parsing non-JSON Claude response."""
        # Mock response with plain text format
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {
                    "text": """DECISION: deny
REASON: Potential security risk detected
CONFIDENCE: 0.8"""
                }
            ]
        }
        mock_response.status_code = 200

        # Setup mock client
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        # Create service
        service = ClaudeService(sampling_config, "test-api-key")
        service.client = mock_httpx_client

        # Test evaluation
        result = await service.evaluate("Test prompt")

        assert result.decision == "deny"
        assert result.confidence == 0.8
        assert result.reasoning == "Potential security risk detected"

    @pytest.mark.asyncio
    async def test_api_error_handling(self, sampling_config, mock_httpx_client):
        """Test Claude API error handling."""
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_response
        )

        # Setup mock client
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        # Create service
        service = ClaudeService(sampling_config, "test-api-key")
        service.client = mock_httpx_client

        # Test evaluation should raise SuperegoError
        with pytest.raises(SuperegoError) as exc_info:
            await service.evaluate("Test prompt")

        assert exc_info.value.code == ErrorCode.AI_SERVICE_UNAVAILABLE


class TestOpenAIService:
    """Test OpenAI service implementation."""

    @pytest.mark.asyncio
    async def test_successful_evaluation(self, sampling_config, mock_httpx_client):
        """Test successful OpenAI evaluation."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"decision": "deny", "confidence": 0.95, "reasoning": "Dangerous operation", "risk_factors": ["file_deletion"]}'
                    }
                }
            ]
        }
        mock_response.status_code = 200

        # Setup mock client
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        # Create service
        service = OpenAIService(sampling_config, "test-api-key")
        service.client = mock_httpx_client

        # Test evaluation
        result = await service.evaluate("Test prompt")

        assert result.decision == "deny"
        assert result.confidence == 0.95
        assert result.reasoning == "Dangerous operation"
        assert result.provider == AIProvider.OPENAI
        assert result.risk_factors == ["file_deletion"]


class TestAIServiceManager:
    """Test AI service manager with caching and fallback."""

    @pytest.mark.asyncio
    async def test_successful_evaluation_with_cache(self, sampling_config):
        """Test evaluation with caching."""
        # Create manager with mocked services
        manager = AIServiceManager(sampling_config)

        # Mock the services
        mock_claude_service = AsyncMock()
        mock_decision = AIDecision(
            decision="allow",
            confidence=0.85,
            reasoning="Cached decision",
            risk_factors=[],
            provider=AIProvider.CLAUDE,
            model="claude-3",
            response_time_ms=100,
        )
        mock_claude_service.evaluate.return_value = mock_decision

        manager._services[AIProvider.CLAUDE] = mock_claude_service

        # First call should hit the service
        result1 = await manager.evaluate_with_ai("Test prompt", cache_key="test-key")
        assert result1.decision == "allow"
        assert mock_claude_service.evaluate.call_count == 1

        # Second call with same key should use cache
        result2 = await manager.evaluate_with_ai("Test prompt", cache_key="test-key")
        assert result2.decision == "allow"
        assert mock_claude_service.evaluate.call_count == 1  # No additional calls

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self, sampling_config):
        """Test fallback to secondary provider."""
        # Create manager
        manager = AIServiceManager(sampling_config)

        # Mock services
        mock_claude_service = AsyncMock()
        mock_claude_service.evaluate.side_effect = SuperegoError(
            ErrorCode.AI_SERVICE_UNAVAILABLE, "Claude unavailable", "Service error"
        )

        mock_openai_service = AsyncMock()
        mock_openai_service.evaluate.return_value = AIDecision(
            decision="deny",
            confidence=0.7,
            reasoning="Fallback decision",
            risk_factors=["fallback"],
            provider=AIProvider.OPENAI,
            model="gpt-4",
            response_time_ms=150,
        )

        manager._services[AIProvider.CLAUDE] = mock_claude_service
        manager._services[AIProvider.OPENAI] = mock_openai_service

        # Should fallback to OpenAI
        result = await manager.evaluate_with_ai("Test prompt")
        assert result.provider == AIProvider.OPENAI
        assert result.decision == "deny"
        assert "fallback" in result.risk_factors

    @pytest.mark.asyncio
    async def test_all_providers_fail(self, sampling_config):
        """Test when all providers fail."""
        # Create manager
        manager = AIServiceManager(sampling_config)

        # Mock both services to fail
        mock_claude_service = AsyncMock()
        mock_claude_service.evaluate.side_effect = SuperegoError(
            ErrorCode.AI_SERVICE_UNAVAILABLE, "Claude error", "Service error"
        )

        mock_openai_service = AsyncMock()
        mock_openai_service.evaluate.side_effect = SuperegoError(
            ErrorCode.AI_SERVICE_UNAVAILABLE, "OpenAI error", "Service error"
        )

        manager._services[AIProvider.CLAUDE] = mock_claude_service
        manager._services[AIProvider.OPENAI] = mock_openai_service

        # Should raise error when all fail
        with pytest.raises(SuperegoError) as exc_info:
            await manager.evaluate_with_ai("Test prompt")

        assert exc_info.value.code == ErrorCode.AI_SERVICE_UNAVAILABLE
        assert "All AI providers failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, sampling_config):
        """Test circuit breaker integration."""
        from superego_mcp.infrastructure.circuit_breaker import CircuitBreaker

        # Create circuit breaker
        circuit_breaker = CircuitBreaker(
            failure_threshold=2, recovery_timeout=1, timeout_seconds=1
        )

        # Create manager with circuit breaker
        manager = AIServiceManager(sampling_config, circuit_breaker)

        # Mock service that times out
        mock_service = AsyncMock()
        mock_service.evaluate = AsyncMock()

        async def slow_evaluate(*args):
            await asyncio.sleep(2)  # Longer than timeout
            return MagicMock()

        mock_service.evaluate.side_effect = slow_evaluate
        manager._services[AIProvider.CLAUDE] = mock_service

        # First few calls should timeout
        for _ in range(2):
            with pytest.raises((TimeoutError, Exception)):
                await manager.evaluate_with_ai("Test prompt")

        # Circuit should now be open
        assert circuit_breaker.state == "open"

    def test_health_status(self, sampling_config):
        """Test health status reporting."""
        manager = AIServiceManager(sampling_config)

        # Mock services
        manager._services[AIProvider.CLAUDE] = MagicMock()
        manager._cache["test-key"] = (MagicMock(), 0)

        health = manager.get_health_status()

        assert health["enabled"] is True
        assert health["primary_provider"] == AIProvider.CLAUDE
        assert AIProvider.CLAUDE in health["services_initialized"]
        assert health["cache_size"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_request_limiting(self, sampling_config):
        """Test concurrent request limiting."""
        # Create config with low limit
        config = SamplingConfig(
            enabled=True,
            primary_provider=AIProvider.CLAUDE,
            max_concurrent_requests=2,
        )

        manager = AIServiceManager(config)

        # Mock service with delay
        mock_service = AsyncMock()

        async def delayed_evaluate(*args):
            await asyncio.sleep(0.1)
            return AIDecision(
                decision="allow",
                confidence=0.8,
                reasoning="Test",
                risk_factors=[],
                provider=AIProvider.CLAUDE,
                model="test",
                response_time_ms=100,
            )

        mock_service.evaluate.side_effect = delayed_evaluate
        manager._services[AIProvider.CLAUDE] = mock_service

        # Launch more requests than limit
        tasks = [manager.evaluate_with_ai(f"Prompt {i}") for i in range(5)]

        # Should complete without error but be rate limited
        results = await asyncio.gather(*tasks)
        assert len(results) == 5
        assert all(r.decision == "allow" for r in results)
