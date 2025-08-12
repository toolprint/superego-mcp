"""Tests for the advanced pattern matching engine."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from superego_mcp.domain.pattern_engine import PatternEngine, PatternType
from superego_mcp.domain.models import ToolRequest


class TestPatternEngine:
    """Test cases for PatternEngine functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pattern_engine = PatternEngine()
        self.sample_request = ToolRequest(
            tool_name="test_tool",
            parameters={"path": "/home/user/file.txt", "size": 1024},
            session_id="test_session",
            agent_id="test_agent",
            cwd="/home/user",
        )

    def test_string_matching(self):
        """Test simple string matching."""
        assert self.pattern_engine.match_string("exact", "exact")
        assert not self.pattern_engine.match_string("exact", "different")
        assert not self.pattern_engine.match_string("exact", "EXACT")

    def test_regex_matching(self):
        """Test regex pattern matching."""
        # Basic regex
        assert self.pattern_engine.match_regex(r"test.*", "testing")
        assert not self.pattern_engine.match_regex(r"test.*", "best")

        # Case insensitive by default
        assert self.pattern_engine.match_regex(r"test", "TEST")

        # Start/end anchors
        assert self.pattern_engine.match_regex(r"^test$", "test")
        assert not self.pattern_engine.match_regex(r"^test$", "testing")

        # Complex patterns
        assert self.pattern_engine.match_regex(r"^(rm|delete|remove).*", "remove_file")
        assert not self.pattern_engine.match_regex(
            r"^(rm|delete|remove).*", "create_file"
        )

    def test_regex_safety(self):
        """Test regex safety limits."""
        # Pattern too long
        long_pattern = "a" * 1001
        assert not self.pattern_engine.match_regex(long_pattern, "test")

        # Invalid regex
        assert not self.pattern_engine.match_regex(r"[", "test")

    def test_glob_matching(self):
        """Test glob pattern matching."""
        # Basic glob
        assert self.pattern_engine.match_glob("*.txt", "file.txt")
        assert not self.pattern_engine.match_glob("*.txt", "file.py")

        # Path matching
        assert self.pattern_engine.match_glob("/etc/**", "/etc/config/file")
        assert not self.pattern_engine.match_glob("/etc/**", "/home/user/file")

        # Character classes
        assert self.pattern_engine.match_glob("file[0-9].txt", "file3.txt")
        assert not self.pattern_engine.match_glob("file[0-9].txt", "filea.txt")

    def test_jsonpath_matching(self):
        """Test JSONPath expression matching."""
        data = {
            "size": 2000000,
            "type": "file",
            "permissions": ["read", "write"],
            "meta": {"owner": "user", "sensitive": True},
        }

        # Simple property check
        assert self.pattern_engine.match_jsonpath("$.size", data)
        assert not self.pattern_engine.match_jsonpath("$.missing", data)

        # Nested property
        assert self.pattern_engine.match_jsonpath("$.meta.owner", data)
        assert self.pattern_engine.match_jsonpath("$.meta.sensitive", data)

        # Array matching
        assert self.pattern_engine.match_jsonpath("$.permissions[*]", data)
        assert self.pattern_engine.match_jsonpath("$.permissions[0]", data)

    def test_jsonpath_safety(self):
        """Test JSONPath safety and error handling."""
        # Invalid JSONPath
        assert not self.pattern_engine.match_jsonpath("$.[invalid", {"test": "data"})

        # Empty data
        assert not self.pattern_engine.match_jsonpath("$.test", {})

    def test_pattern_matching_string_config(self):
        """Test pattern matching with string configuration."""
        # Backward compatibility - string treated as string match
        assert self.pattern_engine.match_pattern("exact", "exact")
        assert not self.pattern_engine.match_pattern("exact", "different")

    def test_pattern_matching_dict_config(self):
        """Test pattern matching with dictionary configuration."""
        # String type
        config = {"type": "string", "pattern": "exact"}
        assert self.pattern_engine.match_pattern(config, "exact")
        assert not self.pattern_engine.match_pattern(config, "different")

        # Regex type
        config = {"type": "regex", "pattern": r"test.*"}
        assert self.pattern_engine.match_pattern(config, "testing")
        assert not self.pattern_engine.match_pattern(config, "best")

        # Glob type
        config = {"type": "glob", "pattern": "*.txt"}
        assert self.pattern_engine.match_pattern(config, "file.txt")
        assert not self.pattern_engine.match_pattern(config, "file.py")

        # JSONPath type
        config = {"type": "jsonpath", "pattern": "$.size"}
        context = {"size": 1024}
        assert self.pattern_engine.match_pattern(config, None, context)
        assert not self.pattern_engine.match_pattern(config, None, {"other": "data"})

    def test_pattern_matching_invalid_config(self):
        """Test pattern matching with invalid configuration."""
        # Missing type
        assert not self.pattern_engine.match_pattern({"pattern": "test"}, "test")

        # Unknown type
        config = {"type": "unknown", "pattern": "test"}
        assert not self.pattern_engine.match_pattern(config, "test")

        # Invalid pattern structure
        assert not self.pattern_engine.match_pattern(123, "test")

    def test_composite_matching_and(self):
        """Test composite AND condition matching."""
        conditions = {
            "AND": [
                {"tool_name": "test_tool"},
                {"parameters": {"path": "/home/user/file.txt"}},
            ]
        }

        assert self.pattern_engine.match_composite(conditions, self.sample_request)

        # Should fail if any condition fails
        conditions["AND"][0]["tool_name"] = "other_tool"
        assert not self.pattern_engine.match_composite(conditions, self.sample_request)

    def test_composite_matching_or(self):
        """Test composite OR condition matching."""
        conditions = {"OR": [{"tool_name": "other_tool"}, {"tool_name": "test_tool"}]}

        assert self.pattern_engine.match_composite(conditions, self.sample_request)

        # Should fail if all conditions fail
        conditions = {
            "OR": [{"tool_name": "other_tool"}, {"tool_name": "another_tool"}]
        }
        assert not self.pattern_engine.match_composite(conditions, self.sample_request)

    def test_composite_matching_mixed(self):
        """Test composite conditions with both AND and OR."""
        conditions = {
            "AND": [
                {"OR": [{"tool_name": "test_tool"}, {"tool_name": "other_tool"}]},
                {"parameters": {"path": "/home/user/file.txt"}},
            ]
        }

        assert self.pattern_engine.match_composite(conditions, self.sample_request)

    def test_evaluate_condition_tool_name(self):
        """Test condition evaluation for tool names."""
        # List matching (backward compatibility)
        condition = {"tool_name": ["test_tool", "other_tool"]}
        assert self.pattern_engine._evaluate_condition(condition, self.sample_request)

        condition = {"tool_name": ["other_tool"]}
        assert not self.pattern_engine._evaluate_condition(
            condition, self.sample_request
        )

        # Pattern matching
        condition = {"tool_name": {"type": "regex", "pattern": r"test.*"}}
        assert self.pattern_engine._evaluate_condition(condition, self.sample_request)

    def test_evaluate_condition_parameters(self):
        """Test condition evaluation for parameters."""
        # Individual parameter matching
        condition = {"parameters": {"path": "/home/user/file.txt"}}
        assert self.pattern_engine._evaluate_condition(condition, self.sample_request)

        # Pattern-based parameter matching
        condition = {"parameters": {"path": {"type": "glob", "pattern": "/home/**"}}}
        assert self.pattern_engine._evaluate_condition(condition, self.sample_request)

        # JSONPath on entire parameters
        condition = {"parameters": {"type": "jsonpath", "pattern": "$.size"}}
        assert self.pattern_engine._evaluate_condition(condition, self.sample_request)

    def test_evaluate_condition_cwd(self):
        """Test condition evaluation for current working directory."""
        # Legacy cwd_pattern (regex)
        condition = {"cwd_pattern": r"/home/.*"}
        assert self.pattern_engine._evaluate_condition(condition, self.sample_request)

        # Modern cwd pattern
        condition = {"cwd": {"type": "glob", "pattern": "/home/*"}}
        assert self.pattern_engine._evaluate_condition(condition, self.sample_request)

    @patch("superego_mcp.domain.pattern_engine.datetime")
    def test_time_range_matching(self, mock_datetime):
        """Test time-based condition matching."""
        # Mock current time to 10:30 UTC
        mock_now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        # Mock the datetime.now method properly
        def mock_now_func(tz=None):
            return mock_now

        mock_datetime.now = mock_now_func

        # Mock strptime to return real datetime.strptime results
        mock_datetime.strptime = datetime.strptime

        # Time within range
        time_config = {"start": "09:00", "end": "17:00", "timezone": "UTC"}
        assert self.pattern_engine._match_time_range(time_config)

        # Time outside range
        time_config = {"start": "18:00", "end": "08:00", "timezone": "UTC"}
        assert not self.pattern_engine._match_time_range(time_config)

    @patch("superego_mcp.domain.pattern_engine.datetime")
    def test_time_range_crossing_midnight(self, mock_datetime):
        """Test time range that crosses midnight."""
        # Mock current time to 02:00 UTC
        mock_now = datetime(2024, 1, 15, 2, 0, 0, tzinfo=timezone.utc)

        # Mock the datetime.now method properly
        def mock_now_func(tz=None):
            return mock_now

        mock_datetime.now = mock_now_func

        # Mock strptime to return real datetime.strptime results
        mock_datetime.strptime = datetime.strptime

        # Range crosses midnight (22:00 to 06:00)
        time_config = {"start": "22:00", "end": "06:00", "timezone": "UTC"}
        assert self.pattern_engine._match_time_range(time_config)

        # Time outside crossing range
        mock_now2 = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        def mock_now_func2(tz=None):
            return mock_now2

        mock_datetime.now = mock_now_func2
        assert not self.pattern_engine._match_time_range(time_config)

    def test_validate_pattern(self):
        """Test pattern validation."""
        # String patterns are always valid
        assert self.pattern_engine.validate_pattern("any_string")

        # Valid pattern configs
        assert self.pattern_engine.validate_pattern(
            {"type": "string", "pattern": "test"}
        )

        assert self.pattern_engine.validate_pattern(
            {"type": "regex", "pattern": r"test.*"}
        )

        assert self.pattern_engine.validate_pattern(
            {"type": "glob", "pattern": "*.txt"}
        )

        assert self.pattern_engine.validate_pattern(
            {"type": "jsonpath", "pattern": "$.test"}
        )

        # Invalid pattern configs
        assert not self.pattern_engine.validate_pattern(
            {"type": "invalid", "pattern": "test"}
        )

        assert not self.pattern_engine.validate_pattern(
            {
                "pattern": "test"  # Missing type
            }
        )

        assert not self.pattern_engine.validate_pattern(
            {
                "type": "regex",
                "pattern": "[",  # Invalid regex
            }
        )

    def test_cache_stats(self):
        """Test pattern compilation cache statistics."""
        # Clear cache first to ensure clean state
        self.pattern_engine.clear_cache()

        # Initially empty
        stats = self.pattern_engine.get_cache_stats()
        assert stats["regex_cache"]["currsize"] == 0
        assert stats["jsonpath_cache"]["currsize"] == 0

        # Use patterns to populate cache
        self.pattern_engine.match_regex(r"test.*", "testing")
        self.pattern_engine.match_jsonpath("$.test", {"test": "value"})

        # Check cache is populated
        stats = self.pattern_engine.get_cache_stats()
        assert stats["regex_cache"]["currsize"] >= 1
        assert stats["jsonpath_cache"]["currsize"] >= 1

    def test_clear_cache(self):
        """Test cache clearing."""
        # Populate cache
        self.pattern_engine.match_regex(r"test.*", "testing")
        self.pattern_engine.match_jsonpath("$.test", {"test": "value"})

        # Verify cache has entries
        stats = self.pattern_engine.get_cache_stats()
        assert stats["regex_cache"]["currsize"] > 0
        assert stats["jsonpath_cache"]["currsize"] > 0

        # Clear cache
        self.pattern_engine.clear_cache()

        # Verify cache is empty
        stats = self.pattern_engine.get_cache_stats()
        assert stats["regex_cache"]["currsize"] == 0
        assert stats["jsonpath_cache"]["currsize"] == 0


