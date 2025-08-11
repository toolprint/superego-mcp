"""Integration tests for FastMCP server implementation."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml

from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.error_handler import (
    AuditLogger,
    ErrorHandler,
    HealthMonitor,
)
from superego_mcp.presentation.mcp_server import (
    create_server,
    mcp,
)


@pytest.fixture
async def temp_rules_file():
    """Create temporary rules file for testing"""
    test_rules = {
        "rules": [
            {
                "id": "test-rule-1",
                "conditions": {"tool_name": "dangerous_tool"},
                "action": "deny",
                "reason": "Test rule for dangerous tool",
                "priority": 1,
            },
            {
                "id": "test-rule-2",
                "conditions": {"tool_name": "safe_tool"},
                "action": "allow",
                "reason": "Test rule for safe tool",
                "priority": 2,
            },
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(test_rules, f)
        temp_file_path = Path(f.name)

    yield temp_file_path

    # Cleanup
    temp_file_path.unlink()


@pytest.fixture
async def configured_server(temp_rules_file):
    """Create configured server with test dependencies"""
    security_policy = SecurityPolicyEngine(temp_rules_file)
    error_handler = ErrorHandler()
    audit_logger = AuditLogger()
    health_monitor = HealthMonitor()

    # Register components
    health_monitor.register_component("security_policy", security_policy)
    health_monitor.register_component("audit_logger", audit_logger)

    server = await create_server(
        security_policy, audit_logger, error_handler, health_monitor
    )

    return server


class TestMCPServerIntegration:
    """Integration tests for FastMCP server"""

    @pytest.mark.asyncio
    async def test_server_creation(self, temp_rules_file):
        """Test server can be created successfully"""
        security_policy = SecurityPolicyEngine(temp_rules_file)
        error_handler = ErrorHandler()
        audit_logger = AuditLogger()
        health_monitor = HealthMonitor()

        server = await create_server(
            security_policy, audit_logger, error_handler, health_monitor
        )

        assert server is not None
        assert server.name == "Superego MCP Server"

    @pytest.mark.asyncio
    async def test_evaluate_tool_request_deny(self, configured_server):
        """Test evaluate_tool_request with denied request"""
        from fastmcp import Context

        from superego_mcp.presentation import mcp_server

        # Test the tool by calling the underlying implementation directly
        result = await mcp_server.evaluate_tool_request.fn(
            tool_name="dangerous_tool",
            parameters={"arg": "value"},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/path",
            ctx=Context(fastmcp=mcp),
        )

        assert result["action"] == "deny"
        assert result["reason"] == "Test rule for dangerous tool"
        assert result["confidence"] == 1.0
        assert result["rule_id"] == "test-rule-1"
        assert "processing_time_ms" in result
        assert result.get("error") != True

    @pytest.mark.asyncio
    async def test_evaluate_tool_request_allow(self, configured_server):
        """Test evaluate_tool_request with allowed request"""
        from fastmcp import Context

        from superego_mcp.presentation import mcp_server

        result = await mcp_server.evaluate_tool_request.fn(
            tool_name="safe_tool",
            parameters={"arg": "value"},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/path",
            ctx=Context(fastmcp=mcp),
        )

        assert result["action"] == "allow"
        assert result["reason"] == "Test rule for safe tool"
        assert result["confidence"] == 1.0
        assert result["rule_id"] == "test-rule-2"
        assert "processing_time_ms" in result
        assert result.get("error") != True

    @pytest.mark.asyncio
    async def test_evaluate_tool_request_no_match(self, configured_server):
        """Test evaluate_tool_request with no matching rules"""
        from fastmcp import Context

        from superego_mcp.presentation import mcp_server

        result = await mcp_server.evaluate_tool_request.fn(
            tool_name="unknown_tool",
            parameters={"arg": "value"},
            session_id="test-session",
            agent_id="test-agent",
            cwd="/test/path",
            ctx=Context(fastmcp=mcp),
        )

        assert result["action"] == "allow"
        assert result["reason"] == "No security rules matched"
        assert result["confidence"] == 0.5
        assert result["rule_id"] is None
        assert "processing_time_ms" in result

    @pytest.mark.asyncio
    async def test_evaluate_tool_request_error_handling(self, configured_server):
        """Test evaluate_tool_request error handling"""
        from fastmcp import Context

        from superego_mcp.presentation import mcp_server

        # Mock security_policy to raise an exception
        with patch(
            "superego_mcp.presentation.mcp_server.security_policy"
        ) as mock_policy:
            mock_policy.evaluate = AsyncMock(side_effect=Exception("Test error"))

            result = await mcp_server.evaluate_tool_request.fn(
                tool_name="test_tool",
                parameters={"arg": "value"},
                session_id="test-session",
                agent_id="test-agent",
                cwd="/test/path",
                ctx=Context(fastmcp=mcp),
            )

            assert result["action"] == "deny"
            assert "Internal security evaluation error" in result["reason"]
            assert result["confidence"] == 0.9
            assert result["error"] == True

    @pytest.mark.asyncio
    async def test_get_current_rules_resource(self, configured_server):
        """Test config://rules resource endpoint"""
        from superego_mcp.presentation import mcp_server

        result = await mcp_server.get_current_rules.fn()

        # Parse the YAML result
        rules_data = yaml.safe_load(result)

        assert "rules" in rules_data
        assert "total_rules" in rules_data
        assert "last_updated" in rules_data
        assert rules_data["total_rules"] == 2
        assert len(rules_data["rules"]) == 2

        # Check rule content
        rule_ids = [rule["id"] for rule in rules_data["rules"]]
        assert "test-rule-1" in rule_ids
        assert "test-rule-2" in rule_ids

    @pytest.mark.asyncio
    async def test_get_current_rules_error_handling(self, configured_server):
        """Test config://rules error handling"""
        with patch(
            "superego_mcp.presentation.mcp_server.security_policy"
        ) as mock_policy:
            mock_policy.rules = []
            mock_policy.rules_file = Mock()
            mock_policy.rules_file.stat = Mock(side_effect=Exception("File error"))

            from superego_mcp.presentation import mcp_server

            result = await mcp_server.get_current_rules.fn()

            assert result.startswith("Error loading rules:")

    @pytest.mark.asyncio
    async def test_get_recent_audit_entries_resource(self, configured_server):
        """Test audit://recent resource endpoint"""
        # First, create some audit entries by evaluating requests
        from fastmcp import Context

        from superego_mcp.presentation import mcp_server

        await mcp_server.evaluate_tool_request.fn(
            tool_name="safe_tool",
            parameters={"test": "value"},
            session_id="audit-test",
            agent_id="test-agent",
            cwd="/test",
            ctx=Context(fastmcp=mcp),
        )

        result = await mcp_server.get_recent_audit_entries.fn()
        audit_data = json.loads(result)

        assert "entries" in audit_data
        assert "stats" in audit_data
        assert len(audit_data["entries"]) >= 1

        # Check stats structure
        stats = audit_data["stats"]
        assert "total" in stats
        assert "allowed" in stats
        assert "denied" in stats
        assert "allow_rate" in stats
        assert "avg_processing_time_ms" in stats

    @pytest.mark.asyncio
    async def test_get_recent_audit_entries_error_handling(self, configured_server):
        """Test audit://recent error handling"""
        with patch("superego_mcp.presentation.mcp_server.audit_logger") as mock_logger:
            mock_logger.get_recent_entries = Mock(side_effect=Exception("Audit error"))

            from superego_mcp.presentation import mcp_server

            result = await mcp_server.get_recent_audit_entries.fn()

            assert result.startswith("Error loading audit entries:")

    @pytest.mark.asyncio
    async def test_get_health_status_resource(self, configured_server):
        """Test health://status resource endpoint"""
        from superego_mcp.presentation import mcp_server

        result = await mcp_server.get_health_status.fn()
        health_data = json.loads(result)

        assert "status" in health_data
        assert "components" in health_data
        assert "metrics" in health_data

        # Check component health
        components = health_data["components"]
        assert "security_policy" in components
        assert "audit_logger" in components

        # Check metrics
        metrics = health_data["metrics"]
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "disk_usage_percent" in metrics

    @pytest.mark.asyncio
    async def test_get_health_status_error_handling(self, configured_server):
        """Test health://status error handling"""
        with patch(
            "superego_mcp.presentation.mcp_server.health_monitor"
        ) as mock_monitor:
            mock_monitor.check_health = AsyncMock(
                side_effect=Exception("Health check error")
            )

            from superego_mcp.presentation import mcp_server

            result = await mcp_server.get_health_status.fn()

            assert result.startswith("Error checking health:")

    @pytest.mark.asyncio
    async def test_audit_logging_integration(self, configured_server):
        """Test that audit logging works correctly with tool evaluation"""
        from fastmcp import Context

        from superego_mcp.presentation import mcp_server

        # Clear any existing audit entries
        mcp_server.audit_logger.entries.clear()

        # Evaluate a tool request
        await mcp_server.evaluate_tool_request.fn(
            tool_name="dangerous_tool",
            parameters={"test": "value"},
            session_id="audit-integration-test",
            agent_id="test-agent",
            cwd="/test",
            ctx=Context(fastmcp=mcp),
        )

        # Check that audit entry was created
        entries = mcp_server.audit_logger.get_recent_entries(limit=1)
        assert len(entries) == 1

        entry = entries[0]
        assert entry.request.tool_name == "dangerous_tool"
        assert entry.decision.action == "deny"
        assert entry.rule_matches == ["test-rule-1"]

    @pytest.mark.asyncio
    async def test_component_health_integration(self, temp_rules_file):
        """Test health monitoring component integration"""
        security_policy = SecurityPolicyEngine(temp_rules_file)
        error_handler = ErrorHandler()
        audit_logger = AuditLogger()
        health_monitor = HealthMonitor()

        # Register components
        health_monitor.register_component("security_policy", security_policy)
        health_monitor.register_component("audit_logger", audit_logger)
        health_monitor.register_component("error_handler", error_handler)

        await create_server(
            security_policy, audit_logger, error_handler, health_monitor
        )

        # Test health check
        from superego_mcp.presentation import mcp_server

        result = await mcp_server.get_health_status.fn()
        health_data = json.loads(result)

        assert health_data["status"] == "healthy"
        assert len(health_data["components"]) == 3

        # All components should be healthy by default
        for component, health in health_data["components"].items():
            assert health["status"] == "healthy"


