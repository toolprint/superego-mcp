"""FastMCP Server Implementation for Superego MCP Server."""

import json

import yaml
from fastmcp import Context, FastMCP

from ..domain.models import ToolRequest
from ..domain.security_policy import SecurityPolicyEngine
from ..infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor
from ..infrastructure.security_formatter import SecurityDecisionFormatter

# Initialize FastMCP server with sampling support
mcp: FastMCP = FastMCP(
    name="Superego MCP Server",
    instructions="Security evaluation and policy enforcement for AI agent tool usage with AI-based sampling support",
)

# Global components (will be injected)
security_policy: SecurityPolicyEngine | None = None
audit_logger: AuditLogger | None = None
error_handler: ErrorHandler | None = None
health_monitor: HealthMonitor | None = None
decision_formatter: SecurityDecisionFormatter | None = None


@mcp.tool
async def evaluate_tool_request(
    tool_name: str,
    parameters: dict,
    session_id: str,
    agent_id: str,
    cwd: str,
    ctx: Context,
) -> dict:
    """Evaluate tool request for security compliance"""

    try:
        # Create domain model from request
        request = ToolRequest(
            tool_name=tool_name,
            parameters=parameters,
            session_id=session_id,
            agent_id=agent_id,
            cwd=cwd,
        )

        # Apply security policy evaluation
        if security_policy is None:
            raise RuntimeError("Security policy engine not initialized")
        decision = await security_policy.evaluate(request)

        # Display security decision if formatter is available
        if decision_formatter is not None:
            decision_formatter.display_decision(request, decision)

        # Extract rule matches for audit trail
        rule_matches = []
        if decision.rule_id:
            rule_matches.append(decision.rule_id)

        # Log decision to audit trail
        if audit_logger is None:
            raise RuntimeError("Audit logger not initialized")
        await audit_logger.log_decision(request, decision, rule_matches)

        # Return MCP-compatible response
        return {
            "action": decision.action,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "processing_time_ms": decision.processing_time_ms,
            "rule_id": decision.rule_id,
        }

    except Exception as e:
        # Handle errors with centralized error handler
        if error_handler is None:
            raise RuntimeError("Error handler not initialized") from e
        fallback_decision = error_handler.handle_error(e, request)

        # Still log the fallback decision
        if audit_logger is None:
            raise RuntimeError("Audit logger not initialized") from e
        await audit_logger.log_decision(request, fallback_decision, [])

        return {
            "action": fallback_decision.action,
            "reason": fallback_decision.reason,
            "confidence": fallback_decision.confidence,
            "processing_time_ms": fallback_decision.processing_time_ms,
            "error": True,
        }


@mcp.resource("config://rules")
async def get_current_rules() -> str:
    """Expose current security rules as MCP resource"""
    try:
        # Read current rules from file and serialize safely
        if security_policy is None:
            raise RuntimeError("Security policy engine not initialized")
        rules_data = {
            "rules": [rule.model_dump(mode="json") for rule in security_policy.rules],
            "total_rules": len(security_policy.rules),
            "last_updated": security_policy.rules_file.stat().st_mtime,
        }
        return yaml.dump(rules_data, default_flow_style=False)

    except Exception as e:
        return f"Error loading rules: {str(e)}"


@mcp.resource("audit://recent")
async def get_recent_audit_entries() -> str:
    """Expose recent audit entries for monitoring"""
    try:
        if audit_logger is None:
            raise RuntimeError("Audit logger not initialized")
        entries = audit_logger.get_recent_entries(limit=50)
        audit_data = {
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "stats": audit_logger.get_stats(),
        }
        return json.dumps(audit_data, indent=2, default=str)

    except Exception as e:
        return f"Error loading audit entries: {str(e)}"


@mcp.resource("health://status")
async def get_health_status() -> str:
    """Expose system health status"""
    try:
        # Health check will be injected from main
        if health_monitor is None:
            raise RuntimeError("Health monitor not initialized")
        health_status = await health_monitor.check_health()
        return json.dumps(health_status.model_dump(mode="json"), indent=2, default=str)

    except Exception as e:
        return f"Error checking health: {str(e)}"


@mcp.tool
async def evaluate_tool_with_human_review(
    tool_name: str,
    parameters: dict,
    session_id: str,
    agent_id: str,
    cwd: str,
    human_justification: str,
    ctx: Context,
) -> dict:
    """Evaluate tool request with additional human justification for sensitive operations"""

    try:
        # Create domain model from request
        request = ToolRequest(
            tool_name=tool_name,
            parameters=parameters,
            session_id=session_id,
            agent_id=agent_id,
            cwd=cwd,
        )

        # Apply security policy evaluation
        if security_policy is None:
            raise RuntimeError("Security policy engine not initialized")
        decision = await security_policy.evaluate(request)

        # Log the human justification along with the decision
        {
            "human_justification": human_justification,
            "decision": decision.model_dump(),
        }

        # Extract rule matches for audit trail
        rule_matches = []
        if decision.rule_id:
            rule_matches.append(decision.rule_id)

        # Log decision to audit trail with extra context
        if audit_logger is None:
            raise RuntimeError("Audit logger not initialized")
        await audit_logger.log_decision(request, decision, rule_matches)

        # Return MCP-compatible response with human review flag
        return {
            "action": decision.action,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "processing_time_ms": decision.processing_time_ms,
            "rule_id": decision.rule_id,
            "human_reviewed": True,
            "ai_provider": decision.ai_provider,
            "risk_factors": decision.risk_factors,
        }

    except Exception as e:
        # Handle errors with centralized error handler
        if error_handler is None:
            raise RuntimeError("Error handler not initialized") from e
        fallback_decision = error_handler.handle_error(e, request)

        # Still log the fallback decision
        if audit_logger is None:
            raise RuntimeError("Audit logger not initialized") from e
        await audit_logger.log_decision(request, fallback_decision, [])

        return {
            "action": fallback_decision.action,
            "reason": fallback_decision.reason,
            "confidence": fallback_decision.confidence,
            "processing_time_ms": fallback_decision.processing_time_ms,
            "error": True,
            "human_reviewed": True,
        }


@mcp.resource("config://ai-sampling")
async def get_ai_sampling_config() -> str:
    """Expose current AI sampling configuration"""
    try:
        # Get AI service health from security policy
        if security_policy is None:
            raise RuntimeError("Security policy engine not initialized")
        health_data = security_policy.health_check()
        ai_config = health_data.get("ai_service", {})

        return json.dumps(ai_config, indent=2, default=str)

    except Exception as e:
        return f"Error loading AI sampling config: {str(e)}"


# Server startup and dependency injection
async def create_server(
    security_policy_engine: SecurityPolicyEngine,
    audit_log: AuditLogger,
    err_handler: ErrorHandler,
    health_mon: HealthMonitor,
    show_decisions: bool = True,
) -> FastMCP:
    """Create and configure MCP server with dependencies"""

    # Inject dependencies into global scope (for Day 1 simplicity)
    global \
        security_policy, \
        audit_logger, \
        error_handler, \
        health_monitor, \
        decision_formatter
    security_policy = security_policy_engine
    audit_logger = audit_log
    error_handler = err_handler
    health_monitor = health_mon
    decision_formatter = SecurityDecisionFormatter() if show_decisions else None

    return mcp


# Entry point for STDIO transport
def run_stdio_server() -> None:
    """Run MCP server with STDIO transport for Claude Code"""
    # FastMCP 2.0 automatically handles sampling requests when needed
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio_server()
