"""Integration tests for multi-transport server functionality."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.config import ConfigManager
from superego_mcp.infrastructure.error_handler import (
    AuditLogger,
    ErrorHandler,
    HealthMonitor,
)
from superego_mcp.presentation.transport_server import MultiTransportServer

# Ensure test environment is detected
os.environ["TESTING"] = "1"

# Add timeout for all async tests to prevent hanging
pytestmark = pytest.mark.timeout(30)  # 30 second timeout for all tests in this module


@pytest.fixture
def temp_config_files():
    """Create temporary configuration files for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)

        # Create rules file
        rules_file = config_dir / "rules.yaml"
        rules_data = {
            "rules": [
                {
                    "id": "test-rule-1",
                    "priority": 100,
                    "conditions": {"tool_name": "test_tool"},
                    "action": "allow",
                },
                {
                    "id": "test-rule-2",
                    "priority": 200,
                    "conditions": {"tool_name": "dangerous_tool"},
                    "action": "deny",
                },
            ]
        }

        with open(rules_file, "w") as f:
            yaml.safe_dump(rules_data, f)

        # Create server config file
        server_config_file = config_dir / "server.yaml"
        server_config_data = {
            "host": "localhost",
            "port": 8000,
            "debug": True,
            "log_level": "DEBUG",
            "rules_file": str(rules_file),
            "hot_reload": False,
            "health_check_enabled": True,
            "health_check_interval": 5,
            "ai_sampling": {
                "enabled": False,  # Disable AI sampling for tests
            },
            "transport": {
                "stdio": {"enabled": True},
                "http": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 18000,  # Use different port for testing
                    "cors_origins": ["*"],
                },
                "sse": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 18002,
                    "cors_origins": ["*"],
                    "keepalive_interval": 5,
                },
            },
        }

        with open(server_config_file, "w") as f:
            yaml.safe_dump(server_config_data, f)

        yield config_dir, rules_file, server_config_file


@pytest.fixture
async def integrated_server(temp_config_files):
    """Create a fully integrated multi-transport server for testing."""
    config_dir, rules_file, server_config_file = temp_config_files

    # Load configuration
    config_manager = ConfigManager(str(server_config_file))
    config = config_manager.load_config()

    # Create components
    error_handler = ErrorHandler()
    audit_logger = AuditLogger()
    health_monitor = HealthMonitor()

    # Create security policy (without AI components for simplicity)
    security_policy = SecurityPolicyEngine(
        rules_file=rules_file,
        health_monitor=health_monitor,
        ai_service_manager=None,
        prompt_builder=None,
    )

    # Register components for health monitoring
    health_monitor.register_component("security_policy", security_policy)
    health_monitor.register_component("audit_logger", audit_logger)

    # Create multi-transport server
    server = MultiTransportServer(
        security_policy=security_policy,
        audit_logger=audit_logger,
        error_handler=error_handler,
        health_monitor=health_monitor,
        config=config,
    )

    yield server

    # Cleanup
    await server.stop()


