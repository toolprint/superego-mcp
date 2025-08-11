"""Security Policy Engine for rule-based security evaluation with priority system."""

import re
import time
from pathlib import Path

import yaml

from .models import (
    Decision,
    ErrorCode,
    SecurityRule,
    SuperegoError,
    ToolAction,
    ToolRequest,
)


class SecurityPolicyEngine:
    """Rule-based security evaluation with priority matching"""

    def __init__(self, rules_file: Path):
        self.rules_file = rules_file
        self.rules: list[SecurityRule] = []
        self.load_rules()

    def load_rules(self) -> None:
        """Load and parse security rules from YAML file"""
        if not self.rules_file.exists():
            raise SuperegoError(
                ErrorCode.INVALID_CONFIGURATION,
                f"Rules file not found: {self.rules_file}",
                "Security rules configuration is missing",
            )

        try:
            with open(self.rules_file) as f:
                rules_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise SuperegoError(
                ErrorCode.INVALID_CONFIGURATION,
                f"Failed to parse YAML rules file: {e}",
                "Security rules configuration is invalid",
            )

        self.rules = []
        for rule_data in rules_data.get("rules", []):
            try:
                rule = SecurityRule(**rule_data)
                self.rules.append(rule)
            except Exception as e:
                raise SuperegoError(
                    ErrorCode.INVALID_CONFIGURATION,
                    f"Invalid rule configuration: {e}",
                    "One or more security rules are invalid",
                )

        # Sort by priority (lower number = higher priority)
        self.rules.sort(key=lambda r: r.priority)

    async def evaluate(self, request: ToolRequest) -> Decision:
        """Evaluate tool request against security rules"""
        start_time = time.perf_counter()

        try:
            # Find first matching rule (highest priority)
            matching_rule = self._find_matching_rule(request)

            if not matching_rule:
                # Default allow if no rules match
                processing_time_ms = max(
                    1, int((time.perf_counter() - start_time) * 1000)
                )
                return Decision(
                    action="allow",
                    reason="No security rules matched",
                    confidence=0.5,
                    processing_time_ms=processing_time_ms,
                )

            if matching_rule.action == ToolAction.SAMPLE:
                # Delegate to AI sampling engine
                return await self._handle_sampling(request, matching_rule, start_time)

            processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            return Decision(
                action=matching_rule.action.value,
                reason=matching_rule.reason or f"Rule {matching_rule.id} matched",
                rule_id=matching_rule.id,
                confidence=1.0,  # Rule-based decisions are certain
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            return self._handle_error(e, request, start_time)

    def _find_matching_rule(self, request: ToolRequest) -> SecurityRule | None:
        """Find highest priority rule matching the request"""
        for rule in self.rules:  # Already sorted by priority
            if self._rule_matches(rule, request):
                return rule
        return None

    def _rule_matches(self, rule: SecurityRule, request: ToolRequest) -> bool:
        """Check if rule conditions match the request"""
        conditions = rule.conditions

        # Tool name matching
        if "tool_name" in conditions:
            tool_pattern = conditions["tool_name"]
            if isinstance(tool_pattern, str):
                if tool_pattern != request.tool_name:
                    return False
            elif isinstance(tool_pattern, list):
                if request.tool_name not in tool_pattern:
                    return False

        # Parameter matching
        if "parameters" in conditions:
            param_conditions = conditions["parameters"]
            for key, expected in param_conditions.items():
                if key not in request.parameters:
                    return False
                if request.parameters[key] != expected:
                    return False

        # Path-based matching
        if "cwd_pattern" in conditions:
            pattern = conditions["cwd_pattern"]
            if not re.match(pattern, request.cwd):
                return False

        return True

    async def _handle_sampling(
        self, request: ToolRequest, rule: SecurityRule, start_time: float
    ) -> Decision:
        """Handle sampling action (placeholder for Day 1)"""
        # For Day 1 prototype, return allow with note about sampling
        processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        return Decision(
            action="allow",
            reason=f"Rule {rule.id} requires sampling - allowing for Day 1 prototype",
            rule_id=rule.id,
            confidence=0.7,
            processing_time_ms=processing_time_ms,
        )

    def _handle_error(
        self, error: Exception, request: ToolRequest, start_time: float
    ) -> Decision:
        """Handle rule evaluation errors"""
        processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        return Decision(
            action="deny",
            reason="Rule evaluation failed - failing closed for security",
            confidence=0.8,
            processing_time_ms=processing_time_ms,
        )

    def get_rules_count(self) -> int:
        """Get the number of loaded rules"""
        return len(self.rules)

    def get_rule_by_id(self, rule_id: str) -> SecurityRule | None:
        """Get a specific rule by ID"""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def reload_rules(self) -> None:
        """Reload rules from the file"""
        self.load_rules()
