#!/usr/bin/env python3
"""
Test script for the security hook.

This script tests the security hook by sending it various hook input scenarios
and verifying the responses match expected behavior.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

# Test scenarios
TEST_SCENARIOS = [
    {
        "name": "Safe file read",
        "input": {
            "session_id": "test-session",
            "transcript_path": "/tmp/test_transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {
                "file_path": "/home/user/project/README.md"
            }
        },
        "expected_continue": True
    },
    {
        "name": "System file modification attempt",
        "input": {
            "session_id": "test-session",
            "transcript_path": "/tmp/test_transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/etc/passwd",
                "old_string": "root:x:0:0:root:/root:/bin/bash",
                "new_string": "hacker:x:0:0:hacker:/root:/bin/bash"
            }
        },
        "expected_continue": False
    },
    {
        "name": "Dangerous bash command",
        "input": {
            "session_id": "test-session",
            "transcript_path": "/tmp/test_transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": "rm -rf /*"
            }
        },
        "expected_continue": False
    },
    {
        "name": "Safe debug tool",
        "input": {
            "session_id": "test-session",
            "transcript_path": "/tmp/test_transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__debug__ping",
            "tool_input": {}
        },
        "expected_continue": True
    },
    {
        "name": "PostToolUse with safe output",
        "input": {
            "session_id": "test-session",
            "transcript_path": "/tmp/test_transcript.json",
            "cwd": "/home/user/project",
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": "ls -la"
            },
            "tool_response": {
                "success": True,
                "output": "total 16\ndrwxr-xr-x  4 user user 4096 Jan 1 12:00 ."
            }
        },
        "expected_continue": True
    }
]


def run_hook_test(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single hook test scenario."""
    hook_script = Path(__file__).parent / "hooks" / "security_hook.py"
    
    if not hook_script.exists():
        raise FileNotFoundError(f"Hook script not found: {hook_script}")
    
    print(f"\n{'='*60}")
    print(f"Testing: {scenario['name']}")
    print(f"{'='*60}")
    
    # Prepare input JSON
    input_json = json.dumps(scenario["input"])
    print(f"Input: {input_json}")
    
    try:
        # Run the hook script with the test input
        result = subprocess.run(
            ["python3", str(hook_script)],
            input=input_json,
            text=True,
            capture_output=True,
            timeout=30
        )
        
        # Parse the response
        try:
            response = json.loads(result.stdout) if result.stdout else {}
        except json.JSONDecodeError:
            response = {"raw_output": result.stdout}
        
        # Check exit code and response
        success = (result.returncode == 0) == scenario["expected_continue"]
        
        result_data = {
            "scenario_name": scenario["name"],
            "success": success,
            "exit_code": result.returncode,
            "expected_continue": scenario["expected_continue"],
            "actual_continue": result.returncode == 0,
            "response": response,
            "stderr": result.stderr,
            "stdout": result.stdout
        }
        
        # Print results
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"Status: {status}")
        print(f"Exit code: {result.returncode} (expected: {0 if scenario['expected_continue'] else 1})")
        
        if response:
            print(f"Response: {json.dumps(response, indent=2)}")
        
        if result.stderr:
            print(f"Stderr: {result.stderr}")
        
        return result_data
        
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT - Hook script took too long to respond")
        return {
            "scenario_name": scenario["name"],
            "success": False,
            "error": "timeout",
            "timeout": True
        }
    except Exception as e:
        print(f"❌ ERROR - {e}")
        return {
            "scenario_name": scenario["name"],
            "success": False,
            "error": str(e)
        }


def main():
    """Run all hook test scenarios."""
    print("🧪 Testing Claude Code Security Hook")
    print("=" * 60)
    
    results = []
    total_tests = len(TEST_SCENARIOS)
    passed_tests = 0
    
    for scenario in TEST_SCENARIOS:
        result = run_hook_test(scenario)
        results.append(result)
        
        if result.get("success", False):
            passed_tests += 1
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success rate: {(passed_tests / total_tests) * 100:.1f}%")
    
    # Print failed tests
    failed_tests = [r for r in results if not r.get("success", False)]
    if failed_tests:
        print(f"\n❌ Failed tests:")
        for test in failed_tests:
            print(f"  - {test['scenario_name']}: {test.get('error', 'assertion failed')}")
    
    # Save detailed results
    output_file = Path("/tmp/hook_test_results.json")
    with open(output_file, 'w') as f:
        json.dump({
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "success_rate": (passed_tests / total_tests) * 100
            },
            "results": results
        }, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    
    # Exit with appropriate code
    sys.exit(0 if passed_tests == total_tests else 1)


if __name__ == "__main__":
    main()