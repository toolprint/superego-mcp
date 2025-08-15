#!/usr/bin/env python3
"""
Manual test for CLI evaluation without dependencies.

This simulates exactly how the CLI would be called as a Claude Code hook.
"""

import json
import sys
from pathlib import Path

# Add src to path to import without installation
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_cli_direct():
    """Test the CLI module directly."""

    # Test cases
    test_cases = [
        {
            "name": "Safe command",
            "input": {
                "session_id": "test",
                "transcript_path": "",
                "cwd": "/tmp",
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "echo hello"},
            },
        },
        {
            "name": "Dangerous command",
            "input": {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
        },
    ]

    print("Testing CLI module directly...")
    print("=" * 50)

    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print("-" * 30)

        # Prepare input
        input_json = json.dumps(test_case["input"])
        print(f"Input: {input_json}")

        try:
            # Import and test the module
            import asyncio
            import sys
            from io import StringIO

            from superego_mcp.cli_eval import CLIEvaluator

            # Mock stdin with our test input
            original_stdin = sys.stdin
            sys.stdin = StringIO(input_json)

            # Create evaluator and run
            evaluator = CLIEvaluator()
            result = asyncio.run(evaluator.evaluate_from_stdin())

            # Restore stdin
            sys.stdin = original_stdin

            # Display result
            print(f"Output: {json.dumps(result, indent=2)}")

            # Validate format
            assert "hookSpecificOutput" in result
            hook_output = result["hookSpecificOutput"]
            assert hook_output["hookEventName"] == "PreToolUse"
            assert hook_output["permissionDecision"] in ["allow", "deny", "ask"]

            print("✅ Success - Valid Claude Code hook output format")

        except ImportError as e:
            print(f"⚠️  Import error (expected without dependencies): {e}")
            print("Note: This is expected when dependencies are not installed")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_cli_direct()
