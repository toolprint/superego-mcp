"""Optimized security policy engine with caching and performance tracking."""

import hashlib
import time

import structlog

from ..domain.models import (
    Decision,
    ErrorCode,
    SecurityRule,
    SuperegoError,
    ToolAction,
    ToolRequest,
)
from ..domain.security_policy import SecurityPolicyEngine
from ..infrastructure.performance import PerformanceMonitor, ResponseCache

logger = structlog.get_logger(__name__)


class OptimizedSecurityPolicyEngine(SecurityPolicyEngine):
    """Security policy engine with performance optimizations."""

    def __init__(  # type: ignore[no-untyped-def]
        self,
        rules_file,
        ai_service_manager=None,
        prompt_builder=None,
        response_cache: ResponseCache | None = None,
        performance_monitor: PerformanceMonitor | None = None,
        metrics_collector=None,
    ):
        """Initialize with performance enhancements.

        Args:
            rules_file: Path to rules YAML file
            ai_service_manager: AI service manager instance
            prompt_builder: Prompt builder instance
            response_cache: Response cache for decisions
            performance_monitor: Performance monitoring instance
            metrics_collector: Metrics collector instance
        """
        super().__init__(rules_file, ai_service_manager, prompt_builder)

        self.response_cache = response_cache or ResponseCache(
            max_size=1000, default_ttl=300
        )

        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.metrics_collector = metrics_collector

    async def evaluate(self, request: ToolRequest) -> Decision:
        """Evaluate tool request with caching and performance tracking."""
        start_time = time.perf_counter()

        # Generate cache key for the request
        cache_key = self._generate_request_cache_key(request)

        # Check cache first
        cached_decision = await self.response_cache.get(cache_key)
        if cached_decision:
            logger.debug("Using cached decision", cache_key=cache_key)
            if self.metrics_collector:
                await self.metrics_collector.update_cache_metrics(
                    "decision_cache", hit=True, size=1
                )
            # Cache returns Any, but we know it's a Decision
            from typing import cast

            return cast(Decision, cached_decision)

        if self.metrics_collector:
            await self.metrics_collector.update_cache_metrics(
                "decision_cache", hit=False, size=1
            )

        try:
            # Track in-flight request
            if self.metrics_collector:
                with self.metrics_collector.track_request("security_evaluation"):
                    decision = await self._evaluate_uncached(request, start_time)
            else:
                decision = await self._evaluate_uncached(request, start_time)

            # Cache the decision
            await self.response_cache.set(cache_key, decision)

            # Record performance metrics
            duration = time.perf_counter() - start_time
            await self.performance_monitor.record_timing("rule_evaluation", duration)

            if self.metrics_collector:
                await self.metrics_collector.record_security_evaluation(
                    decision.action, decision.rule_id, duration
                )

            return decision

        except Exception as e:
            # Record error metrics
            duration = time.perf_counter() - start_time
            if self.metrics_collector:
                await self.metrics_collector.record_security_evaluation(
                    "error", None, duration
                )
            return self._handle_error(e, request, start_time)

    async def _evaluate_uncached(
        self, request: ToolRequest, start_time: float
    ) -> Decision:
        """Evaluate request without caching."""
        # Find first matching rule (highest priority)
        matching_rule = self._find_matching_rule(request)

        if not matching_rule:
            # Default allow if no rules match
            return Decision(
                action="allow",
                reason="No security rules matched",
                confidence=0.5,
                processing_time_ms=int((time.perf_counter() - start_time) * 1000),
            )

        if matching_rule.action == ToolAction.SAMPLE:
            # Delegate to AI sampling engine
            return await self._handle_sampling_optimized(
                request, matching_rule, start_time
            )

        return Decision(
            action=matching_rule.action.value,
            reason=matching_rule.reason or f"Rule {matching_rule.id} matched",
            rule_id=matching_rule.id,
            confidence=1.0,  # Rule-based decisions are certain
            processing_time_ms=int((time.perf_counter() - start_time) * 1000),
        )

    async def _handle_sampling_optimized(  # type: ignore[no-untyped-def]
        self, request: ToolRequest, rule, start_time: float
    ) -> Decision:
        """Handle AI sampling with performance optimizations."""
        if not self.ai_service_manager or not self.prompt_builder:
            # Fallback if AI not configured
            return Decision(
                action="allow",
                reason=f"Rule {rule.id} requires sampling - allowing (AI not configured)",
                rule_id=rule.id,
                confidence=0.3,
                processing_time_ms=int((time.perf_counter() - start_time) * 1000),
            )

        try:
            # Build evaluation prompt
            prompt = self.prompt_builder.build_evaluation_prompt(request, rule)

            # Generate cache key for AI evaluation
            ai_cache_key = self._generate_cache_key(request, rule)

            # Evaluate with AI (uses its own caching)
            ai_decision = await self.ai_service_manager.evaluate_with_ai(
                prompt, cache_key=ai_cache_key
            )

            # Convert AI decision to domain Decision
            return Decision(
                action=ai_decision.decision,
                reason=ai_decision.reasoning,
                rule_id=rule.id,
                confidence=ai_decision.confidence,
                processing_time_ms=int((time.perf_counter() - start_time) * 1000),
            )

        except SuperegoError as e:
            logger.warning("AI sampling failed", rule_id=rule.id, error=str(e))

            # Configurable fallback behavior
            if e.code == ErrorCode.AI_SERVICE_UNAVAILABLE:
                # Fail open for availability
                return Decision(
                    action="allow",
                    reason="AI sampling unavailable - failing open",
                    rule_id=rule.id,
                    confidence=0.3,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000),
                )
            else:
                # Fail closed for other errors
                return Decision(
                    action="deny",
                    reason="AI sampling error - failing closed",
                    rule_id=rule.id,
                    confidence=0.8,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000),
                )

    def _generate_cache_key(self, request: ToolRequest, rule: SecurityRule) -> str:
        """Generate cache key for a tool request."""
        # Create a deterministic string representation
        key_parts = [
            rule.id,
            request.tool_name,
            str(sorted(request.parameters.items())),
            request.agent_id,
            request.cwd,
        ]
        key_string = "|".join(key_parts)

        # Return first 16 chars of hash for readable keys
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def _generate_request_cache_key(self, request: ToolRequest) -> str:
        """Generate cache key for a general tool request."""
        # Create a deterministic string representation
        key_parts = [
            request.tool_name,
            str(sorted(request.parameters.items())),
            request.agent_id,
            request.cwd,
        ]
        key_string = "|".join(key_parts)

        # Return first 16 chars of hash for readable keys
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    async def get_performance_stats(self) -> dict:
        """Get performance statistics."""
        stats = {
            "cache_stats": await self.response_cache.get_stats(),
            "rule_count": len(self.rules),
            "performance": await self.performance_monitor.get_stats("rule_evaluation"),
        }

        if self.ai_service_manager:
            stats["ai_service"] = self.ai_service_manager.get_health_status()

        return stats
