#!/usr/bin/env python3
"""
Test FastAgent connection to MCP server to debug connection issues.
"""

import subprocess
import tempfile
from pathlib import Path


def test_fastagent_with_debugging():
    """Test FastAgent connection with detailed debugging."""
    print("🧪 Testing FastAgent Connection to Superego MCP")
    print("=" * 60)
    
    demo_dir = Path(__file__).parent
    project_root = demo_dir.parent
    
    print(f"📁 Demo directory: {demo_dir}")
    print(f"📁 Project root: {project_root}")
    print(f"📁 Config file: {demo_dir / 'fastagent.config.yaml'}")
    print()
    
    # Test 1: Check if MCP server can be started manually
    print("🧪 Test 1: Manual MCP Server Test")
    print("-" * 40)
    
    try:
        cmd = ["uv", "run", "python", "-m", "superego_mcp.stdio_main"]
        print(f"Running: {' '.join(cmd)}")
        
        # Test with echo to see if server responds
        echo_test = subprocess.run(
            cmd,
            input='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"test","version":"1.0"},"capabilities":{}}}\n',
            capture_output=True,
            text=True,
            timeout=10,
            cwd=project_root
        )
        
        if echo_test.returncode == 0:
            print("✅ MCP server responds to initialize")
            print(f"📥 Response: {echo_test.stdout.strip()[:200]}...")
        else:
            print(f"❌ MCP server failed (code {echo_test.returncode})")
            if echo_test.stderr:
                print(f"🚨 Error: {echo_test.stderr.strip()}")
                
    except Exception as e:
        print(f"❌ Error testing MCP server: {e}")
    
    print()
    
    # Test 2: Try FastAgent with minimal configuration
    print("🧪 Test 2: FastAgent Connection Test")
    print("-" * 40)
    
    # Create a minimal test config
    test_config = f"""
mcp:
  servers:
    superego:
      command: "uv"
      args: ["run", "python", "-m", "superego_mcp.stdio_main"]
      cwd: "{project_root}"
      env:
        SUPEREGO_LOG_LEVEL: "DEBUG"
"""
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(test_config)
            test_config_path = f.name
        
        cmd = [
            "uv", "run", "--extra", "demo",
            "fast-agent", "go",
            "--config-path", test_config_path,
            "--servers", "superego",
            "--message", "Hello test"
        ]
        
        print(f"Running: {' '.join(cmd)}")
        print(f"Config content:\n{test_config}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            cwd=project_root
        )
        
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"📥 Stdout: {result.stdout}")
        if result.stderr:
            print(f"🚨 Stderr: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error testing FastAgent: {e}")
    finally:
        # Cleanup
        try:
            Path(test_config_path).unlink()
        except:
            pass
    
    print()
    print("✅ Tests completed!")


if __name__ == "__main__":
    test_fastagent_with_debugging()