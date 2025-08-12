"""Optimized AI Service with connection pooling and request queuing."""

import asyncio
import hashlib
import json
import os
import time
from typing import Any, Optional

import structlog
from pydantic import BaseModel

from ..domain.models import Decision, ErrorCode, SuperegoError, ToolRequest
from .ai_service import (
    AIDecision,
    AIProvider,
    AIServiceManager,
    BaseAIService,
    SamplingConfig,
)
from .performance import ConnectionPool, ResponseCache
from .request_queue import Priority, RequestQueue


logger = structlog.get_logger(__name__)


class OptimizedClaudeService(BaseAIService):
    """Claude service with connection pooling."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self, config: SamplingConfig, api_key: str, connection_pool: ConnectionPool
    ):
        """Initialize with shared connection pool."""
        super().__init__(config, api_key)
        # Replace default client with pooled client
        self.client = connection_pool

    async def evaluate(self, prompt: str) -> AIDecision:
        """Evaluate using Claude API with connection pooling."""
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
            response = await self.client.request(
                "POST", self.API_URL, headers=headers, json=payload
            )
            response.raise_for_status()

            response_time_ms = int((time.perf_counter() - start_time) * 1000)
            data = response.json()
            content = data["content"][0]["text"]

            return self._parse_response(
                content, AIProvider.CLAUDE, self.config.claude_model, response_time_ms
            )

        except Exception as e:
            self.logger.error("Claude service error", error=str(e))
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                f"Claude service error: {str(e)}",
                "AI service temporarily unavailable",
            )

    async def close(self):
        """Don't close shared connection pool."""
        pass  # Connection pool managed externally


class OptimizedOpenAIService(BaseAIService):
    """OpenAI service with connection pooling."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self, config: SamplingConfig, api_key: str, connection_pool: ConnectionPool
    ):
        """Initialize with shared connection pool."""
        super().__init__(config, api_key)
        # Replace default client with pooled client
        self.client = connection_pool

    async def evaluate(self, prompt: str) -> AIDecision:
        """Evaluate using OpenAI API with connection pooling."""
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
            response = await self.client.request(
                "POST", self.API_URL, headers=headers, json=payload
            )
            response.raise_for_status()

            response_time_ms = int((time.perf_counter() - start_time) * 1000)
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            return self._parse_response(
                content, AIProvider.OPENAI, self.config.openai_model, response_time_ms
            )

        except Exception as e:
            self.logger.error("OpenAI service error", error=str(e))
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                f"OpenAI service error: {str(e)}",
                "AI service temporarily unavailable",
            )

    async def close(self):
        """Don't close shared connection pool."""
        pass  # Connection pool managed externally


class AIEvaluationRequest(BaseModel):
    """Request for AI evaluation."""

    tool_request: ToolRequest
    prompt: str
    cache_key: str
    priority: Priority = Priority.NORMAL


