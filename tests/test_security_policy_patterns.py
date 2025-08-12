"""Integration tests for SecurityPolicyEngine with advanced pattern matching."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.domain.models import ToolRequest, ToolAction


class TestSecurityPolicyPatterns:
    """Integration tests for advanced pattern matching in SecurityPolicyEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.rules_file = Path(self.temp_dir) / "test_rules.yaml"

        # Create test rules with advanced patterns
        self.test_rules = {
            "rules": [
                # Regex pattern rule
                {
                    "id": "block_destructive",
                    "priority": 1,
                    "conditions": {
                        "tool_name": {
                            "type": "regex",
                            "pattern": r"^(rm|delete|destroy).*",
                        }
                    },
                    "action": "deny",
                    "reason": "Destructive command blocked",
                },
                # Glob pattern rule
                {
                    "id": "protect_system",
                    "priority": 2,
                    "conditions": {
                        "parameters": {"path": {"type": "glob", "pattern": "/etc/**"}}
                    },
                    "action": "deny",
                    "reason": "System directory protected",
                },
                # JSONPath pattern rule
                {
                    "id": "large_files",
                    "priority": 3,
                    "conditions": {
                        "parameters": {
                            "size": {
                                "type": "jsonpath",
                                "pattern": "$.size",
                                "threshold": 1000000,
                                "comparison": "gt",
                            }
                        }
                    },
                    "action": "sample",
                    "reason": "Large file operation",
                },
                # Composite AND condition
                {
                    "id": "sensitive_operations",
                    "priority": 4,
                    "conditions": {
                        "AND": [
                            {
                                "tool_name": {
                                    "type": "regex",
                                    "pattern": r"^(write|edit)",
                                }
                            },
                            {"cwd": {"type": "glob", "pattern": "/home/**/.ssh*"}},
                        ]
                    },
                    "action": "deny",
                    "reason": "Sensitive directory operation",
                },
                # Composite OR condition
                {
                    "id": "config_files",
                    "priority": 5,
                    "conditions": {
                        "OR": [
                            {
                                "parameters": {
                                    "path": {"type": "glob", "pattern": "**/*.conf"}
                                }
                            },
                            {
                                "parameters": {
                                    "path": {"type": "glob", "pattern": "**/*.config"}
                                }
                            },
                        ]
                    },
                    "action": "sample",
                    "reason": "Configuration file access",
                },
                # Time-based rule (mocked in tests)
                {
                    "id": "business_hours",
                    "priority": 6,
                    "conditions": {
                        "AND": [
                            {"tool_name": ["deploy", "restart"]},
                            {
                                "time_range": {
                                    "start": "09:00",
                                    "end": "17:00",
                                    "timezone": "UTC",
                                }
                            },
                        ]
                    },
                    "action": "sample",
                    "reason": "Business hours deployment",
                },
                # Disabled rule
                {
                    "id": "disabled_rule",
                    "priority": 7,
                    "enabled": False,
                    "conditions": {"tool_name": ["should_not_match"]},
                    "action": "deny",
                    "reason": "This rule is disabled",
                },
                # Backward compatibility rule
                {
                    "id": "legacy_rule",
                    "priority": 8,
                    "conditions": {
                        "tool_name": ["legacy_command"],
                        "parameters": {"flag": "value"},
                    },
                    "action": "allow",
                    "reason": "Legacy pattern matching",
                },
                # Allow safe commands
                {
                    "id": "allow_safe",
                    "priority": 99,
                    "conditions": {
                        "tool_name": {"type": "regex", "pattern": r"^(read|ls|cat)$"}
                    },
                    "action": "allow",
                    "reason": "Safe command",
                },
            ]
        }

        # Write rules to file
        with open(self.rules_file, "w") as f:
            yaml.dump(self.test_rules, f)

        # Initialize engine
        self.engine = SecurityPolicyEngine(self.rules_file)

    async def test_regex_pattern_matching(self):
        """Test regex pattern matching in rules."""
        # Should match destructive command
        request = ToolRequest(
            tool_name="rm_file",
            parameters={},
            session_id="test",
            agent_id="test",
            cwd="/tmp",
        )

        decision = await self.engine.evaluate(request)
        assert decision.action == "deny"
        assert decision.rule_id == "block_destructive"
        assert "Destructive command blocked" in decision.reason

        # Should not match safe command
        request.tool_name = "create_file"
        decision = await self.engine.evaluate(request)
        assert decision.action != "deny" or decision.rule_id != "block_destructive"

    async def test_glob_pattern_matching(self):
        """Test glob pattern matching in rules."""
        # Should match system directory access
        request = ToolRequest(
            tool_name="write",
            parameters={"path": "/etc/config/file.conf"},
            session_id="test",
            agent_id="test",
            cwd="/tmp",
        )

        decision = await self.engine.evaluate(request)
        assert decision.action == "deny"
        assert decision.rule_id == "protect_system"
        assert "System directory protected" in decision.reason

        # Should not match user directory
        request.parameters["path"] = "/home/user/file.conf"
        decision = await self.engine.evaluate(request)
        assert decision.action != "deny" or decision.rule_id != "protect_system"

    async def test_jsonpath_pattern_matching(self):
        """Test JSONPath pattern matching in rules."""
        # Mock AI service for sampling
        mock_ai_manager = MagicMock()
        mock_ai_decision = MagicMock()
        mock_ai_decision.decision = "deny"
        mock_ai_decision.reasoning = "File too large"
        mock_ai_decision.confidence = 0.9
        mock_ai_decision.provider.value = "test_provider"
        mock_ai_decision.model = "test_model"
        mock_ai_decision.risk_factors = ["large_file"]

        mock_ai_manager.evaluate_with_ai = AsyncMock(return_value=mock_ai_decision)

        mock_prompt_builder = MagicMock()
        mock_prompt_builder.build_evaluation_prompt = MagicMock(
            return_value="test prompt"
        )

        self.engine.ai_service_manager = mock_ai_manager
        self.engine.prompt_builder = mock_prompt_builder

        # Should match large file operation
        request = ToolRequest(
            tool_name="upload",
            parameters={"size": 2000000, "file": "large.bin"},
            session_id="test",
            agent_id="test",
            cwd="/tmp",
        )

        decision = await self.engine.evaluate(request)
        assert decision.rule_id == "large_files"
        assert decision.ai_provider == "test_provider"

        # Should not match small file
        request.parameters["size"] = 500
        decision = await self.engine.evaluate(request)
        assert decision.rule_id != "large_files"

    async def test_composite_and_conditions(self):
        """Test composite AND condition matching."""
        # Should match sensitive operation (write in .ssh directory)
        request = ToolRequest(
            tool_name="write_key",
            parameters={"path": "/home/user/.ssh/id_rsa"},
            session_id="test",
            agent_id="test",
            cwd="/home/user/.ssh",
        )

        decision = await self.engine.evaluate(request)
        assert decision.action == "deny"
        assert decision.rule_id == "sensitive_operations"
        assert "Sensitive directory operation" in decision.reason

        # Should not match write outside .ssh
        request.cwd = "/home/user"
        decision = await self.engine.evaluate(request)
        assert decision.rule_id != "sensitive_operations"

        # Should not match read in .ssh
        request.tool_name = "read_key"
        request.cwd = "/home/user/.ssh"
        decision = await self.engine.evaluate(request)
        assert decision.rule_id != "sensitive_operations"

    async def test_composite_or_conditions(self):
        """Test composite OR condition matching."""
        # Mock AI service for sampling
        mock_ai_manager = MagicMock()
        mock_ai_decision = MagicMock()
        mock_ai_decision.decision = "allow"
        mock_ai_decision.reasoning = "Config file access approved"
        mock_ai_decision.confidence = 0.8
        mock_ai_decision.provider.value = "test_provider"
        mock_ai_decision.model = "test_model"
        mock_ai_decision.risk_factors = []

        mock_ai_manager.evaluate_with_ai = AsyncMock(return_value=mock_ai_decision)

        mock_prompt_builder = MagicMock()
        mock_prompt_builder.build_evaluation_prompt = MagicMock(
            return_value="test prompt"
        )

        self.engine.ai_service_manager = mock_ai_manager
        self.engine.prompt_builder = mock_prompt_builder

        # Should match .conf file
        request = ToolRequest(
            tool_name="read",
            parameters={"path": "/app/config/server.conf"},
            session_id="test",
            agent_id="test",
            cwd="/app",
        )

        decision = await self.engine.evaluate(request)
        assert decision.rule_id == "config_files"

        # Should match .config file
        request.parameters["path"] = "/app/settings/app.config"
        decision = await self.engine.evaluate(request)
        assert decision.rule_id == "config_files"

        # Should not match other files
        request.parameters["path"] = "/app/data/file.txt"
        decision = await self.engine.evaluate(request)
        assert decision.rule_id != "config_files"

    async def test_time_based_conditions(self):
        """Test time-based condition matching."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        # Mock AI service for sampling
        mock_ai_manager = MagicMock()
        mock_ai_decision = MagicMock()
        mock_ai_decision.decision = "allow"
        mock_ai_decision.reasoning = "Deployment approved"
        mock_ai_decision.confidence = 0.9
        mock_ai_decision.provider.value = "test_provider"
        mock_ai_decision.model = "test_model"
        mock_ai_decision.risk_factors = []

        mock_ai_manager.evaluate_with_ai = AsyncMock(return_value=mock_ai_decision)

        mock_prompt_builder = MagicMock()
        mock_prompt_builder.build_evaluation_prompt = MagicMock(
            return_value="test prompt"
        )

        self.engine.ai_service_manager = mock_ai_manager
        self.engine.prompt_builder = mock_prompt_builder

        # Mock time within business hours (10:30 UTC)
        mock_now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        with patch("superego_mcp.domain.pattern_engine.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = datetime.strptime

            request = ToolRequest(
                tool_name="deploy",
                parameters={"service": "web-app"},
                session_id="test",
                agent_id="test",
                cwd="/app",
            )

            decision = await self.engine.evaluate(request)
            assert decision.rule_id == "business_hours"

            # Mock time outside business hours (20:30 UTC)
            mock_now = datetime(2024, 1, 15, 20, 30, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            decision = await self.engine.evaluate(request)
            assert decision.rule_id != "business_hours"

    async def test_disabled_rule_ignored(self):
        """Test that disabled rules are ignored."""
        request = ToolRequest(
            tool_name="should_not_match",
            parameters={},
            session_id="test",
            agent_id="test",
            cwd="/tmp",
        )

        decision = await self.engine.evaluate(request)
        assert decision.rule_id != "disabled_rule"
        # Should fall through to default allow or other rules

    async def test_backward_compatibility(self):
        """Test backward compatibility with legacy rule format."""
        request = ToolRequest(
            tool_name="legacy_command",
            parameters={"flag": "value"},
            session_id="test",
            agent_id="test",
            cwd="/tmp",
        )

        decision = await self.engine.evaluate(request)
        assert decision.action == "allow"
        assert decision.rule_id == "legacy_rule"
        assert "Legacy pattern matching" in decision.reason

        # Should not match with different parameters
        request.parameters["flag"] = "other_value"
        decision = await self.engine.evaluate(request)
        assert decision.rule_id != "legacy_rule"

    async def test_pattern_validation_on_load(self):
        """Test that invalid patterns are caught during rule loading."""
        # Create rules with invalid patterns
        invalid_rules = {
            "rules": [
                {
                    "id": "invalid_regex",
                    "priority": 1,
                    "conditions": {
                        "tool_name": {
                            "type": "regex",
                            "pattern": "[",  # Invalid regex
                        }
                    },
                    "action": "deny",
                    "reason": "Invalid pattern",
                }
            ]
        }

        invalid_rules_file = Path(self.temp_dir) / "invalid_rules.yaml"
        with open(invalid_rules_file, "w") as f:
            yaml.dump(invalid_rules, f)

        # Should raise error on loading
        with pytest.raises(Exception):
            SecurityPolicyEngine(invalid_rules_file)

    async def test_rule_priority_ordering(self):
        """Test that rules are evaluated in priority order."""
        # Create request that could match multiple rules
        request = ToolRequest(
            tool_name="rm_system_file",
            parameters={"path": "/etc/config.conf"},
            session_id="test",
            agent_id="test",
            cwd="/etc",
        )

        decision = await self.engine.evaluate(request)
        # Should match the highest priority rule (lowest priority number)
        assert decision.rule_id == "block_destructive"  # priority 1
        assert decision.action == "deny"

    async def test_health_check_pattern_stats(self):
        """Test that health check includes pattern engine statistics."""
        # Use some patterns to populate cache
        await self.engine.evaluate(
            ToolRequest(
                tool_name="rm_test",
                parameters={},
                session_id="test",
                agent_id="test",
                cwd="/tmp",
            )
        )

        health = self.engine.health_check()

        assert "pattern_engine" in health
        assert "regex_cache" in health["pattern_engine"]
        assert "jsonpath_cache" in health["pattern_engine"]
        assert "enabled_rules_count" in health

        # Should show correct rule counts
        assert health["rules_count"] == len(self.test_rules["rules"])
        expected_enabled = sum(
            1 for rule in self.test_rules["rules"] if rule.get("enabled", True)
        )
        assert health["enabled_rules_count"] == expected_enabled

    async def test_no_matching_rules_default_allow(self):
        """Test default allow when no rules match."""
        request = ToolRequest(
            tool_name="unmatched_command",
            parameters={"some": "param"},
            session_id="test",
            agent_id="test",
            cwd="/unmatched/path",
        )

        decision = await self.engine.evaluate(request)
        assert decision.action == "allow"
        assert decision.rule_id is None
        assert "No security rules matched" in decision.reason
        assert decision.confidence == 0.5

    async def test_pattern_matching_error_handling(self):
        """Test error handling in pattern matching."""
        # Create a request that might cause pattern matching errors
        request = ToolRequest(
            tool_name="test_tool",
            parameters={"complex": {"nested": {"data": "value"}}},
            session_id="test",
            agent_id="test",
            cwd="/tmp",
        )

        # Mock pattern engine to raise an exception
        original_evaluate = self.engine.pattern_engine._evaluate_condition

        def failing_evaluate(*args, **kwargs):
            raise Exception("Pattern matching failed")

        self.engine.pattern_engine._evaluate_condition = failing_evaluate

        try:
            decision = await self.engine.evaluate(request)
            # Should handle the error gracefully and not match the failing rule
            # The rule evaluation should continue to other rules or default allow
            assert decision is not None
        finally:
            # Restore original method
            self.engine.pattern_engine._evaluate_condition = original_evaluate
