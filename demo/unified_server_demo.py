#!/usr/bin/env python3
"""
Demonstration of the unified FastAPI + MCP server architecture.

This script shows how the new unified server combines both MCP protocol
and HTTP/WebSocket endpoints in a single process for improved performance
and simplified deployment.

Usage:
    python demo/unified_server_demo.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from superego_mcp.presentation.unified_server import UnifiedServer
from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.config import ServerConfig
from superego_mcp.infrastructure.error_handler import AuditLogger, ErrorHandler, HealthMonitor


async def demo_unified_server():
    """Demonstrate the unified server functionality."""
    
    print("=== Superego MCP Unified Server Demonstration ===\n")
    
    # Create minimal configuration for demo
    config = ServerConfig(
        host="localhost",
        port=8000,
        debug=True,
        rules_file="config/rules.yaml",
        hot_reload=False,
        health_check_enabled=True,
    )
    
    # Create basic components
    rules_file = Path("config") / "rules.yaml"
    health_monitor = HealthMonitor()
    audit_logger = AuditLogger()
    error_handler = ErrorHandler()
    
    # Create security policy
    security_policy = SecurityPolicyEngine(
        rules_file=rules_file,
        health_monitor=health_monitor,
    )
    
    print("1. Creating unified server instance...")
    
    # Create unified server
    unified_server = UnifiedServer(
        security_policy=security_policy,
        audit_logger=audit_logger,
        error_handler=error_handler,
        health_monitor=health_monitor,
        config=config,
    )
    
    print("   ✓ Server instance created")
    print(f"   ✓ Enabled transports: {', '.join(unified_server._get_enabled_transports())}")
    
    # Show server information
    print("\n2. Server Information:")
    server_info = await unified_server._server_info_internal()
    print(f"   ✓ Name: {server_info['name']}")
    print(f"   ✓ Architecture: {server_info['architecture']}")
    print(f"   ✓ Protocols: {', '.join(server_info['protocols'])}")
    print(f"   ✓ Transports: {', '.join(server_info['transports'])}")
    
    # Test internal evaluation
    print("\n3. Testing internal evaluation logic:")
    decision = await unified_server._evaluate_internal(
        tool_name="test_tool",
        parameters={"command": "echo 'Hello, World!'"},
        agent_id="demo_agent",
        session_id="demo_session",
        cwd="/tmp"
    )
    print(f"   ✓ Evaluation result: {decision.action}")
    print(f"   ✓ Reason: {decision.reason}")
    print(f"   ✓ Confidence: {decision.confidence}")
    
    # Test health check
    print("\n4. Testing health check:")
    health_data = await unified_server._health_check_internal()
    print(f"   ✓ Health status: {health_data.get('status', 'unknown')}")
    
    # Show FastAPI app information
    print("\n5. FastAPI Application:")
    fastapi_app = unified_server.get_fastapi_app()
    print(f"   ✓ Title: {fastapi_app.title}")
    print(f"   ✓ Version: {fastapi_app.version}")
    print("   ✓ Available endpoints:")
    for route in fastapi_app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            methods = ', '.join(route.methods)
            print(f"     - {methods}: {route.path}")
    
    # Show MCP app information
    print("\n6. FastMCP Application:")
    mcp_app = unified_server.get_mcp_app()
    print(f"   ✓ Name: {mcp_app.name}")
    print(f"   ✓ Instructions: {mcp_app.instructions}")
    
    print("\n=== Demonstration Complete ===")
    print("\nThe unified server provides:")
    print("• Single process deployment")
    print("• Both MCP and HTTP/WebSocket protocols")
    print("• Backward compatibility with existing transports")
    print("• Shared evaluation logic across protocols")
    print("• Simplified configuration and management")
    
    print(f"\nTo start the unified server in production:")
    print("  superego mcp -t unified    # Start both STDIO and HTTP")
    print("  superego mcp -t http       # Start HTTP only")
    print("  superego mcp -t stdio      # Start STDIO only (default)")


def main():
    """Main entry point."""
    try:
        asyncio.run(demo_unified_server())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo failed with error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())