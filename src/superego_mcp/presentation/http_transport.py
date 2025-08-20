"""HTTP transport implementation for Superego MCP Server."""

import asyncio
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastmcp import FastMCP
from pydantic import BaseModel
from uvicorn import Config, Server

from ..domain.claude_code_models import (
    HookEventName,
    PermissionDecision,
    PreToolUseHookSpecificOutput,
    PreToolUseInput,
    PreToolUseOutput,
)
from ..domain.models import Decision, ToolRequest
from ..domain.security_policy import SecurityPolicyEngine
from ..infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor

logger = structlog.get_logger(__name__)


class EvaluateRequest(BaseModel):
    """Request model for tool evaluation via HTTP."""

    tool_name: str
    parameters: dict[str, Any]
    agent_id: str
    session_id: str
    cwd: str | None = None


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    timestamp: str
    components: dict[str, Any]


class HTTPTransport:
    """HTTP REST API transport for MCP server."""

    def __init__(
        self,
        mcp: FastMCP,
        security_policy: SecurityPolicyEngine,
        audit_logger: AuditLogger,
        error_handler: ErrorHandler,
        health_monitor: HealthMonitor,
        config: dict[str, Any],
    ):
        """Initialize HTTP transport.

        Args:
            mcp: FastMCP application instance
            security_policy: Security policy engine
            audit_logger: Audit logger instance
            error_handler: Error handler instance
            health_monitor: Health monitor instance
            config: HTTP transport configuration
        """
        self.mcp = mcp
        self.security_policy = security_policy
        self.audit_logger = audit_logger
        self.error_handler = error_handler
        self.health_monitor = health_monitor
        self.config = config
        self.server: Server | None = None

        # Create FastAPI app
        self.app = FastAPI(
            title="Superego MCP Server",
            description="Security evaluation and policy enforcement API",
            version="0.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # Add CORS middleware
        cors_origins = config.get("cors_origins", ["*"])
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )

        # Server instance
        self.server = None

        # Authentication setup
        self.security = HTTPBearer(auto_error=False)
        self.auth_enabled = config.get("auth_enabled", False)
        self.auth_tokens = set(config.get("auth_tokens", []))

        self._setup_routes()

    def _decision_to_permission(self, action: str) -> PermissionDecision:
        """Convert internal Decision action to Claude Code permission decision.

        Args:
            action: Internal decision action (allow, deny, ask, etc.)

        Returns:
            Claude Code permission decision (allow, deny, ask)
        """
        if action in ("allow", "approve"):
            return PermissionDecision.ALLOW
        elif action == "ask":
            return PermissionDecision.ASK
        else:
            # Default to deny for safety (covers "deny", "block", etc.)
            return PermissionDecision.DENY

    def _verify_auth(
        self, credentials: HTTPAuthorizationCredentials | None = None
    ) -> bool:
        """Verify authentication credentials.

        Args:
            credentials: HTTP Bearer credentials

        Returns:
            True if authentication is valid or disabled

        Raises:
            HTTPException: If authentication fails
        """
        if not self.auth_enabled:
            return True

        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if credentials.credentials not in self.auth_tokens:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return True

    def _setup_routes(self) -> None:
        """Set up HTTP API routes."""

        @self.app.post(
            "/v1/evaluate",
            response_model=Decision,
            summary="Evaluate tool request for security",
            description="Analyzes a tool request against security policies and returns an allow/deny/sample decision.",
            openapi_extra={
                "examples": {
                    "safe_file_operation": {
                        "summary": "Safe file read operation",
                        "description": "Reading a configuration file from allowed directory",
                        "value": {
                            "tool_name": "Read",
                            "parameters": {
                                "file_path": "/etc/config/app.yaml",
                                "encoding": "utf-8",
                            },
                            "agent_id": "claude-assistant",
                            "session_id": "sess_abc123",
                            "cwd": "/home/user/project",
                        },
                    },
                    "git_status": {
                        "summary": "Git status check",
                        "description": "Checking git repository status - typically allowed",
                        "value": {
                            "tool_name": "Bash",
                            "parameters": {
                                "command": "git status --porcelain",
                                "description": "Check git working tree status",
                            },
                            "agent_id": "dev-assistant",
                            "session_id": "sess_dev456",
                            "cwd": "/home/user/myproject",
                        },
                    },
                    "dangerous_operation": {
                        "summary": "Dangerous system operation",
                        "description": "Operation that modifies system files - typically denied",
                        "value": {
                            "tool_name": "Bash",
                            "parameters": {
                                "command": "sudo rm -rf /usr/local/bin/*",
                                "description": "Remove system binaries",
                            },
                            "agent_id": "risky-agent",
                            "session_id": "sess_danger789",
                            "cwd": "/tmp",
                        },
                    },
                    "network_operation": {
                        "summary": "Network request requiring evaluation",
                        "description": "External API call that may require sampling/approval",
                        "value": {
                            "tool_name": "WebFetch",
                            "parameters": {
                                "url": "https://api.external-service.com/data",
                                "method": "POST",
                                "headers": {"Authorization": "Bearer token123"},
                            },
                            "agent_id": "web-crawler",
                            "session_id": "sess_net999",
                            "cwd": "/home/user/crawler",
                        },
                    },
                }
            },
            responses={
                200: {
                    "description": "Security decision returned successfully",
                    "content": {
                        "application/json": {
                            "examples": {
                                "allow_decision": {
                                    "summary": "Tool request allowed",
                                    "value": {
                                        "action": "allow",
                                        "reason": "File read operation from safe directory",
                                        "rule_id": "safe-file-read-001",
                                        "confidence": 0.95,
                                        "processing_time_ms": 45,
                                        "ai_provider": "anthropic",
                                        "ai_model": "claude-3-sonnet",
                                        "risk_factors": [],
                                        "requires_approval": False,
                                    },
                                },
                                "deny_decision": {
                                    "summary": "Tool request denied",
                                    "value": {
                                        "action": "deny",
                                        "reason": "Attempt to delete system files detected",
                                        "rule_id": "system-protection-001",
                                        "confidence": 0.99,
                                        "processing_time_ms": 23,
                                        "ai_provider": "anthropic",
                                        "ai_model": "claude-3-sonnet",
                                        "risk_factors": [
                                            "system_file_deletion",
                                            "sudo_escalation",
                                        ],
                                        "requires_approval": False,
                                    },
                                },
                                "sample_decision": {
                                    "summary": "Tool request requires evaluation",
                                    "value": {
                                        "action": "sample",
                                        "reason": "External API call requires human review",
                                        "rule_id": "network-eval-001",
                                        "confidence": 0.7,
                                        "processing_time_ms": 156,
                                        "ai_provider": "anthropic",
                                        "ai_model": "claude-3-sonnet",
                                        "risk_factors": [
                                            "external_api",
                                            "authentication_header",
                                        ],
                                        "requires_approval": True,
                                        "ai_evaluation": {
                                            "risk_level": "medium",
                                            "recommended_action": "require_approval",
                                            "analysis": "External API with auth token - verify endpoint safety",
                                        },
                                    },
                                },
                            }
                        }
                    },
                },
                400: {"description": "Invalid request parameters"},
                500: {"description": "Internal evaluation error"},
            },
        )
        async def evaluate_tool_request(request: EvaluateRequest) -> Decision:
            """Evaluate a tool request for security concerns.

            Args:
                request: Tool evaluation request

            Returns:
                Security decision for the request

            Raises:
                HTTPException: If evaluation fails
            """
            try:
                tool_request = ToolRequest(
                    tool_name=request.tool_name,
                    parameters=request.parameters,
                    agent_id=request.agent_id,
                    session_id=request.session_id,
                    cwd=request.cwd or "/tmp",
                )

                logger.info(
                    "HTTP: Evaluating tool request",
                    tool_name=request.tool_name,
                    agent_id=request.agent_id,
                    session_id=request.session_id,
                )

                decision = await self.security_policy.evaluate(tool_request)

                # Log decision to audit trail
                rule_matches = [decision.rule_id] if decision.rule_id else []
                await self.audit_logger.log_decision(
                    tool_request, decision, rule_matches
                )

                return decision

            except Exception as e:
                logger.error("HTTP: Tool evaluation failed", error=str(e))

                # Handle errors with centralized error handler
                fallback_decision = self.error_handler.handle_error(e, tool_request)

                # Log fallback decision
                await self.audit_logger.log_decision(
                    tool_request, fallback_decision, []
                )

                return fallback_decision

        @self.app.post(
            "/v1/hooks",
            response_model=PreToolUseOutput,
            summary="Evaluate Claude Code hook request",
            description="Processes Claude Code PreToolUse hook events and returns permission decisions.",
            openapi_extra={
                "examples": {
                    "claude_file_read": {
                        "summary": "Claude Code file read hook",
                        "description": "Hook triggered when Claude Code attempts to read a file",
                        "value": {
                            "session_id": "claude_sess_123",
                            "transcript_path": "/tmp/claude_transcript_123.json",
                            "cwd": "/home/user/documents",
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Read",
                            "tool_input": {
                                "file_path": "/home/user/documents/report.md",
                                "limit": 100,
                            },
                        },
                    },
                    "claude_git_operation": {
                        "summary": "Claude Code git operation hook",
                        "description": "Hook triggered when Claude Code executes git commands",
                        "value": {
                            "session_id": "claude_sess_456",
                            "transcript_path": "/tmp/claude_transcript_456.json",
                            "cwd": "/home/user/myproject",
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Bash",
                            "tool_input": {
                                "command": "git add . && git commit -m 'Update documentation'",
                                "description": "Commit documentation changes",
                            },
                        },
                    },
                    "claude_dangerous_command": {
                        "summary": "Claude Code dangerous command hook",
                        "description": "Hook triggered when Claude Code attempts risky operations",
                        "value": {
                            "session_id": "claude_sess_789",
                            "transcript_path": "/tmp/claude_transcript_789.json",
                            "cwd": "/tmp",
                            "hook_event_name": "PreToolUse",
                            "tool_name": "Bash",
                            "tool_input": {
                                "command": "curl -X DELETE https://api.production.com/delete-all",
                                "description": "Delete production data",
                            },
                        },
                    },
                }
            },
            responses={
                200: {
                    "description": "Hook evaluation completed successfully",
                    "content": {
                        "application/json": {
                            "examples": {
                                "allow_response": {
                                    "summary": "Operation allowed",
                                    "value": {
                                        "hookSpecificOutput": {
                                            "hookEventName": "PreToolUse",
                                            "permissionDecision": "allow",
                                            "permissionDecisionReason": "Safe file read operation in user directory",
                                        },
                                        "decision": "approve",
                                        "reason": "Safe file read operation in user directory",
                                    },
                                },
                                "deny_response": {
                                    "summary": "Operation denied",
                                    "value": {
                                        "hookSpecificOutput": {
                                            "hookEventName": "PreToolUse",
                                            "permissionDecision": "deny",
                                            "permissionDecisionReason": "Dangerous command detected: potential data deletion",
                                        },
                                        "decision": "block",
                                        "reason": "Dangerous command detected: potential data deletion",
                                    },
                                },
                                "ask_response": {
                                    "summary": "User approval required",
                                    "value": {
                                        "hookSpecificOutput": {
                                            "hookEventName": "PreToolUse",
                                            "permissionDecision": "ask",
                                            "permissionDecisionReason": "Git commit requires confirmation - review changes before proceeding",
                                        },
                                        "decision": "approve",
                                        "reason": "Git commit requires confirmation - review changes before proceeding",
                                    },
                                },
                            }
                        }
                    },
                },
                400: {"description": "Invalid hook request format"},
                500: {"description": "Hook evaluation error"},
            },
        )
        async def evaluate_hook_request(request: PreToolUseInput) -> PreToolUseOutput:
            """Evaluate a Claude Code PreToolUse hook request.

            Args:
                request: Claude Code hook input in the PreToolUse format

            Returns:
                Claude Code hook output with permission decision

            Raises:
                HTTPException: If evaluation fails
            """
            # Verify authentication (no credentials for now to avoid Depends issue)
            self._verify_auth(None)

            try:
                # Convert PreToolUseInput to internal ToolRequest format
                tool_request = ToolRequest(
                    tool_name=request.tool_name,
                    parameters=request.tool_input.model_dump()
                    if hasattr(request.tool_input, "model_dump")
                    else dict(request.tool_input),
                    agent_id="claude_code_hook",
                    session_id=request.session_id,
                    cwd=request.cwd,
                )

                logger.info(
                    "HTTP: Evaluating Claude Code hook request",
                    tool_name=request.tool_name,
                    session_id=request.session_id,
                    hook_event=request.hook_event_name,
                )

                # Evaluate using security policy
                decision = await self.security_policy.evaluate(tool_request)

                # Log decision to audit trail
                rule_matches = [decision.rule_id] if decision.rule_id else []
                await self.audit_logger.log_decision(
                    tool_request, decision, rule_matches
                )

                # Convert Decision to Claude Code hook format
                permission_decision = self._decision_to_permission(decision.action)

                hook_specific_output = PreToolUseHookSpecificOutput(
                    hookEventName=HookEventName.PRE_TOOL_USE,
                    permissionDecision=permission_decision,
                    permissionDecisionReason=decision.reason,
                )

                return PreToolUseOutput(
                    hookSpecificOutput=hook_specific_output,
                    decision="approve"
                    if permission_decision == PermissionDecision.ALLOW
                    else "block",
                    reason=decision.reason,
                )

            except Exception as e:
                logger.error("HTTP: Claude Code hook evaluation failed", error=str(e))

                # Handle errors with centralized error handler
                if "tool_request" in locals():
                    fallback_decision = self.error_handler.handle_error(e, tool_request)
                else:
                    # Create a minimal fallback decision if tool_request wasn't created
                    from ..domain.models import Decision

                    fallback_decision = Decision(
                        action="deny",
                        reason=f"Evaluation error: {str(e)}",
                        confidence=1.0,
                        ai_provider="error_handler",
                        ai_model="fallback",
                        processing_time_ms=0,
                    )

                # Log fallback decision if we have a tool_request
                if "tool_request" in locals():
                    await self.audit_logger.log_decision(
                        tool_request, fallback_decision, []
                    )

                # Convert to hook format (deny on error for safety)
                hook_specific_output = PreToolUseHookSpecificOutput(
                    hookEventName=HookEventName.PRE_TOOL_USE,
                    permissionDecision=PermissionDecision.DENY,
                    permissionDecisionReason=f"Evaluation error: {str(e)}",
                )

                return PreToolUseOutput(
                    hookSpecificOutput=hook_specific_output,
                    decision="block",
                    reason=f"Evaluation error: {str(e)}",
                )

        @self.app.get(
            "/v1/health",
            response_model=HealthResponse,
            summary="Check service health status",
            description="Returns the current health status of the Superego service and its components.",
            responses={
                200: {
                    "description": "Health check completed successfully",
                    "content": {
                        "application/json": {
                            "examples": {
                                "healthy_response": {
                                    "summary": "All systems healthy",
                                    "value": {
                                        "status": "healthy",
                                        "timestamp": "2024-01-15T10:30:00Z",
                                        "components": {
                                            "security_policy": {
                                                "status": "healthy",
                                                "message": "Security rules loaded successfully",
                                                "last_check": "2024-01-15T10:29:55Z",
                                            },
                                            "ai_service": {
                                                "status": "healthy",
                                                "message": "AI provider responding normally",
                                                "last_check": "2024-01-15T10:29:58Z",
                                            },
                                            "audit_logger": {
                                                "status": "healthy",
                                                "message": "Audit trail operational",
                                                "last_check": "2024-01-15T10:29:59Z",
                                            },
                                            "system_metrics": {
                                                "status": "healthy",
                                                "message": "System resources within normal limits",
                                                "last_check": "2024-01-15T10:30:00Z",
                                            },
                                        },
                                    },
                                },
                                "degraded_response": {
                                    "summary": "Service degraded but operational",
                                    "value": {
                                        "status": "degraded",
                                        "timestamp": "2024-01-15T10:30:00Z",
                                        "components": {
                                            "security_policy": {
                                                "status": "healthy",
                                                "message": "Security rules loaded successfully",
                                                "last_check": "2024-01-15T10:29:55Z",
                                            },
                                            "ai_service": {
                                                "status": "degraded",
                                                "message": "AI provider experiencing high latency",
                                                "last_check": "2024-01-15T10:29:45Z",
                                            },
                                            "audit_logger": {
                                                "status": "healthy",
                                                "message": "Audit trail operational",
                                                "last_check": "2024-01-15T10:29:59Z",
                                            },
                                            "system_metrics": {
                                                "status": "degraded",
                                                "message": "High memory usage detected",
                                                "last_check": "2024-01-15T10:30:00Z",
                                            },
                                        },
                                    },
                                },
                            }
                        }
                    },
                },
                500: {"description": "Health check failed"},
            },
        )
        async def health_check() -> HealthResponse:
            """Check the health of the Superego service.

            Returns:
                Health status information

            Raises:
                HTTPException: If health check fails
            """
            try:
                health_status = await self.health_monitor.check_health()
                return HealthResponse(
                    status=health_status.status,
                    timestamp=str(health_status.timestamp),
                    components=health_status.components,
                )
            except Exception as e:
                logger.error("HTTP: Health check failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

        @self.app.get("/v1/config/rules")
        async def get_current_rules() -> dict[str, Any]:
            """Get current security rules.

            Returns:
                Current security rules and metadata

            Raises:
                HTTPException: If rules cannot be retrieved
            """
            try:
                rules_data = {
                    "rules": [
                        rule.model_dump(mode="json")
                        for rule in self.security_policy.rules
                    ],
                    "total_rules": len(self.security_policy.rules),
                    "last_updated": (
                        self.security_policy.rules_file.stat().st_mtime
                        if self.security_policy.rules_file.exists()
                        else None
                    ),
                }
                return rules_data
            except Exception as e:
                logger.error("HTTP: Failed to get rules", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

        @self.app.get("/v1/audit/recent")
        async def get_recent_audit_entries() -> dict[str, Any]:
            """Get recent audit entries.

            Returns:
                Recent audit entries and statistics

            Raises:
                HTTPException: If audit entries cannot be retrieved
            """
            try:
                entries = self.audit_logger.get_recent_entries(limit=50)
                audit_data = {
                    "entries": [entry.model_dump(mode="json") for entry in entries],
                    "stats": self.audit_logger.get_stats(),
                }
                return audit_data
            except Exception as e:
                logger.error("HTTP: Failed to get audit entries", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

        @self.app.get("/v1/metrics")
        async def get_metrics() -> dict[str, Any]:
            """Get performance metrics.

            Returns:
                System performance metrics

            Raises:
                HTTPException: If metrics cannot be retrieved
            """
            try:
                health_status = await self.health_monitor.check_health()
                metrics = {
                    "system_metrics": health_status.components.get(
                        "system_metrics", {}
                    ),
                    "security_policy_health": health_status.components.get(
                        "security_policy", {}
                    ),
                    "audit_stats": self.audit_logger.get_stats(),
                }
                return metrics
            except Exception as e:
                logger.error("HTTP: Failed to get metrics", error=str(e))
                raise HTTPException(status_code=500, detail=str(e)) from None

        @self.app.get("/v1/server-info")
        async def get_server_info() -> dict[str, Any]:
            """Get server information.

            Returns:
                Server configuration and status information
            """
            return {
                "name": "superego-mcp",
                "version": "0.0.0",
                "description": "Intelligent tool request interception for AI agents",
                "transport": "http",
                "endpoints": {
                    "evaluate": "/v1/evaluate",
                    "hooks": "/v1/hooks",
                    "health": "/v1/health",
                    "rules": "/v1/config/rules",
                    "audit": "/v1/audit/recent",
                    "metrics": "/v1/metrics",
                    "docs": "/docs",
                    "redoc": "/redoc",
                },
                "config": {
                    "host": self.config.get("host", "localhost"),
                    "port": self.config.get("port", 8000),
                    "cors_origins": self.config.get("cors_origins", ["*"]),
                },
            }

        # Global exception handler
        @self.app.exception_handler(Exception)
        async def global_exception_handler(
            request: Request, exc: Exception
        ) -> JSONResponse:
            """Global exception handler for unhandled errors."""
            logger.error(
                "HTTP: Unhandled exception", error=str(exc), path=str(request.url)
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error": str(exc),
                    "transport": "http",
                },
            )

    async def start(self) -> None:
        """Start the HTTP server."""
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 8000)

        logger.info("Starting HTTP transport", host=host, port=port)

        # Create uvicorn config
        config = Config(
            app=self.app,
            host=host,
            port=port,
            log_config=None,  # Use structlog instead
        )

        # Create server
        server = Server(config)
        self.server = server

        try:
            await server.serve()
        except Exception as e:
            logger.error("HTTP transport failed", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self.server:
            logger.info("Stopping HTTP transport")
            self.server.should_exit = True
            # Give it a moment to shut down gracefully
            await asyncio.sleep(0.1)

    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance.

        Returns:
            FastAPI application instance
        """
        return self.app
