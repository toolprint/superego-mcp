"""Tests for the SecurityPolicyEngine implementation."""

import tempfile
import time
from pathlib import Path

import pytest
import yaml

from superego_mcp.domain.models import (
    ErrorCode,
    SuperegoError,
    ToolAction,
    ToolRequest,
)
from superego_mcp.domain.security_policy import SecurityPolicyEngine


class TestSecurityPolicyEngine:
    """Test suite for SecurityPolicyEngine functionality."""

    def create_test_rules_file(self, rules_data: dict) -> Path:
        """Create a temporary rules file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.safe_dump(rules_data, temp_file)
        temp_file.close()
        return Path(temp_file.name)

    def test_load_rules_success(self):
        """Test successful rule loading from YAML file."""
        rules_data = {
            "rules": [
                {
                    "id": "test_rule",
                    "priority": 1,
                    "conditions": {"tool_name": ["rm", "sudo"]},
                    "action": "deny",
                    "reason": "Test rule",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)
            assert len(engine.rules) == 1
            assert engine.rules[0].id == "test_rule"
            assert engine.rules[0].priority == 1
            assert engine.rules[0].action == ToolAction.DENY
        finally:
            rules_file.unlink()

    def test_load_rules_missing_file(self):
        """Test error handling when rules file is missing."""
        missing_file = Path("/nonexistent/rules.yaml")

        with pytest.raises(SuperegoError) as exc_info:
            SecurityPolicyEngine(missing_file)

        assert exc_info.value.code == ErrorCode.INVALID_CONFIGURATION
        assert "Rules file not found" in exc_info.value.message

    def test_load_rules_invalid_yaml(self):
        """Test error handling when YAML is malformed."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        temp_file.write("invalid: yaml: content: [")
        temp_file.close()
        rules_file = Path(temp_file.name)

        try:
            with pytest.raises(SuperegoError) as exc_info:
                SecurityPolicyEngine(rules_file)

            assert exc_info.value.code == ErrorCode.INVALID_CONFIGURATION
            assert "Failed to parse YAML" in exc_info.value.message
        finally:
            rules_file.unlink()

    def test_rule_priority_sorting(self):
        """Test that rules are sorted by priority (lower number = higher priority)."""
        rules_data = {
            "rules": [
                {
                    "id": "rule_low",
                    "priority": 99,
                    "conditions": {"tool_name": "test"},
                    "action": "allow",
                },
                {
                    "id": "rule_high",
                    "priority": 1,
                    "conditions": {"tool_name": "test"},
                    "action": "deny",
                },
                {
                    "id": "rule_mid",
                    "priority": 10,
                    "conditions": {"tool_name": "test"},
                    "action": "sample",
                },
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            # Should be sorted by priority: 1, 10, 99
            assert engine.rules[0].id == "rule_high"
            assert engine.rules[1].id == "rule_mid"
            assert engine.rules[2].id == "rule_low"
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_evaluate_tool_name_match(self):
        """Test rule matching based on tool name."""
        rules_data = {
            "rules": [
                {
                    "id": "deny_dangerous",
                    "priority": 1,
                    "conditions": {"tool_name": ["rm", "sudo"]},
                    "action": "deny",
                    "reason": "Dangerous command blocked",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            # Test matching tool name
            request = ToolRequest(
                tool_name="rm",
                parameters={"file": "test.txt"},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await engine.evaluate(request)

            assert decision.action == "deny"
            assert decision.rule_id == "deny_dangerous"
            assert decision.reason == "Dangerous command blocked"
            assert decision.confidence == 1.0
            assert decision.processing_time_ms > 0
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_evaluate_tool_name_list_match(self):
        """Test rule matching with tool name list."""
        rules_data = {
            "rules": [
                {
                    "id": "deny_list",
                    "priority": 1,
                    "conditions": {"tool_name": ["rm", "sudo", "chmod"]},
                    "action": "deny",
                    "reason": "Command in deny list",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            # Test each tool in the list
            for tool in ["rm", "sudo", "chmod"]:
                request = ToolRequest(
                    tool_name=tool,
                    parameters={},
                    session_id="session1",
                    agent_id="agent1",
                    cwd="/home/user",
                )

                decision = await engine.evaluate(request)
                assert decision.action == "deny"
                assert decision.rule_id == "deny_list"
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_evaluate_parameter_matching(self):
        """Test rule matching based on parameters."""
        rules_data = {
            "rules": [
                {
                    "id": "param_match",
                    "priority": 1,
                    "conditions": {
                        "tool_name": "edit",
                        "parameters": {"file": "/etc/passwd"},
                    },
                    "action": "deny",
                    "reason": "Sensitive file access blocked",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            # Test matching parameters
            request = ToolRequest(
                tool_name="edit",
                parameters={"file": "/etc/passwd"},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await engine.evaluate(request)

            assert decision.action == "deny"
            assert decision.rule_id == "param_match"
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_evaluate_cwd_pattern_matching(self):
        """Test rule matching based on current working directory pattern."""
        rules_data = {
            "rules": [
                {
                    "id": "cwd_pattern",
                    "priority": 1,
                    "conditions": {"cwd_pattern": r"/etc/.*"},
                    "action": "deny",
                    "reason": "System directory access blocked",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            # Test matching CWD pattern
            request = ToolRequest(
                tool_name="ls",
                parameters={},
                session_id="session1",
                agent_id="agent1",
                cwd="/etc/systemd",
            )

            decision = await engine.evaluate(request)

            assert decision.action == "deny"
            assert decision.rule_id == "cwd_pattern"
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_evaluate_no_match_default_allow(self):
        """Test default allow behavior when no rules match."""
        rules_data = {
            "rules": [
                {
                    "id": "specific_rule",
                    "priority": 1,
                    "conditions": {"tool_name": "rm"},
                    "action": "deny",
                    "reason": "RM blocked",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            # Test non-matching request
            request = ToolRequest(
                tool_name="ls",
                parameters={},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await engine.evaluate(request)

            assert decision.action == "allow"
            assert decision.rule_id is None
            assert "No security rules matched" in decision.reason
            assert decision.confidence == 0.5
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_evaluate_sampling_action(self):
        """Test handling of sampling action."""
        rules_data = {
            "rules": [
                {
                    "id": "sample_rule",
                    "priority": 1,
                    "conditions": {"tool_name": "edit"},
                    "action": "sample",
                    "reason": "File edit requires sampling",
                    "sampling_guidance": "Check if edit is safe",
                }
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            request = ToolRequest(
                tool_name="edit",
                parameters={"file": "test.txt"},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await engine.evaluate(request)

            # When no AI service is configured, sampling should deny for security
            assert decision.action == "deny"
            assert decision.rule_id == "sample_rule"
            assert "AI service not configured" in decision.reason
            assert decision.confidence == 0.6
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_evaluate_priority_ordering(self):
        """Test that rules are evaluated in priority order."""
        rules_data = {
            "rules": [
                {
                    "id": "low_priority",
                    "priority": 10,
                    "conditions": {"tool_name": "test"},
                    "action": "allow",
                    "reason": "Low priority allow",
                },
                {
                    "id": "high_priority",
                    "priority": 1,
                    "conditions": {"tool_name": "test"},
                    "action": "deny",
                    "reason": "High priority deny",
                },
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            request = ToolRequest(
                tool_name="test",
                parameters={},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await engine.evaluate(request)

            # Should match high priority rule first
            assert decision.action == "deny"
            assert decision.rule_id == "high_priority"
            assert decision.reason == "High priority deny"
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_performance_benchmark(self):
        """Test that rule evaluation meets performance target (< 10ms)."""
        # Create rules that will exercise the matching logic
        rules_data = {
            "rules": [
                {
                    "id": f"rule_{i}",
                    "priority": i,
                    "conditions": {"tool_name": f"tool_{i}"},
                    "action": "allow",
                    "reason": f"Rule {i}",
                }
                for i in range(100)  # 100 rules to test performance
            ]
        }

        # Add a matching rule at the end
        rules_data["rules"].append(
            {
                "id": "matching_rule",
                "priority": 101,
                "conditions": {"tool_name": "test_tool"},
                "action": "deny",
                "reason": "Found matching rule",
            }
        )

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)

            request = ToolRequest(
                tool_name="test_tool",
                parameters={},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            # Measure performance over multiple runs
            times = []
            for _ in range(10):
                start = time.perf_counter()
                decision = await engine.evaluate(request)
                end = time.perf_counter()
                times.append((end - start) * 1000)  # Convert to milliseconds

                assert decision.action == "deny"
                assert decision.rule_id == "matching_rule"

            # Check that 90% of requests are under 10ms
            times.sort()
            p90_time = times[int(0.9 * len(times))]

            print(f"P90 evaluation time: {p90_time:.2f}ms")
            assert p90_time < 10, (
                f"P90 evaluation time {p90_time:.2f}ms exceeds 10ms target"
            )

            # Also check the processing_time_ms in the decision
            assert decision.processing_time_ms < 10
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_get_rules_count(self):
        """Test getting the number of loaded rules."""
        rules_data = {
            "rules": [
                {
                    "id": "rule1",
                    "priority": 1,
                    "conditions": {"tool_name": "test"},
                    "action": "allow",
                },
                {
                    "id": "rule2",
                    "priority": 2,
                    "conditions": {"tool_name": "test"},
                    "action": "deny",
                },
            ]
        }

        rules_file = self.create_test_rules_file(rules_data)

        try:
            engine = SecurityPolicyEngine(rules_file)
            assert await engine.get_rules_count() == 2
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_get_rule_by_id(self):
        """Test getting a specific rule by ID."""
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
            engine = SecurityPolicyEngine(rules_file)

            rule = await engine.get_rule_by_id("test_rule")
            assert rule is not None
            assert rule.id == "test_rule"
            assert rule.action == ToolAction.ALLOW

            # Test non-existent rule
            missing_rule = await engine.get_rule_by_id("nonexistent")
            assert missing_rule is None
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_reload_rules(self):
        """Test reloading rules from file."""
        # Initial rules
        initial_rules = {
            "rules": [
                {
                    "id": "rule1",
                    "priority": 1,
                    "conditions": {"tool_name": "test"},
                    "action": "allow",
                }
            ]
        }

        rules_file = self.create_test_rules_file(initial_rules)

        try:
            engine = SecurityPolicyEngine(rules_file)
            assert await engine.get_rules_count() == 1

            # Update rules file
            updated_rules = {
                "rules": [
                    {
                        "id": "rule1",
                        "priority": 1,
                        "conditions": {"tool_name": "test"},
                        "action": "allow",
                    },
                    {
                        "id": "rule2",
                        "priority": 2,
                        "conditions": {"tool_name": "test"},
                        "action": "deny",
                    },
                ]
            }

            with open(rules_file, "w") as f:
                yaml.safe_dump(updated_rules, f)

            # Reload and verify
            await engine.reload_rules()
            assert await engine.get_rules_count() == 2
        finally:
            rules_file.unlink()

    @pytest.mark.asyncio
    async def test_error_handling_evaluation_failure(self):
        """Test error handling during rule evaluation."""
        # Create a SecurityPolicyEngine with mocked rule that will cause errors
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
            engine = SecurityPolicyEngine(rules_file)

            # Mock the _rule_matches method to raise an exception
            original_matches = engine._rule_matches

            def failing_matches(rule, request):
                raise ValueError("Simulated evaluation error")

            engine._rule_matches = failing_matches

            request = ToolRequest(
                tool_name="test",
                parameters={},
                session_id="session1",
                agent_id="agent1",
                cwd="/home/user",
            )

            decision = await engine.evaluate(request)

            # Should fail closed with deny
            assert decision.action == "deny"
            assert "Rule evaluation failed" in decision.reason
            assert decision.confidence == 0.8

            # Restore original method
            engine._rule_matches = original_matches
        finally:
            rules_file.unlink()

    def teardown_method(self):
        """Clean up after each test."""
        # Clean up any remaining temporary files
        import glob
        import tempfile

        temp_dir = tempfile.gettempdir()
        temp_files = glob.glob(f"{temp_dir}/tmp*.yaml")
        for temp_file in temp_files:
            try:
                Path(temp_file).unlink()
            except FileNotFoundError:
                pass
