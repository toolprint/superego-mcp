"""Unified FastAPI + MCP server architecture for Superego.

This module implements a unified server that handles both MCP protocol (via FastMCP)
and HTTP/WebSocket requests (via FastAPI) in a single process. This provides:

- Single server process for simplified deployment
- FastAPI mounting of MCP endpoints
- Backward compatibility with existing multi-transport system
- Performance optimization through unified architecture
- UV-compatible execution model
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import BaseModel
from uvicorn import Config, Server

from ..domain.claude_code_models import (
    HookEventName,
    PermissionDecision,
    PreToolUseHookSpecificOutput,
    PreToolUseInput,
    PreToolUseOutput,
)
from ..domain.models import Decision, ToolRequest
from ..domain.security_policy import SecurityPolicyEngine
from ..infrastructure.config import ServerConfig
from ..infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor

logger = structlog.get_logger(__name__)


class EvaluateRequest(BaseModel):
    """Request model for tool evaluation via HTTP."""

    tool_name: str
    parameters: dict[str, Any]
    agent_id: str
    session_id: str
    cwd: str | None = None


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    timestamp: str
    components: dict[str, Any]


class UnifiedServer:
    """Unified server supporting both MCP and HTTP/WebSocket protocols."""

    def __init__(
        self,
        security_policy: SecurityPolicyEngine,
        audit_logger: AuditLogger,
        error_handler: ErrorHandler,
        health_monitor: HealthMonitor,
        config: ServerConfig,
        cli_transport: str | None = None,
        cli_port: int | None = None,
    ):
        """Initialize unified server.

        Args:
            security_policy: Security policy engine
            audit_logger: Audit logger instance
            error_handler: Error handler instance
            health_monitor: Health monitor instance
            config: Server configuration
            cli_transport: CLI override for transport mode (stdio/http)
            cli_port: CLI override for HTTP port
        """
        self.security_policy = security_policy
        self.audit_logger = audit_logger
        self.error_handler = error_handler
        self.health_monitor = health_monitor
        self.config = config
        self.cli_transport = cli_transport
        self.cli_port = cli_port

        # Server instances
        self.uvicorn_server: Server | None = None
        self.stdio_task: asyncio.Task[Any] | None = None

        # Initialize FastMCP with MCP protocol support
        self.mcp: FastMCP = FastMCP(
            name="Superego MCP Server",
            instructions="Security evaluation and policy enforcement with unified FastAPI+MCP support",
        )

        # Initialize FastAPI for HTTP/WebSocket support
        self.fastapi = self._create_fastapi_app()

        # Setup core functionality
        self._setup_mcp_tools()
        self._setup_fastapi_routes()

    def _is_test_environment(self) -> bool:
        """Check if running in test environment."""
        return (
            os.environ.get("PYTEST_CURRENT_TEST") is not None
            or os.environ.get("TESTING") == "1"
            or "pytest" in os.environ.get("_", "")
            or any("pytest" in arg for arg in sys.argv)
        )

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """FastAPI lifespan event handler for startup and shutdown."""
        logger.info("Starting unified server lifespan")
        try:
            # Startup logic
            await self._startup()
            yield
        finally:
            # Shutdown logic
            await self._shutdown()

    async def _startup(self) -> None:
        """Handle server startup."""
        logger.info("Unified server startup initiated")
        # Any additional startup logic can go here

    async def _shutdown(self) -> None:
        """Handle server shutdown."""
        logger.info("Unified server shutdown initiated")
        # Cleanup STDIO task if running
        if self.stdio_task and not self.stdio_task.done():
            logger.info("Cancelling STDIO task")
            self.stdio_task.cancel()
            try:
                await self.stdio_task
            except asyncio.CancelledError:
                pass

    def _create_fastapi_app(self) -> FastAPI:
        """Create FastAPI application with middleware and configuration."""
        app = FastAPI(
            title="Superego MCP Unified Server",
            description="Unified security evaluation and policy enforcement API with MCP support",
            version="0.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            lifespan=self._lifespan,
        )

        # Add CORS middleware
        cors_origins = ["*"]
        if hasattr(self.config, "transport") and hasattr(self.config.transport, "http"):
            cors_origins = getattr(self.config.transport.http, "cors_origins", ["*"])

        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

        # Global exception handler
        @app.exception_handler(Exception)
        async def global_exception_handler(
            request: Request, exc: Exception
        ) -> JSONResponse:
            """Global exception handler for unhandled errors."""
            logger.error(
                "HTTP: Unhandled exception", error=str(exc), path=str(request.url)
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error": str(exc),
                    "transport": "unified",
                },
            )

        return app

    def _setup_mcp_tools(self) -> None:
        """Set up core MCP tools."""

        @self.mcp.tool()
        async def evaluate_tool_request(
            tool_name: str,
            parameters: dict[str, Any],
            agent_id: str,
            session_id: str,
            cwd: str | None = None,
        ) -> Decision:
            """Evaluate a tool request for security concerns (MCP protocol).

            Args:
                tool_name: Name of the tool being invoked
                parameters: Parameters passed to the tool
                agent_id: ID of the requesting agent
                session_id: Session identifier
                cwd: Current working directory

            Returns:
                Security decision for the request
            """
            return await self._evaluate_internal(
                tool_name, parameters, agent_id, session_id, cwd
            )

        @self.mcp.tool()
        async def health_check() -> dict[str, Any]:
            """Check the health of the Superego service (MCP protocol).

            Returns:
                Health status information
            """
            return await self._health_check_internal()

        @self.mcp.tool()
        async def get_server_info() -> dict[str, Any]:
            """Get information about the Superego server (MCP protocol).

            Returns:
                Server information
            """
            return await self._server_info_internal()

        @self.mcp.resource("config://rules")
        async def get_current_rules() -> str:
            """Expose current security rules as MCP resource."""
            return await self._get_rules_internal()

        @self.mcp.resource("audit://recent")
        async def get_recent_audit_entries() -> str:
            """Expose recent audit entries for monitoring."""
            return await self._get_audit_entries_internal()

    def _setup_fastapi_routes(self) -> None:
        """Set up FastAPI HTTP routes."""

        @self.fastapi.post("/v1/evaluate", response_model=Decision)
        async def evaluate_tool_request_http(request: EvaluateRequest) -> Decision:
            """Evaluate a tool request for security concerns (HTTP).

            Args:
                request: Tool evaluation request

            Returns:
                Security decision for the request
            """
            return await self._evaluate_internal(
                request.tool_name,
                request.parameters,
                request.agent_id,
                request.session_id,
                request.cwd,
            )

        @self.fastapi.post("/v1/hooks", response_model=PreToolUseOutput)
        async def evaluate_hook_request_http(
            request: PreToolUseInput,
        ) -> PreToolUseOutput:
            """Evaluate a Claude Code PreToolUse hook request (HTTP).

            Args:
                request: Claude Code hook input in the PreToolUse format

            Returns:
                Claude Code hook output with permission decision
            """
            try:
                # Convert PreToolUseInput to internal ToolRequest format
                tool_request = ToolRequest(
                    tool_name=request.tool_name,
                    parameters=request.tool_input.model_dump()
                    if hasattr(request.tool_input, "model_dump")
                    else dict(request.tool_input),
                    agent_id="claude_code_hook",
                    session_id=request.session_id,
                    cwd=request.cwd,
                )

                logger.info(
                    "HTTP: Evaluating Claude Code hook request",
                    tool_name=request.tool_name,
                    session_id=request.session_id,
                    hook_event=request.hook_event_name,
                )

                # Evaluate using security policy
                decision = await self.security_policy.evaluate(tool_request)

                # Log decision to audit trail
                rule_matches = [decision.rule_id] if decision.rule_id else []
                await self.audit_logger.log_decision(
                    tool_request, decision, rule_matches
                )

                # Convert Decision to Claude Code hook format
                permission_decision = self._decision_to_permission(decision.action)

                hook_specific_output = PreToolUseHookSpecificOutput(
                    hookEventName=HookEventName.PRE_TOOL_USE,
                    permissionDecision=permission_decision,
                    permissionDecisionReason=decision.reason,
                )

                return PreToolUseOutput(
                    hookSpecificOutput=hook_specific_output,
                    decision="approve"
                    if permission_decision == PermissionDecision.ALLOW
                    else "block",
                    reason=decision.reason,
                )

            except Exception as e:
                logger.error("HTTP: Claude Code hook evaluation failed", error=str(e))

                # Handle errors with centralized error handler
                if "tool_request" in locals():
                    fallback_decision = self.error_handler.handle_error(e, tool_request)
                else:
                    # Create a minimal fallback decision if tool_request wasn't created
                    fallback_decision = Decision(
                        action="deny",
                        reason=f"Evaluation error: {str(e)}",
                        confidence=1.0,
                        ai_provider="error_handler",
                        ai_model="fallback",
                        processing_time_ms=0,
                    )

                # Log fallback decision if we have a tool_request
                if "tool_request" in locals():
                    await self.audit_logger.log_decision(
                        tool_request, fallback_decision, []
                    )

                # Convert to hook format (deny on error for safety)
                hook_specific_output = PreToolUseHookSpecificOutput(
                    hookEventName=HookEventName.PRE_TOOL_USE,
                    permissionDecision=PermissionDecision.DENY,
                    permissionDecisionReason=f"Evaluation error: {str(e)}",
                )

                return PreToolUseOutput(
                    hookSpecificOutput=hook_specific_output,
                    decision="block",
                    reason=f"Evaluation error: {str(e)}",
                )

        @self.fastapi.get("/v1/health", response_model=HealthResponse)
        async def health_check_http() -> HealthResponse:
            """Check the health of the Superego service (HTTP).

            Returns:
                Health status information
            """
            try:
                health_data = await self._health_check_internal()
                return HealthResponse(
                    status=health_data.get("status", "unknown"),
                    timestamp=health_data.get("timestamp", str(datetime.utcnow())),
                    components=health_data.get("components", {}),
                )
            except Exception as e:
                logger.error("HTTP: Health check failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

        @self.fastapi.get("/v1/config/rules")
        async def get_current_rules_http() -> dict[str, Any]:
            """Get current security rules (HTTP).

            Returns:
                Current security rules and metadata
            """
            try:
                rules_yaml = await self._get_rules_internal()
                import yaml

                rules_data = yaml.safe_load(rules_yaml)
                return rules_data if isinstance(rules_data, dict) else {}
            except Exception as e:
                logger.error("HTTP: Failed to get rules", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

        @self.fastapi.get("/v1/audit/recent")
        async def get_recent_audit_entries_http() -> dict[str, Any]:
            """Get recent audit entries (HTTP).

            Returns:
                Recent audit entries and statistics
            """
            try:
                audit_json = await self._get_audit_entries_internal()
                import json

                audit_data = json.loads(audit_json)
                return audit_data if isinstance(audit_data, dict) else {}
            except Exception as e:
                logger.error("HTTP: Failed to get audit entries", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

        @self.fastapi.get("/v1/metrics")
        async def get_metrics_http() -> dict[str, Any]:
            """Get performance metrics (HTTP).

            Returns:
                System performance metrics
            """
            try:
                health_data = await self._health_check_internal()
                metrics = {
                    "system_metrics": health_data.get("components", {}).get(
                        "system_metrics", {}
                    ),
                    "security_policy_health": health_data.get("components", {}).get(
                        "security_policy", {}
                    ),
                    "audit_stats": self.audit_logger.get_stats(),
                }
                return metrics
            except Exception as e:
                logger.error("HTTP: Failed to get metrics", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

        @self.fastapi.get("/v1/server-info")
        async def get_server_info_http() -> dict[str, Any]:
            """Get server information (HTTP).

            Returns:
                Server configuration and status information
            """
            server_info = await self._server_info_internal()
            # Add HTTP-specific endpoints
            server_info["endpoints"] = {
                "evaluate": "/v1/evaluate",
                "hooks": "/v1/hooks",
                "health": "/v1/health",
                "rules": "/v1/config/rules",
                "audit": "/v1/audit/recent",
                "metrics": "/v1/metrics",
                "docs": "/docs",
                "redoc": "/redoc",
            }
            return server_info

        # Mount MCP endpoints under /mcp prefix
        # Note: This is a conceptual mounting - actual implementation
        # would need custom middleware to bridge FastAPI and FastMCP
        @self.fastapi.post("/mcp/call")
        async def mcp_call_bridge(request: Request) -> JSONResponse:
            """Bridge endpoint for MCP protocol calls via HTTP.

            This allows HTTP clients to call MCP tools directly.
            """
            try:
                request_data = await request.json()
                # This would need proper MCP protocol handling
                # For now, return a placeholder response
                return JSONResponse(
                    {
                        "status": "mcp_bridge_placeholder",
                        "message": "MCP bridge endpoint - implementation pending",
                        "request_received": bool(request_data),
                    }
                )
            except Exception as e:
                logger.error("MCP bridge call failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

    def _decision_to_permission(self, action: str) -> PermissionDecision:
        """Convert internal Decision action to Claude Code permission decision.

        Args:
            action: Internal decision action (allow, deny, ask, etc.)

        Returns:
            Claude Code permission decision (allow, deny, ask)
        """
        if action in ("allow", "approve"):
            return PermissionDecision.ALLOW
        elif action == "ask":
            return PermissionDecision.ASK
        else:
            # Default to deny for safety (covers "deny", "block", etc.)
            return PermissionDecision.DENY

    async def _evaluate_internal(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        agent_id: str,
        session_id: str,
        cwd: str | None = None,
    ) -> Decision:
        """Internal evaluation logic shared between MCP and HTTP protocols."""
        try:
            tool_request = ToolRequest(
                tool_name=tool_name,
                parameters=parameters,
                agent_id=agent_id,
                session_id=session_id,
                cwd=cwd or "/tmp",
            )

            logger.info(
                "Unified server: Evaluating tool request",
                tool_name=tool_name,
                agent_id=agent_id,
                session_id=session_id,
            )

            decision = await self.security_policy.evaluate(tool_request)

            # Log decision to audit trail
            rule_matches = [decision.rule_id] if decision.rule_id else []
            await self.audit_logger.log_decision(tool_request, decision, rule_matches)

            logger.info(
                "Unified server: Tool request evaluated",
                action=decision.action,
                tool_name=tool_name,
                confidence=decision.confidence,
            )

            return decision

        except Exception as e:
            # Handle errors with centralized error handler
            fallback_decision = self.error_handler.handle_error(e, tool_request)

            # Log fallback decision
            await self.audit_logger.log_decision(tool_request, fallback_decision, [])

            return fallback_decision

    async def _health_check_internal(self) -> dict[str, Any]:
        """Internal health check logic shared between protocols."""
        try:
            health_status = await self.health_monitor.check_health()
            return health_status.model_dump()
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": str(datetime.utcnow()),
            }

    async def _server_info_internal(self) -> dict[str, Any]:
        """Internal server info logic shared between protocols."""
        return {
            "name": "superego-mcp",
            "version": "0.0.0",
            "description": "Intelligent tool request interception for AI agents",
            "architecture": "unified",
            "protocols": ["mcp", "http", "websocket"],
            "transports": self._get_enabled_transports(),
            "config": {
                "hot_reload": self.config.hot_reload,
                "ai_sampling_enabled": self.config.ai_sampling.enabled,
                "health_checks_enabled": self.config.health_check_enabled,
            },
        }

    async def _get_rules_internal(self) -> str:
        """Internal rules retrieval logic shared between protocols."""
        try:
            import yaml

            rules_data = {
                "rules": [
                    rule.model_dump(mode="json") for rule in self.security_policy.rules
                ],
                "total_rules": len(self.security_policy.rules),
                "last_updated": self.security_policy.rules_file.stat().st_mtime
                if self.security_policy.rules_file.exists()
                else None,
            }
            return yaml.dump(rules_data, default_flow_style=False)
        except Exception as e:
            return f"Error loading rules: {str(e)}"

    async def _get_audit_entries_internal(self) -> str:
        """Internal audit entries retrieval logic shared between protocols."""
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

        # HTTP transport (always enabled in unified server)
        enabled.append("http")

        # WebSocket support (via FastAPI)
        enabled.append("websocket")

        return enabled

    async def start(self) -> None:
        """Start the unified server with both MCP and HTTP support."""
        logger.info("Starting Superego unified server")

        try:
            # Handle CLI transport override
            if self.cli_transport:
                logger.info(f"CLI transport override: {self.cli_transport}")

                if self.cli_transport == "stdio":
                    # Start only STDIO transport
                    if not self._is_test_environment():
                        self.stdio_task = asyncio.create_task(
                            self._run_stdio_transport()
                        )
                        logger.info("STDIO transport started (CLI override)")
                        await self.stdio_task
                    else:
                        logger.info("STDIO transport skipped in test environment")

                elif self.cli_transport == "http":
                    # Start only HTTP transport with CLI port override
                    await self._start_http_server()

            else:
                # Start both STDIO and HTTP by default
                tasks = []

                # Start HTTP server
                http_task = asyncio.create_task(self._start_http_server())
                tasks.append(http_task)

                # Start STDIO transport (skip in test environment to avoid blocking)
                if not self._is_test_environment():
                    self.stdio_task = asyncio.create_task(self._run_stdio_transport())
                    tasks.append(self.stdio_task)
                    logger.info("STDIO transport started")
                else:
                    logger.info("STDIO transport skipped in test environment")

                if tasks:
                    # Wait for all tasks with timeout to prevent infinite blocking
                    try:
                        # In test environment, use shorter timeout
                        timeout = 5.0 if self._is_test_environment() else None
                        await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
                    except TimeoutError:
                        if self._is_test_environment():
                            logger.info(
                                "Server tasks timed out in test environment, continuing..."
                            )
                        else:
                            logger.error("Server tasks timed out")
                            raise

        except Exception as e:
            logger.error("Failed to start unified server", error=str(e))
            await self.stop()
            raise

    async def _start_http_server(self) -> None:
        """Start the HTTP server using Uvicorn."""
        # Get configuration
        port = self.cli_port or 8000
        host = "localhost"

        if hasattr(self.config, "transport") and hasattr(self.config.transport, "http"):
            host = self.config.transport.http.host
            if not self.cli_port:  # Only use config port if CLI didn't override
                port = self.config.transport.http.port

        logger.info("Starting HTTP transport", host=host, port=port)

        # Create uvicorn config
        config = Config(
            app=self.fastapi,
            host=host,
            port=port,
            log_config=None,  # Use structlog instead
        )

        # Create and store server
        self.uvicorn_server = Server(config)

        try:
            await self.uvicorn_server.serve()
        except Exception as e:
            logger.error("HTTP transport failed", error=str(e))
            raise

    async def _run_stdio_transport(self) -> None:
        """Run STDIO transport for MCP protocol."""
        try:
            logger.info("Starting STDIO transport for MCP")

            # Run the MCP server in STDIO mode
            # Note: This blocks until the server is stopped
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.mcp.run(transport="stdio")
            )

        except asyncio.CancelledError:
            logger.info("STDIO transport cancelled")
            raise
        except Exception as e:
            logger.error("STDIO transport failed", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the unified server gracefully."""
        logger.info("Stopping unified server")

        try:
            # Stop HTTP server
            if self.uvicorn_server:
                logger.info("Stopping HTTP server")
                self.uvicorn_server.should_exit = True
                await asyncio.sleep(0.1)  # Give it a moment to shut down

            # Stop STDIO task
            if self.stdio_task and not self.stdio_task.done():
                logger.info("Stopping STDIO transport")
                self.stdio_task.cancel()
                try:
                    await self.stdio_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            logger.error("Error during unified server shutdown", error=str(e))
        finally:
            logger.info("Unified server stopped")

    def get_fastapi_app(self) -> FastAPI:
        """Get the FastAPI application instance.

        Returns:
            FastAPI application instance
        """
        return self.fastapi

    def get_mcp_app(self) -> FastMCP:
        """Get the FastMCP application instance.

        Returns:
            FastMCP application instance
        """
        return self.mcp

    async def __aenter__(self) -> "UnifiedServer":
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
            def __init__(self, server: "UnifiedServer") -> None:
                self.server = server

            async def __aenter__(self) -> "UnifiedServer":
                # Start only HTTP transport for testing
                logger.info("Starting test-friendly unified server")

                try:
                    # Override the start method to only start HTTP
                    await self.server._start_http_server()
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