class OptimizedAIServiceManager(AIServiceManager):
    """AI service manager with performance optimizations."""

    def __init__(
        self,
        config: SamplingConfig,
        circuit_breaker=None,
        connection_pool: Optional[ConnectionPool] = None,
        response_cache: Optional[ResponseCache] = None,
        request_queue: Optional[RequestQueue] = None,
        metrics_collector=None,
    ):
        """Initialize with performance enhancements.

        Args:
            config: Sampling configuration
            circuit_breaker: Circuit breaker instance
            connection_pool: Shared connection pool
            response_cache: Response cache instance
            request_queue: Request queue for AI sampling
            metrics_collector: Metrics collector instance
        """
        # Don't call parent __init__ to avoid duplicate initialization
        self.config = config
        self.circuit_breaker = circuit_breaker
        self.logger = structlog.get_logger(__name__)
        self.metrics_collector = metrics_collector

        # Use provided instances or create new ones
        self.connection_pool = connection_pool or ConnectionPool(
            max_connections=100, max_keepalive_connections=20, keepalive_expiry=30
        )

        self.response_cache = response_cache or ResponseCache(
            max_size=1000, default_ttl=config.cache_ttl_seconds
        )

        self.request_queue = request_queue

        # Initialize services with connection pooling
        self._services: dict[AIProvider, BaseAIService] = {}
        self._init_optimized_services()

        # Semaphore for concurrent request limiting
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)

    def _init_optimized_services(self):
        """Initialize optimized AI service instances."""
        # Claude service
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        if claude_key and self.config.primary_provider == AIProvider.CLAUDE:
            self._services[AIProvider.CLAUDE] = OptimizedClaudeService(
                self.config, claude_key, self.connection_pool
            )

        # OpenAI service
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and self.config.fallback_provider == AIProvider.OPENAI:
            self._services[AIProvider.OPENAI] = OptimizedOpenAIService(
                self.config, openai_key, self.connection_pool
            )

    async def evaluate_with_ai(
        self, prompt: str, cache_key: str | None = None
    ) -> AIDecision:
        """Evaluate prompt with AI using optimized caching and queuing."""
        # Generate cache key if not provided
        if cache_key is None:
            cache_key = self._generate_cache_key(prompt)

        # Check response cache first
        cached = await self.response_cache.get(cache_key)
        if cached:
            self.logger.debug("Using cached AI decision", cache_key=cache_key)
            if self.metrics_collector:
                await self.metrics_collector.update_cache_metrics(
                    "ai_response", hit=True, size=1
                )
            return cached

        if self.metrics_collector:
            await self.metrics_collector.update_cache_metrics(
                "ai_response", hit=False, size=1
            )

        # If queue is available, use it for better concurrency control
        if self.request_queue and self.request_queue._running:
            return await self._evaluate_with_queue(prompt, cache_key)
        else:
            return await self._evaluate_direct(prompt, cache_key)

    async def _evaluate_with_queue(self, prompt: str, cache_key: str) -> AIDecision:
        """Evaluate using request queue."""

        async def process_request(req: dict) -> AIDecision:
            return await self._evaluate_direct(req["prompt"], req["cache_key"])

        # Add to queue with normal priority
        request = {"prompt": prompt, "cache_key": cache_key}
        result = await self.request_queue.enqueue(
            request, priority=Priority.NORMAL, request_id=cache_key
        )

        return result

    async def _evaluate_direct(self, prompt: str, cache_key: str) -> AIDecision:
        """Direct evaluation with providers."""
        start_time = time.time()

        # Enforce concurrent request limit
        async with self._semaphore:
            # Record queue wait time if metrics available
            if self.metrics_collector:
                wait_time = time.time() - start_time
                await self.metrics_collector.update_queue_metrics(
                    "ai_sampling", self._semaphore._value, wait_time
                )

            # Try primary provider
            if self.config.primary_provider in self._services:
                try:
                    decision = await self._evaluate_with_provider(
                        self._services[self.config.primary_provider], prompt
                    )

                    # Cache successful response
                    await self.response_cache.set(cache_key, decision)

                    # Record metrics
                    if self.metrics_collector:
                        await self.metrics_collector.record_ai_sampling(
                            str(self.config.primary_provider), "success"
                        )

                    return decision

                except SuperegoError:
                    self.logger.warning(
                        "Primary AI provider failed",
                        provider=self.config.primary_provider,
                    )
                    if self.metrics_collector:
                        await self.metrics_collector.record_ai_sampling(
                            str(self.config.primary_provider), "error"
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
                    await self.response_cache.set(cache_key, decision)

                    # Record metrics
                    if self.metrics_collector:
                        await self.metrics_collector.record_ai_sampling(
                            str(self.config.fallback_provider), "success"
                        )

                    return decision

                except SuperegoError:
                    self.logger.error(
                        "Fallback AI provider also failed",
                        provider=self.config.fallback_provider,
                    )
                    if self.metrics_collector:
                        await self.metrics_collector.record_ai_sampling(
                            str(self.config.fallback_provider), "error"
                        )

            # All providers failed
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "All AI providers failed",
                "AI evaluation service is currently unavailable",
            )

    def _generate_cache_key(self, prompt: str) -> str:
        """Generate cache key from prompt."""
        # Use first 8 chars of hash for readable keys
        return f"ai_{hashlib.sha256(prompt.encode()).hexdigest()[:8]}"

    async def close(self):
        """Close connections and cleanup."""
        # Close services (they won't close shared pool)
        for service in self._services.values():
            await service.close()

        # Close connection pool
        await self.connection_pool.close()

    def get_health_status(self) -> dict[str, Any]:
        """Get enhanced health status."""
        base_status = super().get_health_status()

        # Add performance metrics
        base_status.update(
            {
                "connection_pool": self.connection_pool.get_stats(),
                "response_cache": asyncio.create_task(self.response_cache.get_stats()),
                "queue_stats": self.request_queue.get_stats()
                if self.request_queue
                else None,
                "concurrent_limit": self.config.max_concurrent_requests,
                "concurrent_available": self._semaphore._value,
            }
        )

        return base_status
