"""Observability dashboard and monitoring endpoints for Superego MCP Server."""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from aiohttp import web
from aiohttp_sse import sse_response

from ..infrastructure.metrics import MetricsCollector
from ..infrastructure.performance import PerformanceMonitor

logger = structlog.get_logger(__name__)


class MonitoringDashboard:
    """HTTP endpoints for metrics and monitoring dashboard."""
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        performance_monitor: PerformanceMonitor,
        health_monitor: Any,  # HealthMonitor from error_handler
        port: int = 9090
    ):
        """Initialize monitoring dashboard.
        
        Args:
            metrics_collector: Metrics collector instance
            performance_monitor: Performance monitor instance
            health_monitor: Health monitor instance
            port: Port for metrics endpoint
        """
        self.metrics_collector = metrics_collector
        self.performance_monitor = performance_monitor
        self.health_monitor = health_monitor
        self.port = port
        self.app = web.Application()
        self._setup_routes()
        self.runner: Optional[web.AppRunner] = None
        
    def _setup_routes(self) -> None:
        """Set up HTTP routes."""
        self.app.router.add_get('/metrics', self.handle_metrics)
        self.app.router.add_get('/health', self.handle_health)
        self.app.router.add_get('/dashboard', self.handle_dashboard)
        self.app.router.add_get('/api/metrics/summary', self.handle_metrics_summary)
        self.app.router.add_get('/api/performance', self.handle_performance)
        self.app.router.add_get('/api/metrics/stream', self.handle_metrics_stream)
        
    async def start(self) -> None:
        """Start monitoring dashboard."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info("Monitoring dashboard started", port=self.port)
        
    async def stop(self) -> None:
        """Stop monitoring dashboard."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Monitoring dashboard stopped")
            
    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics endpoint (Prometheus format).
        
        Args:
            request: HTTP request
            
        Returns:
            Prometheus-formatted metrics
        """
        try:
            # Collect latest system metrics
            await self.metrics_collector.collect_system_metrics()
            
            # Get Prometheus metrics
            metrics_data = self.metrics_collector.get_prometheus_metrics()
            
            return web.Response(
                body=metrics_data,
                content_type='text/plain; version=0.0.4'
            )
        except Exception as e:
            logger.error("Failed to generate metrics", error=str(e))
            return web.Response(
                text=f"# Error generating metrics: {str(e)}",
                status=500
            )
            
    async def handle_health(self, request: web.Request) -> web.Response:
        """Handle /health endpoint.
        
        Args:
            request: HTTP request
            
        Returns:
            Health check response
        """
        try:
            health_status = await self.health_monitor.check_health()
            status_code = 200 if health_status.status == "healthy" else 503
            
            return web.json_response(
                health_status.model_dump(),
                status=status_code
            )
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return web.json_response(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                },
                status=503
            )
            
    async def handle_dashboard(self, request: web.Request) -> web.Response:
        """Handle /dashboard endpoint.
        
        Args:
            request: HTTP request
            
        Returns:
            HTML dashboard
        """
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Superego MCP Monitoring Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
            margin: 10px 0;
        }
        .metric-label {
            color: #666;
            font-size: 0.9em;
        }
        .chart-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-healthy { background-color: #28a745; }
        .status-unhealthy { background-color: #dc3545; }
        .status-degraded { background-color: #ffc107; }
        #performance-chart {
            height: 300px;
        }
        .refresh-info {
            text-align: right;
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Superego MCP Monitoring Dashboard</h1>
        
        <div class="refresh-info">
            Auto-refresh: <span id="refresh-countdown">5</span>s
        </div>
        
        <div class="metrics-grid" id="metrics-grid">
            <!-- Metrics cards will be inserted here -->
        </div>
        
        <div class="chart-container">
            <h2>Request Latency (last 5 minutes)</h2>
            <canvas id="performance-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>System Health</h2>
            <div id="health-status">Loading...</div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // Metrics update function
        async function updateMetrics() {
            try {
                const response = await fetch('/api/metrics/summary');
                const data = await response.json();
                
                const metricsGrid = document.getElementById('metrics-grid');
                metricsGrid.innerHTML = '';
                
                // Add metric cards
                const metrics = [
                    { label: 'Uptime', value: formatUptime(data.uptime_seconds) },
                    { label: 'Total Requests', value: data.total_requests || '0' },
                    { label: 'Active Connections', value: data.active_connections || '0' },
                    { label: 'Cache Hit Rate', value: formatPercent(data.cache_hit_rate) },
                    { label: 'Queue Size', value: data.queue_size || '0' },
                    { label: 'Memory Usage', value: formatBytes(data.memory_usage) }
                ];
                
                metrics.forEach(metric => {
                    const card = document.createElement('div');
                    card.className = 'metric-card';
                    card.innerHTML = `
                        <div class="metric-label">${metric.label}</div>
                        <div class="metric-value">${metric.value}</div>
                    `;
                    metricsGrid.appendChild(card);
                });
                
            } catch (error) {
                console.error('Failed to update metrics:', error);
            }
        }
        
        // Health status update
        async function updateHealth() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                
                const healthDiv = document.getElementById('health-status');
                const statusClass = `status-${data.status}`;
                
                healthDiv.innerHTML = `
                    <p><span class="status-indicator ${statusClass}"></span>
                    Overall Status: <strong>${data.status}</strong></p>
                    <p>Components:</p>
                    <ul>
                        ${Object.entries(data.components || {}).map(([name, info]) => `
                            <li>${name}: ${info.status} ${info.message || ''}</li>
                        `).join('')}
                    </ul>
                `;
            } catch (error) {
                console.error('Failed to update health:', error);
            }
        }
        
        // Performance chart
        let performanceChart;
        function initPerformanceChart() {
            const ctx = document.getElementById('performance-chart').getContext('2d');
            performanceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'P50',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }, {
                        label: 'P95',
                        data: [],
                        borderColor: 'rgb(255, 159, 64)',
                        tension: 0.1
                    }, {
                        label: 'P99',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Latency (ms)'
                            }
                        }
                    }
                }
            });
        }
        
        // Update performance chart
        async function updatePerformanceChart() {
            try {
                const response = await fetch('/api/performance');
                const data = await response.json();
                
                if (data.request_latency) {
                    const timestamp = new Date().toLocaleTimeString();
                    
                    performanceChart.data.labels.push(timestamp);
                    performanceChart.data.datasets[0].data.push(data.request_latency.p50 * 1000);
                    performanceChart.data.datasets[1].data.push(data.request_latency.p95 * 1000);
                    performanceChart.data.datasets[2].data.push(data.request_latency.p99 * 1000);
                    
                    // Keep only last 30 data points
                    if (performanceChart.data.labels.length > 30) {
                        performanceChart.data.labels.shift();
                        performanceChart.data.datasets.forEach(dataset => {
                            dataset.data.shift();
                        });
                    }
                    
                    performanceChart.update();
                }
            } catch (error) {
                console.error('Failed to update performance chart:', error);
            }
        }
        
        // Utility functions
        function formatUptime(seconds) {
            const days = Math.floor(seconds / 86400);
            const hours = Math.floor((seconds % 86400) / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            
            if (days > 0) return `${days}d ${hours}h`;
            if (hours > 0) return `${hours}h ${minutes}m`;
            return `${minutes}m`;
        }
        
        function formatPercent(value) {
            if (value === undefined || value === null) return '0%';
            return `${(value * 100).toFixed(1)}%`;
        }
        
        function formatBytes(bytes) {
            if (!bytes) return '0 B';
            const units = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(1024));
            return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
        }
        
        // Auto-refresh countdown
        let refreshCountdown = 5;
        setInterval(() => {
            refreshCountdown--;
            if (refreshCountdown <= 0) {
                refreshCountdown = 5;
                updateMetrics();
                updateHealth();
                updatePerformanceChart();
            }
            document.getElementById('refresh-countdown').textContent = refreshCountdown;
        }, 1000);
        
        // Initialize
        initPerformanceChart();
        updateMetrics();
        updateHealth();
        updatePerformanceChart();
    </script>
</body>
</html>
        """
        return web.Response(text=html_content, content_type='text/html')
        
    async def handle_metrics_summary(self, request: web.Request) -> web.Response:
        """Handle /api/metrics/summary endpoint.
        
        Args:
            request: HTTP request
            
        Returns:
            JSON metrics summary
        """
        try:
            # Get metrics summary
            summary = await self.metrics_collector.get_metrics_summary()
            
            # Add additional computed metrics
            summary['total_requests'] = 0  # Would get from actual metrics
            summary['active_connections'] = 0  # Would get from actual metrics
            summary['cache_hit_rate'] = 0.0  # Would compute from cache metrics
            summary['queue_size'] = 0  # Would get from queue metrics
            summary['memory_usage'] = 0  # Would get from system metrics
            
            return web.json_response(summary)
        except Exception as e:
            logger.error("Failed to get metrics summary", error=str(e))
            return web.json_response(
                {"error": str(e)},
                status=500
            )
            
    async def handle_performance(self, request: web.Request) -> web.Response:
        """Handle /api/performance endpoint.
        
        Args:
            request: HTTP request
            
        Returns:
            JSON performance data
        """
        try:
            # Get performance percentiles
            request_latency = await self.performance_monitor.get_percentiles(
                'request_processing'
            )
            
            # Get other performance metrics
            stats = await self.performance_monitor.get_stats()
            
            return web.json_response({
                'request_latency': request_latency,
                'operation_stats': stats
            })
        except Exception as e:
            logger.error("Failed to get performance data", error=str(e))
            return web.json_response(
                {"error": str(e)},
                status=500
            )
            
    async def handle_metrics_stream(self, request: web.Request) -> web.Response:
        """Handle /api/metrics/stream endpoint (SSE).
        
        Args:
            request: HTTP request
            
        Returns:
            SSE stream of metrics
        """
        async with sse_response(request) as resp:
            try:
                while True:
                    # Get current metrics
                    summary = await self.metrics_collector.get_metrics_summary()
                    
                    # Send as SSE event
                    await resp.send(json.dumps(summary))
                    
                    # Wait before next update
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error("Metrics stream error", error=str(e))
                
        return resp


