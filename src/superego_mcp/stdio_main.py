"""STDIO entry point for Superego MCP Server - for FastAgent integration."""

import asyncio
import logging
import sys
from pathlib import Path

from fastmcp import FastMCP

from .domain.security_policy import SecurityPolicyEngine
from .infrastructure.ai_service import AIServiceManager
from .infrastructure.circuit_breaker import CircuitBreaker
from .infrastructure.config import ConfigManager
from .infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor
from .infrastructure.prompt_builder import SecurePromptBuilder
from .presentation.mcp_server import create_server


async def initialize_server_components() -> FastMCP:
    """Initialize all server components for STDIO mode."""
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()

        # Initialize configuration paths
        config_dir = Path("config")
        rules_file = config_dir / "rules.yaml"

        # Ensure config directory and rules file exist
        config_dir.mkdir(exist_ok=True)
        if not rules_file.exists():
            # Create default rules file if it doesn't exist
            default_rules = {
                "rules": [
                    {
                        "id": "allow_safe_reads",
                        "priority": 10,
                        "action": "allow",
                        "reason": "Safe file reading operations",
                        "conditions": {
                            "tool_name": "read_file|list_files|search_files"
                        },
                    },
                    {
                        "id": "block_dangerous_system",
                        "priority": 5,
                        "action": "deny",
                        "reason": "Dangerous system operations blocked",
                        "conditions": {
                            "parameters": "sudo|rm -rf|/etc/passwd|/etc/shadow"
                        },
                    },
                    {
                        "id": "evaluate_complex_ops",
                        "priority": 15,
                        "action": "sample",
                        "reason": "Complex operations require evaluation",
                        "conditions": {
                            "tool_name": "write_file|execute_command|fetch_url"
                        },
                    },
                ]
            }

            import yaml

            with open(rules_file, "w") as f:
                yaml.safe_dump(default_rules, f, default_flow_style=False, indent=2)

        # Create components
        error_handler = ErrorHandler()
        audit_logger = AuditLogger()
        health_monitor = HealthMonitor()

        # Create AI components if enabled
        ai_service_manager = None
        prompt_builder = None

        if config.ai_sampling.enabled:
            # Create AI service manager with circuit breaker (using defaults)
            circuit_breaker = CircuitBreaker(
                failure_threshold=5,  # Default values
                timeout_seconds=30,
                recovery_timeout=60,
            )

            ai_service_manager = AIServiceManager(
                config=config.ai_sampling,  # Use the config directly
                circuit_breaker=circuit_breaker,
            )

            prompt_builder = SecurePromptBuilder()

        # Create security policy engine
        security_policy_engine = SecurityPolicyEngine(
            rules_file=rules_file,
            health_monitor=health_monitor,
            ai_service_manager=ai_service_manager,
            prompt_builder=prompt_builder,
        )

        # Create and initialize the MCP server with all dependencies
        mcp_server = await create_server(
            security_policy_engine=security_policy_engine,
            audit_log=audit_logger,
            err_handler=error_handler,
            health_mon=health_monitor,
            show_decisions=True,  # Enable security decision visibility
        )

        return mcp_server

    except Exception as e:
        logging.error(f"Failed to initialize server components: {e}")
        import traceback

        traceback.print_exc()
        raise


def main() -> None:
    """Main STDIO entry point for FastAgent integration."""
    # Setup logging for STDIO mode
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(
                sys.stderr
            )  # Log to stderr to avoid interfering with STDIO
        ],
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Superego MCP Server in STDIO mode...")

    try:
        # Initialize server components synchronously in a temporary event loop
        mcp_server = None

        # Use a temporary event loop to initialize components
        async def _init() -> FastMCP:
            return await initialize_server_components()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            mcp_server = loop.run_until_complete(_init())
        finally:
            loop.close()

        logger.info("Starting STDIO transport...")
        # Run the server with STDIO transport (this starts its own event loop)
        mcp_server.run(transport="stdio")

    except KeyboardInterrupt:
        logger.info("STDIO server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"STDIO server failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


# Allow running as python -m superego_mcp.stdio_main
def __main__() -> None:
    main()
