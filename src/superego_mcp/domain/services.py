"""Domain services for the Superego MCP Server."""

import re
import time
from pathlib import Path

from .models import Decision, SecurityRule, ToolAction, ToolRequest
from .repositories import RuleRepository
from .security_policy import SecurityPolicyEngine


class RuleEngine:
    """Engine for evaluating security rules against tool requests."""

    def __init__(self, rule_repository: RuleRepository):
        self.rule_repository = rule_repository

    def evaluate_request(self, request: ToolRequest) -> Decision:
        """Evaluate a tool request against all active security rules.

        Args:
            request: The tool request to evaluate

        Returns:
            Decision with the determined action
        """
        start_time = time.perf_counter()
        rules = self.rule_repository.get_active_rules()

        # Sort by priority (highest first)
        rules.sort(key=lambda r: r.priority, reverse=True)

        matched_rules = []
        for rule in rules:
            if self._matches_rule(request, rule):
                matched_rules.append(rule.id)
                decision = self._apply_rule(request, rule)
                processing_time = int((time.perf_counter() - start_time) * 1000)
                decision.processing_time_ms = processing_time
                return decision

        # Default action if no rules match - allow
        processing_time = int((time.perf_counter() - start_time) * 1000)
        return Decision(
            action="allow",
            reason="No matching security rules found",
            rule_id=None,
            confidence=1.0,
            processing_time_ms=processing_time,
        )

    def _matches_rule(self, request: ToolRequest, rule: SecurityRule) -> bool:
        """Check if a request matches a security rule.

        Args:
            request: The tool request
            rule: The rule to check against

        Returns:
            True if the request matches the rule
        """
        # Check conditions defined in the rule
        for condition_key, condition_value in rule.conditions.items():
            if condition_key == "tool_name":
                if not re.search(
                    str(condition_value), request.tool_name, re.IGNORECASE
                ):
                    return False
            elif condition_key == "agent_id":
                if request.agent_id != condition_value:
                    return False
            elif condition_key == "parameter_contains":
                if not any(
                    str(condition_value).lower() in str(v).lower()
                    for v in request.parameters.values()
                ):
                    return False
            elif condition_key == "cwd_pattern":
                if not re.search(str(condition_value), request.cwd, re.IGNORECASE):
                    return False

        return True

    def _apply_rule(self, request: ToolRequest, rule: SecurityRule) -> Decision:
        """Apply a matched security rule to create a decision.

        Args:
            request: The original request
            rule: The matched rule

        Returns:
            Decision with the appropriate action
        """
        action_mapping = {
            ToolAction.ALLOW: "allow",
            ToolAction.DENY: "deny",
            ToolAction.SAMPLE: "allow",  # For now, sample actions are treated as allow
        }

        action = action_mapping.get(rule.action, "deny")
        reason = rule.reason or f"Action {rule.action.value} applied by rule {rule.id}"

        return Decision(
            action=action,
            reason=reason,
            rule_id=rule.id,
            confidence=0.95,  # High confidence for rule-based decisions
            processing_time_ms=0,  # Will be set by caller
        )


class InterceptionService:
    """High-level service for tool request interception and security evaluation."""

    def __init__(self, security_policy_engine: SecurityPolicyEngine):
        self.security_policy_engine = security_policy_engine
        # Keep backward compatibility with RuleEngine
        self.rule_engine = None

    @classmethod
    def from_rules_file(cls, rules_file: Path) -> "InterceptionService":
        """Create InterceptionService from rules file path."""
        engine = SecurityPolicyEngine(rules_file)
        return cls(engine)

    @classmethod
    def from_rule_engine(cls, rule_engine: RuleEngine) -> "InterceptionService":
        """Create InterceptionService from legacy RuleEngine for backward compatibility."""
        instance = cls.__new__(cls)
        instance.rule_engine = rule_engine
        instance.security_policy_engine = None
        return instance

    async def evaluate_request(self, request: ToolRequest) -> Decision:
        """Evaluate a tool request for security concerns.

        Args:
            request: The tool request to evaluate

        Returns:
            Security decision for the request
        """
        if self.security_policy_engine:
            return await self.security_policy_engine.evaluate(request)
        elif self.rule_engine:
            # Backward compatibility
            return self.rule_engine.evaluate_request(request)
        else:
            raise ValueError("InterceptionService not properly initialized")

    async def health_check(self) -> dict:
        """Check the health of the interception service.

        Returns:
            Health status information
        """
        if self.security_policy_engine:
            return {
                "status": "healthy",
                "rules_loaded": await self.security_policy_engine.get_rules_count(),
                "service": "InterceptionService",
                "engine": "SecurityPolicyEngine",
            }
        elif self.rule_engine:
            return {
                "status": "healthy",
                "rules_loaded": len(
                    self.rule_engine.rule_repository.get_active_rules()
                ),
                "service": "InterceptionService",
                "engine": "RuleEngine",
            }
        else:
            return {
                "status": "unhealthy",
                "error": "No policy engine initialized",
                "service": "InterceptionService",
            }
