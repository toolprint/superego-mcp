"""Structured logging configuration for Superego MCP Server."""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Configure structured logging for the application"""

    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        stream=sys.stdout,
        format="%(message)s"
        if json_logs
        else "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Configure structlog processors
    processors = [
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


def get_audit_logger() -> structlog.BoundLogger:
    """Get the audit logger instance"""
    return structlog.get_logger("audit")


def get_application_logger(name: str) -> structlog.BoundLogger:
    """Get an application logger instance"""
    return structlog.get_logger(name)