class TestMCPServerConfiguration:
    """Test MCP server configuration and setup"""

    @pytest.mark.asyncio
    async def test_mcp_server_tools_registration(self, configured_server):
        """Test that MCP tools are properly registered"""
        # Check that the tool is registered
        tools = await mcp.get_tools()

        # The evaluate_tool_request should be available
        assert "evaluate_tool_request" in tools
        assert tools["evaluate_tool_request"].name == "evaluate_tool_request"

    @pytest.mark.asyncio
    async def test_mcp_server_resources_registration(self, configured_server):
        """Test that MCP resources are properly registered"""
        # Check that resources are registered
        resources = await mcp.get_resources()

        # Check for expected resources
        assert "config://rules" in resources
        assert "audit://recent" in resources
        assert "health://status" in resources


@pytest.mark.integration
class TestMCPServerEndToEnd:
    """End-to-end tests for complete MCP server functionality"""

    @pytest.mark.asyncio
    async def test_full_request_evaluation_cycle(self, configured_server):
        """Test complete request evaluation cycle with all components"""
        from fastmcp import Context

        from superego_mcp.presentation import mcp_server

        # Clear audit log for clean test
        mcp_server.audit_logger.entries.clear()

        # Step 1: Evaluate a denied request
        deny_result = await mcp_server.evaluate_tool_request.fn(
            tool_name="dangerous_tool",
            parameters={"command": "rm -rf /"},
            session_id="e2e-test",
            agent_id="test-agent",
            cwd="/tmp",
            ctx=Context(fastmcp=mcp),
        )

        assert deny_result["action"] == "deny"
        assert deny_result["rule_id"] == "test-rule-1"

        # Step 2: Evaluate an allowed request
        allow_result = await mcp_server.evaluate_tool_request.fn(
            tool_name="safe_tool",
            parameters={"file": "test.txt"},
            session_id="e2e-test",
            agent_id="test-agent",
            cwd="/tmp",
            ctx=Context(fastmcp=mcp),
        )

        assert allow_result["action"] == "allow"
        assert allow_result["rule_id"] == "test-rule-2"

        # Step 3: Check audit trail
        audit_result = await mcp_server.get_recent_audit_entries.fn()
        audit_data = json.loads(audit_result)

        assert len(audit_data["entries"]) == 2
        assert audit_data["stats"]["total"] == 2
        assert audit_data["stats"]["allowed"] == 1
        assert audit_data["stats"]["denied"] == 1
        assert audit_data["stats"]["allow_rate"] == 0.5

        # Step 4: Check health status
        health_result = await mcp_server.get_health_status.fn()
        health_data = json.loads(health_result)

        assert health_data["status"] == "healthy"
        assert len(health_data["components"]) >= 2

        # Step 5: Check rules configuration
        rules_result = await mcp_server.get_current_rules.fn()
        rules_data = yaml.safe_load(rules_result)

        assert rules_data["total_rules"] == 2
        assert len(rules_data["rules"]) == 2
