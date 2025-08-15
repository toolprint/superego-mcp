"""AI Service integration for LLM-based security evaluation."""

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Protocol

import httpx
import structlog
from pydantic import BaseModel, Field

from ..domain.models import ErrorCode, SuperegoError


class AIProvider(str, Enum):
    """Supported AI providers."""

    CLAUDE = "claude"
    OPENAI = "openai"


class AIDecision(BaseModel):
    """AI evaluation decision response."""

    decision: str = Field(..., pattern="^(allow|deny)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    risk_factors: list[str] = Field(default_factory=list)
    provider: AIProvider
    model: str
    response_time_ms: int


class SamplingConfig(BaseModel):
    """Configuration for AI sampling."""

    enabled: bool = True
    primary_provider: AIProvider = AIProvider.CLAUDE
    fallback_provider: AIProvider | None = AIProvider.OPENAI
    timeout_seconds: int = 10
    cache_ttl_seconds: int = 300
    max_concurrent_requests: int = 10

    # Provider-specific settings
    claude_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4-turbo-preview"
    temperature: float = 0.0  # Low temperature for consistent security decisions


class AIServiceProtocol(Protocol):
    """Protocol for AI service implementations."""

    async def evaluate(self, prompt: str) -> AIDecision:
        """Evaluate a security request using AI."""
        ...


class BaseAIService(ABC):
    """Base class for AI service implementations."""

    def __init__(self, config: SamplingConfig, api_key: str):
        self.config = config
        self.api_key = api_key
        self.logger = structlog.get_logger(self.__class__.__name__)
        self.client = httpx.AsyncClient(timeout=config.timeout_seconds)

    @abstractmethod
    async def evaluate(self, prompt: str) -> AIDecision:
        """Evaluate a security request using AI."""
        pass

    def _parse_response(
        self,
        response_text: str,
        provider: AIProvider,
        model: str,
        response_time_ms: int,
    ) -> AIDecision:
        """Parse AI response into structured decision."""
        try:
            # Try to extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)
            else:
                # Fallback parsing for non-JSON responses
                lines = response_text.strip().split("\n")
                data = {}

                for line in lines:
                    if line.startswith("DECISION:"):
                        decision = line.split(":", 1)[1].strip().lower()
                        data["decision"] = "allow" if decision == "allow" else "deny"
                    elif line.startswith("REASON:"):
                        data["reasoning"] = line.split(":", 1)[1].strip()
                    elif line.startswith("CONFIDENCE:"):
                        try:
                            data["confidence"] = float(line.split(":", 1)[1].strip())
                        except ValueError:
                            data["confidence"] = 0.7

            # Validate and return decision
            return AIDecision(
                decision=data.get("decision", "deny"),  # Default to deny for safety
                confidence=data.get("confidence", 0.5),
                reasoning=data.get(
                    "reasoning", data.get("reason", "Failed to parse AI response")
                ),
                risk_factors=data.get("risk_factors", []),
                provider=provider,
                model=model,
                response_time_ms=response_time_ms,
            )

        except Exception as e:
            self.logger.error(
                "Failed to parse AI response",
                error=str(e),
                response=response_text[:200],
            )
            # Return safe default on parse failure
            return AIDecision(
                decision="deny",
                confidence=0.3,
                reasoning="Failed to parse AI response - defaulting to deny",
                risk_factors=["parse_error"],
                provider=provider,
                model=model,
                response_time_ms=response_time_ms,
            )

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class ClaudeService(BaseAIService):
    """Claude AI service implementation."""

    API_URL = "https://api.anthropic.com/v1/messages"

    async def evaluate(self, prompt: str) -> AIDecision:
        """Evaluate using Claude API."""
        start_time = time.perf_counter()

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.config.claude_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature,
            "max_tokens": 500,
        }

        try:
            response = await self.client.post(
                self.API_URL, headers=headers, json=payload
            )
            response.raise_for_status()

            response_time_ms = int((time.perf_counter() - start_time) * 1000)
            data = response.json()
            content = data["content"][0]["text"]

            return self._parse_response(
                content, AIProvider.CLAUDE, self.config.claude_model, response_time_ms
            )

        except httpx.HTTPStatusError as e:
            self.logger.error(
                "Claude API error", status=e.response.status_code, error=str(e)
            )
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                f"Claude API error: {e.response.status_code}",
                "AI service temporarily unavailable",
            ) from e
        except Exception as e:
            self.logger.error("Claude service error", error=str(e))
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                f"Claude service error: {str(e)}",
                "AI service temporarily unavailable",
            ) from e


