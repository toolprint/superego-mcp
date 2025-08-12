"""Tests for enhanced HealthMonitor with configuration reload tracking."""

import pytest
from unittest.mock import MagicMock

from superego_mcp.infrastructure.error_handler import HealthMonitor


class TestHealthMonitorHotReload:
    """Test suite for HealthMonitor configuration reload functionality."""

    @pytest.fixture
    def health_monitor(self):
        """Create a HealthMonitor instance for testing."""
        return HealthMonitor()

    @pytest.fixture
    def mock_component_with_health_check(self):
        """Mock component that has a health_check method."""
        component = MagicMock()
        component.health_check.return_value = {
            "status": "healthy",
            "message": "Component is working",
        }
        return component

    @pytest.fixture
    def mock_component_without_health_check(self):
        """Mock component without health_check method."""
        component = MagicMock()
        del component.health_check  # Remove health_check method
        return component

    @pytest.mark.unit
    def test_initial_config_reload_metrics(self, health_monitor):
        """Test initial state of configuration reload metrics."""
        metrics = health_monitor._config_reload_metrics

        assert metrics["total_reloads"] == 0
        assert metrics["successful_reloads"] == 0
        assert metrics["failed_reloads"] == 0
        assert metrics["last_reload_time"] is None
        assert metrics["last_reload_success"] is None

    @pytest.mark.unit
    def test_record_config_reload_attempt(self, health_monitor):
        """Test recording configuration reload attempts."""
        initial_time = health_monitor._config_reload_metrics["last_reload_time"]

        health_monitor.record_config_reload_attempt()

        assert health_monitor._config_reload_metrics["total_reloads"] == 1
        assert health_monitor._config_reload_metrics["last_reload_time"] is not None
        assert health_monitor._config_reload_metrics["last_reload_time"] != initial_time

    @pytest.mark.unit
    def test_record_config_reload_success(self, health_monitor):
        """Test recording successful configuration reload."""
        health_monitor.record_config_reload_attempt()
        health_monitor.record_config_reload_success()

        assert health_monitor._config_reload_metrics["successful_reloads"] == 1
        assert health_monitor._config_reload_metrics["last_reload_success"] is True
        assert health_monitor._config_reload_metrics["failed_reloads"] == 0

    @pytest.mark.unit
    def test_record_config_reload_failure(self, health_monitor):
        """Test recording failed configuration reload."""
        health_monitor.record_config_reload_attempt()
        health_monitor.record_config_reload_failure()

        assert health_monitor._config_reload_metrics["failed_reloads"] == 1
        assert health_monitor._config_reload_metrics["last_reload_success"] is False
        assert health_monitor._config_reload_metrics["successful_reloads"] == 0

    @pytest.mark.unit
    def test_multiple_reload_attempts(self, health_monitor):
        """Test tracking multiple reload attempts."""
        # First attempt - success
        health_monitor.record_config_reload_attempt()
        health_monitor.record_config_reload_success()

        # Second attempt - failure
        health_monitor.record_config_reload_attempt()
        health_monitor.record_config_reload_failure()

        # Third attempt - success
        health_monitor.record_config_reload_attempt()
        health_monitor.record_config_reload_success()

        metrics = health_monitor._config_reload_metrics
        assert metrics["total_reloads"] == 3
        assert metrics["successful_reloads"] == 2
        assert metrics["failed_reloads"] == 1
        assert metrics["last_reload_success"] is True

    @pytest.mark.unit
    def test_get_config_reload_success_rate_no_reloads(self, health_monitor):
        """Test success rate calculation with no reloads."""
        rate = health_monitor.get_config_reload_success_rate()
        assert rate == 1.0  # Should return 1.0 when no reloads attempted

    @pytest.mark.unit
    def test_get_config_reload_success_rate_all_successful(self, health_monitor):
        """Test success rate calculation with all successful reloads."""
        for _ in range(5):
            health_monitor.record_config_reload_attempt()
            health_monitor.record_config_reload_success()

        rate = health_monitor.get_config_reload_success_rate()
        assert rate == 1.0

    @pytest.mark.unit
    def test_get_config_reload_success_rate_all_failed(self, health_monitor):
        """Test success rate calculation with all failed reloads."""
        for _ in range(3):
            health_monitor.record_config_reload_attempt()
            health_monitor.record_config_reload_failure()

        rate = health_monitor.get_config_reload_success_rate()
        assert rate == 0.0

    @pytest.mark.unit
    def test_get_config_reload_success_rate_mixed(self, health_monitor):
        """Test success rate calculation with mixed results."""
        # 3 successes, 2 failures
        for _ in range(3):
            health_monitor.record_config_reload_attempt()
            health_monitor.record_config_reload_success()

        for _ in range(2):
            health_monitor.record_config_reload_attempt()
            health_monitor.record_config_reload_failure()

        rate = health_monitor.get_config_reload_success_rate()
        assert rate == 0.6  # 3/5 = 0.6

    @pytest.mark.unit
    def test_is_config_reload_healthy_no_reloads(self, health_monitor):
        """Test config reload health check with no reloads."""
        is_healthy = health_monitor.is_config_reload_healthy()
        assert is_healthy is True  # No reloads = healthy

    @pytest.mark.unit
    def test_is_config_reload_healthy_above_threshold(self, health_monitor):
        """Test config reload health check above threshold."""
        # 4 successes, 1 failure = 80% success rate (at threshold)
        for _ in range(4):
            health_monitor.record_config_reload_attempt()
            health_monitor.record_config_reload_success()

        health_monitor.record_config_reload_attempt()
        health_monitor.record_config_reload_failure()

        is_healthy = health_monitor.is_config_reload_healthy()
        assert is_healthy is True

    @pytest.mark.unit
    def test_is_config_reload_healthy_below_threshold(self, health_monitor):
        """Test config reload health check below threshold."""
        # 3 successes, 2 failures = 60% success rate (below 80% threshold)
        for _ in range(3):
            health_monitor.record_config_reload_attempt()
            health_monitor.record_config_reload_success()

        for _ in range(2):
            health_monitor.record_config_reload_attempt()
            health_monitor.record_config_reload_failure()

        is_healthy = health_monitor.is_config_reload_healthy()
        assert is_healthy is False

    @pytest.mark.unit
    async def test_health_check_includes_config_metrics(
        self, health_monitor, mock_component_with_health_check
    ):
        """Test that health check includes configuration reload metrics."""
        health_monitor.register_component(
            "test_component", mock_component_with_health_check
        )

        # Add some reload history
        health_monitor.record_config_reload_attempt()
        health_monitor.record_config_reload_success()

        health_status = await health_monitor.check_health()

        assert "config_reload_metrics" in health_status.metrics
        config_metrics = health_status.metrics["config_reload_metrics"]

        assert config_metrics["total_reloads"] == 1
        assert config_metrics["successful_reloads"] == 1
        assert config_metrics["failed_reloads"] == 0
        assert config_metrics["last_reload_success"] is True
        assert config_metrics["last_reload_time"] is not None

    @pytest.mark.unit
    async def test_health_check_with_components(
        self,
        health_monitor,
        mock_component_with_health_check,
        mock_component_without_health_check,
    ):
        """Test health check with various component types."""
        health_monitor.register_component(
            "with_health", mock_component_with_health_check
        )
        health_monitor.register_component(
            "without_health", mock_component_without_health_check
        )

        health_status = await health_monitor.check_health()

        # Both components should be included
        assert "with_health" in health_status.components
        assert "without_health" in health_status.components

        # Component with health check should use its result
        assert health_status.components["with_health"].status == "healthy"
        assert health_status.components["with_health"].message == "Component is working"

        # Component without health check should default to healthy
        assert health_status.components["without_health"].status == "healthy"
        assert health_status.components["without_health"].message is None

    @pytest.mark.unit
    async def test_health_check_with_failing_component_health_check(
        self, health_monitor
    ):
        """Test health check when component health check raises exception."""
        failing_component = MagicMock()
        failing_component.health_check.side_effect = Exception("Component failed")

        health_monitor.register_component("failing", failing_component)

        health_status = await health_monitor.check_health()

        assert health_status.components["failing"].status == "unhealthy"
        assert "Component failed" in health_status.components["failing"].message

    @pytest.mark.unit
    async def test_health_check_with_async_component_health_check(self, health_monitor):
        """Test health check with async component health check method."""
        async_component = MagicMock()

        # Create an async mock
        async def async_health_check():
            return {"status": "healthy", "message": "Async component OK"}

        async_component.health_check = async_health_check
        health_monitor.register_component("async_comp", async_component)

        health_status = await health_monitor.check_health()

        assert health_status.components["async_comp"].status == "healthy"
        assert health_status.components["async_comp"].message == "Async component OK"

    @pytest.mark.unit
    def test_overall_status_determination_with_config_issues(self, health_monitor):
        """Test overall status determination considering config reload health."""
        healthy_component = MagicMock()
        healthy_component.health_check.return_value = {"status": "healthy"}

        health_monitor.register_component("healthy", healthy_component)

        # Create unhealthy config reload scenario
        for _ in range(2):
            health_monitor.record_config_reload_attempt()
            health_monitor.record_config_reload_failure()

        # The overall status determination is based on component health
        # Config reload health is tracked in metrics but doesn't directly affect status
        component_health = {"healthy": MagicMock(status="healthy")}
        overall_status = health_monitor._determine_overall_status(component_health)

        assert overall_status == "healthy"

    @pytest.mark.unit
    async def test_health_check_system_metrics_included(self, health_monitor):
        """Test that system metrics are still included in health check."""
        health_status = await health_monitor.check_health()

        # Verify standard system metrics are present
        assert "cpu_percent" in health_status.metrics
        assert "memory_percent" in health_status.metrics
        assert "disk_usage_percent" in health_status.metrics

        # Verify config reload metrics are also present
        assert "config_reload_metrics" in health_status.metrics
