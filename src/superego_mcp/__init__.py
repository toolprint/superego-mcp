"""Superego MCP Server - Intelligent tool-call review system for AI agents.

This package provides an MCP server that intercepts and analyzes tool requests
from AI agents, applying configurable rules and policies to determine whether
requests should be allowed, modified, or blocked.
"""

__version__ = "0.0.0"
__author__ = "Brian Cripe"
__email__ = "brian@onegrep.dev"

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
