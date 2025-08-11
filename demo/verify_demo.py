"""Verify FastAgent demo is ready to run.

Simple verification script to ensure all components are set up correctly.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Verify demo readiness."""
    print("🛡️  FastAgent Demo Verification")
    print("=" * 40)

    project_root = Path(__file__).parent.parent

    # Check 1: FastAgent availability
    print("\n1. Checking FastAgent availability...")
    try:
        result = subprocess.run(
            ["uv", "run", "--extra", "demo", "fast-agent", "--version"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"   ✅ FastAgent available: {version}")
        else:
            print("   ❌ FastAgent not available")
            return False
    except Exception as e:
        print(f"   ❌ Error checking FastAgent: {e}")
        return False

    # Check 2: Configuration files
    print("\n2. Checking configuration files...")
    config_files = [
        "demo/fastagent.config.yaml",
        "config/rules.yaml",
        "config/server.yaml"
    ]

    all_present = True
    for config_file in config_files:
        file_path = project_root / config_file
        if file_path.exists():
            print(f"   ✅ {config_file}")
        else:
            print(f"   ❌ Missing: {config_file}")
            all_present = False

    if not all_present:
        return False

    # Check 3: Demo files
    print("\n3. Checking demo files...")
    demo_files = [
        "demo/simple_fastagent_demo.py",
        "demo/security_scenarios.py",
        "demo/README.md"
    ]

    all_present = True
    for demo_file in demo_files:
        file_path = project_root / demo_file
        if file_path.exists():
            print(f"   ✅ {demo_file}")
        else:
            print(f"   ❌ Missing: {demo_file}")
            all_present = False

    if not all_present:
        return False

    # Check 4: MCP server can be invoked
    print("\n4. Checking MCP server command...")
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-c", "import superego_mcp.main; print('MCP server importable')"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=10
        )
        if result.returncode == 0:
            print("   ✅ MCP server module importable")
        else:
            print(f"   ❌ MCP server import failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ Error checking MCP server: {e}")
        return False

    # Success!
    print("\n🎉 All checks passed! FastAgent demo is ready.")
    print("\n📝 Quick Start:")
    print("   1. Run scenarios: just demo-scenarios")
    print("   2. Run simple demo: just demo-fastagent-simple")
    print("   3. Interactive mode: just demo-interactive")
    print("\n💡 Note: The MCP server will start automatically when FastAgent runs.")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
