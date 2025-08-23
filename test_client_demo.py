#!/usr/bin/env python3
"""Quick demonstration of the Superego HTTP client and response formatting.

This script shows how to use the SuperegoTestClient and ResponseFormatter
components for testing the Superego MCP server.
"""

import asyncio
import time
from typing import Dict, Any

from test_harness.config.loader import load_config
from test_harness.client.superego_client import SuperegoTestClient, SuperegoClientError
from test_harness.client.response_formatter import ResponseFormatter, create_test_result


async def demo_client_and_formatter() -> None:
    """Demonstrate the HTTP client and response formatter functionality."""
    print("🚀 Superego HTTP Client and Response Formatter Demo")
    print("=" * 60)
    
    # Load configuration
    try:
        config = load_config("default")
        print(f"✓ Configuration loaded (server: {config.server.base_url})")
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return
    
    # Initialize formatter
    formatter = ResponseFormatter(colors=True)
    test_results = []
    
    # Test the client functionality
    async with SuperegoTestClient(config) as client:
        print("\n🔍 Testing SuperegoTestClient methods...")
        
        # Test health check
        print("\n1. Health Check Test")
        try:
            start_time = time.perf_counter()
            health_data = await client.check_health()
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            result = create_test_result(
                success=True,
                response_data=health_data,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Health Check",
                endpoint="/v1/health",
                method="GET"
            )
            test_results.append(result)
            formatter.format_pretty(result)
            
        except SuperegoClientError as e:
            result = create_test_result(
                success=False,
                response_time_ms=0.0,
                test_name="Health Check",
                endpoint="/v1/health",
                method="GET",
                error_message=str(e),
                error_type=type(e).__name__
            )
            test_results.append(result)
            formatter.format_pretty(result)
        
        # Test tool evaluation
        print("\n2. Tool Evaluation Test")
        try:
            start_time = time.perf_counter()
            eval_result = await client.evaluate_tool(
                tool_name="test_tool",
                parameters={"action": "demo", "safe": True},
                agent_id="demo-agent",
                session_id="demo-session"
            )
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            result = create_test_result(
                success=True,
                response_data=eval_result,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Tool Evaluation",
                endpoint="/v1/evaluate",
                method="POST",
                agent_id="demo-agent",
                session_id="demo-session"
            )
            test_results.append(result)
            formatter.format_pretty(result)
            
        except SuperegoClientError as e:
            result = create_test_result(
                success=False,
                response_time_ms=0.0,
                test_name="Tool Evaluation",
                endpoint="/v1/evaluate",
                method="POST",
                error_message=str(e),
                error_type=type(e).__name__,
                agent_id="demo-agent",
                session_id="demo-session"
            )
            test_results.append(result)
            formatter.format_pretty(result)
        
        # Test Claude Code hook
        print("\n3. Claude Code Hook Test")
        try:
            start_time = time.perf_counter()
            hook_result = await client.test_claude_hook(
                event_name="pre_tool_use",
                tool_name="test_tool",
                arguments={"action": "demo", "safe": True},
                agent_id="demo-agent",
                session_id="demo-session"
            )
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            result = create_test_result(
                success=True,
                response_data=hook_result,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Claude Code Hook",
                endpoint="/v1/hooks",
                method="POST",
                agent_id="demo-agent",
                session_id="demo-session"
            )
            test_results.append(result)
            formatter.format_pretty(result)
            
        except SuperegoClientError as e:
            result = create_test_result(
                success=False,
                response_time_ms=0.0,
                test_name="Claude Code Hook",
                endpoint="/v1/hooks",
                method="POST",
                error_message=str(e),
                error_type=type(e).__name__,
                agent_id="demo-agent",
                session_id="demo-session"
            )
            test_results.append(result)
            formatter.format_pretty(result)
    
    # Demonstrate different output formats
    print("\n📊 Response Formatting Demo")
    print("=" * 60)
    
    # Table format
    print("\n🏆 Table Format:")
    formatter.format_table(test_results)
    
    # Summary format
    print("\n📈 Summary Format:")
    formatter.format_summary(test_results)
    
    # JSON format (print directly)
    print("\n📋 JSON Format:")
    json_output = formatter.format_json(test_results)
    print(json_output[:500] + "..." if len(json_output) > 500 else json_output)
    
    # Tree format grouped by endpoint
    print("\n🌳 Tree Format (grouped by endpoint):")
    formatter.format_tree(test_results, group_by="endpoint")
    
    print("\n✅ Demo completed!")
    print(f"📊 Total tests executed: {len(test_results)}")
    passed = sum(1 for r in test_results if r.success)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {len(test_results) - passed}")


if __name__ == "__main__":
    try:
        asyncio.run(demo_client_and_formatter())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()