"""Security Policy Engine for rule-based security evaluation with priority system."""

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Any

import structlog
import yaml

from .models import (
    Decision,
    ErrorCode,
    SecurityRule,
    SuperegoError,
    ToolAction,
    ToolRequest,
)
from .pattern_engine import PatternEngine


class SecurityPolicyEngine:
    """Rule-based security evaluation with priority matching with hot-reload support"""

    def __init__(  # type: ignore[no-untyped-def]
        self,
        rules_file: Path,
        health_monitor=None,
        ai_service_manager=None,
        prompt_builder=None,
        inference_manager=None,
    ):
        self.rules_file = rules_file
        self.rules: list[SecurityRule] = []
        self._rules_lock = asyncio.Lock()  # Thread-safe access to rules
        self._backup_rules: list[SecurityRule] | None = None
        self.logger = structlog.get_logger(__name__)
        self.health_monitor = health_monitor
        self.ai_service_manager = ai_service_manager
        self.prompt_builder = prompt_builder
        self.inference_manager = inference_manager  # New inference system
        self.pattern_engine = PatternEngine()
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
            ) from e

        self.rules = []
        for rule_data in rules_data.get("rules", []):
            try:
                rule = SecurityRule(**rule_data)

                # Validate patterns in rule conditions
                self._validate_rule_patterns(rule)

                self.rules.append(rule)
            except Exception as e:
                raise SuperegoError(
                    ErrorCode.INVALID_CONFIGURATION,
                    f"Invalid rule configuration: {e}",
                    "One or more security rules are invalid",
                ) from e

        # Sort by priority (lower number = higher priority)
        self.rules.sort(key=lambda r: r.priority)

    def _validate_rule_patterns(self, rule: SecurityRule) -> None:
        """Validate patterns in rule conditions during loading."""
        conditions = rule.conditions

        def validate_pattern_recursive(obj: Any, path: str = "") -> None:
            """Recursively validate patterns in nested structures."""
            if isinstance(obj, dict):
                # Check for pattern configuration objects
                if "type" in obj and "pattern" in obj:
                    if not self.pattern_engine.validate_pattern(obj):
                        raise ValueError(f"Invalid pattern at {path}: {obj}")
                else:
                    # Recursively check nested dictionaries
                    for key, value in obj.items():
                        validate_pattern_recursive(
                            value, f"{path}.{key}" if path else key
                        )
            elif isinstance(obj, list):
                # Check patterns in lists
                for i, item in enumerate(obj):
                    validate_pattern_recursive(
                        item, f"{path}[{i}]" if path else f"[{i}]"
                    )

        # Validate all patterns in the rule conditions
        validate_pattern_recursive(conditions, f"rule.{rule.id}.conditions")

    async def evaluate(self, request: ToolRequest) -> Decision:
        """Evaluate tool request against security rules with thread-safe access"""
        start_time = time.perf_counter()

        try:
            # Thread-safe rule access during evaluation
            async with self._rules_lock:
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
                    return await self._handle_sampling(
                        request, matching_rule, start_time
                    )

                processing_time_ms = max(
                    1, int((time.perf_counter() - start_time) * 1000)
                )
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
            # Skip disabled rules
            if not rule.enabled:
                continue

            if self._rule_matches(rule, request):
                return rule
        return None

    def _rule_matches(self, rule: SecurityRule, request: ToolRequest) -> bool:
        """Check if rule conditions match the request using advanced pattern engine"""
        try:
            # Handle composite conditions (AND/OR logic)
            if "AND" in rule.conditions or "OR" in rule.conditions:
                return self.pattern_engine.match_composite(rule.conditions, request)

            # Handle individual conditions using pattern engine
            return self.pattern_engine._evaluate_condition(rule.conditions, request)

        except Exception as e:
            self.logger.warning(
                "Rule matching failed, skipping rule",
                rule_id=rule.id,
                error=str(e),
                tool_name=request.tool_name,
            )
            return False

    async def _handle_sampling(
        self, request: ToolRequest, rule: SecurityRule, start_time: float
    ) -> Decision:
        """Handle sampling action with AI evaluation using new inference system"""
        # Check if new inference system is available
        if self.inference_manager:
            return await self._handle_sampling_with_inference_manager(
                request, rule, start_time
            )

        # Fallback to legacy implementation for backward compatibility
        if self.ai_service_manager and self.prompt_builder:
            return await self._handle_sampling_legacy(request, rule, start_time)

        # No inference available - fail closed
        processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        return Decision(
            action="deny",
            reason=f"Rule {rule.id} requires inference but no providers configured",
            rule_id=rule.id,
            confidence=0.6,
            processing_time_ms=processing_time_ms,
        )

    async def _handle_sampling_with_inference_manager(
        self, request: ToolRequest, rule: SecurityRule, start_time: float
    ) -> Decision:
        """Handle sampling using the new inference system"""
        try:
            # Build secure prompt
            prompt = self.prompt_builder.build_evaluation_prompt(request, rule)

            # Generate cache key
            cache_key = self._generate_cache_key(request, rule)

            # Get inference decision using the new system
            inference_decision = await self.inference_manager.evaluate(
                request=request, rule=rule, prompt=prompt, cache_key=cache_key
            )

            # Convert to domain Decision
            processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))

            return Decision(
                action=inference_decision.decision,
                reason=inference_decision.reasoning,
                rule_id=rule.id,
                confidence=inference_decision.confidence,
                processing_time_ms=processing_time_ms,
                ai_provider=inference_decision.provider,
                ai_model=inference_decision.model,
                risk_factors=inference_decision.risk_factors,
            )

        except Exception as e:
            self.logger.error(
                "Inference evaluation failed",
                error=str(e),
                rule_id=rule.id,
                tool=request.tool_name,
            )

            # Fail closed
            processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            return Decision(
                action="deny",
                reason=f"Inference evaluation failed for rule {rule.id} - denying for security",
                rule_id=rule.id,
                confidence=0.5,
                processing_time_ms=processing_time_ms,
            )

    async def _handle_sampling_legacy(
        self, request: ToolRequest, rule: SecurityRule, start_time: float
    ) -> Decision:
        """Handle sampling action with legacy AI evaluation (backward compatibility)"""
        try:
            # Build secure prompt
            prompt = self.prompt_builder.build_evaluation_prompt(request, rule)

            # Generate cache key from request
            cache_key = self._generate_cache_key(request, rule)

            # Get AI evaluation using legacy system
            ai_decision = await self.ai_service_manager.evaluate_with_ai(
                prompt=prompt, cache_key=cache_key
            )

            # Convert AI decision to domain Decision
            processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))

            return Decision(
                action=ai_decision.decision,
                reason=ai_decision.reasoning,
                rule_id=rule.id,
                confidence=ai_decision.confidence,
                processing_time_ms=processing_time_ms,
                ai_provider=ai_decision.provider if isinstance(ai_decision.provider, str) else ai_decision.provider.value,
                ai_model=ai_decision.model,
                risk_factors=ai_decision.risk_factors,
            )

        except Exception as e:
            self.logger.error(
                "Legacy AI sampling failed",
                error=str(e),
                rule_id=rule.id,
                tool=request.tool_name,
            )

            # Fallback to deny on AI failure (fail closed)
            processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            return Decision(
                action="deny",
                reason=f"AI evaluation failed for rule {rule.id} - denying for security",
                rule_id=rule.id,
                confidence=0.5,
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

    async def get_rules_count(self) -> int:
        """Get the number of loaded rules with thread-safe access"""
        async with self._rules_lock:
            return len(self.rules)

    async def get_rule_by_id(self, rule_id: str) -> SecurityRule | None:
        """Get a specific rule by ID with thread-safe access"""
        async with self._rules_lock:
            for rule in self.rules:
                if rule.id == rule_id:
                    return rule
            return None

    async def reload_rules(self) -> None:
        """Atomically reload rules from file with backup/restore on failure"""
        # Record reload attempt in health monitor
        if self.health_monitor:
            self.health_monitor.record_config_reload_attempt()

        async with self._rules_lock:
            # Create backup of current rules
            self._backup_rules = self.rules.copy()
            original_count = len(self.rules)

            self.logger.info(
                "Starting configuration reload",
                rules_file=str(self.rules_file),
                current_rules_count=original_count,
            )

            try:
                # Load new rules
                self.load_rules()
                new_count = len(self.rules)

                # Clear backup on successful load
                self._backup_rules = None

                # Record success in health monitor
                if self.health_monitor:
                    self.health_monitor.record_config_reload_success()

                self.logger.info(
                    "Configuration reload successful",
                    old_rules_count=original_count,
                    new_rules_count=new_count,
                    rules_file=str(self.rules_file),
                )

            except Exception as e:
                # Record failure in health monitor
                if self.health_monitor:
                    self.health_monitor.record_config_reload_failure()

                # Restore from backup on failure
                if self._backup_rules is not None:
                    self.rules = self._backup_rules
                    self._backup_rules = None

                    self.logger.error(
                        "Configuration reload failed, restored backup",
                        error=str(e),
                        restored_rules_count=len(self.rules),
                        rules_file=str(self.rules_file),
                        exc_info=True,
                    )
                else:
                    self.logger.error(
                        "Configuration reload failed with no backup available",
                        error=str(e),
                        rules_file=str(self.rules_file),
                        exc_info=True,
                    )

                raise SuperegoError(
                    ErrorCode.INVALID_CONFIGURATION,
                    f"Failed to reload configuration: {e}",
                    "Configuration reload failed, using previous rules",
                ) from e

    def _generate_cache_key(self, request: ToolRequest, rule: SecurityRule) -> str:
        """Generate cache key for AI decision caching"""
        # Create deterministic cache key from request attributes
        key_parts = [
            rule.id,
            request.tool_name,
            str(sorted(request.parameters.items())),
            request.cwd,
        ]

        # Add sampling guidance if present
        if rule.sampling_guidance:
            key_parts.append(rule.sampling_guidance)

        # Hash the combined key
        key_str = "|".join(key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def health_check(self) -> dict[str, Any]:
        """Provide health status for monitoring"""
        # Note: Using synchronous access here for health checks to avoid blocking
        # This is safe because health checks are typically called from monitoring threads
        rules_count = len(self.rules)
        enabled_rules_count = sum(1 for rule in self.rules if rule.enabled)
        has_backup = self._backup_rules is not None

        health_info = {
            "status": "healthy" if rules_count > 0 else "degraded",
            "message": (
                f"Loaded {rules_count} security rules ({enabled_rules_count} enabled)"
                if rules_count > 0
                else "No security rules loaded"
            ),
            "rules_count": rules_count,
            "enabled_rules_count": enabled_rules_count,
            "rules_file": str(self.rules_file),
            "file_exists": self.rules_file.exists(),
            "has_backup": has_backup,
            "pattern_engine": self.pattern_engine.get_cache_stats(),
        }

        # Add AI service health if available (legacy)
        if self.ai_service_manager:
            health_info["ai_service"] = self.ai_service_manager.get_health_status()

        # Add inference manager health if available (new system)
        if self.inference_manager:
            try:
                import asyncio

                # Get the current event loop, or create a new one if none exists
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, but this is a sync method
                    # For health checks, we'll provide a simplified status
                    health_info["inference_system"] = {
                        "available": True,
                        "total_providers": len(self.inference_manager.providers),
                        "provider_names": list(self.inference_manager.providers.keys()),
                        "note": "Use async health_check_async() for detailed provider status",
                    }
                except RuntimeError:
                    # No event loop, safe to run async code
                    import asyncio

                    async def get_inference_health():
                        return await self.inference_manager.health_check()

                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        inference_health = loop.run_until_complete(
                            get_inference_health()
                        )
                        health_info["inference_system"] = inference_health
                        loop.close()
                    except Exception as e:
                        health_info["inference_system"] = {
                            "available": True,
                            "error": str(e),
                            "total_providers": len(self.inference_manager.providers),
                            "provider_names": list(
                                self.inference_manager.providers.keys()
                            ),
                        }
            except Exception as e:
                health_info["inference_system"] = {"available": False, "error": str(e)}

        return health_info

    async def health_check_async(self) -> dict[str, Any]:
        """Provide detailed async health status including inference providers"""
        # Get base health info
        health_info = self.health_check()

        # Add detailed inference manager health if available
        if self.inference_manager:
            try:
                inference_health = await self.inference_manager.health_check()
                health_info["inference_system"] = inference_health
            except Exception as e:
                health_info["inference_system"] = {
                    "available": False,
                    "error": str(e),
                    "total_providers": len(self.inference_manager.providers)
                    if self.inference_manager.providers
                    else 0,
                }

        return health_info
