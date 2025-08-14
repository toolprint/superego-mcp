#!/usr/bin/env python3
"""Debug environment variables during demo execution."""

import os
import sys

print("=== Environment Debug ===")
print(f"Python executable: {sys.executable}")
print(f"Working directory: {os.getcwd()}")

# Check all ANTHROPIC-related env vars
anthropic_vars = {k: v for k, v in os.environ.items() if 'ANTHROPIC' in k.upper()}
if anthropic_vars:
    print("\nANTHROPIC environment variables:")
    for k, v in anthropic_vars.items():
        # Show first/last few chars for security
        if len(v) > 10:
            display_v = f"{v[:8]}...{v[-4:]}"
        else:
            display_v = v
        print(f"  {k}: {display_v}")
else:
    print("\nNo ANTHROPIC environment variables found")

# Check if we can reproduce the CLI prompt issue
print(f"\nChecking CLI availability...")
try:
    import subprocess
    result = subprocess.run(
        ["claude", "--version"],
        capture_output=True,
        text=True,
        timeout=5,
        env=os.environ.copy()
    )
    print(f"Claude CLI version check: return_code={result.returncode}")
    if result.stdout:
        print(f"Stdout: {result.stdout.strip()}")
    if result.stderr:
        print(f"Stderr: {result.stderr.strip()}")
except Exception as e:
    print(f"CLI check failed: {e}")

print("=== End Environment Debug ===")