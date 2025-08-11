"""Tests for error handling and logging infrastructure."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from superego_mcp.domain.models import (
    ComponentHealth,
    Decision,
    ErrorCode,
    HealthStatus,
    SuperegoError,
    ToolRequest,
)
from superego_mcp.infrastructure.circuit_breaker import CircuitBreakerOpenError
from superego_mcp.infrastructure.error_handler import (
    AuditLogger,
    ErrorHandler,
    HealthMonitor,
)


class TestErrorHandler:
    """Test suite for ErrorHandler class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.error_handler = ErrorHandler()
        self.sample_request = ToolRequest(
            tool_name="test_tool",
            parameters={"key": "value"},
            session_id="test-session-123",
            agent_id="test-agent-456",
            cwd="/test/path",
        )

    def test_handle_superego_error_ai_service_unavailable_fails_open(self):
        """Test that AI service unavailable error fails open with low confidence"""
        error = SuperegoError(
            code=ErrorCode.AI_SERVICE_UNAVAILABLE,
            message="AI service is down",
            user_message="AI evaluation temporarily unavailable",
        )

        decision = self.error_handler.handle_error(error, self.sample_request)

        assert decision.action == "allow"
        assert decision.confidence == 0.3
        assert decision.reason == "AI evaluation temporarily unavailable"
        assert decision.processing_time_ms >= 0

    def test_handle_superego_error_config_error_fails_closed(self):
        """Test that configuration error fails closed with high confidence"""
        error = SuperegoError(
            code=ErrorCode.INVALID_CONFIGURATION,
            message="Invalid config detected",
            user_message="Security configuration error",
        )

        decision = self.error_handler.handle_error(error, self.sample_request)

        assert decision.action == "deny"
        assert decision.confidence == 0.8
        assert decision.reason == "Security configuration error"
        assert decision.processing_time_ms >= 0

    def test_handle_circuit_breaker_error_fails_open(self):
        """Test that circuit breaker error fails open with very low confidence"""
        error = CircuitBreakerOpenError("AI service unavailable - circuit breaker open")

        decision = self.error_handler.handle_error(error, self.sample_request)

        assert decision.action == "allow"
        assert decision.confidence == 0.2
        assert decision.reason == "AI evaluation unavailable - allowing with caution"
        assert decision.processing_time_ms >= 0

    def test_handle_unexpected_error_fails_closed(self):
        """Test that unexpected error fails closed with high confidence"""
        error = ValueError("Unexpected error occurred")

        decision = self.error_handler.handle_error(error, self.sample_request)

        assert decision.action == "deny"
        assert decision.confidence == 0.9
        assert decision.reason == "Internal security evaluation error"
        assert decision.processing_time_ms >= 0

    @patch("superego_mcp.infrastructure.error_handler.structlog.get_logger")
    def test_error_logging_includes_structured_data(self, mock_logger):
        """Test that error logging includes proper structured data"""
        mock_log_instance = Mock()
        mock_logger.return_value = mock_log_instance

        error_handler = ErrorHandler()
        error = SuperegoError(
            code=ErrorCode.RULE_EVALUATION_FAILED,
            message="Rule evaluation failed",
            user_message="Security rule could not be evaluated",
            context={"rule_id": "test-rule"},
        )

        error_handler.handle_error(error, self.sample_request)

        mock_log_instance.error.assert_called_once()
        call_args = mock_log_instance.error.call_args
        assert call_args[0][0] == "Superego error occurred"
        assert call_args[1]["error_code"] == ErrorCode.RULE_EVALUATION_FAILED.value
        assert call_args[1]["tool_name"] == "test_tool"
        assert call_args[1]["session_id"] == "test-session-123"


