"""Tests for SecurityPolicyEngine hot-reload functionality."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from superego_mcp.domain.models import ErrorCode, SuperegoError, ToolRequest
from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.error_handler import HealthMonitor


class TestSecurityPolicyHotReload:
    """Test suite for SecurityPolicyEngine hot-reload functionality."""

    @pytest.fixture
    def sample_rules_data(self):
        """Sample rules data for testing."""
        return {
            "rules": [
                {
                    "id": "deny_rm",
                    "priority": 1,
                    "conditions": {"tool_name": "rm"},
                    "action": "deny",
                    "reason": "Dangerous command",
                },
                {
                    "id": "allow_read",
                    "priority": 10,
                    "conditions": {"tool_name": "read"},
                    "action": "allow",
                    "reason": "Safe read command",
                },
            ]
        }

    @pytest.fixture
    async def temp_rules_file(self, sample_rules_data):
        """Create a temporary rules file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(sample_rules_data, f)
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def mock_health_monitor(self):
        """Mock health monitor for testing."""
        monitor = MagicMock(spec=HealthMonitor)
        return monitor

    @pytest.fixture
    async def policy_engine(self, temp_rules_file, mock_health_monitor):
        """Create a SecurityPolicyEngine instance for testing."""
        engine = SecurityPolicyEngine(temp_rules_file, mock_health_monitor)
        return engine

    @pytest.mark.unit
    def test_policy_engine_with_health_monitor(
        self, temp_rules_file, mock_health_monitor
    ):
        """Test SecurityPolicyEngine initialization with health monitor."""
        engine = SecurityPolicyEngine(temp_rules_file, mock_health_monitor)

        assert engine.health_monitor == mock_health_monitor
        assert len(engine.rules) == 2
        assert engine.rules[0].id == "deny_rm"  # Higher priority first

    @pytest.mark.unit
    def test_policy_engine_without_health_monitor(self, temp_rules_file):
        """Test SecurityPolicyEngine initialization without health monitor."""
        engine = SecurityPolicyEngine(temp_rules_file)

        assert engine.health_monitor is None
        assert len(engine.rules) == 2

    @pytest.mark.unit
    async def test_thread_safe_rule_access(self, policy_engine):
        """Test thread-safe access to rules during evaluation."""
        request = ToolRequest(
            tool_name="read",
            parameters={},
            cwd="/test",
            session_id="test-session",
            agent_id="test-agent",
        )

        # This should complete without deadlock
        decision = await policy_engine.evaluate(request)

        assert decision.action == "allow"
        assert decision.rule_id == "allow_read"

    @pytest.mark.unit
    async def test_get_rules_count_thread_safe(self, policy_engine):
        """Test thread-safe access to rules count."""
        count = await policy_engine.get_rules_count()
        assert count == 2

    @pytest.mark.unit
    async def test_get_rule_by_id_thread_safe(self, policy_engine):
        """Test thread-safe access to specific rule."""
        rule = await policy_engine.get_rule_by_id("deny_rm")

        assert rule is not None
        assert rule.id == "deny_rm"
        assert rule.action.value == "deny"

    @pytest.mark.unit
    async def test_get_rule_by_id_not_found(self, policy_engine):
        """Test getting non-existent rule returns None."""
        rule = await policy_engine.get_rule_by_id("nonexistent")
        assert rule is None

    @pytest.mark.unit
    async def test_reload_rules_success(
        self, policy_engine, temp_rules_file, mock_health_monitor
    ):
        """Test successful rules reload."""
        # Modify the rules file
        new_rules_data = {
            "rules": [
                {
                    "id": "new_rule",
                    "priority": 1,
                    "conditions": {"tool_name": "new_tool"},
                    "action": "sample",
                    "reason": "New rule for testing",
                }
            ]
        }

        with open(temp_rules_file, "w") as f:
            yaml.dump(new_rules_data, f)

        # Reload rules
        await policy_engine.reload_rules()

        # Verify new rules are loaded
        assert len(policy_engine.rules) == 1
        assert policy_engine.rules[0].id == "new_rule"

        # Verify health monitor was notified
        mock_health_monitor.record_config_reload_attempt.assert_called_once()
        mock_health_monitor.record_config_reload_success.assert_called_once()

    @pytest.mark.unit
    async def test_reload_rules_invalid_yaml(
        self, policy_engine, temp_rules_file, mock_health_monitor
    ):
        """Test reload with invalid YAML restores backup."""
        original_count = len(policy_engine.rules)
        original_rule_id = policy_engine.rules[0].id

        # Write invalid YAML
        with open(temp_rules_file, "w") as f:
            f.write("invalid: yaml: content: [")

        # Reload should fail and restore backup
        with pytest.raises(SuperegoError) as exc_info:
            await policy_engine.reload_rules()

        assert exc_info.value.code == ErrorCode.INVALID_CONFIGURATION
        assert "Failed to reload configuration" in exc_info.value.message

        # Verify backup was restored
        assert len(policy_engine.rules) == original_count
        assert policy_engine.rules[0].id == original_rule_id

        # Verify health monitor was notified
        mock_health_monitor.record_config_reload_attempt.assert_called_once()
        mock_health_monitor.record_config_reload_failure.assert_called_once()

    @pytest.mark.unit
    async def test_reload_rules_invalid_rule_structure(
        self, policy_engine, temp_rules_file, mock_health_monitor
    ):
        """Test reload with invalid rule structure restores backup."""
        original_count = len(policy_engine.rules)

        # Write YAML with invalid rule structure
        invalid_rules = {
            "rules": [
                {
                    "id": "invalid_rule",
                    # Missing required fields
                }
            ]
        }

        with open(temp_rules_file, "w") as f:
            yaml.dump(invalid_rules, f)

        # Reload should fail and restore backup
        with pytest.raises(SuperegoError):
            await policy_engine.reload_rules()

        # Verify backup was restored
        assert len(policy_engine.rules) == original_count

        mock_health_monitor.record_config_reload_failure.assert_called_once()

    @pytest.mark.unit
    async def test_reload_rules_missing_file(
        self, policy_engine, temp_rules_file, mock_health_monitor
    ):
        """Test reload when file is deleted restores backup."""
        original_count = len(policy_engine.rules)

        # Delete the file
        temp_rules_file.unlink()

        # Reload should fail and restore backup
        with pytest.raises(SuperegoError):
            await policy_engine.reload_rules()

        # Verify backup was restored
        assert len(policy_engine.rules) == original_count

        mock_health_monitor.record_config_reload_failure.assert_called_once()

    @pytest.mark.unit
    async def test_concurrent_reload_and_evaluation(
        self, policy_engine, temp_rules_file
    ):
        """Test that concurrent reload and evaluation don't cause race conditions."""
        request = ToolRequest(
            tool_name="read",
            parameters={},
            cwd="/test",
            session_id="test-session",
            agent_id="test-agent",
        )

        async def continuous_evaluation():
            """Continuously evaluate requests."""
            results = []
            for _ in range(10):
                try:
                    decision = await policy_engine.evaluate(request)
                    results.append(decision.action)
                    await asyncio.sleep(0.01)
                except Exception:
                    # Ignore exceptions during concurrent access
                    pass
            return results

        async def reload_rules():
            """Reload rules after a short delay."""
            await asyncio.sleep(0.02)
            try:
                await policy_engine.reload_rules()
            except Exception:
                # Ignore reload failures during concurrent testing
                pass

        # Run evaluation and reload concurrently
        eval_task = asyncio.create_task(continuous_evaluation())
        reload_task = asyncio.create_task(reload_rules())

        results, _ = await asyncio.gather(eval_task, reload_task)

        # Should have completed without deadlock
        assert len(results) >= 5  # At least some evaluations succeeded

    @pytest.mark.unit
    def test_health_check(self, policy_engine, temp_rules_file):
        """Test health check functionality."""
        health = policy_engine.health_check()

        assert health["status"] == "healthy"
        assert health["rules_count"] == 2
        assert health["rules_file"] == str(temp_rules_file)
        assert health["file_exists"] is True
        assert health["has_backup"] is False

    @pytest.mark.unit
    def test_health_check_no_rules(self, temp_rules_file, mock_health_monitor):
        """Test health check with no rules loaded."""
        # Create empty rules file
        with open(temp_rules_file, "w") as f:
            yaml.dump({"rules": []}, f)

        engine = SecurityPolicyEngine(temp_rules_file, mock_health_monitor)
        health = engine.health_check()

        assert health["status"] == "degraded"
        assert health["rules_count"] == 0
        assert "No security rules loaded" in health["message"]

    @pytest.mark.unit
    def test_health_check_missing_file(self, mock_health_monitor):
        """Test health check when rules file doesn't exist."""
        missing_file = Path("/tmp/nonexistent_rules.yaml")

        # This should raise an error during initialization
        with pytest.raises(SuperegoError):
            SecurityPolicyEngine(missing_file, mock_health_monitor)

    @pytest.mark.unit
    async def test_reload_without_health_monitor(self, temp_rules_file):
        """Test that reload works without health monitor."""
        engine = SecurityPolicyEngine(temp_rules_file)  # No health monitor

        # Modify rules
        new_rules_data = {
            "rules": [
                {
                    "id": "no_monitor_rule",
                    "priority": 1,
                    "conditions": {"tool_name": "test"},
                    "action": "allow",
                    "reason": "Test without monitor",
                }
            ]
        }

        with open(temp_rules_file, "w") as f:
            yaml.dump(new_rules_data, f)

        # Should work without health monitor
        await engine.reload_rules()

        assert len(engine.rules) == 1
        assert engine.rules[0].id == "no_monitor_rule"

    @pytest.mark.integration
    async def test_full_hot_reload_scenario(
        self, policy_engine, temp_rules_file, mock_health_monitor
    ):
        """Test complete hot-reload scenario with evaluation."""
        # Initial evaluation
        request = ToolRequest(
            tool_name="rm",
            parameters={},
            cwd="/test",
            session_id="test-session",
            agent_id="test-agent",
        )

        decision1 = await policy_engine.evaluate(request)
        assert decision1.action == "deny"
        assert decision1.rule_id == "deny_rm"

        # Update rules to allow rm
        new_rules_data = {
            "rules": [
                {
                    "id": "allow_rm_now",
                    "priority": 1,
                    "conditions": {"tool_name": "rm"},
                    "action": "allow",
                    "reason": "Now allowed for testing",
                }
            ]
        }

        with open(temp_rules_file, "w") as f:
            yaml.dump(new_rules_data, f)

        # Reload rules
        await policy_engine.reload_rules()

        # Evaluate same request again
        decision2 = await policy_engine.evaluate(request)
        assert decision2.action == "allow"
        assert decision2.rule_id == "allow_rm_now"

        # Verify health monitor tracking
        assert mock_health_monitor.record_config_reload_attempt.call_count == 1
        assert mock_health_monitor.record_config_reload_success.call_count == 1
