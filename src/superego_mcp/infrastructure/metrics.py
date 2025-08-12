"""Advanced metrics collection system with Prometheus format support."""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import psutil
import structlog
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = structlog.get_logger(__name__)


@dataclass
class MetricValue:
    """Container for a metric value with metadata."""

    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Comprehensive metrics collection with Prometheus format support."""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """Initialize metrics collector.

        Args:
            registry: Prometheus registry (creates new if None)
        """
        self.registry = registry or CollectorRegistry()
        self._start_time = time.time()

        # Initialize Prometheus metrics
        self._setup_prometheus_metrics()

        # Internal storage for custom metrics
        self._custom_metrics: Dict[str, List[MetricValue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def _setup_prometheus_metrics(self) -> None:
        """Set up Prometheus metric collectors."""
        # Request metrics
        self.requests_total = Counter(
            "superego_requests_total",
            "Total requests processed",
            ["method", "transport", "status"],
            registry=self.registry,
        )

        self.request_duration_seconds = Histogram(
            "superego_request_duration_seconds",
            "Request processing time",
            ["method", "transport"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry,
        )

        self.requests_in_flight = Gauge(
            "superego_requests_in_flight",
            "Current requests being processed",
            ["transport"],
            registry=self.registry,
        )

        # Transport metrics
        self.http_requests_total = Counter(
            "superego_http_requests_total",
            "HTTP transport requests",
            ["method", "status_code"],
            registry=self.registry,
        )

        self.websocket_connections_active = Gauge(
            "superego_websocket_connections_active",
            "Active WebSocket connections",
            registry=self.registry,
        )

        self.sse_clients_active = Gauge(
            "superego_sse_clients_active", "Active SSE clients", registry=self.registry
        )

        # Security metrics
        self.security_evaluations_total = Counter(
            "superego_security_evaluations_total",
            "Security evaluations by action",
            ["action", "rule_id"],
            registry=self.registry,
        )

        self.ai_sampling_requests_total = Counter(
            "superego_ai_sampling_requests_total",
            "AI sampling requests",
            ["provider", "status"],
            registry=self.registry,
        )

        self.rule_evaluation_duration = Histogram(
            "superego_rule_evaluation_duration_seconds",
            "Rule evaluation time",
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
            registry=self.registry,
        )

        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            "superego_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["service"],
            registry=self.registry,
        )

        self.circuit_breaker_failures = Counter(
            "superego_circuit_breaker_failures_total",
            "Circuit breaker failure count",
            ["service"],
            registry=self.registry,
        )

        # Queue metrics
        self.queue_size = Gauge(
            "superego_queue_size",
            "Current queue size",
            ["queue_name"],
            registry=self.registry,
        )

        self.queue_wait_time = Histogram(
            "superego_queue_wait_time_seconds",
            "Time spent waiting in queue",
            ["queue_name"],
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry,
        )

        # System metrics
        self.memory_usage_bytes = Gauge(
            "superego_memory_usage_bytes",
            "Memory usage in bytes",
            registry=self.registry,
        )

        self.cpu_usage_percent = Gauge(
            "superego_cpu_usage_percent", "CPU usage percentage", registry=self.registry
        )

        self.open_file_descriptors = Gauge(
            "superego_open_file_descriptors",
            "Open file descriptors",
            registry=self.registry,
        )

        # Cache metrics
        self.cache_hits = Counter(
            "superego_cache_hits_total",
            "Cache hit count",
            ["cache_name"],
            registry=self.registry,
        )

        self.cache_misses = Counter(
            "superego_cache_misses_total",
            "Cache miss count",
            ["cache_name"],
            registry=self.registry,
        )

        self.cache_size = Gauge(
            "superego_cache_size",
            "Current cache size",
            ["cache_name"],
            registry=self.registry,
        )

    async def record_request(
        self, method: str, transport: str, duration: float, status: str = "success"
    ) -> None:
        """Record request metrics.

        Args:
            method: Request method/tool name
            transport: Transport type (http, websocket, sse, stdio)
            duration: Request duration in seconds
            status: Request status (success, error)
        """
        self.requests_total.labels(
            method=method, transport=transport, status=status
        ).inc()

        self.request_duration_seconds.labels(
            method=method, transport=transport
        ).observe(duration)

    async def record_security_evaluation(
        self, action: str, rule_id: Optional[str], duration: float
    ) -> None:
        """Record security evaluation metrics.

        Args:
            action: Decision action (allow, deny, sample)
            rule_id: Matching rule ID
            duration: Evaluation duration in seconds
        """
        self.security_evaluations_total.labels(
            action=action, rule_id=rule_id or "default"
        ).inc()

        self.rule_evaluation_duration.observe(duration)

    async def record_ai_sampling(self, provider: str, status: str) -> None:
        """Record AI sampling request.

        Args:
            provider: AI provider name
            status: Request status (success, error, timeout)
        """
        self.ai_sampling_requests_total.labels(provider=provider, status=status).inc()

    async def update_circuit_breaker(
        self, service: str, state: str, failures: int
    ) -> None:
        """Update circuit breaker metrics.

        Args:
            service: Service name
            state: Circuit breaker state
            failures: Current failure count
        """
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, -1)
        self.circuit_breaker_state.labels(service=service).set(state_value)

        if failures > 0:
            self.circuit_breaker_failures.labels(service=service).inc(failures)

    async def update_queue_metrics(
        self, queue_name: str, size: int, wait_time: Optional[float] = None
    ) -> None:
        """Update queue metrics.

        Args:
            queue_name: Queue identifier
            size: Current queue size
            wait_time: Time spent waiting in queue
        """
        self.queue_size.labels(queue_name=queue_name).set(size)

        if wait_time is not None:
            self.queue_wait_time.labels(queue_name=queue_name).observe(wait_time)

    async def update_cache_metrics(self, cache_name: str, hit: bool, size: int) -> None:
        """Update cache metrics.

        Args:
            cache_name: Cache identifier
            hit: Whether it was a cache hit
            size: Current cache size
        """
        if hit:
            self.cache_hits.labels(cache_name=cache_name).inc()
        else:
            self.cache_misses.labels(cache_name=cache_name).inc()

        self.cache_size.labels(cache_name=cache_name).set(size)

    async def collect_system_metrics(self) -> None:
        """Collect system-level metrics."""
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            self.memory_usage_bytes.set(memory.used)

            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_usage_percent.set(cpu_percent)

            # File descriptor metrics
            process = psutil.Process()
            num_fds = process.num_fds() if hasattr(process, "num_fds") else 0
            self.open_file_descriptors.set(num_fds)

        except Exception as e:
            logger.error("Failed to collect system metrics", error=str(e))

    def increment_active_connections(self, transport: str) -> None:
        """Increment active connection count.

        Args:
            transport: Transport type
        """
        if transport == "websocket":
            self.websocket_connections_active.inc()
        elif transport == "sse":
            self.sse_clients_active.inc()

    def decrement_active_connections(self, transport: str) -> None:
        """Decrement active connection count.

        Args:
            transport: Transport type
        """
        if transport == "websocket":
            self.websocket_connections_active.dec()
        elif transport == "sse":
            self.sse_clients_active.dec()

    def track_request(self, transport: str) -> Callable:
        """Context manager to track in-flight requests.

        Args:
            transport: Transport type

        Returns:
            Context manager for tracking
        """

        class RequestTracker:
            def __init__(self, gauge: Gauge, transport: str):
                self.gauge = gauge
                self.transport = transport

            def __enter__(self):
                self.gauge.labels(transport=self.transport).inc()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.gauge.labels(transport=self.transport).dec()

        return RequestTracker(self.requests_in_flight, transport)

    async def record_custom_metric(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a custom metric value.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
        """
        async with self._lock:
            metric = MetricValue(value=value, labels=labels or {})
            self._custom_metrics[name].append(metric)

            # Keep only last 1000 values per metric
            if len(self._custom_metrics[name]) > 1000:
                self._custom_metrics[name] = self._custom_metrics[name][-1000:]

    async def get_custom_metrics(self) -> Dict[str, List[MetricValue]]:
        """Get all custom metrics.

        Returns:
            Dictionary of metric names to values
        """
        async with self._lock:
            return dict(self._custom_metrics)

    def get_prometheus_metrics(self) -> bytes:
        """Get metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics
        """
        return generate_latest(self.registry)

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics.

        Returns:
            Dictionary with metric summaries
        """
        # Collect current system metrics
        await self.collect_system_metrics()

        # Get custom metrics
        custom = await self.get_custom_metrics()

        # Build summary
        summary = {
            "uptime_seconds": time.time() - self._start_time,
            "timestamp": datetime.utcnow().isoformat(),
            "custom_metrics": {
                name: {
                    "count": len(values),
                    "latest": values[-1].value if values else None,
                    "latest_timestamp": values[-1].timestamp if values else None,
                }
                for name, values in custom.items()
            },
        }

        return summary

    async def calculate_percentiles(
        self, metric_name: str, percentiles: List[int] = [50, 90, 95, 99]
    ) -> Dict[int, float]:
        """Calculate percentiles for a custom metric.

        Args:
            metric_name: Name of the metric
            percentiles: List of percentiles to calculate

        Returns:
            Dictionary of percentile to value
        """
        async with self._lock:
            values = self._custom_metrics.get(metric_name, [])
            if not values:
                return {p: 0.0 for p in percentiles}

            sorted_values = sorted(v.value for v in values)
            result = {}

            for p in percentiles:
                idx = int(len(sorted_values) * p / 100)
                idx = min(idx, len(sorted_values) - 1)
                result[p] = sorted_values[idx]

            return result
