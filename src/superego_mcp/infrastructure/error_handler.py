"""Error handling and logging infrastructure for Superego MCP Server."""

import asyncio
import time
from typing import Any, Literal

import psutil
import structlog

from ..domain.models import (
    AuditEntry,
    ComponentHealth,
    Decision,
    ErrorCode,
    HealthStatus,
    SuperegoError,
    ToolRequest,
)
from .circuit_breaker import CircuitBreakerOpenError


class ErrorHandler:
    """Centralized error handling with structured logging"""

    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__)

    def handle_error(self, error: Exception, request: ToolRequest) -> Decision:
        """Convert exceptions to security decisions"""
        start_time = time.perf_counter()
        processing_time = int((time.perf_counter() - start_time) * 1000)

        if isinstance(error, SuperegoError):
            return self._handle_superego_error(error, request, processing_time)
        elif isinstance(error, CircuitBreakerOpenError):
            return self._handle_circuit_breaker_error(error, request, processing_time)
        else:
            return self._handle_unexpected_error(error, request, processing_time)

    def _handle_superego_error(
        self, error: SuperegoError, request: ToolRequest, processing_time: int
    ) -> Decision:
        """Handle known SuperegoError instances"""

        # Log structured error information
        self.logger.error(
            "Superego error occurred",
            error_code=error.code.value,
            error_message=error.message,
            user_message=error.user_message,
            context=error.context,
            tool_name=request.tool_name,
            session_id=request.session_id,
            agent_id=request.agent_id,
        )

        if error.code == ErrorCode.AI_SERVICE_UNAVAILABLE:
            # Fail open for AI service issues - allow with low confidence
            return Decision(
                action="allow",
                reason=error.user_message,
                confidence=0.3,
                processing_time_ms=processing_time,
            )
        else:
            # Fail closed for security errors - deny with high confidence
            return Decision(
                action="deny",
                reason=error.user_message,
                confidence=0.8,
                processing_time_ms=processing_time,
            )

    def _handle_circuit_breaker_error(
        self, error: CircuitBreakerOpenError, request: ToolRequest, processing_time: int
    ) -> Decision:
        """Handle circuit breaker failures"""

        self.logger.warning(
            "Circuit breaker prevented AI service call",
            tool_name=request.tool_name,
            session_id=request.session_id,
            error_message=str(error),
        )

        # Fail open for circuit breaker - allow with very low confidence
        return Decision(
            action="allow",
            reason="AI evaluation unavailable - allowing with caution",
            confidence=0.2,
            processing_time_ms=processing_time,
        )

    def _handle_unexpected_error(
        self, error: Exception, request: ToolRequest, processing_time: int
    ) -> Decision:
        """Handle unexpected exceptions"""

        self.logger.error(
            "Unexpected error during request processing",
            error_type=type(error).__name__,
            error_message=str(error),
            tool_name=request.tool_name,
            session_id=request.session_id,
            exc_info=True,  # Include full traceback
        )

        # Fail closed for unexpected errors - security first
        return Decision(
            action="deny",
            reason="Internal security evaluation error",
            confidence=0.9,
            processing_time_ms=processing_time,
        )


class AuditLogger:
    """Structured audit logging for security decisions"""

    def __init__(self) -> None:
        self.logger = structlog.get_logger("audit")
        self.entries: list[AuditEntry] = []  # In-memory for Day 1

    async def log_decision(
        self,
        request: ToolRequest,
        decision: Decision,
        rule_matches: list[str] | None = None,
    ) -> None:
        """Log security decision to audit trail"""

        entry = AuditEntry(
            request=request, decision=decision, rule_matches=rule_matches or []
        )

        # Add to in-memory storage
        self.entries.append(entry)

        # Structured logging
        await self.logger.ainfo(
            "Security decision logged",
            audit_id=entry.id,
            tool_name=request.tool_name,
            action=decision.action,
            reason=decision.reason,
            confidence=decision.confidence,
            processing_time_ms=decision.processing_time_ms,
            rule_id=decision.rule_id,
            rule_matches=rule_matches,
            session_id=request.session_id,
            agent_id=request.agent_id,
            cwd=request.cwd,
            timestamp=entry.timestamp.isoformat(),
        )

    def get_recent_entries(self, limit: int = 100) -> list[AuditEntry]:
        """Get recent audit entries for monitoring"""
        return sorted(self.entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_stats(self) -> dict[str, Any]:
        """Get audit statistics for monitoring"""
        if not self.entries:
            return {"total": 0}

        total = len(self.entries)
        allowed = sum(1 for e in self.entries if e.decision.action == "allow")
        denied = total - allowed

        avg_processing_time = (
            sum(e.decision.processing_time_ms for e in self.entries) / total
        )

        return {
            "total": total,
            "allowed": allowed,
            "denied": denied,
            "allow_rate": allowed / total,
            "avg_processing_time_ms": avg_processing_time,
        }


class HealthMonitor:
    """System health monitoring with component checks"""

    def __init__(self) -> None:
        self.components: dict[str, Any] = {}

    def register_component(self, name: str, component: Any) -> None:
        """Register component for health monitoring"""
        self.components[name] = component

    async def check_health(self) -> HealthStatus:
        """Comprehensive health check"""
        component_health = {}

        # Check each registered component
        for name, component in self.components.items():
            if hasattr(component, "health_check") and callable(
                component.health_check
            ):
                try:
                    health_check_method = component.health_check
                    # Check if it's a coroutine function
                    if asyncio.iscoroutinefunction(health_check_method):
                        result = await health_check_method()
                    else:
                        result = health_check_method()

                    component_health[name] = ComponentHealth(
                        status=result.get("status", "healthy"),
                        message=result.get("message"),
                    )
                except Exception as e:
                    component_health[name] = ComponentHealth(
                        status="unhealthy", message=str(e)
                    )
            else:
                # Default healthy for components without health checks
                component_health[name] = ComponentHealth(status="healthy")

        # Collect system metrics
        metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage("/").percent,
        }

        # Determine overall status
        overall_status = self._determine_overall_status(component_health)

        return HealthStatus(
            status=overall_status, components=component_health, metrics=metrics
        )

    def _determine_overall_status(
        self, component_health: dict[str, ComponentHealth]
    ) -> Literal["healthy", "degraded", "unhealthy"]:
        """Determine overall health from component statuses"""

        if not component_health:
            return "healthy"

        statuses = [comp.status for comp in component_health.values()]

        if any(status == "unhealthy" for status in statuses):
            return "unhealthy"
        elif any(status == "degraded" for status in statuses):
            return "degraded"
        else:
            return "healthy"
