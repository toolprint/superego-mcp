"""Main entry point for Superego MCP Server."""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from .domain.security_policy import SecurityPolicyEngine
from .infrastructure.ai_service import AIServiceManager
from .infrastructure.circuit_breaker import CircuitBreaker
from .infrastructure.config import ConfigManager
from .infrastructure.config_watcher import ConfigWatcher
from .infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor
from .infrastructure.inference import InferenceConfig as InferenceStrategyConfig
from .infrastructure.inference import InferenceStrategyManager
from .infrastructure.prompt_builder import SecurePromptBuilder


def main() -> None:
    """Main application bootstrap with hot-reload support"""
    # Configure logging using explicit environment variables
    log_format = os.getenv("SUPEREGO_LOG_FORMAT", "console")  # console|json
    log_handler = os.getenv("SUPEREGO_LOG_HANDLER", "print")  # print|write
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    from .infrastructure.logging_config import configure_logging_explicit
    configure_logging_explicit(
        log_format=log_format,
        log_handler=log_handler,
        level=log_level,
        stream=sys.stderr  # Always use stderr to avoid conflicts with STDIO transport
    )

    # Run the async main function
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


async def async_main(transport: str | None = None, port: int | None = None) -> None:
    """Async main function with lifecycle management"""
    # Logging is now configured in main() function using environment variables

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()

    # Initialize configuration paths from loaded config
    rules_file = Path(config.rules_file)

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

        # Convert config format - need to convert between different CLIProviderConfig types
        from .infrastructure.inference import (
            CLIProviderConfig as InferenceCLIProviderConfig,
        )

        converted_cli_providers = []
        for cli_provider in config.inference.cli_providers:
            converted_cli_providers.append(
                InferenceCLIProviderConfig(
                    name=cli_provider.name,
                    enabled=cli_provider.enabled,
                    type=cli_provider.type,
                    command=cli_provider.command,
                    model=cli_provider.model,
                    system_prompt=cli_provider.system_prompt,
                    api_key_env_var=cli_provider.api_key_env_var,
                    max_retries=getattr(cli_provider, "max_retries", 2),
                    retry_delay_ms=getattr(cli_provider, "retry_delay_ms", 1000),
                    timeout_seconds=getattr(cli_provider, "timeout_seconds", 30),
                )
            )

        strategy_config = InferenceStrategyConfig(
            timeout_seconds=config.inference.timeout_seconds,
            provider_preference=config.inference.provider_preference,
            cli_providers=converted_cli_providers,
            api_providers=config.inference.api_providers,
        )

        inference_manager = InferenceStrategyManager(
            config=strategy_config, dependencies=dependencies
        )

        print(
            f"Inference system initialized with {len(inference_manager.providers)} provider(s): {list(inference_manager.providers.keys())}"
        )
    elif ai_service_manager and prompt_builder:
        # Fallback: create minimal inference config for backward compatibility
        fallback_config = InferenceStrategyConfig()
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

    # Create unified server (FastAPI + MCP in single process)
    from .presentation.unified_server import UnifiedServer

    unified_server = UnifiedServer(
        security_policy=security_policy,
        audit_logger=audit_logger,
        error_handler=error_handler,
        health_monitor=health_monitor,
        config=config,
        cli_transport=transport,
        cli_port=port,
    )

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()
    shutdown_count = 0

    def signal_handler(signum: int, frame: Any) -> None:
        nonlocal shutdown_count
        shutdown_count += 1

        if shutdown_count == 1:
            print("\nShutdown signal received...")
            shutdown_event.set()
        elif shutdown_count == 2:
            print("\nSecond shutdown signal received, forcing exit...")
            import os

            os._exit(1)
        else:
            print("\nMultiple shutdown signals received, forcing immediate exit...")
            import os

            os._exit(2)

    # Register signal handlers for graceful shutdown
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, signal_handler)

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
        server_task = asyncio.create_task(unified_server.start())
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
        print("Stopping unified server...")
        await unified_server.stop()

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

        # Add a small delay to allow any final cleanup
        await asyncio.sleep(0.1)


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
