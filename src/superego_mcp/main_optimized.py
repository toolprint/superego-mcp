"""Main entry point for Superego MCP Server with performance optimizations."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from .domain.models import *
from .domain.security_policy_optimized import OptimizedSecurityPolicyEngine
from .infrastructure.ai_service_optimized import OptimizedAIServiceManager
from .infrastructure.circuit_breaker import CircuitBreaker
from .infrastructure.config import ConfigManager
from .infrastructure.config_watcher import ConfigWatcher
from .infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor
from .infrastructure.metrics import MetricsCollector
from .infrastructure.performance import (
    ConnectionPool,
    PerformanceMonitor,
    ResponseCache,
)
from .infrastructure.prompt_builder import SecurePromptBuilder
from .infrastructure.request_queue import RequestQueue
from .presentation.monitoring import AlertManager, MonitoringDashboard


def main():
    """Main application bootstrap with performance optimizations"""
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Run the async main function
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


async def async_main():
    """Async main function with lifecycle management and performance enhancements"""
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize configuration paths
    config_dir = Path("config")
    rules_file = config_dir / "rules.yaml"

    # Create core components
    error_handler = ErrorHandler()
    audit_logger = AuditLogger()
    health_monitor = HealthMonitor()
    
    # Create performance components
    metrics_collector = MetricsCollector()
    performance_monitor = PerformanceMonitor()
    
    # Create shared connection pool
    connection_pool = None
    if config.performance.connection_pooling:
        connection_pool = ConnectionPool(
            max_connections=config.performance.connection_pooling.max_connections,
            max_keepalive_connections=config.performance.connection_pooling.max_keepalive_connections,
            keepalive_expiry=config.performance.connection_pooling.keepalive_timeout
        )
    
    # Create response cache
    response_cache = ResponseCache(
        max_size=config.performance.caching.pattern_cache_size,
        default_ttl=config.performance.caching.response_cache_ttl
    )
    
    # Create request queue for AI sampling
    request_queue = None
    if config.ai_sampling.enabled and config.performance.request_queue:
        request_queue = RequestQueue(
            max_size=config.performance.request_queue.max_size,
            default_timeout=config.performance.request_queue.timeout_seconds,
            max_concurrent=config.performance.request_queue.ai_sampling_concurrency,
            enable_backpressure=config.performance.request_queue.enable_backpressure
        )
    
    # Create AI components if enabled
    ai_service_manager = None
    prompt_builder = None
    
    if config.ai_sampling.enabled:
        # Create circuit breaker for AI service
        ai_circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
            timeout_seconds=config.ai_sampling.timeout_seconds
        )
        
        # Create optimized AI service manager
        ai_service_manager = OptimizedAIServiceManager(
            config=config.ai_sampling,
            circuit_breaker=ai_circuit_breaker,
            connection_pool=connection_pool,
            response_cache=response_cache,
            request_queue=request_queue,
            metrics_collector=metrics_collector
        )
        
        # Create secure prompt builder
        prompt_builder = SecurePromptBuilder()
        
        # Start request queue if created
        if request_queue:
            await request_queue.start(ai_service_manager._evaluate_direct)
        
        print(f"AI sampling enabled with primary provider: {config.ai_sampling.primary_provider}")
        print(f"Request queue configured with max size: {config.performance.request_queue.max_size}")
    
    # Create optimized security policy
    security_policy = OptimizedSecurityPolicyEngine(
        rules_file=rules_file,
        ai_service_manager=ai_service_manager,
        prompt_builder=prompt_builder,
        response_cache=response_cache,
        performance_monitor=performance_monitor,
        metrics_collector=metrics_collector
    )

    # Create config watcher with reload callback
    config_watcher = ConfigWatcher(
        watch_path=rules_file,
        reload_callback=security_policy.reload_rules,
        debounce_seconds=1.0,
    )

    # Register components for health monitoring
    health_monitor.register_component("security_policy", security_policy)
    health_monitor.register_component("audit_logger", audit_logger)
    health_monitor.register_component("config_watcher", config_watcher)
    if ai_service_manager:
        health_monitor.register_component("ai_service", ai_service_manager)
    if request_queue:
        health_monitor.register_component("request_queue", request_queue)

    print("Starting Superego MCP Server with performance optimizations...")

    # Create multi-transport server
    from .presentation.transport_server import MultiTransportServer

    multi_transport_server = MultiTransportServer(
        security_policy=security_policy,
        audit_logger=audit_logger,
        error_handler=error_handler,
        health_monitor=health_monitor,
        config=config,
    )
    
    # Create monitoring dashboard if metrics enabled
    monitoring_dashboard = None
    alert_manager = None
    
    if config.performance.metrics_enabled:
        alert_manager = AlertManager()
        monitoring_dashboard = MonitoringDashboard(
            metrics_collector=metrics_collector,
            performance_monitor=performance_monitor,
            health_monitor=health_monitor,
            port=config.performance.metrics_port
        )
        await monitoring_dashboard.start()
        print(f"Monitoring dashboard available at http://localhost:{config.performance.metrics_port}/dashboard")
        print(f"Prometheus metrics available at http://localhost:{config.performance.metrics_port}/metrics")

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        print("\nShutdown signal received...")
        shutdown_event.set()

    # Register signal handlers for graceful shutdown
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler())

    # Start background tasks
    background_tasks = []
    
    # Periodic metrics collection
    async def collect_metrics():
        while not shutdown_event.is_set():
            await metrics_collector.collect_system_metrics()
            
            # Check alerts if alert manager configured
            if alert_manager:
                metrics_summary = await metrics_collector.get_metrics_summary()
                alerts = await alert_manager.check_alerts(metrics_summary)
                for alert in alerts:
                    print(f"ALERT: {alert['name']} - {alert['severity']}: {alert['current_value']} > {alert['threshold']}")
            
            await asyncio.sleep(5)
    
    if config.performance.metrics_enabled:
        metrics_task = asyncio.create_task(collect_metrics())
        background_tasks.append(metrics_task)

    try:
        # Start config watcher
        await config_watcher.start()
        
        print("Configuration hot-reload enabled")
        
        # Log enabled transports
        enabled_transports = []
        if getattr(config, 'transport', None):
            for transport_name, transport_config in config.transport.model_dump().items():
                if transport_config.get('enabled', False) or transport_name == 'stdio':
                    enabled_transports.append(transport_name.upper())
        
        print(f"Enabled transports: {', '.join(enabled_transports) if enabled_transports else 'STDIO only'}")
        
        # Log performance configuration
        print("\nPerformance optimizations enabled:")
        print(f"- Response caching: TTL={config.performance.caching.response_cache_ttl}s")
        print(f"- Connection pooling: max={config.performance.connection_pooling.max_connections}")
        print(f"- Request queue: size={config.performance.request_queue.max_size}, concurrency={config.performance.request_queue.ai_sampling_concurrency}")
        if config.performance.batching.enabled:
            print(f"- Request batching: size={config.performance.batching.batch_size}, timeout={config.performance.batching.batch_timeout}s")
        
        print("\nServer ready - press Ctrl+C to stop")

        # Run server in a separate task to allow for graceful shutdown
        server_task = asyncio.create_task(multi_transport_server.start())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either server completion or shutdown signal
        done, pending = await asyncio.wait(
            [server_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    finally:
        # Stop background tasks
        for task in background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Cleanup resources
        print("Stopping multi-transport server...")
        await multi_transport_server.stop()
        
        print("Stopping configuration watcher...")
        await config_watcher.stop()
        
        # Stop monitoring dashboard
        if monitoring_dashboard:
            print("Stopping monitoring dashboard...")
            await monitoring_dashboard.stop()
        
        # Stop request queue
        if request_queue:
            print("Stopping request queue...")
            await request_queue.stop()
        
        # Cleanup AI service if initialized
        if ai_service_manager:
            print("Closing AI service connections...")
            await ai_service_manager.close()
        
        # Close connection pool
        if connection_pool:
            print("Closing connection pool...")
            await connection_pool.close()
        
        # Print final metrics summary
        if config.performance.metrics_enabled:
            print("\nFinal performance metrics:")
            metrics_summary = await metrics_collector.get_metrics_summary()
            print(f"- Uptime: {metrics_summary['uptime_seconds']:.1f}s")
            
            if request_queue:
                queue_stats = request_queue.get_stats()
                print(f"- Requests processed: {queue_stats['total_processed']}")
                print(f"- Success rate: {queue_stats['success_rate']:.2%}")
            
            cache_stats = await response_cache.get_stats()
            print(f"- Cache hit rate: {cache_stats['hit_rate']:.2%}")
        
        print("Server shutdown complete")


def run_optimized_server():
    """Run the optimized MCP server"""
    main()


def cli_main():
    """CLI entry point for the optimized server."""
    main()


if __name__ == "__main__":
    main()