class TestPatternEnginePerformance:
    """Performance tests for PatternEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pattern_engine = PatternEngine()

    def test_regex_compilation_caching(self):
        """Test that regex compilation uses caching effectively."""
        pattern = r"test.*pattern"

        # First compilation
        stats_before = self.pattern_engine.get_cache_stats()
        self.pattern_engine.match_regex(pattern, "test_string_pattern")
        stats_after = self.pattern_engine.get_cache_stats()

        # Should have one miss (cache miss for compilation)
        assert (
            stats_after["regex_cache"]["misses"] > stats_before["regex_cache"]["misses"]
        )

        # Second use should hit cache
        stats_before = stats_after
        self.pattern_engine.match_regex(pattern, "another_test_pattern")
        stats_after = self.pattern_engine.get_cache_stats()

        # Should have one more hit
        assert stats_after["regex_cache"]["hits"] > stats_before["regex_cache"]["hits"]

    def test_jsonpath_compilation_caching(self):
        """Test that JSONPath compilation uses caching effectively."""
        pattern = "$.test.path"
        data = {"test": {"path": "value"}}

        # First compilation
        stats_before = self.pattern_engine.get_cache_stats()
        self.pattern_engine.match_jsonpath(pattern, data)
        stats_after = self.pattern_engine.get_cache_stats()

        # Should have one miss
        assert (
            stats_after["jsonpath_cache"]["misses"]
            > stats_before["jsonpath_cache"]["misses"]
        )

        # Second use should hit cache
        stats_before = stats_after
        self.pattern_engine.match_jsonpath(pattern, {"test": {"path": "other_value"}})
        stats_after = self.pattern_engine.get_cache_stats()

        # Should have one more hit
        assert (
            stats_after["jsonpath_cache"]["hits"]
            > stats_before["jsonpath_cache"]["hits"]
        )

    def test_pattern_matching_performance(self):
        """Test that pattern matching is reasonably fast."""
        import time

        patterns = [
            {"type": "regex", "pattern": r"^(test|demo|sample).*"},
            {"type": "glob", "pattern": "/home/**/*.txt"},
            {"type": "jsonpath", "pattern": "$.size"},
        ]

        values = ["test_command", "/home/user/file.txt", {"size": 2000}]
        contexts = [None, None, {"size": 2000}]

        start_time = time.perf_counter()

        # Run many pattern matches
        for _ in range(1000):
            for i, pattern in enumerate(patterns):
                self.pattern_engine.match_pattern(pattern, values[i], contexts[i])

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should complete 3000 pattern matches in reasonable time (< 1 second)
        assert total_time < 1.0, (
            f"Pattern matching too slow: {total_time:.3f}s for 3000 matches"
        )
