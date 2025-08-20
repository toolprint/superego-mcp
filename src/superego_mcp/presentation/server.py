"""MCP Server implementation for Superego."""

import os
from datetime import datetime
from typing import Any

import structlog
from fastmcp import FastMCP
from pydantic import BaseModel

from superego_mcp.domain.models import Decision, ToolRequest
from superego_mcp.domain.services import InterceptionService
from superego_mcp.infrastructure.config import ServerConfig
from superego_mcp.infrastructure.security_formatter import SecurityDecisionFormatter

logger = structlog.get_logger(__name__)


class EvaluateRequest(BaseModel):
    """Request model for security evaluation."""

    tool_name: str
    parameters: dict[str, Any]
    agent_id: str
    session_id: str
    cwd: str | None = None


class SuperegoMCPServer:
    """FastMCP server for Superego tool interception."""

    def __init__(
        self,
        interception_service: InterceptionService,
        config: ServerConfig,
        show_decisions: bool = True,
    ):
        """Initialize the MCP server.

        Args:
            interception_service: Service for handling tool interception
            config: Server configuration
            show_decisions: Whether to display security decisions
        """
        self.interception_service = interception_service
        self.config = config
        self.show_decisions = show_decisions
        self.formatter = SecurityDecisionFormatter() if show_decisions else None
        self.app: FastMCP = FastMCP("superego-mcp")
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up MCP server routes."""

        @self.app.tool()
        async def evaluate_tool_request(request: EvaluateRequest) -> Decision:
            """Evaluate a tool request for security concerns.

            Args:
                request: The tool evaluation request

            Returns:
                Security decision for the request
            """
            tool_request = ToolRequest(
                tool_name=request.tool_name,
                parameters=request.parameters,
                agent_id=request.agent_id,
                session_id=request.session_id,
                cwd=request.cwd or os.getcwd(),
                timestamp=datetime.utcnow(),
            )

            logger.info(
                "Evaluating tool request",
                tool_name=request.tool_name,
                agent_id=request.agent_id,
                session_id=request.session_id,
            )

            decision = await self.interception_service.evaluate_request(tool_request)

            # Display security decision if enabled
            if self.show_decisions and self.formatter:
                self.formatter.display_decision(tool_request, decision)

            logger.info(
                "Tool request evaluated",
                action=decision.action,
                tool_name=request.tool_name,
                agent_id=request.agent_id,
                confidence=decision.confidence,
            )

            return decision

        @self.app.tool()
        async def health_check() -> dict[str, Any]:
            """Check the health of the Superego service.

            Returns:
                Health status information
            """
            return await self.interception_service.health_check()

        @self.app.tool()
        async def get_server_info() -> dict[str, Any]:
            """Get information about the Superego server.

            Returns:
                Server information
            """
            return {
                "name": "superego-mcp",
                "version": "0.0.0",
                "description": "Intelligent tool request interception for AI agents",
                "config": {
                    "host": self.config.host,
                    "port": self.config.port,
                    "debug": self.config.debug,
                    "rules_file": self.config.rules_file,
                    "hot_reload": self.config.hot_reload,
                },
            }

    async def start(self) -> None:
        """Start the MCP server."""
        logger.info(
            "Starting Superego MCP server",
            host=self.config.host,
            port=self.config.port,
            debug=self.config.debug,
        )

        # Start the FastMCP server
        await self.app.run(  # type: ignore[func-returns-value]
            host=self.config.host, port=self.config.port, debug=self.config.debug
        )

    def get_app(self) -> FastMCP:
        """Get the FastMCP application instance.

        Returns:
            FastMCP application
        """
        return self.app
