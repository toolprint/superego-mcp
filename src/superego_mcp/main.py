"""Main entry point for Superego MCP Server."""

import logging
from pathlib import Path

from .domain.models import *
from .domain.security_policy import SecurityPolicyEngine
from .infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor


def main():
    """Main application bootstrap"""

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Initialize configuration paths
    config_dir = Path("config")
    rules_file = config_dir / "rules.yaml"

    # Create components
    security_policy = SecurityPolicyEngine(rules_file)
    error_handler = ErrorHandler()
    audit_logger = AuditLogger()
    health_monitor = HealthMonitor()

    # Register components for health monitoring
    health_monitor.register_component("security_policy", security_policy)
    health_monitor.register_component("audit_logger", audit_logger)

    print("Starting Superego MCP Server with STDIO transport...")

    # Set up global components for FastMCP
    from .presentation import mcp_server

    mcp_server.security_policy = security_policy
    mcp_server.audit_logger = audit_logger
    mcp_server.error_handler = error_handler
    mcp_server.health_monitor = health_monitor

    # Run with STDIO transport
    mcp_server.run_stdio_server()


def cli_main():
    """CLI entry point for the server."""
    main()


if __name__ == "__main__":
    main()
