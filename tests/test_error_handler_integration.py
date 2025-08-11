"""Integration tests for error handler with existing components."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from superego_mcp.domain.models import (
    AuditEntry,
    ComponentHealth,
    Decision,
    ErrorCode,
    HealthStatus,
    SuperegoError,
    ToolRequest,
)
from superego_mcp.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
)
from superego_mcp.infrastructure.error_handler import (
    AuditLogger,
    ErrorHandler,
    HealthMonitor,
)


class TestErrorHandlerCircuitBreakerIntegration:
    """Integration tests between ErrorHandler and CircuitBreaker"""

    def setup_method(self):
        """Setup test fixtures"""
        self.error_handler = ErrorHandler()
        self.circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=5)
        self.sample_request = ToolRequest(
            tool_name="test_tool",
            parameters={"key": "value"},
            session_id="test-session-123",
            agent_id="test-agent-456",
            cwd="/test/path",
        )

    def test_circuit_breaker_open_error_handling(self):
        """Test that ErrorHandler properly handles CircuitBreakerOpenError"""
        # Create circuit breaker error as would be raised by the circuit breaker
        cb_error = CircuitBreakerOpenError(
            "AI service unavailable - circuit breaker open"
        )

        decision = self.error_handler.handle_error(cb_error, self.sample_request)

        # Should fail open with low confidence
        assert decision.action == "allow"
        assert decision.confidence == 0.2
        assert "AI evaluation unavailable" in decision.reason
        assert decision.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_in_health_monitoring(self):
        """Test that circuit breaker state can be monitored via HealthMonitor"""
        health_monitor = HealthMonitor()

        # Register circuit breaker as a component
        health_monitor.register_component("circuit_breaker", self.circuit_breaker)

        # Initially should be healthy (circuit closed)
        health_status = await health_monitor.check_health()
        assert health_status.status == "healthy"
        assert "circuit_breaker" in health_status.components
        assert health_status.components["circuit_breaker"].status == "healthy"

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_health_check_method(self):
        """Test circuit breaker integration when it has a health_check method"""

        # Add health_check method to circuit breaker
        async def health_check():
            state = self.circuit_breaker.get_state()
            if state["state"] == "open":
                return {
                    "status": "unhealthy",
                    "message": f"Circuit breaker is {state['state']}",
                }
            elif state["state"] == "half_open":
                return {
                    "status": "degraded",
                    "message": f"Circuit breaker is {state['state']}",
                }
            else:
                return {
                    "status": "healthy",
                    "message": f"Circuit breaker is {state['state']}",
                }

        self.circuit_breaker.health_check = health_check

        health_monitor = HealthMonitor()
        health_monitor.register_component("circuit_breaker", self.circuit_breaker)

        # Test healthy state
        health_status = await health_monitor.check_health()
        assert health_status.components["circuit_breaker"].status == "healthy"
        assert "closed" in health_status.components["circuit_breaker"].message

        # Force circuit breaker to open state
        self.circuit_breaker.state = "open"
        self.circuit_breaker.failure_count = 5

        health_status = await health_monitor.check_health()
        assert health_status.components["circuit_breaker"].status == "unhealthy"
        assert "open" in health_status.components["circuit_breaker"].message


class TestAuditLoggerIntegration:
    """Integration tests for AuditLogger with domain models"""

    def setup_method(self):
        """Setup test fixtures"""
        self.audit_logger = AuditLogger()
        self.error_handler = ErrorHandler()

    @pytest.mark.asyncio
    async def test_audit_logging_with_error_handler_decisions(self):
        """Test that audit logger properly logs decisions from error handler"""
        request = ToolRequest(
            tool_name="dangerous_tool",
            parameters={"command": "rm -rf /"},
            session_id="test-session-456",
            agent_id="test-agent-789",
            cwd="/dangerous/path",
        )

        # Create error that should fail closed
        error = SuperegoError(
            code=ErrorCode.INVALID_CONFIGURATION,
            message="Config validation failed",
            user_message="Security configuration error detected",
        )

        decision = self.error_handler.handle_error(error, request)

        # Log the decision
        await self.audit_logger.log_decision(request, decision, ["config-rule-1"])

        # Verify audit entry was created correctly
        assert len(self.audit_logger.entries) == 1
        entry = self.audit_logger.entries[0]

        assert entry.request.tool_name == "dangerous_tool"
        assert entry.request.session_id == "test-session-456"
        assert entry.decision.action == "deny"
        assert entry.decision.confidence == 0.8
        assert entry.rule_matches == ["config-rule-1"]

    @pytest.mark.asyncio
    async def test_audit_entry_model_validation(self):
        """Test that AuditEntry model validates data correctly"""
        request = ToolRequest(
            tool_name="valid_tool",
            parameters={"safe": "parameter"},
            session_id="session-123",
            agent_id="agent-456",
            cwd="/safe/path",
        )

        decision = Decision(
            action="allow",
            reason="Request passed all security checks",
            confidence=0.95,
            processing_time_ms=25,
            rule_id="allow-rule-1",
        )

        await self.audit_logger.log_decision(request, decision, ["rule-1", "rule-2"])

        entry = self.audit_logger.entries[0]

        # Verify all fields are properly set and validated
        assert isinstance(entry, AuditEntry)
        assert entry.id is not None and len(entry.id) > 0
        assert entry.timestamp is not None
        assert entry.request == request
        assert entry.decision == decision
        assert entry.rule_matches == ["rule-1", "rule-2"]

    def test_audit_statistics_with_mixed_decisions(self):
        """Test audit statistics calculation with various decision types"""
        # Simulate various decisions
        decisions_data = [
            ("allow", 0.9, 100),
            ("deny", 0.8, 150),
            ("allow", 0.7, 200),
            ("allow", 0.6, 75),
            ("deny", 0.95, 300),
        ]

        for action, confidence, processing_time in decisions_data:
            entry = Mock()
            entry.decision = Decision(
                action=action,
                reason=f"Test {action}",
                confidence=confidence,
                processing_time_ms=processing_time,
            )
            self.audit_logger.entries.append(entry)

        stats = self.audit_logger.get_stats()

        assert stats["total"] == 5
        assert stats["allowed"] == 3
        assert stats["denied"] == 2
        assert stats["allow_rate"] == pytest.approx(0.6)
        assert stats["avg_processing_time_ms"] == pytest.approx(165.0)


class TestHealthMonitoringComponentIntegration:
    """Integration tests for health monitoring with various components"""

    def setup_method(self):
        """Setup test fixtures"""
        self.health_monitor = HealthMonitor()

    @pytest.mark.asyncio
    async def test_multiple_component_types_integration(self):
        """Test health monitoring with different types of components"""
        # Mock components with different health check implementations
        healthy_component = AsyncMock()
        healthy_component.health_check.return_value = {"status": "healthy"}

        degraded_component = AsyncMock()
        degraded_component.health_check.return_value = {
            "status": "degraded",
            "message": "Performance issues detected",
        }

        failing_component = AsyncMock()
        failing_component.health_check.side_effect = Exception("Connection lost")

        simple_component = Mock()  # No health_check method
        del (
            simple_component.health_check
        )  # Explicitly remove to simulate no health_check

        # Register all components
        self.health_monitor.register_component("database", healthy_component)
        self.health_monitor.register_component("ai_service", degraded_component)
        self.health_monitor.register_component("cache", failing_component)
        self.health_monitor.register_component("config", simple_component)

        health_status = await self.health_monitor.check_health()

        # Overall status should be unhealthy due to failing component
        assert health_status.status == "unhealthy"

        # Check individual component statuses
        assert health_status.components["database"].status == "healthy"
        assert health_status.components["ai_service"].status == "degraded"
        assert (
            health_status.components["ai_service"].message
            == "Performance issues detected"
        )
        assert health_status.components["cache"].status == "unhealthy"
        assert health_status.components["cache"].message == "Connection lost"
        assert (
            health_status.components["config"].status == "healthy"
        )  # Default for no health_check

    @pytest.mark.asyncio
    async def test_component_health_models_validation(self):
        """Test that ComponentHealth and HealthStatus models validate correctly"""
        component = AsyncMock()
        component.health_check.return_value = {
            "status": "degraded",
            "message": "Slow response times",
        }

        self.health_monitor.register_component("slow_service", component)

        health_status = await self.health_monitor.check_health()

        # Verify models are properly instantiated and validated
        assert isinstance(health_status, HealthStatus)
        assert isinstance(health_status.components["slow_service"], ComponentHealth)

        # Verify all required fields are present
        comp_health = health_status.components["slow_service"]
        assert comp_health.status == "degraded"
        assert comp_health.message == "Slow response times"
        assert comp_health.last_check is not None

        # Verify health status has all required fields
        assert health_status.status == "degraded"
        assert health_status.timestamp is not None
        assert isinstance(health_status.metrics, dict)
        assert "cpu_percent" in health_status.metrics

    @pytest.mark.asyncio
    @patch("superego_mcp.infrastructure.error_handler.psutil.cpu_percent")
    @patch("superego_mcp.infrastructure.error_handler.psutil.virtual_memory")
    @patch("superego_mcp.infrastructure.error_handler.psutil.disk_usage")
    async def test_system_metrics_integration(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_percent
    ):
        """Test integration of system metrics collection"""
        # Mock realistic system metrics
        mock_cpu_percent.return_value = 15.5
        mock_virtual_memory.return_value = Mock(percent=45.2)
        mock_disk_usage.return_value = Mock(percent=80.1)

        # Add a component to ensure the health check runs completely
        component = Mock()
        self.health_monitor.register_component("test_component", component)

        health_status = await self.health_monitor.check_health()

        # Verify system metrics are collected and integrated properly
        assert health_status.metrics["cpu_percent"] == 15.5
        assert health_status.metrics["memory_percent"] == 45.2
        assert health_status.metrics["disk_usage_percent"] == 80.1

        # Verify the health status model structure
        assert isinstance(health_status.metrics, dict)
        assert len(health_status.metrics) == 3
        assert all(isinstance(v, (int, float)) for v in health_status.metrics.values())
