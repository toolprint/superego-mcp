#!/usr/bin/env python3
"""
Direct MCP server test - bypasses FastAgent to test server functionality.
"""

import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def test_mcp_server_direct():
    """Test the MCP server directly via STDIO."""
    print("🧪 Testing MCP Server Direct Communication")
    print("=" * 50)
    
    # Test data for MCP communication
    test_requests = [
        {
            "name": "Initialize",
            "request": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    },
                    "capabilities": {}
                }
            }
        },
        {
            "name": "List Tools",
            "request": {
                "jsonrpc": "2.0", 
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
        },
        {
            "name": "Test Tool Request - Safe (read_file)",
            "request": {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "evaluate_tool_request",
                    "arguments": {
                        "tool_name": "read_file",
                        "parameters": {"path": "/home/user/config.yaml"},
                        "session_id": "test-session",
                        "agent_id": "test-agent", 
                        "cwd": "/home/user"
                    }
                }
            }
        },
        {
            "name": "Test Tool Request - Dangerous (sudo rm)",
            "request": {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "evaluate_tool_request",
                    "arguments": {
                        "tool_name": "execute_command",
                        "parameters": {"command": "sudo rm -rf /"},
                        "session_id": "test-session",
                        "agent_id": "test-agent",
                        "cwd": "/home/user"
                    }
                }
            }
        },
        {
            "name": "Test Tool Request - Complex (write_file)",
            "request": {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "evaluate_tool_request",
                    "arguments": {
                        "tool_name": "write_file",
                        "parameters": {"path": "/tmp/test.sh", "content": "#!/bin/bash\necho 'Hello World'"},
                        "session_id": "test-session",
                        "agent_id": "test-agent",
                        "cwd": "/home/user"
                    }
                }
            }
        }
    ]
    
    for test in test_requests:
        print(f"\n📋 {test['name']}")
        print("-" * 30)
        
        try:
            # Start the MCP server process
            cmd = ["uv", "run", "python", "-m", "superego_mcp.stdio_main"]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            # Send the request
            request_json = json.dumps(test['request']) + '\n'
            print(f"📤 Sending: {request_json.strip()}")
            
            stdout, stderr = process.communicate(
                input=request_json,
                timeout=10  # 10 second timeout
            )
            
            if process.returncode == 0:
                print(f"✅ Success!")
                print(f"📥 Response: {stdout.strip()}")
                if stderr.strip():
                    print(f"🔍 Logs: {stderr.strip()}")
            else:
                print(f"❌ Failed (code {process.returncode})")
                if stdout.strip():
                    print(f"📥 Stdout: {stdout.strip()}")
                if stderr.strip():
                    print(f"🚨 Stderr: {stderr.strip()}")
                    
        except subprocess.TimeoutExpired:
            print("⏱️  Timeout - server took too long to respond")
            process.kill()
        except Exception as e:
            print(f"❌ Error: {e}")
            
        print()


def test_import():
    """Test that we can import the STDIO module."""
    print("🧪 Testing Module Import")
    print("=" * 50)
    
    try:
        from superego_mcp.stdio_main import main
        print("✅ Successfully imported stdio_main.main")
        
        from superego_mcp.stdio_main import initialize_server_components
        print("✅ Successfully imported initialize_server_components")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_basic_startup():
    """Test that the server can start without errors."""
    print("🧪 Testing Basic Server Startup")
    print("=" * 50)
    
    try:
        cmd = ["uv", "run", "python", "-c", "from superego_mcp.stdio_main import main; print('Import successful')"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode == 0:
            print("✅ Basic startup test passed")
            print(f"📥 Output: {result.stdout.strip()}")
            if result.stderr.strip():
                print(f"🔍 Logs: {result.stderr.strip()}")
            return True
        else:
            print(f"❌ Basic startup failed (code {result.returncode})")
            if result.stdout.strip():
                print(f"📥 Stdout: {result.stdout.strip()}")
            if result.stderr.strip():
                print(f"🚨 Stderr: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"❌ Startup test error: {e}")
        return False


def main():
    """Run all tests."""
    print("🛡️  Superego MCP Server - Direct Testing")
    print("=" * 60)
    print()
    
    # Test 1: Import test
    if not test_import():
        print("❌ Import test failed - stopping here")
        return False
    
    print()
    
    # Test 2: Basic startup
    if not test_basic_startup():
        print("❌ Basic startup failed - MCP communication test may fail")
    
    print()
    
    # Test 3: Direct MCP communication
    test_mcp_server_direct()
    
    print("\n✅ All tests completed!")
    print("If any tests failed, check the error messages above.")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)