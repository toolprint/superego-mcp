"""FastMCP Server Implementation for Superego MCP Server."""

import json

import yaml
from fastmcp import Context, FastMCP

from ..domain.models import ToolRequest
from ..domain.security_policy import SecurityPolicyEngine
from ..infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor

# Initialize FastMCP server
mcp = FastMCP("Superego MCP Server")

# Global components (will be injected)
security_policy: SecurityPolicyEngine = None
audit_logger: AuditLogger = None
error_handler: ErrorHandler = None
health_monitor: HealthMonitor = None


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
        decision = await security_policy.evaluate(request)

        # Extract rule matches for audit trail
        rule_matches = []
        if decision.rule_id:
            rule_matches.append(decision.rule_id)

        # Log decision to audit trail
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
        fallback_decision = error_handler.handle_error(e, request)

        # Still log the fallback decision
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
        health_status = await health_monitor.check_health()
        return json.dumps(health_status.model_dump(mode="json"), indent=2, default=str)

    except Exception as e:
        return f"Error checking health: {str(e)}"


# Server startup and dependency injection
async def create_server(
    security_policy_engine: SecurityPolicyEngine,
    audit_log: AuditLogger,
    err_handler: ErrorHandler,
    health_mon: HealthMonitor,
) -> FastMCP:
    """Create and configure MCP server with dependencies"""

    # Inject dependencies into global scope (for Day 1 simplicity)
    global security_policy, audit_logger, error_handler, health_monitor
    security_policy = security_policy_engine
    audit_logger = audit_log
    error_handler = err_handler
    health_monitor = health_mon

    return mcp


# Entry point for STDIO transport
def run_stdio_server():
    """Run MCP server with STDIO transport for Claude Code"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio_server()
