"""Performance tests for optimization features."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from superego_mcp.domain.models import ToolRequest
from superego_mcp.infrastructure.metrics import MetricsCollector
from superego_mcp.infrastructure.performance import (
    ConnectionPool,
    ObjectPool,
    PerformanceMonitor,
    RequestBatcher,
    ResponseCache,
)
from superego_mcp.infrastructure.request_queue import Priority, RequestQueue


class TestResponseCache:
    """Test response cache functionality."""

    @pytest.mark.asyncio
    async def test_cache_hit_miss(self):
        """Test cache hits and misses."""
        cache = ResponseCache(max_size=10, default_ttl=5)

        # Test miss
        result = await cache.get("key1")
        assert result is None

        # Test set and hit
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_cache_ttl(self):
        """Test cache TTL expiration."""
        cache = ResponseCache(max_size=10, default_ttl=0.1)  # 100ms TTL

        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

        # Wait for expiration
        await asyncio.sleep(0.2)
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = ResponseCache(max_size=3, default_ttl=10)

        # Fill cache
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # Access key1 to make it recently used
        await cache.get("key1")

        # Add new item, should evict key2 (least recently used)
        await cache.set("key4", "value4")

        assert await cache.get("key1") == "value1"  # Still present
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"  # Still present
        assert await cache.get("key4") == "value4"  # New item

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics."""
        cache = ResponseCache(max_size=10, default_ttl=5)

        # Generate some hits and misses
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        stats = await cache.get_stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 10
        assert stats["total_hits"] == 2
        assert stats["hit_rate"] == 2.0  # 2 hits / 1 entry


class TestConnectionPool:
    """Test connection pooling."""

    @pytest.mark.asyncio
    async def test_connection_pool_basic(self):
        """Test basic connection pool operations."""
        with patch.object(httpx.AsyncClient, "request") as mock_request:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            pool = ConnectionPool(
                max_connections=10, max_keepalive_connections=5, keepalive_expiry=30
            )

            # Make a request
            response = await pool.request("GET", "https://httpbin.org/get")
            assert response.status_code == 200

            # Check stats
            stats = pool.get_stats()
            assert stats["max_connections"] == 10
            assert stats["max_keepalive"] == 5

            await pool.close()

    @pytest.mark.asyncio
    async def test_connection_reuse(self):
        """Test connection reuse in pool."""
        with patch.object(httpx.AsyncClient, "request") as mock_request:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            pool = ConnectionPool(max_connections=5)

            # Make multiple requests to same host
            start_time = time.time()
            for _ in range(5):
                response = await pool.request("GET", "https://httpbin.org/get")
                assert response.status_code == 200
            elapsed = time.time() - start_time

            # Should be very fast with mocked requests
            assert elapsed < 1.0

            # Verify we made 5 requests
            assert mock_request.call_count == 5

            await pool.close()


class TestObjectPool:
    """Test object pooling."""

    @pytest.mark.asyncio
    async def test_object_pool_reuse(self):
        """Test object reuse from pool."""
        created_count = 0

        def factory():
            nonlocal created_count
            created_count += 1
            return {"id": created_count}

        pool = ObjectPool(factory, max_size=5)

        # Acquire and release objects
        obj1 = await pool.acquire()
        assert obj1["id"] == 1
        await pool.release(obj1)

        obj2 = await pool.acquire()
        assert obj2["id"] == 1  # Reused

        stats = pool.get_stats()
        assert stats["created_count"] == 1
        assert stats["reused_count"] == 1
        assert stats["reuse_rate"] == 1.0


