"""Tests for multi-transport server implementation."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from superego_mcp.domain.models import Decision, ToolRequest
from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.config import ServerConfig
from superego_mcp.infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor
from superego_mcp.presentation.http_transport import HTTPTransport
from superego_mcp.presentation.sse_transport import SSETransport
from superego_mcp.presentation.transport_server import MultiTransportServer
from superego_mcp.presentation.websocket_transport import WebSocketTransport


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
    
    health_monitor.check_health.return_value = AsyncMock(return_value=Mock(
        status="healthy",
        timestamp="2025-01-01T00:00:00",
        components={},
        model_dump=Mock(return_value={
            "status": "healthy",
            "timestamp": "2025-01-01T00:00:00",
            "components": {}
        })
    ))()
    
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
                "cors_origins": ["*"]
            },
            "websocket": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8001,
                "cors_origins": ["*"]
            },
            "sse": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8002,
                "cors_origins": ["*"]
            }
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
        assert "stdio" in enabled
        assert "http" in enabled
        assert "websocket" in enabled
        assert "sse" in enabled

    @pytest.mark.asyncio
    async def test_tool_evaluation_core_functionality(self, mock_components, test_config):
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
        security_policy.evaluate.return_value = AsyncMock(return_value=mock_decision)()
        audit_logger.log_decision.return_value = AsyncMock()()
        
        server = MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=test_config,
        )
        
        # Get the evaluate function from MCP tools
        evaluate_tool = None
        for tool_name, tool_func in server.mcp._tools.items():
            if "evaluate_tool_request" in tool_name:
                evaluate_tool = tool_func
                break
        
        assert evaluate_tool is not None
        
        # Test evaluation
        result = await evaluate_tool(
            tool_name="test_tool",
            parameters={"arg": "value"},
            agent_id="test_agent",
            session_id="test_session",
            cwd="/tmp",
        )
        
        assert result.action == "allow"
        assert result.reason == "Test allowed"
        assert result.confidence == 0.9
        
        # Verify mocks were called
        security_policy.evaluate.assert_called_once()
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
            "cors_origins": ["*"]
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

    @pytest.mark.asyncio
    async def test_http_evaluate_endpoint(self, http_transport, mock_components):
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
        security_policy.evaluate.return_value = AsyncMock(return_value=mock_decision)()
        audit_logger.log_decision.return_value = AsyncMock()()
        
        async with AsyncClient(app=http_transport.app, base_url="http://test") as client:
            response = await client.post(
                "/v1/evaluate",
                json={
                    "tool_name": "test_tool",
                    "parameters": {"arg": "value"},
                    "agent_id": "test_agent",
                    "session_id": "test_session",
                    "cwd": "/tmp",
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "allow"
        assert data["reason"] == "Test allowed"
        assert data["confidence"] == 0.9


class TestWebSocketTransport:
    """Test cases for WebSocket transport."""

    @pytest.fixture
    def ws_transport(self, mock_components):
        """Create WebSocket transport for testing."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components
        
        # Create a mock FastMCP instance
        mock_mcp = Mock()
        
        config = {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8001,
            "cors_origins": ["*"]
        }
        
        return WebSocketTransport(
            mcp=mock_mcp,
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=config,
        )

    def test_ws_transport_initialization(self, ws_transport):
        """Test WebSocket transport initialization."""
        assert ws_transport.app is not None
        assert ws_transport.connection_manager is not None
        assert ws_transport.config["enabled"] is True
        assert ws_transport.config["port"] == 8001

    def test_connection_manager(self, ws_transport):
        """Test WebSocket connection manager."""
        manager = ws_transport.connection_manager
        
        # Test subscription management
        mock_websocket = Mock()
        
        # Test subscribe
        assert manager.subscribe(mock_websocket, "health") is True
        assert mock_websocket in manager.subscriptions["health"]
        
        # Test unsubscribe
        assert manager.unsubscribe(mock_websocket, "health") is True
        assert mock_websocket not in manager.subscriptions["health"]
        
        # Test invalid subscription type
        assert manager.subscribe(mock_websocket, "invalid") is False

    @pytest.mark.asyncio
    async def test_ws_message_handling(self, ws_transport, mock_components):
        """Test WebSocket message handling."""
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
        
        # Create mock message
        from superego_mcp.presentation.websocket_transport import WSMessage
        
        message = WSMessage(
            message_id="test-123",
            type="evaluate",
            data={
                "tool_name": "test_tool",
                "parameters": {"arg": "value"},
                "agent_id": "test_agent",
                "session_id": "test_session",
                "cwd": "/tmp",
            }
        )
        
        mock_websocket = Mock()
        
        response = await ws_transport._handle_message(message, mock_websocket)
        
        assert response is not None
        assert response.message_id == "test-123"
        assert response.type == "response"
        assert response.data["action"] == "allow"


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
            "keepalive_interval": 30
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
        event = SSEEvent(
            event="test_event",
            data=json.dumps({"message": "test"})
        )
        
        await manager.broadcast("health", event)
        
        # Check that event was received
        received_event = queue.get_nowait()
        assert received_event.event == "test_event"
        assert "test" in received_event.data

    def test_sse_message_formatting(self, sse_transport):
        """Test SSE message formatting."""
        from superego_mcp.presentation.sse_transport import SSEEvent
        
        event = SSEEvent(
            id="123",
            event="test_event",
            data="test data",
            retry=5000
        )
        
        formatted = sse_transport._format_sse_message(event)
        
        assert "id: 123" in formatted
        assert "event: test_event" in formatted
        assert "data: test data" in formatted
        assert "retry: 5000" in formatted
        assert formatted.endswith("\n\n")

    def test_sse_api_routes(self, sse_transport):
        """Test SSE API routes."""
        client = TestClient(sse_transport.app)
        
        # Test that routes are accessible (they will return streaming responses)
        response = client.get("/v1/events/config")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        response = client.get("/v1/events/health")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        response = client.get("/v1/events/audit")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


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
        security_policy.evaluate.return_value = AsyncMock(return_value=mock_decision)()
        audit_logger.log_decision.return_value = AsyncMock()()
        
        server = MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=test_config,
        )
        
        # Test that server can handle concurrent tool evaluations
        evaluate_tool = None
        for tool_name, tool_func in server.mcp._tools.items():
            if "evaluate_tool_request" in tool_name:
                evaluate_tool = tool_func
                break
        
        assert evaluate_tool is not None
        
        # Run multiple concurrent evaluations
        tasks = []
        for i in range(5):
            task = evaluate_tool(
                tool_name=f"test_tool_{i}",
                parameters={"arg": f"value_{i}"},
                agent_id=f"test_agent_{i}",
                session_id=f"test_session_{i}",
                cwd="/tmp",
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Verify all evaluations succeeded
        assert len(results) == 5
        for result in results:
            assert result.action == "allow"
            assert result.confidence == 0.9
        
        # Verify security policy was called for each evaluation
        assert security_policy.evaluate.call_count == 5

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
        
        # Should only have STDIO enabled by default
        enabled = server._get_enabled_transports()
        assert "stdio" in enabled
        assert len(enabled) == 1  # Only STDIO should be enabled by default

    @pytest.mark.asyncio
    async def test_error_handling_across_transports(self, mock_components, test_config):
        """Test error handling across different transports."""
        security_policy, audit_logger, error_handler, health_monitor = mock_components
        
        # Setup mock to raise exception
        security_policy.evaluate.side_effect = Exception("Test error")
        
        # Setup error handler mock
        fallback_decision = Decision(
            action="deny",
            reason="Error occurred",
            confidence=0.0,
            processing_time_ms=1,
        )
        error_handler.handle_error.return_value = fallback_decision
        audit_logger.log_decision.return_value = AsyncMock()()
        
        server = MultiTransportServer(
            security_policy=security_policy,
            audit_logger=audit_logger,
            error_handler=error_handler,
            health_monitor=health_monitor,
            config=test_config,
        )
        
        # Get the evaluate function from MCP tools
        evaluate_tool = None
        for tool_name, tool_func in server.mcp._tools.items():
            if "evaluate_tool_request" in tool_name:
                evaluate_tool = tool_func
                break
        
        assert evaluate_tool is not None
        
        # Test evaluation with error
        result = await evaluate_tool(
            tool_name="test_tool",
            parameters={"arg": "value"},
            agent_id="test_agent",
            session_id="test_session",
            cwd="/tmp",
        )
        
        # Should get fallback decision
        assert result.action == "deny"
        assert result.reason == "Error occurred"
        
        # Verify error handler was called
        error_handler.handle_error.assert_called_once()
        audit_logger.log_decision.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])