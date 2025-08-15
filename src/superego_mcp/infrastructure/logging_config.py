"""Structured logging configuration for Superego MCP Server."""

import logging
import sys
from typing import Any, TextIO

import structlog


def configure_logging(
    level: str = "INFO",
    json_logs: bool = True,
    stream: TextIO = sys.stdout
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to use JSON formatting (True) or human-readable (False)
        stream: Output stream for logs (sys.stdout or sys.stderr)
    """
    # Clear any existing handlers to avoid conflicts
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        stream=stream,
        format="%(message)s"
        if json_logs
        else "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True  # Override existing configuration
    )

    # Configure structlog processors
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        # JSON output for production
        processors.extend(
            [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
        )
    else:
        # Human-readable for development
        processors.extend(
            [
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.dev.ConsoleRenderer(),
            ]
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def configure_stderr_logging(level: str = "WARNING", json_logs: bool = False) -> None:
    """Configure logging to stderr with sensible defaults for CLI tools.

    This is a convenience function for CLI tools that need to output clean
    JSON or other data on stdout while keeping logs on stderr.

    Args:
        level: Log level (default: WARNING to reduce noise)
        json_logs: Whether to use JSON formatting (default: False for CLI readability)
    """
    configure_logging(level=level, json_logs=json_logs, stream=sys.stderr)


def get_audit_logger() -> Any:
    """Get the audit logger instance"""
    return structlog.get_logger("audit")


def get_application_logger(name: str) -> Any:
    """Get an application logger instance"""
    return structlog.get_logger(name)
