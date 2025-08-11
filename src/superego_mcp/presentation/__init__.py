"""Presentation layer for MCP server endpoints.

This module contains the FastMCP server implementation.
"""

from .handlers import SecurityEvaluationHandler
from .mcp_server import create_server, mcp, run_stdio_server
from .monitoring import MonitoringDashboard, AlertManager

__all__ = [
    "create_server",
    "run_stdio_server",
    "mcp",
    "SecurityEvaluationHandler",
    "MonitoringDashboard",
    "AlertManager",
]