class TestMultiTransportIntegration:
    """Integration tests for multi-transport functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_server_startup_and_shutdown(self, integrated_server):
        """Test that multi-transport server can start and stop cleanly."""
        server = integrated_server

        # Test that server initializes without errors
        assert server.mcp is not None
        assert server.security_policy is not None
        assert server.audit_logger is not None

        # Test enabled transports (STDIO not enabled in test environment)
        enabled = server._get_enabled_transports()
        assert "http" in enabled
        assert "sse" in enabled

        # Test that we can get the MCP app
        app = server.get_mcp_app()
        assert app is not None

    @pytest.mark.integration
    def test_http_transport_evaluation(self, integrated_server):
        """Test tool evaluation via HTTP transport."""
        server = integrated_server

        # Create HTTP transport manually for testing
        from superego_mcp.presentation.http_transport import HTTPTransport

        http_transport = HTTPTransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.http.model_dump(),
        )

        # Test evaluation endpoint
        from fastapi.testclient import TestClient

        client = TestClient(http_transport.app)

        # Test allowed tool
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
        assert "test-rule-1" in data.get("rule_id", "")

        # Test denied tool
        response = client.post(
            "/v1/evaluate",
            json={
                "tool_name": "dangerous_tool",
                "parameters": {"arg": "value"},
                "agent_id": "test_agent",
                "session_id": "test_session",
                "cwd": "/tmp",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "deny"
        assert "test-rule-2" in data.get("rule_id", "")

    @pytest.mark.integration
    def test_http_health_and_info_endpoints(self, integrated_server):
        """Test HTTP health check and server info endpoints."""
        server = integrated_server

        # Create HTTP transport manually for testing
        from superego_mcp.presentation.http_transport import HTTPTransport

        http_transport = HTTPTransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.http.model_dump(),
        )

        from fastapi.testclient import TestClient

        client = TestClient(http_transport.app)

        # Test health endpoint
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data

        # Test server info endpoint
        response = client.get("/v1/server-info")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "superego-mcp"
        assert data["transport"] == "http"
        assert "endpoints" in data

        # Test rules endpoint
        response = client.get("/v1/config/rules")
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "total_rules" in data
        assert data["total_rules"] == 2

        # Test audit endpoint
        response = client.get("/v1/audit/recent")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "stats" in data

        # Test metrics endpoint
        response = client.get("/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "audit_stats" in data

    # WebSocket transport removed - test disabled
    # @pytest.mark.integration
    # @pytest.mark.asyncio
    # async def test_websocket_transport_functionality(self, integrated_server):
    #     """Test WebSocket transport functionality."""
    #     server = integrated_server
    #
    #     # Create WebSocket transport manually for testing
    #     from superego_mcp.presentation.websocket_transport import (
    #         WebSocketTransport,
    #         WSMessage,
    #     )
    #
    #     ws_transport = WebSocketTransport(
    #         mcp=server.mcp,
    #         security_policy=server.security_policy,
    #         audit_logger=server.audit_logger,
    #         error_handler=server.error_handler,
    #         health_monitor=server.health_monitor,
    #         config=server.config.transport.websocket.model_dump(),
    #     )
    #
    #     # Test message handling directly
    #     eval_message = WSMessage(
    #         message_id="test-123",
    #         type="evaluate",
    #         data={
    #             "tool_name": "test_tool",
    #             "parameters": {"arg": "value"},
    #             "agent_id": "test_agent",
    #             "session_id": "test_session",
    #             "cwd": "/tmp",
    #         },
    #     )
    #
    #     mock_websocket = None  # We'll test without actual websocket connection
    #     response = await ws_transport._handle_message(eval_message, mock_websocket)
    #
    #     assert response is not None
    #     assert response.message_id == "test-123"
    #     assert response.type == "response"
    #     assert response.data["action"] == "allow"
    #
    #     # Test health check message
    #     health_message = WSMessage(message_id="health-123", type="health", data={})
    #
    #     response = await ws_transport._handle_message(health_message, mock_websocket)
    #     assert response is not None
    #     assert response.message_id == "health-123"
    #     assert response.type == "response"
    #     assert "status" in response.data
    #
    #     # Test ping message
    #     ping_message = WSMessage(message_id="ping-123", type="ping", data={})
    #
    #     response = await ws_transport._handle_message(ping_message, mock_websocket)
    #     assert response is not None
    #     assert response.message_id == "ping-123"
    #     assert response.type == "response"
    #     assert response.data["pong"] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sse_transport_functionality(self, integrated_server):
        """Test Server-Sent Events transport functionality."""
        server = integrated_server

        # Create SSE transport manually for testing
        from superego_mcp.presentation.sse_transport import SSEEvent, SSETransport

        sse_transport = SSETransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.sse.model_dump(),
        )

        # Test SSE manager functionality
        manager = sse_transport.sse_manager

        # Test subscription
        queue = await manager.subscribe("health")
        assert queue is not None
        assert queue in manager.subscribers["health"]

        # Test broadcasting
        test_event = SSEEvent(
            event="test_event",
            data=json.dumps({"message": "test", "timestamp": "2025-01-01T00:00:00"}),
        )

        await manager.broadcast("health", test_event)

        # Verify event was received
        received_event = queue.get_nowait()
        assert received_event.event == "test_event"
        assert "test" in received_event.data

        # Test message formatting
        formatted = sse_transport._format_sse_message(test_event)
        assert "event: test_event" in formatted
        assert "data: " in formatted
        assert formatted.endswith("\n\n")

        # Test unsubscribe
        manager.unsubscribe("health", queue)
        assert queue not in manager.subscribers["health"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_multi_transport_operations(self, integrated_server):
        """Test concurrent operations across multiple transports."""
        server = integrated_server

        # Create transport instances
        from superego_mcp.presentation.http_transport import HTTPTransport
        from superego_mcp.presentation.websocket_transport import (
            WebSocketTransport,
            WSMessage,
        )

        http_transport = HTTPTransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.http.model_dump(),
        )

        ws_transport = WebSocketTransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.websocket.model_dump(),
        )

        # Prepare concurrent operations
        async def http_evaluation():
            from fastapi.testclient import TestClient

            client = TestClient(http_transport.app)
            return client.post(
                "/v1/evaluate",
                json={
                    "tool_name": "test_tool",
                    "parameters": {"http": "request"},
                    "agent_id": "http_agent",
                    "session_id": "http_session",
                    "cwd": "/tmp",
                },
            )

        async def ws_evaluation():
            message = WSMessage(
                message_id="ws-eval-123",
                type="evaluate",
                data={
                    "tool_name": "test_tool",
                    "parameters": {"ws": "request"},
                    "agent_id": "ws_agent",
                    "session_id": "ws_session",
                    "cwd": "/tmp",
                },
            )
            return await ws_transport._handle_message(message, None)

        async def core_evaluation():
            # Test core MCP functionality
            evaluate_tool = None
            if hasattr(server.mcp, "_tools"):
                for tool_name, tool_func in server.mcp._tools.items():
                    if "evaluate_tool_request" in tool_name:
                        evaluate_tool = tool_func
                        break
            elif hasattr(server.mcp, "tools"):
                for tool_name, tool_func in server.mcp.tools.items():
                    if "evaluate_tool_request" in tool_name:
                        evaluate_tool = tool_func
                        break

            if evaluate_tool:
                return await evaluate_tool(
                    tool_name="test_tool",
                    parameters={"core": "request"},
                    agent_id="core_agent",
                    session_id="core_session",
                    cwd="/tmp",
                )
            return None

        # Run concurrent operations
        results = await asyncio.gather(
            http_evaluation(),
            ws_evaluation(),
            core_evaluation(),
            return_exceptions=True,
        )

        # Verify all operations succeeded
        http_result, ws_result, core_result = results

        # Check HTTP result
        assert hasattr(http_result, "status_code")
        assert http_result.status_code == 200
        http_data = http_result.json()
        assert http_data["action"] == "allow"

        # Check WebSocket result
        assert ws_result is not None
        assert ws_result.type == "response"
        assert ws_result.data["action"] == "allow"

        # Check core MCP result (if available)
        if core_result is not None:
            assert core_result["action"] == "allow"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling_across_transports(self, integrated_server):
        """Test error handling consistency across transports."""
        server = integrated_server

        # Create transport instances
        from superego_mcp.presentation.http_transport import HTTPTransport
        from superego_mcp.presentation.websocket_transport import (
            WebSocketTransport,
            WSMessage,
        )

        http_transport = HTTPTransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.http.model_dump(),
        )

        ws_transport = WebSocketTransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.websocket.model_dump(),
        )

        # Test HTTP error handling - invalid request
        from fastapi.testclient import TestClient

        client = TestClient(http_transport.app)
        response = client.post(
            "/v1/evaluate",
            json={
                # Missing required fields
                "tool_name": "test_tool",
                # "agent_id": "test_agent",  # Missing
                # "session_id": "test_session",  # Missing
            },
        )

        # Should return 422 for validation error
        assert response.status_code == 422

        # Test WebSocket error handling - invalid message
        invalid_message = WSMessage(
            message_id="invalid-123",
            type="evaluate",
            data={
                "tool_name": "test_tool",
                # Missing required fields
            },
        )

        response = await ws_transport._handle_message(invalid_message, None)
        assert response is not None
        assert response.type == "error"
        assert "Missing required field" in response.error

        # Test unknown message type
        unknown_message = WSMessage(
            message_id="unknown-123", type="unknown_type", data={}
        )

        response = await ws_transport._handle_message(unknown_message, None)
        assert response is not None
        assert response.type == "error"
        assert "Unknown message type" in response.error

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_audit_logging_across_transports(self, integrated_server):
        """Test that audit logging works consistently across transports."""
        server = integrated_server

        # Clear existing audit entries
        server.audit_logger.get_recent_entries(limit=1000)  # This should clear or reset

        # Create transport instances
        from superego_mcp.presentation.http_transport import HTTPTransport
        from superego_mcp.presentation.websocket_transport import (
            WebSocketTransport,
            WSMessage,
        )

        http_transport = HTTPTransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.http.model_dump(),
        )

        ws_transport = WebSocketTransport(
            mcp=server.mcp,
            security_policy=server.security_policy,
            audit_logger=server.audit_logger,
            error_handler=server.error_handler,
            health_monitor=server.health_monitor,
            config=server.config.transport.websocket.model_dump(),
        )

        # Perform operations via different transports
        # HTTP operation
        from fastapi.testclient import TestClient

        client = TestClient(http_transport.app)
        client.post(
            "/v1/evaluate",
            json={
                "tool_name": "test_tool",
                "parameters": {"source": "http"},
                "agent_id": "http_agent",
                "session_id": "http_session",
                "cwd": "/tmp",
            },
        )

        # WebSocket operation
        ws_message = WSMessage(
            message_id="audit-test-123",
            type="evaluate",
            data={
                "tool_name": "dangerous_tool",
                "parameters": {"source": "websocket"},
                "agent_id": "ws_agent",
                "session_id": "ws_session",
                "cwd": "/tmp",
            },
        )
        await ws_transport._handle_message(ws_message, None)

        # Core MCP operation
        evaluate_tool = None
        if hasattr(server.mcp, "_tools"):
            for tool_name, tool_func in server.mcp._tools.items():
                if "evaluate_tool_request" in tool_name:
                    evaluate_tool = tool_func
                    break
        elif hasattr(server.mcp, "tools"):
            for tool_name, tool_func in server.mcp.tools.items():
                if "evaluate_tool_request" in tool_name:
                    evaluate_tool = tool_func
                    break

        if evaluate_tool:
            await evaluate_tool(
                tool_name="test_tool",
                parameters={"source": "core"},
                agent_id="core_agent",
                session_id="core_session",
                cwd="/tmp",
            )

        # Check audit stats
        stats = server.audit_logger.get_stats()
        assert (
            stats.get("total", 0) >= 2
        )  # At least 2 entries from our operations (core MCP might not run)

        # Check recent entries
        recent_entries = server.audit_logger.get_recent_entries(limit=10)
        assert len(recent_entries) >= 2  # At least 2 entries from our operations

        # Verify entries contain different agent IDs from different transports
        agent_ids = [
            entry.request.agent_id
            for entry in recent_entries
            if hasattr(entry, "request")
        ]
        assert any("http_agent" in aid for aid in agent_ids)
        assert any("ws_agent" in aid for aid in agent_ids)
        # Don't assert core_agent since core MCP might not execute


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
