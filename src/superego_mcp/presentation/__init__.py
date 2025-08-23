"""Presentation layer for MCP server endpoints.

This module contains the FastMCP server implementation and unified server architecture.
"""

from .handlers import SecurityEvaluationHandler
from .mcp_server import create_server, mcp, run_stdio_server
from .monitoring import AlertManager, MonitoringDashboard
from .transport_server import MultiTransportServer  # Backward compatibility
from .unified_server import UnifiedServer

__all__ = [
    "create_server",
    "run_stdio_server",
    "mcp",
    "SecurityEvaluationHandler",
    "MonitoringDashboard",
    "AlertManager",
    "UnifiedServer",
    "MultiTransportServer",
]
