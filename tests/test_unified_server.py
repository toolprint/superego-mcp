"""Tests for the unified server architecture."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from superego_mcp.domain.models import Decision
from superego_mcp.infrastructure.config import ServerConfig
from superego_mcp.presentation.unified_server import UnifiedServer


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for testing."""
    security_policy = AsyncMock()
    audit_logger = AsyncMock()
    error_handler = MagicMock()
    health_monitor = AsyncMock()
    config = MagicMock(spec=ServerConfig)

    # Configure mock defaults
    config.hot_reload = False
    config.ai_sampling = MagicMock()
    config.ai_sampling.enabled = False
    config.health_check_enabled = True

    # Mock a sample decision
    sample_decision = Decision(
        action="allow",
        reason="Test decision",
        confidence=0.95,
        ai_provider="test",
        ai_model="test-model",
        processing_time_ms=100,
    )
    security_policy.evaluate.return_value = sample_decision

    # Mock health check response
    health_status = MagicMock()
    health_status.model_dump.return_value = {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "components": {},
    }
    health_monitor.check_health.return_value = health_status

    return {
        "security_policy": security_policy,
        "audit_logger": audit_logger,
        "error_handler": error_handler,
        "health_monitor": health_monitor,
        "config": config,
    }


def test_unified_server_initialization(mock_dependencies):
    """Test that the unified server initializes properly."""
    server = UnifiedServer(**mock_dependencies)

    # Check that both FastAPI and FastMCP apps are created
    assert server.fastapi is not None
    assert server.mcp is not None

    # Check that the server has the expected attributes
    assert server.security_policy is not None
    assert server.audit_logger is not None
    assert server.error_handler is not None
    assert server.health_monitor is not None


def test_unified_server_transport_detection(mock_dependencies):
    """Test that the server correctly detects enabled transports."""
    server = UnifiedServer(**mock_dependencies)

    transports = server._get_enabled_transports()

    # Should include HTTP and WebSocket by default
    assert "http" in transports
    assert "websocket" in transports

    # STDIO should be included unless in test environment
    if not server._is_test_environment():
        assert "stdio" in transports


def test_unified_server_test_environment_detection(mock_dependencies):
    """Test that the server correctly detects test environment."""
    server = UnifiedServer(**mock_dependencies)

    # Should detect test environment
    assert server._is_test_environment() is True


@pytest.mark.asyncio
async def test_unified_server_evaluate_internal(mock_dependencies):
    """Test the internal evaluation logic."""
    server = UnifiedServer(**mock_dependencies)

    # Test evaluation
    decision = await server._evaluate_internal(
        tool_name="test_tool",
        parameters={"param": "value"},
        agent_id="test_agent",
        session_id="test_session",
        cwd="/tmp",
    )

    # Check that the evaluation was called
    assert decision.action == "allow"
    assert decision.reason == "Test decision"

    # Verify security policy was called
    mock_dependencies["security_policy"].evaluate.assert_called_once()

    # Verify audit logging was called
    mock_dependencies["audit_logger"].log_decision.assert_called_once()


@pytest.mark.asyncio
async def test_unified_server_health_check_internal(mock_dependencies):
    """Test the internal health check logic."""
    server = UnifiedServer(**mock_dependencies)

    # Test health check
    health_data = await server._health_check_internal()

    # Check that health data is returned
    assert health_data["status"] == "healthy"
    assert "timestamp" in health_data
    assert "components" in health_data

    # Verify health monitor was called
    mock_dependencies["health_monitor"].check_health.assert_called_once()


@pytest.mark.asyncio
async def test_unified_server_server_info_internal(mock_dependencies):
    """Test the internal server info logic."""
    server = UnifiedServer(**mock_dependencies)

    # Test server info
    info = await server._server_info_internal()

    # Check that server info is returned
    assert info["name"] == "superego-mcp"
    assert info["architecture"] == "unified"
    assert "protocols" in info
    assert "mcp" in info["protocols"]
    assert "http" in info["protocols"]
    assert "websocket" in info["protocols"]


def test_unified_server_decision_to_permission_conversion(mock_dependencies):
    """Test the decision to permission conversion logic."""
    server = UnifiedServer(**mock_dependencies)

    # Test various action conversions
    from superego_mcp.domain.claude_code_models import PermissionDecision

    assert server._decision_to_permission("allow") == PermissionDecision.ALLOW
    assert server._decision_to_permission("approve") == PermissionDecision.ALLOW
    assert server._decision_to_permission("ask") == PermissionDecision.ASK
    assert server._decision_to_permission("deny") == PermissionDecision.DENY
    assert server._decision_to_permission("block") == PermissionDecision.DENY
    assert server._decision_to_permission("unknown") == PermissionDecision.DENY


def test_unified_server_cli_transport_override(mock_dependencies):
    """Test CLI transport override functionality."""
    # Test with HTTP override
    server = UnifiedServer(**mock_dependencies, cli_transport="http", cli_port=9000)

    assert server.cli_transport == "http"
    assert server.cli_port == 9000

    # Test with STDIO override
    server = UnifiedServer(**mock_dependencies, cli_transport="stdio")

    assert server.cli_transport == "stdio"
    assert server.cli_port is None


def test_unified_server_get_app_methods(mock_dependencies):
    """Test that the server provides access to both app instances."""
    server = UnifiedServer(**mock_dependencies)

    # Test FastAPI app access
    fastapi_app = server.get_fastapi_app()
    assert fastapi_app is not None
    assert hasattr(fastapi_app, "router")  # FastAPI characteristic

    # Test FastMCP app access
    mcp_app = server.get_mcp_app()
    assert mcp_app is not None


@pytest.mark.asyncio
async def test_unified_server_context_managers(mock_dependencies):
    """Test async context manager support."""
    server = UnifiedServer(**mock_dependencies)

    # Test that the server can be used as an async context manager
    # Note: This test doesn't actually start the server to avoid blocking
    assert hasattr(server, "__aenter__")
    assert hasattr(server, "__aexit__")

    # Test test context creation
    test_context = server.create_test_context()
    assert test_context is not None


def test_unified_server_backward_compatibility(mock_dependencies):
    """Test that the unified server maintains backward compatibility."""
    server = UnifiedServer(**mock_dependencies)

    # Should have the same interface as MultiTransportServer
    assert hasattr(server, "start")
    assert hasattr(server, "stop")
    assert hasattr(server, "get_mcp_app")

    # Should have additional unified server methods
    assert hasattr(server, "get_fastapi_app")
    assert hasattr(server, "_evaluate_internal")
    assert hasattr(server, "_health_check_internal")
    assert hasattr(server, "_server_info_internal")


if __name__ == "__main__":
    pytest.main([__file__])
