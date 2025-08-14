#!/usr/bin/env python3
"""
Quick test script to verify the new real AI provider functionality.
"""

import sys
from pathlib import Path

# Add the project source directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "demo"))

from base_demo import BaseDemo


class TestDemo(BaseDemo):
    """Simple test demo for real AI functionality."""
    
    def run(self):
        """Run a few test scenarios."""
        print(f"\n{'='*60}")
        print(f"Testing AI Provider: {self.ai_provider}")
        print(f"{'='*60}")
        
        # Test scenarios that should trigger sampling
        scenarios = [
            {
                "tool_name": "Write",
                "parameters": {"file_path": "test.py", "content": "print('hello')"},
                "description": "Write a simple Python file"
            },
            {
                "tool_name": "Bash", 
                "parameters": {"command": "ls -la"},
                "description": "List directory contents"
            },
            {
                "tool_name": "Edit",
                "parameters": {"file_path": "config.yaml", "old_string": "old", "new_string": "new"},
                "description": "Edit configuration file"
            }
        ]
        
        print(f"Running {len(scenarios)} test scenarios...")
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n--- Test {i}/{len(scenarios)} ---")
            self.process_tool_request(
                tool_name=scenario["tool_name"],
                parameters=scenario["parameters"], 
                description=scenario["description"]
            )
        
        # Display results
        self.display_summary()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Real AI Provider Functionality")
    BaseDemo.add_common_arguments(parser)
    args = parser.parse_args()
    
    print(f"Testing with AI provider: {args.ai_provider}")
    if args.ai_provider == "claude_cli":
        import os
        import subprocess
        
        # Test Claude CLI availability
        try:
            result = subprocess.run(["claude", "-p", "test"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                api_key = os.getenv(args.api_key_env) if args.api_key_env else None
                auth_method = "API key" if api_key else "OAuth/CLI auth"
                print(f"Claude CLI is working with {auth_method}")
            else:
                print("Claude CLI test failed - will fall back to mock")
        except Exception as e:
            print(f"Claude CLI not available: {e} - will fall back to mock")
    
    try:
        demo = TestDemo(
            demo_name="test_real_ai",
            log_level=args.log_level,
            rules_file=args.rules_file,
            ai_provider=args.ai_provider,
            claude_model=args.claude_model,
            api_key_env=args.api_key_env
        )
        demo.run()
        
    except KeyboardInterrupt:
        print("\nTest interrupted")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()