class TestRequestQueue:
    """Test request queue functionality."""

    @pytest.mark.asyncio
    async def test_queue_basic_operation(self):
        """Test basic queue operations."""
        queue = RequestQueue(max_size=10, default_timeout=5.0)

        processed_requests = []

        async def processor(request):
            await asyncio.sleep(0.1)  # Simulate processing
            processed_requests.append(request)
            return f"processed_{request}"

        await queue.start(processor)

        # Enqueue requests
        result1 = await queue.enqueue("request1")
        result2 = await queue.enqueue("request2")

        assert result1 == "processed_request1"
        assert result2 == "processed_request2"
        assert len(processed_requests) == 2

        await queue.stop()

    @pytest.mark.asyncio
    async def test_queue_priority(self):
        """Test priority queue ordering."""
        queue = RequestQueue(max_size=10, max_concurrent=1)

        results = []

        async def slow_processor(request):
            await asyncio.sleep(0.1)
            results.append(request)
            return request

        await queue.start(slow_processor)

        # Enqueue requests with different priorities
        tasks = [
            queue.enqueue("low", priority=Priority.LOW),
            queue.enqueue("high", priority=Priority.HIGH),
            queue.enqueue("normal", priority=Priority.NORMAL),
        ]

        await asyncio.gather(*tasks)

        # High priority should be processed first (after the initial one)
        assert "high" in results[:2]

        await queue.stop()

    @pytest.mark.asyncio
    async def test_queue_timeout(self):
        """Test request timeout in queue."""
        queue = RequestQueue(max_size=10, default_timeout=0.2)

        async def slow_processor(request):
            await asyncio.sleep(0.5)  # Longer than timeout
            return request

        await queue.start(slow_processor)

        with pytest.raises(asyncio.TimeoutError):
            await queue.enqueue("request1")

        stats = queue.get_stats()
        assert stats["total_timeout"] > 0

        await queue.stop()

    @pytest.mark.asyncio
    async def test_queue_backpressure(self):
        """Test queue backpressure handling."""
        queue = RequestQueue(max_size=2, max_concurrent=1, enable_backpressure=True)

        # Use a processor that blocks
        processor_started = asyncio.Event()
        processor_can_continue = asyncio.Event()

        async def blocking_processor(request):
            processor_started.set()
            await processor_can_continue.wait()
            return request

        await queue.start(blocking_processor)

        # First request should start processing
        task1 = asyncio.create_task(queue.enqueue("req1"))
        await processor_started.wait()  # Wait for processor to start

        # Fill the queue to capacity
        task2 = asyncio.create_task(queue.enqueue("req2"))
        task3 = asyncio.create_task(queue.enqueue("req3"))

        # Wait a moment for tasks to be queued
        await asyncio.sleep(0.1)

        # Try to add one more - this should raise QueueFull due to backpressure
        with pytest.raises(asyncio.QueueFull):
            await queue.enqueue("req4", timeout=0.5)

        # Clean up
        processor_can_continue.set()  # Allow processor to finish
        await queue.stop()

        # Cancel all tasks
        for task in [task1, task2, task3]:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class TestPerformanceMonitor:
    """Test performance monitoring."""

    @pytest.mark.asyncio
    async def test_timing_recording(self):
        """Test recording and retrieving timings."""
        monitor = PerformanceMonitor()

        # Record some timings
        await monitor.record_timing("operation1", 0.1)
        await monitor.record_timing("operation1", 0.2)
        await monitor.record_timing("operation1", 0.15)

        # Get percentiles
        percentiles = await monitor.get_percentiles("operation1")
        assert percentiles[50] == 0.15  # Median
        assert percentiles[99] <= 0.2

        # Get stats
        stats = await monitor.get_stats("operation1")
        assert stats["count"] == 3
        assert 0.1 <= stats["mean"] <= 0.2
        assert stats["min"] == 0.1
        assert stats["max"] == 0.2


