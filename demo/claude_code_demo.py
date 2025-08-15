#!/usr/bin/env python3
"""
Claude Code Demo Script for Superego MCP

This demo showcases the security evaluation capabilities of Superego MCP
using the hook-based test harness for consistent ToolRequest triggering.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Add the project source directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from base_demo import BaseDemo
from demo_utils import (
    Colors,
    create_demo_header,
    format_timestamp,
    parse_common_args,
    prompt_yes_no,
    display_scenario_menu,
    create_standard_scenarios
)


class ClaudeCodeDemo(BaseDemo):
    """Interactive demo for Superego MCP using hook simulation."""
    
    def __init__(self, **kwargs):
        """Initialize the Claude Code demo."""
        super().__init__(demo_name="claude_code", **kwargs)
        
        # Demo-specific configuration
        self.scenarios = self._create_claude_code_scenarios()
    
    def _create_claude_code_scenarios(self) -> List[Dict[str, Any]]:
        """Create Claude Code specific test scenarios."""
        return [
            # Safe file operations
            {
                "tool_name": "Read",
                "parameters": {"file_path": "./demo/README.md"},
                "description": "Safe file read - Reading documentation"
            },
            {
                "tool_name": "Write",
                "parameters": {
                    "file_path": "/tmp/demo_output.json",
                    "content": '{"demo": true, "timestamp": "2024-01-01"}'
                },
                "description": "Safe file write - Writing to temp directory"
            },
            
            # System file access attempts
            {
                "tool_name": "Read",
                "parameters": {"file_path": "/etc/passwd"},
                "description": "System file access - Attempting to read passwd"
            },
            {
                "tool_name": "Edit",
                "parameters": {
                    "file_path": "/etc/hosts",
                    "old_string": "127.0.0.1 localhost",
                    "new_string": "127.0.0.1 malicious.com"
                },
                "description": "System file modification - Attempting to edit hosts"
            },
            
            # Code execution
            {
                "tool_name": "Bash",
                "parameters": {
                    "command": "ls -la",
                    "description": "List directory contents"
                },
                "description": "Safe command - Directory listing"
            },
            {
                "tool_name": "Bash",
                "parameters": {
                    "command": "rm -rf /",
                    "description": "Delete all system files"
                },
                "description": "Dangerous command - System destruction attempt"
            },
            
            # Git operations
            {
                "tool_name": "Bash",
                "parameters": {
                    "command": "git status",
                    "description": "Check git status"
                },
                "description": "Git operation - Status check"
            },
            {
                "tool_name": "Bash",
                "parameters": {
                    "command": "git push --force origin main",
                    "description": "Force push to main branch"
                },
                "description": "Git operation - Force push (potentially dangerous)"
            },
            
            # Network operations
            {
                "tool_name": "WebFetch",
                "parameters": {
                    "url": "https://api.github.com/users/octocat",
                    "prompt": "Get user information"
                },
                "description": "API request - GitHub public API"
            },
            {
                "tool_name": "WebFetch",
                "parameters": {
                    "url": "http://suspicious-site.tk/collect",
                    "prompt": "Send data to endpoint"
                },
                "description": "Suspicious URL - Unknown domain"
            },
            
            # Path traversal attempts
            {
                "tool_name": "Read",
                "parameters": {"file_path": "./docs/../../../etc/shadow"},
                "description": "Path traversal - Attempting to access shadow file"
            },
            
            # Sensitive data search
            {
                "tool_name": "Grep",
                "parameters": {
                    "pattern": "password|secret|api_key",
                    "path": ".",
                    "output_mode": "content"
                },
                "description": "Sensitive data search - Looking for secrets"
            },
            
            # SSH key access
            {
                "tool_name": "Read",
                "parameters": {"file_path": "~/.ssh/id_rsa"},
                "description": "SSH key access - Attempting to read private key"
            },
            
            # Environment variable exposure
            {
                "tool_name": "Bash",
                "parameters": {
                    "command": "env | grep -E '(KEY|TOKEN|SECRET)'",
                    "description": "Search for sensitive environment variables"
                },
                "description": "Environment scan - Looking for credentials"
            }
        ]
    
    def run_interactive_scenario(self):
        """Run a single scenario interactively."""
        print(f"\n{Colors.BOLD}Enter Custom Tool Request{Colors.RESET}")
        
        # Get tool name
        tool_name = input("Tool name (e.g., Read, Write, Bash): ").strip()
        if not tool_name:
            print(f"{Colors.RED}Tool name is required{Colors.RESET}")
            return
        
        # Get parameters
        print("Enter parameters (one per line, format: key=value)")
        print("Press Enter twice when done")
        
        parameters = {}
        while True:
            line = input().strip()
            if not line:
                break
            
            if '=' in line:
                key, value = line.split('=', 1)
                parameters[key.strip()] = value.strip()
            else:
                print(f"{Colors.YELLOW}Invalid format. Use: key=value{Colors.RESET}")
        
        if not parameters:
            print(f"{Colors.RED}No parameters provided{Colors.RESET}")
            return
        
        # Get description
        description = input("Description (optional): ").strip()
        
        # Process the request
        self.process_tool_request(tool_name, parameters, description or f"Custom {tool_name} request")
    
    def run_demo_mode(self):
        """Run the demo in demonstration mode."""
        print(f"\n{Colors.BOLD}Demo Mode - Running Pre-defined Scenarios{Colors.RESET}")
        print("This will demonstrate various security evaluations.\n")
        
        for i, scenario in enumerate(self.scenarios, 1):
            print(f"\n{Colors.CYAN}Scenario {i}/{len(self.scenarios)}{Colors.RESET}")
            
            if not prompt_yes_no(f"Run: {scenario['description']}?", default=True):
                print(f"{Colors.YELLOW}Skipped{Colors.RESET}")
                continue
            
            self.process_tool_request(
                scenario["tool_name"],
                scenario["parameters"],
                scenario["description"]
            )
            
            # Brief pause for readability
            import time
            time.sleep(0.5)
        
        self.display_summary()
    
    def run_interactive_mode(self):
        """Run the demo in interactive mode."""
        print(f"\n{Colors.BOLD}Interactive Mode{Colors.RESET}")
        print("Enter tool requests to see how Superego evaluates them.")
        print("Commands: 'help', 'scenarios', 'custom', 'summary', 'exit'\n")
        
        while True:
            command = input(f"\n{Colors.CYAN}Command>{Colors.RESET} ").strip().lower()
            
            if command == "exit":
                break
            elif command == "help":
                self._show_help()
            elif command == "scenarios":
                self._run_scenario_menu()
            elif command == "custom":
                self.run_interactive_scenario()
            elif command == "summary":
                self.display_summary()
            else:
                print(f"{Colors.YELLOW}Unknown command. Type 'help' for options.{Colors.RESET}")
    
    def _show_help(self):
        """Display help information."""
        help_text = f"""
{Colors.BOLD}Available Commands:{Colors.RESET}
  help      - Show this help message
  scenarios - Choose from pre-defined scenarios
  custom    - Enter a custom tool request
  summary   - Show evaluation summary
  exit      - Exit interactive mode

