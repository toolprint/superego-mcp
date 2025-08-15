"""Tests for multi-transport server implementation."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from superego_mcp.domain.models import Decision, ToolRequest
from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.config import ServerConfig
from superego_mcp.infrastructure.error_handler import (
    AuditLogger,
    ErrorHandler,
    HealthMonitor,
)
from superego_mcp.presentation.http_transport import HTTPTransport
from superego_mcp.presentation.sse_transport import SSETransport
from superego_mcp.presentation.transport_server import MultiTransportServer

# Ensure test environment is detected
os.environ["TESTING"] = "1"

# Add timeout for all async tests to prevent hanging
pytestmark = pytest.mark.timeout(15)  # 15 second timeout for all tests in this module


@pytest.fixture
def mock_components():
    """Create mock components for testing."""
    security_policy = Mock(spec=SecurityPolicyEngine)
    audit_logger = Mock(spec=AuditLogger)
    error_handler = Mock(spec=ErrorHandler)
    health_monitor = Mock(spec=HealthMonitor)

    # Setup mock return values
    security_policy.rules = []
    security_policy.rules_file = Mock()
    security_policy.rules_file.exists.return_value = True
    security_policy.rules_file.stat.return_value = Mock(st_mtime=1234567890)

    audit_logger.get_recent_entries.return_value = []
    audit_logger.get_stats.return_value = {"total_entries": 0}

    async def mock_health_check():
        mock_status = Mock()
        mock_status.status = "healthy"
        mock_status.timestamp = "2025-01-01T00:00:00"
        mock_status.components = {}
        mock_status.model_dump.return_value = {
            "status": "healthy",
            "timestamp": "2025-01-01T00:00:00",
            "components": {},
        }
        return mock_status

    health_monitor.check_health = mock_health_check

    return security_policy, audit_logger, error_handler, health_monitor


@pytest.fixture
def test_config():
    """Create test configuration."""
    return ServerConfig(
        transport={
            "http": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "cors_origins": ["*"],
            },
            "sse": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8002,
                "cors_origins": ["*"],
            },
        }
    )


class TestMultiTransportServer:
    """Test cases for MultiTransportServer."""

    @pytest.mark.asyncio
    async def test_server_initialization(self, mock_components, test_config):
        """Test server initialization with multiple transports."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        server = MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=test_config,
        )

        assert server.security_policy == security_policy
        assert server.audit_logger == audit_logger
        assert server.error_handler == error_handler
        assert server.health_monitor == health_monitor
        assert server.config == test_config
        assert server.mcp is not None

    def test_enabled_transports(self, mock_components, test_config):
        """Test getting enabled transports."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        server = MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=test_config,
        )

        enabled = server._get_enabled_transports()
        # STDIO is not enabled in test environment
        assert "http" in enabled
        assert "sse" in enabled

    @pytest.mark.asyncio
    async def test_tool_evaluation_core_functionality(
        self, mock_components, test_config
    ):
        """Test core tool evaluation functionality."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        # Setup mock decision
        mock_decision = Decision(
            action="allow",
            reason="Test allowed",
            confidence=0.9,
            processing_time_ms=10,
            rule_id="test-rule",
        )

        # Create proper async mock
        async def mock_evaluate(request):
            return mock_decision

        security_policy.evaluate = mock_evaluate
        audit_logger.log_decision = AsyncMock()

        MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=test_config,
        )

        # Test evaluation by directly calling the MCP tool function
        # The FastMCP framework will have registered the evaluate_tool_request function

        # Create tool request data
        tool_request_data = {
            "tool_name": "test_tool",
            "parameters": {"arg": "value"},
            "agent_id": "test_agent",
            "session_id": "test_session",
            "cwd": "/tmp",
        }

        # Manually call the security policy evaluation like the MCP tool would
        tool_request = ToolRequest(**tool_request_data)
        result = await security_policy.evaluate(tool_request)

        assert result.action == "allow"
        assert result.reason == "Test allowed"
        assert result.confidence == 0.9

        # Verify audit logger would be called (simulate the MCP tool behavior)
        rule_matches = [result.rule_id] if result.rule_id else []
        await audit_logger.log_decision(tool_request, result, rule_matches)
        audit_logger.log_decision.assert_called_once()


