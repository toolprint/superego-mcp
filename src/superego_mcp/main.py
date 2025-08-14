"""Main entry point for Superego MCP Server."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from .domain.security_policy import SecurityPolicyEngine
from .infrastructure.ai_service import AIServiceManager
from .infrastructure.circuit_breaker import CircuitBreaker
from .infrastructure.config import ConfigManager
from .infrastructure.config_watcher import ConfigWatcher
from .infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor
from .infrastructure.inference import InferenceConfig, InferenceStrategyManager
from .infrastructure.prompt_builder import SecurePromptBuilder


def main() -> None:
    """Main application bootstrap with hot-reload support"""
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


async def async_main() -> None:
    """Async main function with lifecycle management"""
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()

    # Initialize configuration paths
    config_dir = Path("config")
    rules_file = config_dir / "rules.yaml"

    # Create components
    error_handler = ErrorHandler()
    audit_logger = AuditLogger()
    health_monitor = HealthMonitor()

    # Create AI components if enabled (legacy support)
    ai_service_manager = None
    prompt_builder = None

    if config.ai_sampling.enabled:
        # Create circuit breaker for AI service
        ai_circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
            timeout_seconds=config.ai_sampling.timeout_seconds,
        )

        # Create AI service manager
        ai_service_manager = AIServiceManager(
            config=config.ai_sampling, circuit_breaker=ai_circuit_breaker
        )

        # Create secure prompt builder
        prompt_builder = SecurePromptBuilder()

        print(
            f"AI sampling enabled with primary provider: {config.ai_sampling.primary_provider}"
        )

    # Create inference system (new extensible system)
    inference_manager = None
    if hasattr(config, "inference") and config.inference:
        # Always create prompt builder if not already created
        if not prompt_builder:
            prompt_builder = SecurePromptBuilder()

        # Create inference strategy manager
        dependencies = {
            "ai_service_manager": ai_service_manager,
            "prompt_builder": prompt_builder,
        }

        inference_manager = InferenceStrategyManager(
            config=config.inference, dependencies=dependencies
        )

        print(
            f"Inference system initialized with {len(inference_manager.providers)} provider(s): {list(inference_manager.providers.keys())}"
        )
    elif ai_service_manager and prompt_builder:
        # Fallback: create minimal inference config for backward compatibility
        fallback_config = InferenceConfig()
        dependencies = {
            "ai_service_manager": ai_service_manager,
            "prompt_builder": prompt_builder,
        }

        inference_manager = InferenceStrategyManager(
            config=fallback_config, dependencies=dependencies
        )

        print("Inference system initialized in backward compatibility mode")

    # Create security policy with all dependencies
    security_policy = SecurityPolicyEngine(
        rules_file=rules_file,
        health_monitor=health_monitor,
        ai_service_manager=ai_service_manager,
        prompt_builder=prompt_builder,
        inference_manager=inference_manager,
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

    print("Starting Superego MCP Server with hot-reload support...")

    # Create multi-transport server
    from .presentation.transport_server import MultiTransportServer

    multi_transport_server = MultiTransportServer(
        security_policy=security_policy,
        audit_logger=audit_logger,
        error_handler=error_handler,
        health_monitor=health_monitor,
        config=config,
    )

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        print("\nShutdown signal received...")
        shutdown_event.set()

    # Register signal handlers for graceful shutdown
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler())

    try:
        # Start config watcher
        await config_watcher.start()

        print("Configuration hot-reload enabled")

        # Log enabled transports
        enabled_transports = []
        if getattr(config, "transport", None):
            for (
                transport_name,
                transport_config,
            ) in config.transport.model_dump().items():
                if transport_config.get("enabled", False) or transport_name == "stdio":
                    enabled_transports.append(transport_name.upper())

        print(
            f"Enabled transports: {', '.join(enabled_transports) if enabled_transports else 'STDIO only'}"
        )
        print("Server ready - press Ctrl+C to stop")

        # Run server in a separate task to allow for graceful shutdown
        server_task = asyncio.create_task(multi_transport_server.start())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either server completion or shutdown signal
        done, pending = await asyncio.wait(
            [server_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    finally:
        # Cleanup resources
        print("Stopping multi-transport server...")
        await multi_transport_server.stop()

        print("Stopping configuration watcher...")
        await config_watcher.stop()

        # Cleanup AI service if initialized
        if ai_service_manager:
            print("Closing AI service connections...")
            await ai_service_manager.close()

        # Cleanup inference system if initialized
        if inference_manager:
            print("Cleaning up inference system...")
            await inference_manager.cleanup()

        print("Server shutdown complete")


def run_server_with_stdio() -> None:
    """Run the MCP server with STDIO transport"""
    from .presentation import mcp_server

    # This will run synchronously and block
    mcp_server.run_stdio_server()


def cli_main() -> None:
    """CLI entry point for the server."""
    main()


if __name__ == "__main__":
    main()
