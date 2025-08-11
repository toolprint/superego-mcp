"""Domain models for the Superego MCP Server."""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ToolAction(str, Enum):
    """Actions that can be taken on tool requests."""

    ALLOW = "allow"
    DENY = "deny"
    SAMPLE = "sample"


class ErrorCode(str, Enum):
    """Error codes for structured error handling."""

    RULE_EVALUATION_FAILED = "RULE_EVAL_001"
    AI_SERVICE_UNAVAILABLE = "AI_SVC_001"
    INVALID_CONFIGURATION = "CONFIG_001"
    PARAMETER_VALIDATION_FAILED = "PARAM_001"
    INTERNAL_ERROR = "INTERNAL_001"


class SuperegoError(Exception):
    """Base exception with user-friendly messages."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        user_message: str,
        context: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.user_message = user_message
        self.context = context or {}
        super().__init__(message)


class ToolRequest(BaseModel):
    """Domain model for tool execution requests"""

    tool_name: str = Field(..., pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    parameters: dict[str, Any]
    session_id: str
    agent_id: str
    cwd: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("parameters")
    @classmethod
    def sanitize_parameters(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Prevent parameter injection attacks"""
        return cls._deep_sanitize(v)

    @classmethod
    def _deep_sanitize(cls, obj: Any) -> Any:
        """Recursively sanitize parameters to prevent injection attacks."""
        if isinstance(obj, dict):
            sanitized = {}
            for key, value in obj.items():
                # Sanitize keys - remove any potentially dangerous characters
                if isinstance(key, str):
                    sanitized_key = (
                        key.replace("..", "").replace("/", "").replace("\\", "")
                    )
                    sanitized_key = "".join(c for c in sanitized_key if c.isprintable())
                else:
                    sanitized_key = str(key)
                sanitized[sanitized_key] = cls._deep_sanitize(value)
            return sanitized
        elif isinstance(obj, list | tuple):
            return [cls._deep_sanitize(item) for item in obj]
        elif isinstance(obj, str):
            # Remove null bytes, control characters, and normalize
            sanitized = obj.replace("\x00", "").replace("\r\n", "\n")
            # Remove other control characters except newlines and tabs
            sanitized = "".join(c for c in sanitized if c.isprintable() or c in "\n\t")
            return sanitized
        else:
            return obj


class SecurityRule(BaseModel):
    """Domain model for security rules"""

    id: str
    priority: int = Field(..., ge=0, le=999)
    conditions: dict[str, Any]
    action: ToolAction
    reason: str | None = None
    sampling_guidance: str | None = None

    model_config = {"frozen": True}  # Immutable rules


class Decision(BaseModel):
    """Domain model for security decisions"""

    action: Literal["allow", "deny"]
    reason: str
    rule_id: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: int


class AuditEntry(BaseModel):
    """Domain model for audit trail entries"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request: ToolRequest
    decision: Decision
    rule_matches: list[str]
    ttl: datetime | None = None


class ComponentHealth(BaseModel):
    """Health status for individual system components"""

    status: Literal["healthy", "degraded", "unhealthy"]
    message: str | None = None
    last_check: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HealthStatus(BaseModel):
    """Overall system health status with component details and metrics"""

    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    components: dict[str, ComponentHealth]
    metrics: dict[str, float]