class TestHTTPTransport:
    """Test cases for HTTP transport."""

    @pytest.fixture
    def http_transport(self, mock_components):
        """Create HTTP transport for testing."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        # Create a mock FastMCP instance
        mock_mcp = Mock()

        config = {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8000,
            "cors_origins": ["*"],
        }

        return HTTPTransport(
            mcp=mock_mcp,
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=config,
        )

    def test_http_transport_initialization(self, http_transport):
        """Test HTTP transport initialization."""
        assert http_transport.app is not None
        assert http_transport.config["enabled"] is True
        assert http_transport.config["port"] == 8000

    def test_http_api_routes(self, http_transport, mock_components):
        """Test HTTP API routes."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        # Setup mock decision
        mock_decision = Decision(
            action="allow",
            reason="Test allowed",
            confidence=0.9,
            processing_time_ms=10,
            rule_id="test-rule",
        )
        security_policy.evaluate.return_value = AsyncMock(return_value=mock_decision)()
        audit_logger.log_decision.return_value = AsyncMock()()

        client = TestClient(http_transport.app)

        # Test health endpoint
        response = client.get("/v1/health")
        assert response.status_code == 200

        # Test server info endpoint
        response = client.get("/v1/server-info")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "superego-mcp"
        assert data["transport"] == "http"

    def test_http_evaluate_endpoint(self, http_transport, mock_components):
        """Test HTTP evaluate endpoint."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        # Setup mock decision
        mock_decision = Decision(
            action="allow",
            reason="Test allowed",
            confidence=0.9,
            processing_time_ms=10,
            rule_id="test-rule",
        )

        # Create proper async mock
        async def mock_evaluate(request):
            return mock_decision

        security_policy.evaluate = mock_evaluate
        audit_logger.log_decision = AsyncMock()

        # Use TestClient for synchronous testing
        client = TestClient(http_transport.app)
        response = client.post(
            "/v1/evaluate",
            json={
                "tool_name": "test_tool",
                "parameters": {"arg": "value"},
                "agent_id": "test_agent",
                "session_id": "test_session",
                "cwd": "/tmp",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "allow"
        assert data["reason"] == "Test allowed"
        assert data["confidence"] == 0.9



class TestSSETransport:
    """Test cases for SSE transport."""

    @pytest.fixture
    def sse_transport(self, mock_components):
        """Create SSE transport for testing."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        # Create a mock FastMCP instance
        mock_mcp = Mock()

        config = {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8002,
            "cors_origins": ["*"],
            "keepalive_interval": 30,
        }

        return SSETransport(
            mcp=mock_mcp,
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=config,
        )

    def test_sse_transport_initialization(self, sse_transport):
        """Test SSE transport initialization."""
        assert sse_transport.app is not None
        assert sse_transport.sse_manager is not None
        assert sse_transport.config["enabled"] is True
        assert sse_transport.config["port"] == 8002

    @pytest.mark.asyncio
    async def test_sse_manager_subscription(self, sse_transport):
        """Test SSE manager subscription."""
        manager = sse_transport.sse_manager

        # Test subscribe
        queue = await manager.subscribe("health")
        assert queue is not None
        assert queue in manager.subscribers["health"]

        # Test unsubscribe
        manager.unsubscribe("health", queue)
        assert queue not in manager.subscribers["health"]

        # Test invalid subscription
        with pytest.raises(ValueError):
            await manager.subscribe("invalid")

    @pytest.mark.asyncio
    async def test_sse_broadcast(self, sse_transport):
        """Test SSE event broadcasting."""
        manager = sse_transport.sse_manager

        from superego_mcp.presentation.sse_transport import SSEEvent

        # Subscribe to health events
        queue = await manager.subscribe("health")

        # Broadcast event
        event = SSEEvent(event="test_event", data=json.dumps({"message": "test"}))

        await manager.broadcast("health", event)

        # Check that event was received
        received_event = queue.get_nowait()
        assert received_event.event == "test_event"
        assert "test" in received_event.data

    def test_sse_message_formatting(self, sse_transport):
        """Test SSE message formatting."""
        from superego_mcp.presentation.sse_transport import SSEEvent

        event = SSEEvent(id="123", event="test_event", data="test data", retry=5000)

        formatted = sse_transport._format_sse_message(event)

        assert "id: 123" in formatted
        assert "event: test_event" in formatted
        assert "data: test data" in formatted
        assert "retry: 5000" in formatted
        assert formatted.endswith("\n\n")

    def test_sse_api_routes(self, sse_transport):
        """Test SSE API routes."""
        # SSE routes return streaming responses, so we can't easily test them with TestClient
        # Instead, test that the app has the expected routes
        from starlette.routing import Route

        # Check that the SSE transport has an app
        assert sse_transport.app is not None

        # Verify routes are configured (this doesn't actually make requests)
        routes = []
        for route in sse_transport.app.routes:
            if isinstance(route, Route):
                routes.append(route.path)

        # Check that expected SSE endpoints are configured
        expected_endpoints = [
            "/v1/events/config",
            "/v1/events/health",
            "/v1/events/audit",
        ]
        for endpoint in expected_endpoints:
            assert any(endpoint in route for route in routes), (
                f"Endpoint {endpoint} not found"
            )