class TestMetricsCollector:
    """Test metrics collection."""

    @pytest.mark.asyncio
    async def test_request_metrics(self):
        """Test request metric recording."""
        collector = MetricsCollector()

        # Record some requests
        await collector.record_request("evaluate", "http", 0.05, "success")
        await collector.record_request("evaluate", "http", 0.1, "error")

        # Check Prometheus metrics
        metrics = collector.get_prometheus_metrics()
        assert b"superego_requests_total" in metrics
        assert b"superego_request_duration_seconds" in metrics

    @pytest.mark.asyncio
    async def test_security_evaluation_metrics(self):
        """Test security evaluation metrics."""
        collector = MetricsCollector()

        await collector.record_security_evaluation("allow", "rule1", 0.01)
        await collector.record_security_evaluation("deny", "rule2", 0.02)

        metrics = collector.get_prometheus_metrics()
        assert b"superego_security_evaluations_total" in metrics
        assert b"superego_rule_evaluation_duration_seconds" in metrics

    @pytest.mark.asyncio
    async def test_cache_metrics(self):
        """Test cache metric recording."""
        collector = MetricsCollector()

        await collector.update_cache_metrics("response", hit=True, size=100)
        await collector.update_cache_metrics("response", hit=False, size=100)

        metrics = collector.get_prometheus_metrics()
        assert b"superego_cache_hits_total" in metrics
        assert b"superego_cache_misses_total" in metrics

    @pytest.mark.asyncio
    async def test_custom_metrics(self):
        """Test custom metric recording."""
        collector = MetricsCollector()

        # Record custom metrics
        await collector.record_custom_metric("custom_metric", 42.0)
        await collector.record_custom_metric("custom_metric", 43.0)

        # Get custom metrics
        custom = await collector.get_custom_metrics()
        assert "custom_metric" in custom
        assert len(custom["custom_metric"]) == 2
        assert custom["custom_metric"][-1].value == 43.0

        # Calculate percentiles
        percentiles = await collector.calculate_percentiles("custom_metric")
        assert percentiles[50] in [42.0, 43.0]


class TestRequestBatcher:
    """Test request batching."""

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch request processing."""

        class TestBatcher(RequestBatcher):
            async def _execute_batch(self, requests):
                # Return doubled values
                return [r * 2 for r in requests]

        batcher = TestBatcher(batch_size=3, batch_timeout=0.1)

        # Add requests
        results = await asyncio.gather(
            batcher.add_request(1),
            batcher.add_request(2),
            batcher.add_request(3),
        )

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_batch_timeout(self):
        """Test batch timeout processing."""

        class TestBatcher(RequestBatcher):
            async def _execute_batch(self, requests):
                return [r * 2 for r in requests]

        batcher = TestBatcher(batch_size=10, batch_timeout=0.1)

        # Add only one request (won't reach batch size)
        start_time = time.time()
        result = await batcher.add_request(5)
        elapsed = time.time() - start_time

        assert result == 10
        assert 0.1 <= elapsed < 0.2  # Processed after timeout


@pytest.mark.asyncio
async def test_performance_targets():
    """Test that performance targets are met."""
    from superego_mcp.domain.security_policy_optimized import (
        OptimizedSecurityPolicyEngine,
    )
    from superego_mcp.infrastructure.metrics import MetricsCollector
    from superego_mcp.infrastructure.performance import (
        PerformanceMonitor,
        ResponseCache,
    )

    # Create components
    metrics = MetricsCollector()
    monitor = PerformanceMonitor()
    cache = ResponseCache()

    # Create mock rules file
    import tempfile
    import yaml

    rules = {
        "rules": [
            {
                "id": "test_rule",
                "priority": 1,
                "conditions": {"tool_name": "test_tool"},
                "action": "allow",
                "reason": "Test rule",
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(rules, f)
        rules_file = f.name

    # Create engine
    from pathlib import Path

    engine = OptimizedSecurityPolicyEngine(
        rules_file=Path(rules_file),
        response_cache=cache,
        performance_monitor=monitor,
        metrics_collector=metrics,
    )

    # Test rule evaluation performance
    request = ToolRequest(
        tool_name="test_tool",
        parameters={},
        session_id="test",
        agent_id="test",
        cwd="/tmp",
    )

    # Warm up cache
    await engine.evaluate(request)

    # Measure performance
    timings = []
    for _ in range(100):
        start = time.perf_counter()
        await engine.evaluate(request)
        timings.append(time.perf_counter() - start)

    # Check P90 < 10ms target
    timings.sort()
    p90 = timings[int(len(timings) * 0.9)]
    assert p90 < 0.01  # 10ms

    # Check P99 < 50ms target
    p99 = timings[int(len(timings) * 0.99)]
    assert p99 < 0.05  # 50ms

    # Clean up
    import os

    os.unlink(rules_file)
