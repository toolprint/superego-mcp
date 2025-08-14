#!/usr/bin/env python3
"""
Simple FastAgent Demo for Superego MCP.

A streamlined demo showcasing basic FastAgent integration patterns
using the hook-based test harness.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Add the project source directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from base_demo import BaseDemo
from demo_utils import Colors, create_demo_header, parse_common_args


class SimpleFastAgentDemo(BaseDemo):
    """Simple FastAgent demo with essential scenarios."""
    
    def __init__(self, **kwargs):
        """Initialize the simple demo."""
        super().__init__(demo_name="simple_fastagent", **kwargs)
        
        # Create a focused set of scenarios
        self.scenarios = self._create_simple_scenarios()
    
    def _create_simple_scenarios(self) -> List[Dict[str, Any]]:
        """Create a simple set of test scenarios."""
        return [
            # Basic file operations
            {
                "tool_name": "Read",
                "parameters": {"file_path": "./README.md"},
                "description": "Read project README"
            },
            {
                "tool_name": "Write",
                "parameters": {
                    "file_path": "/tmp/test_output.txt",
                    "content": "Test output from Superego demo"
                },
                "description": "Write to temporary file"
            },
            
            # Basic commands
            {
                "tool_name": "Bash",
                "parameters": {
                    "command": "echo 'Hello from Superego'",
                    "description": "Simple echo command"
                },
                "description": "Safe echo command"
            },
            {
                "tool_name": "Bash",
                "parameters": {
                    "command": "ls -la /home",
                    "description": "List home directory"
                },
                "description": "Directory listing"
            },
            
            # Dangerous operations
            {
                "tool_name": "Read",
                "parameters": {"file_path": "/etc/shadow"},
                "description": "Attempt to read shadow file"
            },
            {
                "tool_name": "Bash",
                "parameters": {
                    "command": "rm -rf /important/data",
                    "description": "Delete important data"
                },
                "description": "Dangerous deletion command"
            },
            
            # Network operation
            {
                "tool_name": "WebFetch",
                "parameters": {
                    "url": "https://httpbin.org/json",
                    "prompt": "Get JSON test data"
                },
                "description": "Fetch test JSON data"
            },
            
            # Search operation
            {
                "tool_name": "Grep",
                "parameters": {
                    "pattern": "class|function",
                    "path": "./src",
                    "output_mode": "files_with_matches"
                },
                "description": "Find code files"
            }
        ]
    
    def run_quick_demo(self):
        """Run a quick demonstration with key scenarios."""
        print(f"\n{Colors.BOLD}Quick Demo - Essential Scenarios{Colors.RESET}")
        print("Running 3 representative scenarios:\n")
        
        # Select representative scenarios
        quick_scenarios = [
            self.scenarios[0],  # Safe read
            self.scenarios[2],  # Safe command
            self.scenarios[4]   # Dangerous read
        ]
        
        for i, scenario in enumerate(quick_scenarios, 1):
            print(f"\n{Colors.CYAN}Quick Demo {i}/3{Colors.RESET}")
            self.process_tool_request(
                scenario["tool_name"],
                scenario["parameters"],
                scenario["description"]
            )
    
    def run_full_demo(self):
        """Run all scenarios."""
        print(f"\n{Colors.BOLD}Full Demo - All Scenarios{Colors.RESET}")
        print(f"Running all {len(self.scenarios)} scenarios:\n")
        
        for i, scenario in enumerate(self.scenarios, 1):
            print(f"\n{Colors.CYAN}Scenario {i}/{len(self.scenarios)}{Colors.RESET}")
            self.process_tool_request(
                scenario["tool_name"],
                scenario["parameters"],
                scenario["description"]
            )
    
    def run(self):
        """Main entry point for the demo."""
        print(create_demo_header("Simple FastAgent Demo"))
        print(f"\nA streamlined demonstration of Superego MCP security evaluation.")
        print(f"Session ID: {self.session_id}\n")
        
        # Choose demo type
        print(f"{Colors.BOLD}Select Demo Type:{Colors.RESET}")
        print("1. Quick demo (3 scenarios)")
        print("2. Full demo (all scenarios)")
        print("3. Custom selection")
        
        while True:
            choice = input("\nChoice (1-3): ").strip()
            
            if choice == "1":
                self.run_quick_demo()
                break
            elif choice == "2":
                self.run_full_demo()
                break
            elif choice == "3":
                self._run_custom_selection()
                break
            else:
                print(f"{Colors.YELLOW}Invalid choice. Please enter 1, 2, or 3.{Colors.RESET}")
        
        # Show summary
        print(f"\n{Colors.BOLD}Demo Complete{Colors.RESET}")
        self.display_summary()
    
    def _run_custom_selection(self):
        """Allow custom scenario selection."""
        print(f"\n{Colors.BOLD}Custom Scenario Selection{Colors.RESET}")
        print("Select scenarios to run:\n")
        
        # Display all scenarios
        for i, scenario in enumerate(self.scenarios, 1):
            print(f"{i}. {scenario['description']}")
        
        print("\nEnter scenario numbers separated by commas (e.g., 1,3,5)")
        print("Or 'all' to run all scenarios")
        
        selection = input("\nSelection: ").strip()
        
        if selection.lower() == 'all':
            selected_indices = list(range(len(self.scenarios)))
        else:
            try:
                selected_indices = [int(x.strip()) - 1 for x in selection.split(',')]
                # Validate indices
                for idx in selected_indices:
                    if idx < 0 or idx >= len(self.scenarios):
                        print(f"{Colors.RED}Invalid scenario number: {idx + 1}{Colors.RESET}")
                        return
            except ValueError:
                print(f"{Colors.RED}Invalid input format{Colors.RESET}")
                return
        
        # Run selected scenarios
        print(f"\n{Colors.BOLD}Running {len(selected_indices)} Selected Scenarios{Colors.RESET}")
        for i, idx in enumerate(selected_indices, 1):
            scenario = self.scenarios[idx]
            print(f"\n{Colors.CYAN}Selection {i}/{len(selected_indices)}{Colors.RESET}")
            self.process_tool_request(
                scenario["tool_name"],
                scenario["parameters"],
                scenario["description"]
            )


def main():
    """Main entry point."""
    args = parse_common_args("Simple FastAgent Demo")
    
    try:
        demo = SimpleFastAgentDemo(
            log_level=args.log_level,
            rules_file=args.rules,
            session_id=args.session_id
        )
        
        demo.run()
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Demo interrupted{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()