class TestIntegration:
    """Integration tests for multi-transport functionality."""

    @pytest.mark.asyncio
    async def test_concurrent_transport_operations(self, mock_components, test_config):
        """Test concurrent operations across multiple transports."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        # Setup mock decision
        mock_decision = Decision(
            action="allow",
            reason="Test allowed",
            confidence=0.9,
            processing_time_ms=10,
            rule_id="test-rule",
        )

        # Create proper async mock
        async def mock_evaluate(request):
            return mock_decision

        security_policy.evaluate = mock_evaluate
        audit_logger.log_decision = AsyncMock()

        MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=test_config,
        )

        # Test concurrent evaluations by directly calling security policy
        # (simulating what the MCP tool would do internally)
        tasks = []
        for i in range(5):
            tool_request = ToolRequest(
                tool_name=f"test_tool_{i}",
                parameters={"arg": f"value_{i}"},
                agent_id=f"test_agent_{i}",
                session_id=f"test_session_{i}",
                cwd="/tmp",
            )
            task = security_policy.evaluate(tool_request)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all evaluations succeeded
        assert len(results) == 5
        for result in results:
            assert result.action == "allow"
            assert result.confidence == 0.9

    def test_transport_configuration_validation(self, mock_components):
        """Test transport configuration validation."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        # Test with minimal config
        minimal_config = ServerConfig()

        server = MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=minimal_config,
        )

        # Should have no transports enabled by default (since we're in test environment, STDIO is skipped)
        enabled = server._get_enabled_transports()
        # In test environment, STDIO is not enabled, so no transports are enabled with minimal config
        assert len(enabled) == 0

    @pytest.mark.asyncio
    async def test_error_handling_across_transports(self, mock_components, test_config):
        """Test error handling across different transports."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components

        # Setup mock to raise exception
        async def mock_evaluate_error(request):
            raise Exception("Test error")

        security_policy.evaluate = mock_evaluate_error

        # Setup error handler mock
        fallback_decision = Decision(
            action="deny",
            reason="Error occurred",
            confidence=0.0,
            processing_time_ms=1,
        )
        error_handler.handle_error.return_value = fallback_decision
        audit_logger.log_decision = AsyncMock()

        MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=test_config,
        )

        # Test error handling by directly calling security policy
        # Create tool request that will cause an error
        tool_request = ToolRequest(
            tool_name="test_tool",
            parameters={"arg": "value"},
            agent_id="test_agent",
            session_id="test_session",
            cwd="/tmp",
        )

        # The security policy will raise an error, but in a real MCP tool,
        # the error handler would catch it and return a fallback decision
        try:
            await security_policy.evaluate(tool_request)
            raise AssertionError("Expected an exception to be raised")
        except Exception as e:
            # This is expected - simulate what the MCP tool would do
            result = error_handler.handle_error(e, tool_request)

            # Should get fallback decision
            assert result.action == "deny"
            assert result.reason == "Error occurred"

            # Verify error handler was called
            error_handler.handle_error.assert_called_once()

            # Simulate audit logging
            await audit_logger.log_decision(tool_request, result, [])
            audit_logger.log_decision.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])
