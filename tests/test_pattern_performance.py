"""Performance tests for advanced pattern matching functionality."""

import pytest
import time
import tempfile
import yaml
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.domain.pattern_engine import PatternEngine
from superego_mcp.domain.models import ToolRequest


class TestPatternPerformance:
    """Performance tests for pattern matching engine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pattern_engine = PatternEngine()

    def test_string_matching_performance(self):
        """Test performance of string matching."""
        patterns = ["exact_match", "another_match", "third_match"]
        values = [
            "exact_match",
            "different",
            "another_match",
            "third_match",
            "no_match",
        ]

        start_time = time.perf_counter()

        for _ in range(10000):
            for pattern in patterns:
                for value in values:
                    self.pattern_engine.match_string(pattern, value)

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should complete 150,000 string matches very quickly
        assert total_time < 0.1, f"String matching too slow: {total_time:.3f}s"

        operations_per_second = (10000 * len(patterns) * len(values)) / total_time
        print(f"String matching: {operations_per_second:,.0f} ops/sec")

    def test_regex_compilation_cache_performance(self):
        """Test performance benefit of regex compilation caching."""
        patterns = [
            r"^test.*",
            r"(file|path)\.txt$",
            r"^(create|update|delete)_.*",
            r"\b(admin|root|sudo)\b",
            r"^/etc/.*\.conf$",
        ]
        test_strings = [
            "test_command",
            "file.txt",
            "create_user",
            "admin_task",
            "/etc/config.conf",
            "no_match",
            "path.txt",
            "update_record",
        ]

        # Test with caching (normal operation)
        start_time = time.perf_counter()

        for _ in range(1000):
            for pattern in patterns:
                for test_string in test_strings:
                    self.pattern_engine.match_regex(pattern, test_string)

        cached_time = time.perf_counter() - start_time

        # Clear cache and test without caching benefit
        self.pattern_engine.clear_cache()

        start_time = time.perf_counter()

        # Use different patterns each time to avoid cache benefit
        for i in range(1000):
            for j, base_pattern in enumerate(patterns):
                # Make each pattern slightly different to avoid caching
                pattern = f"{base_pattern}_{i}_{j}"
                for test_string in test_strings:
                    try:
                        self.pattern_engine.match_regex(pattern, test_string)
                    except:
                        pass  # Ignore invalid patterns from modification

        uncached_time = time.perf_counter() - start_time

        # Cached version should be significantly faster
        print(f"Regex cached: {cached_time:.3f}s, uncached: {uncached_time:.3f}s")
        print(f"Cache speedup: {uncached_time / cached_time:.1f}x")

        # Allow some variance, but caching should provide meaningful benefit
        assert cached_time < uncached_time * 0.8, (
            "Regex caching not providing expected performance benefit"
        )

    def test_glob_matching_performance(self):
        """Test performance of glob pattern matching."""
        patterns = ["*.txt", "/etc/**", "**/config/*", "file[0-9].log", "/home/*/.*"]
        paths = [
            "document.txt",
            "/etc/config/app.conf",
            "/app/config/settings.yaml",
            "file5.log",
            "/home/user/.bashrc",
            "/var/log/system.log",
            "/etc/passwd",
            "/home/user/config/app.conf",
        ]

        start_time = time.perf_counter()

        for _ in range(5000):
            for pattern in patterns:
                for path in paths:
                    self.pattern_engine.match_glob(pattern, path)

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should complete 200,000 glob matches reasonably quickly
        assert total_time < 0.5, f"Glob matching too slow: {total_time:.3f}s"

        operations_per_second = (5000 * len(patterns) * len(paths)) / total_time
        print(f"Glob matching: {operations_per_second:,.0f} ops/sec")

    def test_jsonpath_compilation_cache_performance(self):
        """Test performance benefit of JSONPath compilation caching."""
        patterns = [
            "$.size",
            "$[*].size",
            "$.meta.owner",
            "$[*].type",
            "$.permissions[*]",
        ]

        test_data = [
            {"size": 2048, "type": "file", "meta": {"owner": "user"}},
            {"size": 512, "type": "dir", "permissions": ["read", "write"]},
            {"type": "file", "meta": {"owner": "admin"}, "permissions": ["read"]},
            {"size": 1500, "type": "file"},
            {},
        ]

        # Test with caching
        start_time = time.perf_counter()

        for _ in range(1000):
            for pattern in patterns:
                for data in test_data:
                    self.pattern_engine.match_jsonpath(pattern, data)

        cached_time = time.perf_counter() - start_time

        # Clear cache and test performance impact
        cache_stats_before = self.pattern_engine.get_cache_stats()
        self.pattern_engine.clear_cache()
        cache_stats_after = self.pattern_engine.get_cache_stats()

        assert cache_stats_after["jsonpath_cache"]["currsize"] == 0

        print(f"JSONPath with caching: {cached_time:.3f}s")
        print(
            f"Cache stats: {cache_stats_before['jsonpath_cache']['hits']} hits, "
            f"{cache_stats_before['jsonpath_cache']['misses']} misses"
        )

        operations_per_second = (1000 * len(patterns) * len(test_data)) / cached_time
        print(f"JSONPath matching: {operations_per_second:,.0f} ops/sec")

        # Should be reasonably fast
        assert cached_time < 1.0, f"JSONPath matching too slow: {cached_time:.3f}s"

    def test_composite_pattern_performance(self):
        """Test performance of composite pattern matching."""
        request = ToolRequest(
            tool_name="test_command",
            parameters={
                "path": "/home/user/document.txt",
                "size": 2048,
                "type": "file",
            },
            session_id="test",
            agent_id="test",
            cwd="/home/user",
        )

        # Complex composite condition
        conditions = {
            "AND": [
                {
                    "OR": [
                        {"tool_name": {"type": "regex", "pattern": r"^(test|demo).*"}},
                        {"tool_name": ["specific_command", "other_command"]},
                    ]
                },
                {"parameters": {"path": {"type": "glob", "pattern": "/home/**"}}},
                {"parameters": {"type": "jsonpath", "pattern": "$[*].size"}},
            ]
        }

        start_time = time.perf_counter()

        for _ in range(1000):
            self.pattern_engine.match_composite(conditions, request)

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should complete 1000 complex composite matches quickly
        assert total_time < 0.5, f"Composite matching too slow: {total_time:.3f}s"

        operations_per_second = 1000 / total_time
        print(f"Composite matching: {operations_per_second:,.0f} ops/sec")


class TestSecurityPolicyPerformance:
    """Performance tests for SecurityPolicyEngine with pattern matching."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.rules_file = Path(self.temp_dir) / "perf_rules.yaml"

        # Create rules with various pattern types for performance testing
        rules = {"rules": []}

        # Add many rules with different pattern types
        for i in range(50):
            rules["rules"].extend(
                [
                    {
                        "id": f"regex_rule_{i}",
                        "priority": i * 10 + 1,
                        "conditions": {
                            "tool_name": {"type": "regex", "pattern": rf"^test_{i}.*"}
                        },
                        "action": "deny",
                        "reason": f"Regex rule {i}",
                    },
                    {
                        "id": f"glob_rule_{i}",
                        "priority": i * 10 + 2,
                        "conditions": {
                            "parameters": {
                                "path": {"type": "glob", "pattern": f"/test{i}/**"}
                            }
                        },
                        "action": "sample",
                        "reason": f"Glob rule {i}",
                    },
                    {
                        "id": f"composite_rule_{i}",
                        "priority": i * 10 + 3,
                        "conditions": {
                            "AND": [
                                {
                                    "tool_name": {
                                        "type": "regex",
                                        "pattern": rf"^complex_{i}",
                                    }
                                },
                                {
                                    "parameters": {
                                        "type": "jsonpath",
                                        "pattern": f"$[{i % 3}].id",
                                    }
                                },
                            ]
                        },
                        "action": "allow",
                        "reason": f"Composite rule {i}",
                    },
                ]
            )

        # Add final catch-all rule
        rules["rules"].append(
            {
                "id": "default_allow",
                "priority": 999,
                "conditions": {"tool_name": {"type": "regex", "pattern": ".*"}},
                "action": "allow",
                "reason": "Default allow",
            }
        )

        with open(self.rules_file, "w") as f:
            yaml.dump(rules, f)

        # Mock AI service for sampling rules
        self.mock_ai_manager = MagicMock()
        self.mock_ai_decision = MagicMock()
        self.mock_ai_decision.decision = "allow"
        self.mock_ai_decision.reasoning = "AI approved"
        self.mock_ai_decision.confidence = 0.8
        self.mock_ai_decision.provider.value = "test_provider"
        self.mock_ai_decision.model = "test_model"
        self.mock_ai_decision.risk_factors = []

        self.mock_ai_manager.evaluate_with_ai = AsyncMock(
            return_value=self.mock_ai_decision
        )

        self.mock_prompt_builder = MagicMock()
        self.mock_prompt_builder.build_evaluation_prompt = MagicMock(
            return_value="test prompt"
        )

        self.engine = SecurityPolicyEngine(
            self.rules_file,
            ai_service_manager=self.mock_ai_manager,
            prompt_builder=self.mock_prompt_builder,
        )

    async def test_rule_evaluation_performance(self):
        """Test performance of rule evaluation with many rules."""
        # Test requests that will match different rules
        test_requests = [
            ToolRequest(
                tool_name="no_match_command",
                parameters={"path": "/no/match"},
                session_id="test",
                agent_id="test",
                cwd="/tmp",
            ),
            ToolRequest(
                tool_name="test_25_command",
                parameters={"path": "/test25/file"},
                session_id="test",
                agent_id="test",
                cwd="/tmp",
            ),
            ToolRequest(
                tool_name="complex_10",
                parameters={"id": 10, "data": "test"},
                session_id="test",
                agent_id="test",
                cwd="/tmp",
            ),
        ]

        # Warm up the engine
        for request in test_requests:
            await self.engine.evaluate(request)

        # Performance test
        start_time = time.perf_counter()

        for _ in range(100):
            for request in test_requests:
                decision = await self.engine.evaluate(request)
                assert decision is not None

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should evaluate 300 requests against ~150 rules quickly
        assert total_time < 2.0, (
            f"Rule evaluation too slow: {total_time:.3f}s for 300 evaluations"
        )

        evaluations_per_second = 300 / total_time
        print(f"Rule evaluations: {evaluations_per_second:,.0f} evaluations/sec")
        print(f"Average time per evaluation: {(total_time / 300) * 1000:.2f}ms")

    async def test_pattern_cache_effectiveness(self):
        """Test that pattern caching improves performance over time."""
        request = ToolRequest(
            tool_name="test_1_command",
            parameters={"path": "/test1/config.txt"},
            session_id="test",
            agent_id="test",
            cwd="/test1",
        )

        # Clear cache to start fresh
        self.engine.pattern_engine.clear_cache()

        # First batch - patterns will be compiled and cached
        start_time = time.perf_counter()

        for _ in range(100):
            await self.engine.evaluate(request)

        first_batch_time = time.perf_counter() - start_time

        # Second batch - should benefit from cached patterns
        start_time = time.perf_counter()

        for _ in range(100):
            await self.engine.evaluate(request)

        second_batch_time = time.perf_counter() - start_time

        print(
            f"First batch: {first_batch_time:.3f}s, Second batch: {second_batch_time:.3f}s"
        )

        # Second batch should be faster due to caching
        # Allow some variance, but should show improvement
        assert second_batch_time <= first_batch_time * 1.1, (
            "Pattern caching not providing expected performance benefit"
        )

        # Check cache statistics
        cache_stats = self.engine.pattern_engine.get_cache_stats()
        print(
            f"Regex cache: {cache_stats['regex_cache']['hits']} hits, "
            f"{cache_stats['regex_cache']['misses']} misses"
        )
        print(
            f"JSONPath cache: {cache_stats['jsonpath_cache']['hits']} hits, "
            f"{cache_stats['jsonpath_cache']['misses']} misses"
        )

        # Should have significant cache hits
        assert cache_stats["regex_cache"]["hits"] > 0

    async def test_early_termination_performance(self):
        """Test that rule evaluation terminates early on first match."""
        # Create request that matches the first rule
        request = ToolRequest(
            tool_name="test_0_early_match",
            parameters={},
            session_id="test",
            agent_id="test",
            cwd="/tmp",
        )

        start_time = time.perf_counter()

        for _ in range(1000):
            decision = await self.engine.evaluate(request)
            assert decision.rule_id == "regex_rule_0"  # Should match first rule

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should be very fast since it matches the first rule every time
        assert total_time < 0.5, f"Early termination not working: {total_time:.3f}s"

        operations_per_second = 1000 / total_time
        print(
            f"Early termination performance: {operations_per_second:,.0f} evaluations/sec"
        )

    async def test_memory_usage_stability(self):
        """Test that memory usage remains stable under repeated evaluations."""
        import gc
        import psutil
        import os

        process = psutil.Process(os.getpid())

        # Get initial memory usage
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run many evaluations
        requests = [
            ToolRequest(
                tool_name=f"test_{i % 10}_command",
                parameters={"path": f"/test{i % 5}/file{i}.txt", "id": i},
                session_id=f"session_{i % 3}",
                agent_id=f"agent_{i % 2}",
                cwd=f"/test{i % 5}",
            )
            for i in range(1000)
        ]

        for request in requests:
            await self.engine.evaluate(request)

        # Check memory usage after evaluations
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        print(
            f"Initial memory: {initial_memory:.1f}MB, "
            f"Final memory: {final_memory:.1f}MB, "
            f"Increase: {memory_increase:.1f}MB"
        )

        # Memory increase should be reasonable (allow for some caching)
        assert memory_increase < 50, (
            f"Excessive memory usage: {memory_increase:.1f}MB increase"
        )
