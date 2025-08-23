"""Structured logging configuration for Superego MCP Server."""

import logging
import sys
from typing import Any, TextIO

import structlog


def configure_logging(
    level: str = "INFO", json_logs: bool = True, stream: TextIO = sys.stdout
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
        force=True,  # Override existing configuration
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


def configure_logging_explicit(
    log_format: str = "console",
    log_handler: str = "print",
    level: str = "INFO",
    stream: TextIO = sys.stdout,
) -> None:
    """Configure logging with explicit settings.

    Args:
        log_format: Output format - "console" for human-readable, "json" for structured
        log_handler: Handler type - "print" for PrintLogger, "write" for WriteLogger
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
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
        if log_format == "json"
        else "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,  # Override existing configuration
    )

    # Ensure all third-party loggers also use the same stream (stderr) to avoid STDIO conflicts
    # This prevents uvicorn, FastMCP, and other libraries from writing to stdout
    for logger_name in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "websockets",
    ]:
        logger = logging.getLogger(logger_name)
        # Remove any existing handlers that might write to stdout
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        # Add new handler with our configured stream (stderr)
        handler = logging.StreamHandler(stream)
        handler.setFormatter(
            logging.Formatter(
                "%(message)s"
                if log_format == "json"
                else "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
        )
        logger.addHandler(handler)
        logger.propagate = False  # Prevent propagation to root logger

    # Configure structlog processors based on format
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        # JSON output for production/log aggregation
        processors.extend(
            [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
        )
    else:
        # Human-readable console output for development
        processors.extend(
            [
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.dev.ConsoleRenderer(),
            ]
        )

    # Choose logger factory based on handler type
    if log_handler == "write":
        # WriteLogger for Docker containers - atomic writes, handles closed files better
        logger_factory: Any = structlog.WriteLoggerFactory(stream)
    else:
        # PrintLogger for local development - default behavior
        logger_factory = structlog.stdlib.LoggerFactory()

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        logger_factory=logger_factory,
        cache_logger_on_first_use=True,
    )
