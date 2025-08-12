"""Advanced pattern matching engine for security rules with caching optimization."""

import re
import fnmatch
import time
from datetime import datetime, time as dt_time
from enum import Enum
from typing import Any, Dict, Union, TYPE_CHECKING
from functools import lru_cache

import structlog
from jsonpath_ng import parse as jsonpath_parse
from dateutil import tz

if TYPE_CHECKING:
    from .models import ToolRequest


class PatternType(str, Enum):
    """Supported pattern matching types."""

    STRING = "string"
    REGEX = "regex"
    GLOB = "glob"
    JSONPATH = "jsonpath"


class PatternEngine:
    """Unified pattern matching engine with performance optimization."""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self._compiled_patterns: Dict[str, Any] = {}

    @lru_cache(maxsize=256)
    def _compile_regex(self, pattern: str) -> re.Pattern:
        """Compile and cache regex patterns."""
        try:
            # Add safety limits to prevent catastrophic backtracking
            if len(pattern) > 1000:
                raise ValueError("Regex pattern too long")
            return re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

    @lru_cache(maxsize=256)
    def _compile_jsonpath(self, pattern: str) -> Any:
        """Compile and cache JSONPath expressions."""
        try:
            return jsonpath_parse(pattern)
        except Exception as e:
            raise ValueError(f"Invalid JSONPath pattern: {e}")

    def match_string(self, pattern: str, value: str) -> bool:
        """Simple string equality matching."""
        return pattern == value

    def match_regex(self, pattern: str, value: str) -> bool:
        """Regex pattern matching with caching."""
        try:
            compiled_regex = self._compile_regex(pattern)
            return bool(compiled_regex.search(value))
        except ValueError as e:
            self.logger.warning("Regex matching failed", pattern=pattern, error=str(e))
            return False

    def match_glob(self, pattern: str, value: str) -> bool:
        """Unix glob pattern matching for paths."""
        try:
            return fnmatch.fnmatch(value, pattern)
        except Exception as e:
            self.logger.warning("Glob matching failed", pattern=pattern, error=str(e))
            return False

    def match_jsonpath(
        self,
        pattern: str,
        data: dict,
        threshold: Any = None,
        comparison: str = "exists",
    ) -> bool:
        """JSONPath expression evaluation with optional value comparison."""
        try:
            compiled_jsonpath = self._compile_jsonpath(pattern)
            matches = compiled_jsonpath.find(data)

            if not matches:
                return False

            # If only checking for existence
            if comparison == "exists" or threshold is None:
                return True

            # Value comparison
            for match in matches:
                value = match.value
                if (
                    comparison == "gt"
                    and isinstance(value, (int, float))
                    and isinstance(threshold, (int, float))
                ):
                    if value > threshold:
                        return True
                elif (
                    comparison == "gte"
                    and isinstance(value, (int, float))
                    and isinstance(threshold, (int, float))
                ):
                    if value >= threshold:
                        return True
                elif (
                    comparison == "lt"
                    and isinstance(value, (int, float))
                    and isinstance(threshold, (int, float))
                ):
                    if value < threshold:
                        return True
                elif (
                    comparison == "lte"
                    and isinstance(value, (int, float))
                    and isinstance(threshold, (int, float))
                ):
                    if value <= threshold:
                        return True
                elif comparison == "eq":
                    if value == threshold:
                        return True

            return False
        except ValueError as e:
            self.logger.warning(
                "JSONPath matching failed", pattern=pattern, error=str(e)
            )
            return False

    def match_pattern(
        self, pattern_config: Union[str, dict], value: Any, context: dict = None
    ) -> bool:
        """
        Match a pattern configuration against a value.

        Args:
            pattern_config: Either a string (for backward compatibility) or dict with type and pattern
            value: The value to match against
            context: Additional context (e.g., full request data for JSONPath)
        """
        # Backward compatibility: if pattern_config is a string, treat as string match
        if isinstance(pattern_config, str):
            return self.match_string(pattern_config, str(value))

        # Modern pattern configuration
        if not isinstance(pattern_config, dict) or "type" not in pattern_config:
            return False

        pattern_type = pattern_config["type"]
        pattern = pattern_config["pattern"]

        if pattern_type == PatternType.STRING:
            return self.match_string(pattern, str(value))
        elif pattern_type == PatternType.REGEX:
            return self.match_regex(pattern, str(value))
        elif pattern_type == PatternType.GLOB:
            return self.match_glob(pattern, str(value))
        elif pattern_type == PatternType.JSONPATH:
            # For JSONPath, use context data or the value itself if it's a dict
            data = (
                context
                if context is not None
                else (value if isinstance(value, dict) else {})
            )
            threshold = pattern_config.get("threshold")
            comparison = pattern_config.get("comparison", "exists")
            return self.match_jsonpath(pattern, data, threshold, comparison)
        else:
            self.logger.warning("Unknown pattern type", pattern_type=pattern_type)
            return False

    def match_composite(self, conditions: dict, request: "ToolRequest") -> bool:
        """
        Match composite conditions with AND/OR logic.

        Args:
            conditions: Dictionary with AND/OR keys containing condition lists
            request: The tool request to evaluate
        """
        # Handle AND conditions
        if "AND" in conditions:
            and_conditions = conditions["AND"]
            if not all(
                self._evaluate_condition(cond, request) for cond in and_conditions
            ):
                return False

        # Handle OR conditions
        if "OR" in conditions:
            or_conditions = conditions["OR"]
            if not any(
                self._evaluate_condition(cond, request) for cond in or_conditions
            ):
                return False

        # Handle direct conditions (same as AND)
        direct_conditions = {
            k: v for k, v in conditions.items() if k not in ["AND", "OR"]
        }
        if direct_conditions and not self._evaluate_condition(
            direct_conditions, request
        ):
            return False

        return True

    def _evaluate_condition(self, condition: dict, request: "ToolRequest") -> bool:
        """Evaluate a single condition against a request."""
        # Tool name matching
        if "tool_name" in condition:
            tool_pattern = condition["tool_name"]
            if isinstance(tool_pattern, list):
                # List matching for backward compatibility
                if request.tool_name not in tool_pattern:
                    return False
            else:
                # Pattern matching
                if not self.match_pattern(tool_pattern, request.tool_name):
                    return False

        # Parameter matching
        if "parameters" in condition:
            param_conditions = condition["parameters"]

            # Handle JSONPath patterns on entire parameters dict
            if isinstance(param_conditions, dict) and "type" in param_conditions:
                if not self.match_pattern(
                    param_conditions, request.parameters, request.parameters
                ):
                    return False
            else:
                # Handle individual parameter conditions
                for key, expected in param_conditions.items():
                    if key not in request.parameters:
                        return False
                    if not self.match_pattern(
                        expected, request.parameters[key], request.parameters
                    ):
                        return False

        # CWD pattern matching (backward compatibility)
        if "cwd_pattern" in condition:
            pattern = condition["cwd_pattern"]
            # Treat as regex pattern for backward compatibility
            if not self.match_regex(pattern, request.cwd):
                return False

        # Enhanced path matching
        if "cwd" in condition:
            cwd_pattern = condition["cwd"]
            if not self.match_pattern(cwd_pattern, request.cwd):
                return False

        # Time-based matching
        if "time_range" in condition:
            if not self._match_time_range(condition["time_range"]):
                return False

        return True

    def _match_time_range(self, time_config: dict) -> bool:
        """Match time-based conditions."""
        try:
            start_time_str = time_config.get("start", "00:00")
            end_time_str = time_config.get("end", "23:59")
            timezone_str = time_config.get("timezone", "UTC")

            # Parse time strings
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()

            # Get current time in specified timezone
            timezone = tz.gettz(timezone_str)
            current_time = datetime.now(timezone).time()

            # Handle time range that crosses midnight
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time

        except Exception as e:
            self.logger.warning(
                "Time range matching failed", time_config=time_config, error=str(e)
            )
            return False

    def validate_pattern(self, pattern_config: Union[str, dict]) -> bool:
        """Validate a pattern configuration without executing it."""
        try:
            if isinstance(pattern_config, str):
                return True  # String patterns are always valid

            if not isinstance(pattern_config, dict) or "type" not in pattern_config:
                return False

            pattern_type = pattern_config["type"]
            pattern = pattern_config["pattern"]

            if pattern_type == PatternType.REGEX:
                self._compile_regex(pattern)
            elif pattern_type == PatternType.JSONPATH:
                self._compile_jsonpath(pattern)
            elif pattern_type in [PatternType.STRING, PatternType.GLOB]:
                # These are always valid as long as pattern is a string
                return isinstance(pattern, str)
            else:
                return False

            return True
        except Exception:
            return False

    def get_cache_stats(self) -> dict:
        """Get pattern compilation cache statistics."""
        regex_cache = self._compile_regex.cache_info()
        jsonpath_cache = self._compile_jsonpath.cache_info()

        return {
            "regex_cache": {
                "hits": regex_cache.hits,
                "misses": regex_cache.misses,
                "maxsize": regex_cache.maxsize,
                "currsize": regex_cache.currsize,
            },
            "jsonpath_cache": {
                "hits": jsonpath_cache.hits,
                "misses": jsonpath_cache.misses,
                "maxsize": jsonpath_cache.maxsize,
                "currsize": jsonpath_cache.currsize,
            },
        }

    def clear_cache(self) -> None:
        """Clear pattern compilation caches."""
        self._compile_regex.cache_clear()
        self._compile_jsonpath.cache_clear()
        self._compiled_patterns.clear()