class OpenAIService(BaseAIService):
    """OpenAI service implementation."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    async def evaluate(self, prompt: str) -> AIDecision:
        """Evaluate using OpenAI API."""
        start_time = time.perf_counter()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a security evaluation system. Respond with JSON containing: decision (allow/deny), confidence (0.0-1.0), reasoning, and risk_factors array.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self.client.post(
                self.API_URL, headers=headers, json=payload
            )
            response.raise_for_status()

            response_time_ms = int((time.perf_counter() - start_time) * 1000)
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            return self._parse_response(
                content, AIProvider.OPENAI, self.config.openai_model, response_time_ms
            )

        except httpx.HTTPStatusError as e:
            self.logger.error(
                "OpenAI API error", status=e.response.status_code, error=str(e)
            )
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                f"OpenAI API error: {e.response.status_code}",
                "AI service temporarily unavailable",
            ) from e
        except Exception as e:
            self.logger.error("OpenAI service error", error=str(e))
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                f"OpenAI service error: {str(e)}",
                "AI service temporarily unavailable",
            ) from e


class AIServiceManager:
    """Manages AI service instances with caching and fallback."""

    def __init__(self, config: SamplingConfig, circuit_breaker: Any = None) -> None:
        self.config = config
        self.circuit_breaker = circuit_breaker
        self.logger = structlog.get_logger(__name__)

        # Initialize services
        self._services: dict[AIProvider, BaseAIService] = {}
        self._init_services()

        # Simple in-memory cache
        self._cache: dict[str, tuple[AIDecision, float]] = {}
        self._cache_lock = asyncio.Lock()

        # Semaphore for concurrent request limiting
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)

    def _init_services(self) -> None:
        """Initialize AI service instances."""
        # Claude service
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        if claude_key and self.config.primary_provider == AIProvider.CLAUDE:
            self._services[AIProvider.CLAUDE] = ClaudeService(self.config, claude_key)

        # OpenAI service
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and self.config.fallback_provider == AIProvider.OPENAI:
            self._services[AIProvider.OPENAI] = OpenAIService(self.config, openai_key)

    async def evaluate_with_ai(
        self, prompt: str, cache_key: str | None = None
    ) -> AIDecision:
        """Evaluate prompt with AI, using cache and fallback as needed."""
        # Check cache first
        if cache_key:
            cached = await self._get_cached(cache_key)
            if cached:
                self.logger.debug("Using cached AI decision", cache_key=cache_key)
                return cached

        # Enforce concurrent request limit
        async with self._semaphore:
            # Try primary provider
            if self.config.primary_provider in self._services:
                try:
                    decision = await self._evaluate_with_provider(
                        self._services[self.config.primary_provider], prompt
                    )

                    # Cache successful response
                    if cache_key:
                        await self._set_cached(cache_key, decision)

                    return decision

                except SuperegoError:
                    self.logger.warning(
                        "Primary AI provider failed",
                        provider=self.config.primary_provider,
                    )

            # Try fallback provider
            if (
                self.config.fallback_provider
                and self.config.fallback_provider in self._services
            ):
                try:
                    decision = await self._evaluate_with_provider(
                        self._services[self.config.fallback_provider], prompt
                    )

                    # Cache successful response
                    if cache_key:
                        await self._set_cached(cache_key, decision)

                    return decision

                except SuperegoError:
                    self.logger.error(
                        "Fallback AI provider also failed",
                        provider=self.config.fallback_provider,
                    )

            # All providers failed
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "All AI providers failed",
                "AI evaluation service is currently unavailable",
            )

    async def _evaluate_with_provider(
        self, service: BaseAIService, prompt: str
    ) -> AIDecision:
        """Evaluate with specific provider, using circuit breaker if available."""
        if self.circuit_breaker:
            result = await self.circuit_breaker.call(service.evaluate, prompt)
            # Circuit breaker returns Any, but we know it should be AIDecision
            return result  # type: ignore[no-any-return]
        else:
            return await service.evaluate(prompt)

    async def _get_cached(self, cache_key: str) -> AIDecision | None:
        """Get cached decision if still valid."""
        async with self._cache_lock:
            if cache_key in self._cache:
                decision, timestamp = self._cache[cache_key]
                if time.time() - timestamp < self.config.cache_ttl_seconds:
                    return decision
                else:
                    # Expired
                    del self._cache[cache_key]
        return None

    async def _set_cached(self, cache_key: str, decision: AIDecision) -> None:
        """Cache a decision."""
        async with self._cache_lock:
            self._cache[cache_key] = (decision, time.time())

            # Simple cache size management (LRU-ish)
            if len(self._cache) > 1000:
                # Remove oldest entries
                sorted_keys = sorted(
                    self._cache.keys(), key=lambda k: self._cache[k][1]
                )
                for key in sorted_keys[:100]:
                    del self._cache[key]

    async def close(self) -> None:
        """Close all service connections."""
        for service in self._services.values():
            await service.close()

    def get_health_status(self) -> dict[str, Any]:
        """Get health status for monitoring."""
        return {
            "enabled": self.config.enabled,
            "primary_provider": self.config.primary_provider,
            "fallback_provider": self.config.fallback_provider,
            "services_initialized": list(self._services.keys()),
            "cache_size": len(self._cache),
            "circuit_breaker_state": (
                self.circuit_breaker.get_state() if self.circuit_breaker else None
            ),
        }
