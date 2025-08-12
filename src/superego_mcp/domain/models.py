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


class PatternType(str, Enum):
    """Supported pattern matching types."""

    STRING = "string"
    REGEX = "regex"
    GLOB = "glob"
    JSONPATH = "jsonpath"


class PatternConfig(BaseModel):
    """Configuration for advanced pattern matching."""

    type: PatternType
    pattern: str
    case_sensitive: bool = Field(
        default=True, description="Case sensitivity for string patterns"
    )

    model_config = {"frozen": True}


class TimeRangeConfig(BaseModel):
    """Configuration for time-based rule activation."""

    start: str = Field(
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Start time in HH:MM format",
    )
    end: str = Field(
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="End time in HH:MM format",
    )
    timezone: str = Field(default="UTC", description="Timezone identifier")

    model_config = {"frozen": True}


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
        result = cls._deep_sanitize(v)
        # Ensure we return a dict as expected
        if isinstance(result, dict):
            return result
        else:
            # Fallback to original if sanitization returned unexpected type
            return v

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
            sanitized_str = obj.replace("\x00", "").replace("\r\n", "\n")
            # Remove other control characters except newlines and tabs
            sanitized_str = "".join(
                c for c in sanitized_str if c.isprintable() or c in "\n\t"
            )
            return sanitized_str
        else:
            return obj


class SecurityRule(BaseModel):
    """Domain model for security rules with advanced pattern support"""

    id: str
    priority: int = Field(..., ge=0, le=999)
    conditions: dict[str, Any]
    action: ToolAction
    reason: str | None = None
    sampling_guidance: str | None = None
    enabled: bool = Field(default=True, description="Whether the rule is active")

    model_config = {"frozen": True}  # Immutable rules

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate rule conditions structure."""
        if not v:
            raise ValueError("Conditions cannot be empty")

        # Validate that we have at least one valid condition key
        valid_keys = {
            "tool_name",
            "parameters",
            "cwd",
            "cwd_pattern",
            "time_range",
            "AND",
            "OR",
        }

        if not any(key in valid_keys for key in v.keys()):
            raise ValueError(f"Conditions must contain at least one of: {valid_keys}")

        return v


class Decision(BaseModel):
    """Domain model for security decisions"""

    action: Literal["allow", "deny"]
    reason: str
    rule_id: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: int
    # AI-specific fields
    ai_provider: str | None = None
    ai_model: str | None = None
    risk_factors: list[str] = Field(default_factory=list)


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
    metrics: dict[str, float | dict[str, Any]]
