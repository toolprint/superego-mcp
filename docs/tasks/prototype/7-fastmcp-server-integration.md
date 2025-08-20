---
schema: 1
id: 7
title: FastMCP Server Integration
status: done
created: "2025-08-11T05:47:14.858Z"
updated: "2025-08-11T07:10:43.710Z"
tags:
  - phase1
  - infrastructure
  - high-priority
  - large
dependencies:
  - 1
  - 2
  - 6
---
## Description
Implement MCP server with FastMCP 2.0 framework, STDIO transport, and complete request processing pipeline

## Details
Implement MCP server with FastMCP 2.0 framework and STDIO transport for Superego MCP Server.

Technical Requirements:
- FastMCP 2.0 server with tool and resource endpoints
- STDIO transport for Claude Code integration
- Request processing pipeline with security evaluation
- MCP resource endpoints for configuration exposure

FastMCP Server Implementation:
```python
from fastmcp import FastMCP, Context
import asyncio
import yaml
import json
from typing import Dict, Any

# Initialize FastMCP server
mcp = FastMCP("Superego MCP Server")

# Global components (will be injected)
security_policy: SecurityPolicyEngine = None
audit_logger: AuditLogger = None  
error_handler: ErrorHandler = None

@mcp.tool
async def evaluate_tool_request(
    tool_name: str,
    parameters: dict,
    session_id: str,
    agent_id: str,
    cwd: str,
    ctx: Context
) -> dict:
    """Evaluate tool request for security compliance"""
    
    try:
        # Create domain model from request
        request = ToolRequest(
            tool_name=tool_name,
            parameters=parameters,
            session_id=session_id,
            agent_id=agent_id,
            cwd=cwd
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
            "rule_id": decision.rule_id
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
            "error": True
        }

@mcp.resource("config://rules")
async def get_current_rules() -> str:
    """Expose current security rules as MCP resource"""
    try:
        # Read current rules from file
        rules_data = {
            'rules': [rule.model_dump() for rule in security_policy.rules],
            'total_rules': len(security_policy.rules),
            'last_updated': security_policy.rules_file.stat().st_mtime
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
            'entries': [entry.model_dump() for entry in entries],
            'stats': audit_logger.get_stats()
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
        return json.dumps(health_status.model_dump(), indent=2, default=str)
        
    except Exception as e:
        return f"Error checking health: {str(e)}"

# Server startup and dependency injection
async def create_server(
    security_policy_engine: SecurityPolicyEngine,
    audit_log: AuditLogger,
    err_handler: ErrorHandler,
    health_mon: HealthMonitor
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
```

Main Application Bootstrap:
```python
# src/superego_mcp/main.py
import asyncio
import logging
from pathlib import Path

from .domain.models import *
from .domain.security_policy import SecurityPolicyEngine  
from .infrastructure.error_handler import ErrorHandler, AuditLogger, HealthMonitor
from .infrastructure.circuit_breaker import CircuitBreaker
from .presentation.mcp_server import create_server, run_stdio_server

async def main():
    """Main application bootstrap"""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize configuration paths
    config_dir = Path("config")
    rules_file = config_dir / "rules.yaml"
    
    # Create components
    security_policy = SecurityPolicyEngine(rules_file)
    error_handler = ErrorHandler()
    audit_logger = AuditLogger()
    health_monitor = HealthMonitor()
    
    # Register components for health monitoring
    health_monitor.register_component("security_policy", security_policy)
    health_monitor.register_component("audit_logger", audit_logger)
    
    # Create and run MCP server
    server = await create_server(
        security_policy, 
        audit_logger, 
        error_handler,
        health_monitor
    )
    
    # Run with STDIO transport
    print("Starting Superego MCP Server with STDIO transport...")
    run_stdio_server()

if __name__ == "__main__":
    asyncio.run(main())
```

Implementation Steps:
1. Create src/superego_mcp/presentation/mcp_server.py  
2. Implement FastMCP tool and resource endpoints
3. Add request processing pipeline with error handling
4. Create main.py with component bootstrapping
5. Add STDIO transport configuration
6. Implement server integration tests
EOF < /dev/null

## Validation
- [ ] FastMCP server starts successfully with STDIO transport
- [ ] evaluate_tool_request tool processes requests correctly
- [ ] Resource endpoints expose rules, audit data, health status
- [ ] Error handling integrates with centralized ErrorHandler
- [ ] Component dependency injection works correctly
- [ ] Tests: Tool invocation, resource access, error scenarios

Test scenarios:
1. Start server with STDIO transport - should initialize without errors
2. Call evaluate_tool_request with valid data - should return decision
3. Access config://rules resource - should return YAML rules data
4. Access audit://recent resource - should return JSON audit entries
5. Access health://status resource - should return health information
6. Test error handling with invalid requests
7. Verify dependency injection works correctly