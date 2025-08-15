"""Tests for the InterceptionService with SecurityPolicyEngine integration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from superego_mcp.domain.models import ToolRequest
from superego_mcp.domain.services import InterceptionService


class TestInterceptionService:
    """Test suite for InterceptionService functionality."""

    def create_test_rules_file(self, rules_data: dict) -> Path:
        """Create a temporary rules file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.safe_dump(rules_data, temp_file)
        temp_file.close()
        return Path(temp_file.name)

    @pytest.mark.asyncio
    async def test_interception_service_from_rules_file(self):
        """Test creating InterceptionService from rules file."""
        rules_data = {
            "rules": [
                {
                    "id": "test_rule",
                    "priority": 1,
                    "conditions": {"tool_name": "test"},
                    "action": "allow",
                    "reason": "Test rule",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            service = InterceptionService.from_rules_file(rules_file)

            # Verify it uses SecurityPolicyEngine
            assert service.security_policy_engine is not None
            assert service.rule_engine is None

            # Test request evaluation
            request = ToolRequest(
                tool_name="test",
                parameters={},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await service.evaluate_request(request)
            assert decision.action == "allow"
            assert decision.rule_id == "test_rule"
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_interception_service_health_check_with_policy_engine(self):
        """Test health check with SecurityPolicyEngine."""
        rules_data = {
            "rules": [
                {
                    "id": "rule1",
                    "priority": 1,
                    "conditions": {"tool_name": {"equals": "safe_tool"}},
                    "action": "allow",
                },
                {
                    "id": "rule2",
                    "priority": 2,
                    "conditions": {"tool_name": {"equals": "dangerous_tool"}},
                    "action": "deny",
                },
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            service = InterceptionService.from_rules_file(rules_file)
            health = await service.health_check()

            assert health["status"] == "healthy"
            assert health["rules_loaded"] == 2
            assert health["service"] == "InterceptionService"
            assert health["engine"] == "SecurityPolicyEngine"
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_interception_service_evaluation_flow(self):
        """Test complete evaluation flow with SecurityPolicyEngine."""
        rules_data = {
            "rules": [
                {
                    "id": "deny_dangerous",
                    "priority": 1,
                    "conditions": {"tool_name": ["rm", "sudo"]},
                    "action": "deny",
                    "reason": "Dangerous command blocked",
                },
                {
                    "id": "allow_safe",
                    "priority": 10,
                    "conditions": {"tool_name": ["ls", "cat"]},
                    "action": "allow",
                    "reason": "Safe command allowed",
                },
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            service = InterceptionService.from_rules_file(rules_file)

            # Test dangerous command is blocked
            dangerous_request = ToolRequest(
                tool_name="rm",
                parameters={"file": "test.txt"},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await service.evaluate_request(dangerous_request)
            assert decision.action == "deny"
            assert decision.rule_id == "deny_dangerous"

            # Test safe command is allowed
            safe_request = ToolRequest(
                tool_name="ls",
                parameters={},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await service.evaluate_request(safe_request)
            assert decision.action == "allow"
            assert decision.rule_id == "allow_safe"
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_interception_service_performance_benchmark(self):
        """Test InterceptionService performance meets requirements."""
        # Create many rules to test performance
        rules_data = {
            "rules": [
                {
                    "id": f"rule_{i}",
                    "priority": i,
                    "conditions": {"tool_name": f"tool_{i}"},
                    "action": "allow",
                    "reason": f"Rule {i}",
                }
                for i in range(50)  # 50 rules
            ]
            + [
                {
                    "id": "target_rule",
                    "priority": 51,
                    "conditions": {"tool_name": "target_tool"},
                    "action": "deny",
                    "reason": "Target rule matched",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            service = InterceptionService.from_rules_file(rules_file)

            request = ToolRequest(
                tool_name="target_tool",
                parameters={},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            # Test multiple evaluations for performance consistency
            for _ in range(5):
                decision = await service.evaluate_request(request)

                assert decision.action == "deny"
                assert decision.rule_id == "target_rule"
                # Check that processing time is reasonable
                assert decision.processing_time_ms < 10, (
                    f"Processing time {decision.processing_time_ms}ms exceeds 10ms target"
                )
        finally:
            rules_file.unlink()

    def test_interception_service_initialization_error(self):
        """Test proper error handling for uninitialized service."""
        # Create service without proper initialization
        service = InterceptionService.__new__(InterceptionService)
        service.security_policy_engine = None
        service.rule_engine = None

        request = ToolRequest(
            tool_name="test",
            parameters={},
            session_id="session1",
            agent_id="agent1",
            cwd="/home/user",
        )

        with pytest.raises(
            ValueError, match="InterceptionService not properly initialized"
        ):
            # Use asyncio.run for sync test
            import asyncio

            asyncio.run(service.evaluate_request(request))

    @pytest.mark.asyncio
    async def test_interception_service_unhealthy_status(self):
        """Test health check returns unhealthy when not properly initialized."""
        # Create service without proper initialization
        service = InterceptionService.__new__(InterceptionService)
        service.security_policy_engine = None
        service.rule_engine = None

        health = await service.health_check()

        assert health["status"] == "unhealthy"
        assert "No policy engine initialized" in health["error"]
        assert health["service"] == "InterceptionService"

    def teardown_method(self):
        """Clean up after each test."""
        import glob
        import tempfile

        temp_dir = tempfile.gettempdir()
        temp_files = glob.glob(f"{temp_dir}/tmp*.yaml")
        for temp_file in temp_files:
            try:
                Path(temp_file).unlink()
            except FileNotFoundError:
                pass