class TestAuditLogger:
    """Test suite for AuditLogger class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.audit_logger = AuditLogger()
        self.sample_request = ToolRequest(
            tool_name="test_tool",
            parameters={"key": "value"},
            session_id="test-session-123",
            agent_id="test-agent-456",
            cwd="/test/path",
        )
        self.sample_decision = Decision(
            action="allow",
            reason="Test decision",
            confidence=0.8,
            processing_time_ms=50,
        )

    @pytest.mark.asyncio
    async def test_log_decision_stores_entry(self):
        """Test that log_decision stores audit entry in memory"""
        rule_matches = ["rule-1", "rule-2"]

        await self.audit_logger.log_decision(
            self.sample_request, self.sample_decision, rule_matches
        )

        assert len(self.audit_logger.entries) == 1
        entry = self.audit_logger.entries[0]
        assert entry.request == self.sample_request
        assert entry.decision == self.sample_decision
        assert entry.rule_matches == rule_matches
        assert entry.id is not None
        assert entry.timestamp is not None

    @pytest.mark.asyncio
    @patch("superego_mcp.infrastructure.error_handler.structlog.get_logger")
    async def test_log_decision_structured_logging(self, mock_logger):
        """Test that log_decision creates structured log entry"""
        mock_log_instance = AsyncMock()
        mock_logger.return_value = mock_log_instance

        audit_logger = AuditLogger()

        await audit_logger.log_decision(self.sample_request, self.sample_decision)

        mock_log_instance.ainfo.assert_called_once()
        call_args = mock_log_instance.ainfo.call_args
        assert call_args[0][0] == "Security decision logged"
        assert call_args[1]["tool_name"] == "test_tool"
        assert call_args[1]["action"] == "allow"
        assert call_args[1]["session_id"] == "test-session-123"

    def test_get_recent_entries_returns_sorted_entries(self):
        """Test that get_recent_entries returns entries sorted by timestamp"""
        # Add multiple entries with different timestamps
        for i in range(5):
            entry = Mock()
            entry.timestamp = datetime.now(UTC).replace(second=i)
            self.audit_logger.entries.append(entry)

        recent = self.audit_logger.get_recent_entries(limit=3)

        assert len(recent) == 3
        # Should be sorted in descending order (most recent first)
        assert recent[0].timestamp >= recent[1].timestamp >= recent[2].timestamp

    def test_get_stats_empty_returns_zero_total(self):
        """Test that get_stats returns zero total for empty entries"""
        stats = self.audit_logger.get_stats()

        assert stats == {"total": 0}

    def test_get_stats_calculates_metrics_correctly(self):
        """Test that get_stats calculates correct metrics"""
        # Add mixed allow/deny decisions
        decisions = [
            Decision(
                action="allow", reason="test", confidence=0.8, processing_time_ms=100
            ),
            Decision(
                action="deny", reason="test", confidence=0.9, processing_time_ms=200
            ),
            Decision(
                action="allow", reason="test", confidence=0.7, processing_time_ms=150
            ),
        ]

        for decision in decisions:
            entry = Mock()
            entry.decision = decision
            self.audit_logger.entries.append(entry)

        stats = self.audit_logger.get_stats()

        assert stats["total"] == 3
        assert stats["allowed"] == 2
        assert stats["denied"] == 1
        assert stats["allow_rate"] == pytest.approx(2 / 3)
        assert stats["avg_processing_time_ms"] == pytest.approx(150.0)


class TestHealthMonitor:
    """Test suite for HealthMonitor class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.health_monitor = HealthMonitor()

    def test_register_component_stores_component(self):
        """Test that register_component stores component correctly"""
        component = Mock()

        self.health_monitor.register_component("test_component", component)

        assert "test_component" in self.health_monitor.components
        assert self.health_monitor.components["test_component"] is component

    @pytest.mark.asyncio
    async def test_check_health_component_with_health_check(self):
        """Test health check for component with health_check method"""
        component = AsyncMock()
        component.health_check.return_value = {
            "status": "healthy",
            "message": "All good",
        }

        self.health_monitor.register_component("test_component", component)

        health_status = await self.health_monitor.check_health()

        assert health_status.status == "healthy"
        assert "test_component" in health_status.components
        assert health_status.components["test_component"].status == "healthy"
        assert health_status.components["test_component"].message == "All good"

    @pytest.mark.asyncio
    @patch("superego_mcp.infrastructure.error_handler.psutil.cpu_percent")
    @patch("superego_mcp.infrastructure.error_handler.psutil.virtual_memory")
    @patch("superego_mcp.infrastructure.error_handler.psutil.disk_usage")
    async def test_check_health_component_without_health_check(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_percent
    ):
        """Test health check for component without health_check method"""
        # Mock normal system metrics
        mock_cpu_percent.return_value = 25.0
        mock_virtual_memory.return_value = Mock(percent=50.0)
        mock_disk_usage.return_value = Mock(percent=60.0)

        component = Mock()
        # Explicitly remove health_check method to simulate component without it
        del component.health_check

        self.health_monitor.register_component("simple_component", component)

        health_status = await self.health_monitor.check_health()

        assert health_status.status == "healthy"
        assert "simple_component" in health_status.components
        assert health_status.components["simple_component"].status == "healthy"

    @pytest.mark.asyncio
    @patch("superego_mcp.infrastructure.error_handler.psutil.cpu_percent")
    @patch("superego_mcp.infrastructure.error_handler.psutil.virtual_memory")
    @patch("superego_mcp.infrastructure.error_handler.psutil.disk_usage")
    async def test_check_health_component_health_check_fails(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_percent
    ):
        """Test health check when component health_check raises exception"""
        # Mock normal system metrics
        mock_cpu_percent.return_value = 25.0
        mock_virtual_memory.return_value = Mock(percent=50.0)
        mock_disk_usage.return_value = Mock(percent=60.0)

        component = AsyncMock()
        component.health_check.side_effect = Exception("Component failed")

        self.health_monitor.register_component("failing_component", component)

        health_status = await self.health_monitor.check_health()

        assert health_status.status == "unhealthy"
        assert "failing_component" in health_status.components
        assert health_status.components["failing_component"].status == "unhealthy"
        assert (
            health_status.components["failing_component"].message == "Component failed"
        )

    @pytest.mark.asyncio
    @patch("superego_mcp.infrastructure.error_handler.psutil.cpu_percent")
    @patch("superego_mcp.infrastructure.error_handler.psutil.virtual_memory")
    @patch("superego_mcp.infrastructure.error_handler.psutil.disk_usage")
    async def test_check_health_collects_system_metrics(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_percent
    ):
        """Test that health check collects system metrics"""
        # Mock system metrics
        mock_cpu_percent.return_value = 25.5
        mock_virtual_memory.return_value = Mock(percent=60.2)
        mock_disk_usage.return_value = Mock(percent=75.8)

        health_status = await self.health_monitor.check_health()

        assert health_status.metrics["cpu_percent"] == 25.5
        assert health_status.metrics["memory_percent"] == 60.2
        assert health_status.metrics["disk_usage_percent"] == 75.8

    def test_determine_overall_status_empty_components(self):
        """Test overall status determination with no components"""
        status = self.health_monitor._determine_overall_status({})
        assert status == "healthy"

    def test_determine_overall_status_all_healthy(self):
        """Test overall status when all components are healthy"""
        components = {
            "comp1": ComponentHealth(status="healthy"),
            "comp2": ComponentHealth(status="healthy"),
        }

        status = self.health_monitor._determine_overall_status(components)
        assert status == "healthy"

    def test_determine_overall_status_one_degraded(self):
        """Test overall status when one component is degraded"""
        components = {
            "comp1": ComponentHealth(status="healthy"),
            "comp2": ComponentHealth(status="degraded"),
        }

        status = self.health_monitor._determine_overall_status(components)
        assert status == "degraded"

    def test_determine_overall_status_one_unhealthy(self):
        """Test overall status when one component is unhealthy"""
        components = {
            "comp1": ComponentHealth(status="healthy"),
            "comp2": ComponentHealth(status="degraded"),
            "comp3": ComponentHealth(status="unhealthy"),
        }

        status = self.health_monitor._determine_overall_status(components)
        assert status == "unhealthy"

    @pytest.mark.asyncio
    @patch("superego_mcp.infrastructure.error_handler.psutil.cpu_percent")
    @patch("superego_mcp.infrastructure.error_handler.psutil.virtual_memory")
    @patch("superego_mcp.infrastructure.error_handler.psutil.disk_usage")
    async def test_check_health_returns_proper_health_status_model(
        self, mock_disk_usage, mock_virtual_memory, mock_cpu_percent
    ):
        """Test that check_health returns properly formatted HealthStatus"""
        # Mock normal system metrics
        mock_cpu_percent.return_value = 30.0
        mock_virtual_memory.return_value = Mock(percent=45.0)
        mock_disk_usage.return_value = Mock(percent=70.0)

        health_status = await self.health_monitor.check_health()

        assert isinstance(health_status, HealthStatus)
        assert health_status.status in ["healthy", "degraded", "unhealthy"]
        assert isinstance(health_status.timestamp, datetime)
        assert isinstance(health_status.components, dict)
        assert isinstance(health_status.metrics, dict)
        assert "cpu_percent" in health_status.metrics
        assert "memory_percent" in health_status.metrics
        assert "disk_usage_percent" in health_status.metrics
