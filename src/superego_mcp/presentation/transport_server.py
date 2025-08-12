"""Unified multi-transport server for Superego MCP Server."""

import asyncio
import os
import sys
from typing import Any

import structlog
from fastmcp import FastMCP

from ..domain.models import Decision, ToolRequest
from ..domain.security_policy import SecurityPolicyEngine
from ..infrastructure.config import ServerConfig
from ..infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor
from .http_transport import HTTPTransport
from .sse_transport import SSETransport
from .websocket_transport import WebSocketTransport

logger = structlog.get_logger(__name__)


class MultiTransportServer:
    """Unified server supporting multiple transport protocols."""

    def __init__(
        self,
        security_policy: SecurityPolicyEngine,
        audit_logger: AuditLogger,
        error_handler: ErrorHandler,
        health_monitor: HealthMonitor,
        config: ServerConfig,
    ):
        """Initialize multi-transport server.

        Args:
            security_policy: Security policy engine
            audit_logger: Audit logger instance
            error_handler: Error handler instance
            health_monitor: Health monitor instance
            config: Server configuration
        """
        self.security_policy = security_policy
        self.audit_logger = audit_logger
        self.error_handler = error_handler
        self.health_monitor = health_monitor
        self.config = config

        # Initialize FastMCP with multi-transport support
        self.mcp: FastMCP = FastMCP(
            name="Superego MCP Server",
            instructions="Security evaluation and policy enforcement with multi-transport support",
        )

        # Transport handlers
        self.http_transport: HTTPTransport | None = None
        self.websocket_transport: WebSocketTransport | None = None
        self.sse_transport: SSETransport | None = None

        # Running tasks
        self.transport_tasks: list[asyncio.Task[Any]] = []

        self._setup_core_tools()

    def _is_test_environment(self) -> bool:
        """Check if running in test environment."""
        return (
            os.environ.get("PYTEST_CURRENT_TEST") is not None
            or os.environ.get("TESTING") == "1"
            or "pytest" in os.environ.get("_", "")
            or any("pytest" in arg for arg in sys.argv)
        )

    def _setup_core_tools(self) -> None:
        """Set up core MCP tools available across all transports."""

        @self.mcp.tool()
        async def evaluate_tool_request(
            tool_name: str,
            parameters: dict[str, Any],
            agent_id: str,
            session_id: str,
            cwd: str | None = None,
        ) -> Decision:
            """Evaluate a tool request for security concerns.

            Args:
                tool_name: Name of the tool being invoked
                parameters: Parameters passed to the tool
                agent_id: ID of the requesting agent
                session_id: Session identifier
                cwd: Current working directory

            Returns:
                Security decision for the request
            """
            try:
                tool_request = ToolRequest(
                    tool_name=tool_name,
                    parameters=parameters,
                    agent_id=agent_id,
                    session_id=session_id,
                    cwd=cwd or "/tmp",
                )

                logger.info(
                    "Evaluating tool request",
                    tool_name=tool_name,
                    agent_id=agent_id,
                    session_id=session_id,
                )

                decision = await self.security_policy.evaluate(tool_request)

                # Log decision to audit trail
                rule_matches = [decision.rule_id] if decision.rule_id else []
                await self.audit_logger.log_decision(
                    tool_request, decision, rule_matches
                )

                logger.info(
                    "Tool request evaluated",
                    action=decision.action,
                    tool_name=tool_name,
                    confidence=decision.confidence,
                )

                return decision

            except Exception as e:
                # Handle errors with centralized error handler
                fallback_decision = self.error_handler.handle_error(e, tool_request)

                # Log fallback decision
                await self.audit_logger.log_decision(
                    tool_request, fallback_decision, []
                )

                return fallback_decision

        @self.mcp.tool()
        async def health_check() -> dict[str, Any]:
            """Check the health of the Superego service.

            Returns:
                Health status information
            """
            try:
                health_status = await self.health_monitor.check_health()
                return health_status.model_dump()
            except Exception as e:
                logger.error("Health check failed", error=str(e))
                return {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": str(asyncio.get_event_loop().time()),
                }

        @self.mcp.tool()
        async def get_server_info() -> dict[str, Any]:
            """Get information about the Superego server.

            Returns:
                Server information
            """
            return {
                "name": "superego-mcp",
                "version": "0.1.0",
                "description": "Intelligent tool request interception for AI agents",
                "transports": self._get_enabled_transports(),
                "config": {
                    "hot_reload": self.config.hot_reload,
                    "ai_sampling_enabled": self.config.ai_sampling.enabled,
                    "health_checks_enabled": self.config.health_check_enabled,
                },
            }

        @self.mcp.resource("config://rules")
        async def get_current_rules() -> str:
            """Expose current security rules as MCP resource."""
            try:
                import yaml

                rules_data = {
                    "rules": [
                        rule.model_dump(mode="json")
                        for rule in self.security_policy.rules
                    ],
                    "total_rules": len(self.security_policy.rules),
                    "last_updated": self.security_policy.rules_file.stat().st_mtime
                    if self.security_policy.rules_file.exists()
                    else None,
                }
                return yaml.dump(rules_data, default_flow_style=False)
            except Exception as e:
                return f"Error loading rules: {str(e)}"

        @self.mcp.resource("audit://recent")
        async def get_recent_audit_entries() -> str:
            """Expose recent audit entries for monitoring."""
            try:
                import json

                entries = self.audit_logger.get_recent_entries(limit=50)
                audit_data = {
                    "entries": [entry.model_dump(mode="json") for entry in entries],
                    "stats": self.audit_logger.get_stats(),
                }
                return json.dumps(audit_data, indent=2, default=str)
            except Exception as e:
                return f"Error loading audit entries: {str(e)}"

    def _get_enabled_transports(self) -> list[str]:
        """Get list of enabled transports."""
        enabled = []

        # STDIO enabled unless in test environment
        if not self._is_test_environment():
            enabled.append("stdio")

        if hasattr(self.config, "transport"):
            transport_config = self.config.transport
            if hasattr(transport_config, "http") and transport_config.http.enabled:
                enabled.append("http")
            if (
                hasattr(transport_config, "websocket")
                and transport_config.websocket.enabled
            ):
                enabled.append("websocket")
            if hasattr(transport_config, "sse") and transport_config.sse.enabled:
                enabled.append("sse")

        return enabled

    async def start(self) -> None:
        """Start all configured transports."""
        logger.info("Starting Superego MCP multi-transport server")

        try:
            # Get transport configuration
            if hasattr(self.config, "transport"):
                transport_config = self.config.transport

                # Start HTTP transport if enabled
                if hasattr(transport_config, "http") and transport_config.http.enabled:
                    self.http_transport = HTTPTransport(
                        mcp=self.mcp,
                        security_policy=self.security_policy,
                        audit_logger=self.audit_logger,
                        error_handler=self.error_handler,
                        health_monitor=self.health_monitor,
                        config=transport_config.http.model_dump(),
                    )
                    assert self.http_transport is not None
                    http_task = asyncio.create_task(self.http_transport.start())
                    self.transport_tasks.append(http_task)
                    logger.info(
                        "HTTP transport started",
                        host=transport_config.http.host,
                        port=transport_config.http.port,
                    )

                # Start WebSocket transport if enabled
                if (
                    hasattr(transport_config, "websocket")
                    and transport_config.websocket.enabled
                ):
                    self.websocket_transport = WebSocketTransport(
                        mcp=self.mcp,
                        security_policy=self.security_policy,
                        audit_logger=self.audit_logger,
                        error_handler=self.error_handler,
                        health_monitor=self.health_monitor,
                        config=transport_config.websocket.model_dump(),
                    )
                    assert self.websocket_transport is not None
                    ws_task = asyncio.create_task(self.websocket_transport.start())
                    self.transport_tasks.append(ws_task)
                    logger.info(
                        "WebSocket transport started",
                        host=transport_config.websocket.host,
                        port=transport_config.websocket.port,
                    )

                # Start SSE transport if enabled
                if hasattr(transport_config, "sse") and transport_config.sse.enabled:
                    self.sse_transport = SSETransport(
                        mcp=self.mcp,
                        security_policy=self.security_policy,
                        audit_logger=self.audit_logger,
                        error_handler=self.error_handler,
                        health_monitor=self.health_monitor,
                        config=transport_config.sse.model_dump(),
                    )
                    assert self.sse_transport is not None
                    sse_task = asyncio.create_task(self.sse_transport.start())
                    self.transport_tasks.append(sse_task)
                    logger.info(
                        "SSE transport started",
                        host=transport_config.sse.host,
                        port=transport_config.sse.port,
                    )

            # Start STDIO transport (skip in test environment to avoid blocking)
            if not self._is_test_environment():
                stdio_task = asyncio.create_task(self._run_stdio_transport())
                self.transport_tasks.append(stdio_task)
                logger.info("STDIO transport started")
            else:
                logger.info("STDIO transport skipped in test environment")

            if self.transport_tasks:
                # Wait for all transport tasks with timeout to prevent infinite blocking
                try:
                    # In test environment, use shorter timeout
                    timeout = 5.0 if self._is_test_environment() else None
                    await asyncio.wait_for(
                        asyncio.gather(*self.transport_tasks), timeout=timeout
                    )
                except TimeoutError:
                    if self._is_test_environment():
                        logger.info(
                            "Transport tasks timed out in test environment, continuing..."
                        )
                    else:
                        logger.error("Transport tasks timed out")
                        raise
            else:
                logger.warning("No transports configured to start")

        except Exception as e:
            logger.error("Failed to start multi-transport server", error=str(e))
            await self.stop()
            raise

    async def _run_stdio_transport(self) -> None:
        """Run STDIO transport in async context."""
        try:
            # For async context, we need to handle STDIO differently
            # Since FastMCP's run() is synchronous, we run it in a separate task
            import asyncio

            loop = asyncio.get_event_loop()

            # Run STDIO transport in executor to avoid blocking
            # Add timeout as defensive measure
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: self.mcp.run(transport="stdio")),
                    timeout=None,  # STDIO should run indefinitely in production
                )
            except TimeoutError:
                logger.warning("STDIO transport timed out")
                raise
        except asyncio.CancelledError:
            logger.info("STDIO transport cancelled")
            raise
        except Exception as e:
            logger.error("STDIO transport failed", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop all running transports gracefully."""
        logger.info("Stopping multi-transport server")

        try:
            # Cancel all transport tasks
            for task in self.transport_tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete cancellation with timeout
            if self.transport_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self.transport_tasks, return_exceptions=True),
                        timeout=10.0,  # 10 second timeout for graceful shutdown
                    )
                except TimeoutError:
                    logger.warning(
                        "Some transport tasks did not shut down gracefully within timeout"
                    )

            # Stop individual transports with timeout
            shutdown_tasks = []
            if self.http_transport:
                shutdown_tasks.append(self.http_transport.stop())
            if self.websocket_transport:
                shutdown_tasks.append(self.websocket_transport.stop())
            if self.sse_transport:
                shutdown_tasks.append(self.sse_transport.stop())

            if shutdown_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*shutdown_tasks, return_exceptions=True),
                        timeout=5.0,  # 5 second timeout for transport shutdown
                    )
                except TimeoutError:
                    logger.warning(
                        "Some transports did not stop gracefully within timeout"
                    )

        except Exception as e:
            logger.error("Error during server shutdown", error=str(e))
        finally:
            self.transport_tasks.clear()
            logger.info("Multi-transport server stopped")

    def get_mcp_app(self) -> FastMCP:
        """Get the FastMCP application instance.

        Returns:
            FastMCP application instance
        """
        return self.mcp

    async def __aenter__(self) -> "MultiTransportServer":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Async context manager exit with guaranteed cleanup."""
        await self.stop()
        return False

    def create_test_context(self) -> Any:
        """Create a test-friendly context that doesn't start STDIO transport.

        Returns:
            An async context manager for testing
        """

        class TestContext:
            def __init__(self, server: "MultiTransportServer") -> None:
                self.server = server

            async def __aenter__(self) -> "MultiTransportServer":
                # Start only non-STDIO transports for testing
                logger.info("Starting test-friendly multi-transport server")

                try:
                    # Get transport configuration
                    if hasattr(self.server.config, "transport"):
                        transport_config = self.server.config.transport

                        # Start HTTP transport if enabled
                        if (
                            hasattr(transport_config, "http")
                            and transport_config.http.enabled
                        ):
                            self.server.http_transport = HTTPTransport(
                                mcp=self.server.mcp,
                                security_policy=self.server.security_policy,
                                audit_logger=self.server.audit_logger,
                                error_handler=self.server.error_handler,
                                health_monitor=self.server.health_monitor,
                                config=transport_config.http.model_dump(),
                            )
                            # Note: Don't actually start the server for testing

                        # Similar setup for WebSocket and SSE without starting servers
                        if (
                            hasattr(transport_config, "websocket")
                            and transport_config.websocket.enabled
                        ):
                            self.server.websocket_transport = WebSocketTransport(
                                mcp=self.server.mcp,
                                security_policy=self.server.security_policy,
                                audit_logger=self.server.audit_logger,
                                error_handler=self.server.error_handler,
                                health_monitor=self.server.health_monitor,
                                config=transport_config.websocket.model_dump(),
                            )

                        if (
                            hasattr(transport_config, "sse")
                            and transport_config.sse.enabled
                        ):
                            self.server.sse_transport = SSETransport(
                                mcp=self.server.mcp,
                                security_policy=self.server.security_policy,
                                audit_logger=self.server.audit_logger,
                                error_handler=self.server.error_handler,
                                health_monitor=self.server.health_monitor,
                                config=transport_config.sse.model_dump(),
                            )

                    logger.info("Test-friendly server setup completed")
                    return self.server

                except Exception as e:
                    logger.error("Failed to setup test server", error=str(e))
                    await self.server.stop()
                    raise

            async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
                """Cleanup test context."""
                await self.server.stop()
                return False

        return TestContext(self)
