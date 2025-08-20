"""Superego MCP Server - Intelligent tool request interception for AI agents.

This package provides an MCP server that intercepts and analyzes tool requests
from AI agents, applying configurable rules and policies to determine whether
requests should be allowed, modified, or blocked.
"""

__version__ = "0.0.0"
__author__ = "Superego MCP Team"
__email__ = "team@superego-mcp.dev"

from .domain.models import (
    AuditEntry,
    Decision,
    ErrorCode,
    SecurityRule,
    SuperegoError,
    ToolAction,
    ToolRequest,
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "AuditEntry",
    "Decision",
    "ErrorCode",
    "SecurityRule",
    "SuperegoError",
    "ToolAction",
    "ToolRequest",
]