{Colors.BOLD}Example Tools:{Colors.RESET}
  Read      - Read file contents
  Write     - Write to a file
  Edit      - Edit file contents
  Bash      - Execute shell commands
  WebFetch  - Fetch web content
  Grep      - Search file contents
  LS        - List directory contents

{Colors.BOLD}Example Parameters:{Colors.RESET}
  file_path=/tmp/test.txt
  command=ls -la
  url=https://example.com
  pattern=TODO
"""
        print(help_text)
    
    def _run_scenario_menu(self):
        """Display and run scenarios from a menu."""
        choice = display_scenario_menu(self.scenarios)
        
        if choice is None:
            return
        elif choice == -1:  # Run all
            for scenario in self.scenarios:
                self.process_tool_request(
                    scenario["tool_name"],
                    scenario["parameters"],
                    scenario["description"]
                )
        else:
            scenario = self.scenarios[choice]
            self.process_tool_request(
                scenario["tool_name"],
                scenario["parameters"],
                scenario["description"]
            )
    
    def run(self):
        """Main entry point for the demo."""
        print(create_demo_header("Superego MCP - Claude Code Demo"))
        print(f"\nThis demo showcases security evaluation using hook-based simulation.")
        print(f"Session ID: {self.session_id}")
        print(f"Time: {format_timestamp()}\n")
        
        # Choose mode
        print(f"{Colors.BOLD}Select Mode:{Colors.RESET}")
        print("1. Demo mode (run pre-defined scenarios)")
        print("2. Interactive mode (create custom requests)")
        print("3. Both modes")
        
        while True:
            choice = input("\nChoice (1-3): ").strip()
            
            if choice == "1":
                self.run_demo_mode()
                break
            elif choice == "2":
                self.run_interactive_mode()
                break
            elif choice == "3":
                self.run_demo_mode()
                self.run_interactive_mode()
                break
            else:
                print(f"{Colors.YELLOW}Invalid choice. Please enter 1, 2, or 3.{Colors.RESET}")
        
        # Show final summary
        print(f"\n{Colors.BOLD}Final Summary{Colors.RESET}")
        self.display_summary()
        
        # Offer to save results
        if prompt_yes_no("\nSave results to file?", default=False):
            self.save_results()
            print(f"{Colors.GREEN}Results saved!{Colors.RESET}")


def main():
    """Main entry point."""
    args = parse_common_args("Claude Code Demo for Superego MCP")
    
    try:
        demo = ClaudeCodeDemo(
            log_level=args.log_level,
            rules_file=args.rules,
            session_id=args.session_id
        )
        
        if args.interactive:
            demo.run_interactive_mode()
        else:
            demo.run()
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Demo interrupted by user{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()