class AlertManager:
    """Manage alerts based on metric thresholds."""
    
    def __init__(self):
        """Initialize alert manager."""
        self.alert_rules = {
            'high_latency': {
                'metric': 'request_latency_p99',
                'threshold': 0.05,  # 50ms
                'duration': 60,  # 1 minute
                'severity': 'warning'
            },
            'error_rate': {
                'metric': 'error_rate',
                'threshold': 0.05,  # 5%
                'duration': 300,  # 5 minutes
                'severity': 'critical'
            },
            'memory_usage': {
                'metric': 'memory_usage_percent',
                'threshold': 80,  # 80%
                'duration': 120,  # 2 minutes
                'severity': 'warning'
            },
            'queue_backlog': {
                'metric': 'queue_size',
                'threshold': 100,
                'duration': 30,  # 30 seconds
                'severity': 'warning'
            }
        }
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
        self.alert_history: List[Dict[str, Any]] = []
        
    async def check_alerts(self, metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """Check metrics against alert rules.
        
        Args:
            metrics: Current metric values
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        current_time = time.time()
        
        for alert_name, rule in self.alert_rules.items():
            metric_value = metrics.get(rule['metric'], 0)
            
            if metric_value > rule['threshold']:
                if alert_name not in self.active_alerts:
                    # New alert
                    self.active_alerts[alert_name] = {
                        'start_time': current_time,
                        'rule': rule,
                        'current_value': metric_value
                    }
                else:
                    # Update existing alert
                    self.active_alerts[alert_name]['current_value'] = metric_value
                    
                    # Check if duration exceeded
                    duration = current_time - self.active_alerts[alert_name]['start_time']
                    if duration >= rule['duration']:
                        alert = {
                            'name': alert_name,
                            'severity': rule['severity'],
                            'metric': rule['metric'],
                            'threshold': rule['threshold'],
                            'current_value': metric_value,
                            'duration': duration,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        triggered_alerts.append(alert)
                        self.alert_history.append(alert)
                        
                        # Keep only last 1000 alerts in history
                        if len(self.alert_history) > 1000:
                            self.alert_history = self.alert_history[-1000:]
            else:
                # Metric below threshold, clear alert if exists
                if alert_name in self.active_alerts:
                    del self.active_alerts[alert_name]
                    
        return triggered_alerts
        
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get currently active alerts.
        
        Returns:
            List of active alerts
        """
        return [
            {
                'name': name,
                'severity': alert['rule']['severity'],
                'metric': alert['rule']['metric'],
                'threshold': alert['rule']['threshold'],
                'current_value': alert['current_value'],
                'duration': time.time() - alert['start_time']
            }
            for name, alert in self.active_alerts.items()
        ]
        
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of historical alerts
        """
        return self.alert_history[-limit:]