#!/usr/bin/env python3
"""
Interactive Inference Provider Tester

A comprehensive tool for testing and debugging inference providers.
Helps isolate issues between working and failing scenarios.
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

# Add the project source directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "demo"))

from base_demo import BaseDemo


class InteractiveTestDemo(BaseDemo):
    """Concrete implementation of BaseDemo for interactive testing."""

    def run(self):
        """Required abstract method implementation - not used in interactive mode."""
        pass


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class InferenceProviderTester:
    """Interactive tester for inference providers."""

    def __init__(self):
        """Initialize the tester."""
        self.current_provider = "mock"
        self.current_model = "claude-sonnet-4-20250514"
        self.demo_instances = {}
        self.test_results = []

        # Preset test cases
        self.preset_cases = {
            "write_simple": {
                "name": "Write Simple File",
                "tool_name": "Write",
                "parameters": {"file_path": "test.py", "content": "print('hello')"},
                "description": "Write a simple Python file",
            },
            "bash_ls": {
                "name": "List Directory",
                "tool_name": "Bash",
                "parameters": {"command": "ls -la"},
                "description": "List directory contents",
            },
            "edit_config": {
                "name": "Edit Config File",
                "tool_name": "Edit",
                "parameters": {
                    "file_path": "config.yaml",
                    "old_string": "old",
                    "new_string": "new",
                },
                "description": "Edit configuration file",
            },
            "write_complex": {
                "name": "Write Complex File",
                "tool_name": "Write",
                "parameters": {
                    "file_path": "./src/new_module.py",
                    "content": "# New module\n\ndef main():\n    pass\n",
                },
                "description": "Creating a new file in project directory",
            },
            "bash_dangerous": {
                "name": "Dangerous Command",
                "tool_name": "Bash",
                "parameters": {
                    "command": "rm -rf /tmp/test",
                    "description": "Delete test files",
                },
                "description": "Running potentially dangerous command",
            },
            "read_sensitive": {
                "name": "Read Sensitive File",
                "tool_name": "Read",
                "parameters": {"file_path": "/etc/passwd"},
                "description": "Attempting to read system files",
            },
        }

    def get_demo_instance(self, provider: str) -> BaseDemo:
        """Get or create a demo instance for the specified provider."""
        if provider not in self.demo_instances:
            print(f"{Colors.BLUE}Creating {provider} demo instance...{Colors.RESET}")
            try:
                self.demo_instances[provider] = InteractiveTestDemo(
                    demo_name=f"interactive_test_{provider}",
                    log_level="INFO",
                    ai_provider=provider,
                    claude_model=self.current_model,
                    session_id=f"interactive-{int(time.time())}",
                )
                print(f"{Colors.GREEN}✓ {provider} instance created{Colors.RESET}")
            except Exception as e:
                print(
                    f"{Colors.RED}✗ Failed to create {provider} instance: {e}{Colors.RESET}"
                )
                return None

        return self.demo_instances[provider]

    def print_header(self, title: str):
        """Print a formatted header."""
        print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}{title:^60}{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 60}{Colors.RESET}")

    def print_menu(self):
        """Print the main menu."""
        self.print_header("Inference Provider Tester")
        print(
            f"\n{Colors.BOLD}Current Provider:{Colors.RESET} {Colors.GREEN}{self.current_provider}{Colors.RESET}"
        )
        print(
            f"{Colors.BOLD}Current Model:{Colors.RESET} {Colors.GREEN}{self.current_model}{Colors.RESET}"
        )
        print(f"\n{Colors.BOLD}Options:{Colors.RESET}")
        print("1. Select Provider")
        print("2. Test Single Request")
        print("3. Compare Providers")
        print("4. Use Preset Test Cases")
        print("5. View Provider Details")
        print("6. Debug CLI Command")
        print("7. View Test Results")
        print("8. Clear Test Results")
        print("9. Exit")

    def select_provider(self):
        """Interactive provider selection."""
        providers = ["mock", "claude_cli", "api"]

        print(f"\n{Colors.BOLD}Available Providers:{Colors.RESET}")
        for i, provider in enumerate(providers, 1):
            status = "✓" if provider in self.demo_instances else " "
            current = " (current)" if provider == self.current_provider else ""
            print(f"{i}. {status} {provider}{current}")

        try:
            choice = (
                int(
                    input(
                        f"\n{Colors.YELLOW}Select provider (1-{len(providers)}): {Colors.RESET}"
                    )
                )
                - 1
            )
            if 0 <= choice < len(providers):
                self.current_provider = providers[choice]
                print(
                    f"{Colors.GREEN}✓ Selected provider: {self.current_provider}{Colors.RESET}"
                )
            else:
                print(f"{Colors.RED}Invalid selection{Colors.RESET}")
        except (ValueError, KeyboardInterrupt):
            print(f"{Colors.RED}Invalid input{Colors.RESET}")

    def test_single_request(self):
        """Test a single custom request."""
        print(f"\n{Colors.BOLD}Enter Tool Request Details:{Colors.RESET}")

        try:
            tool_name = input("Tool name: ").strip()
            if not tool_name:
                print(f"{Colors.RED}Tool name required{Colors.RESET}")
                return

            print("Parameters (JSON format, or press Enter for empty dict):")
            params_input = input().strip()
            if params_input:
                try:
                    parameters = json.loads(params_input)
                except json.JSONDecodeError as e:
                    print(f"{Colors.RED}Invalid JSON: {e}{Colors.RESET}")
                    return
            else:
                parameters = {}

            description = (
                input("Description (optional): ").strip() or f"{tool_name} operation"
            )

            self._execute_test(tool_name, parameters, description)

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Test cancelled{Colors.RESET}")

    def compare_providers(self):
        """Compare the same request across multiple providers."""
        print(f"\n{Colors.BOLD}Provider Comparison{Colors.RESET}")
        print("Enter a test request to run on all available providers:")

        try:
            tool_name = input("Tool name: ").strip()
            if not tool_name:
                print(f"{Colors.RED}Tool name required{Colors.RESET}")
                return

            print("Parameters (JSON format, or press Enter for empty dict):")
            params_input = input().strip()
            if params_input:
                try:
                    parameters = json.loads(params_input)
                except json.JSONDecodeError as e:
                    print(f"{Colors.RED}Invalid JSON: {e}{Colors.RESET}")
                    return
            else:
                parameters = {}

            description = (
                input("Description (optional): ").strip() or f"{tool_name} operation"
            )

            # Test with each provider
            providers = ["mock", "claude_cli"]
            results = {}

            for provider in providers:
                print(f"\n{Colors.BLUE}Testing with {provider}...{Colors.RESET}")
                original_provider = self.current_provider
                self.current_provider = provider

                result = self._execute_test(
                    tool_name, parameters, description, show_result=False
                )
                results[provider] = result

                self.current_provider = original_provider

            # Display comparison
            self._display_comparison(results, tool_name, parameters, description)

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Comparison cancelled{Colors.RESET}")

    def use_preset_cases(self):
        """Use predefined test cases."""
        print(f"\n{Colors.BOLD}Preset Test Cases:{Colors.RESET}")

        cases = list(self.preset_cases.items())
        for i, (_key, case) in enumerate(cases, 1):
            print(f"{i}. {case['name']} - {case['description']}")

        try:
            choice = (
                int(
                    input(
                        f"\n{Colors.YELLOW}Select test case (1-{len(cases)}): {Colors.RESET}"
                    )
                )
                - 1
            )
            if 0 <= choice < len(cases):
                key, case = cases[choice]
                print(f"\n{Colors.GREEN}Running: {case['name']}{Colors.RESET}")
                self._execute_test(
                    case["tool_name"], case["parameters"], case["description"]
                )
            else:
                print(f"{Colors.RED}Invalid selection{Colors.RESET}")
        except (ValueError, KeyboardInterrupt):
            print(f"{Colors.RED}Invalid input{Colors.RESET}")

    def view_provider_details(self):
        """Show details about the current provider."""
        demo = self.get_demo_instance(self.current_provider)
        if not demo:
            return

        print(f"\n{Colors.BOLD}Provider Details:{Colors.RESET}")
        print(f"Type: {demo.ai_provider}")
        print(f"Model: {demo.claude_model}")
        print(f"Session ID: {demo.session_id}")

        if hasattr(demo, "provider_info") and demo.provider_info:
            print(f"Provider Info: {json.dumps(demo.provider_info, indent=2)}")

        # Show health status if available
        try:
            if hasattr(demo.security_engine, "health_check"):
                health = demo.security_engine.health_check()
                print(f"\n{Colors.BOLD}Health Status:{Colors.RESET}")
                print(json.dumps(health, indent=2, default=str))
        except Exception as e:
            print(f"{Colors.YELLOW}Health check failed: {e}{Colors.RESET}")

    def debug_cli_command(self):
        """Debug CLI command execution manually."""
        if self.current_provider != "claude_cli":
            print(
                f"{Colors.RED}CLI debugging only available for claude_cli provider{Colors.RESET}"
            )
            return

        print(f"\n{Colors.BOLD}CLI Command Debugger{Colors.RESET}")
        prompt = input("Enter prompt to test: ").strip()
        if not prompt:
            prompt = "Test prompt for debugging"

        print(f"\n{Colors.BLUE}Testing CLI command manually...{Colors.RESET}")

        import subprocess
        import time

        cmd = ["claude", "--output-format", "json", "--model", self.current_model]
        print(f"Command: {' '.join(cmd)}")
        print(f"Input: {prompt}")

        try:
            start_time = time.time()
            result = subprocess.run(
                cmd, input=prompt, text=True, capture_output=True, timeout=30
            )
            end_time = time.time()

            print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
            print(f"Return code: {result.returncode}")
            print(f"Duration: {(end_time - start_time):.2f}s")
            print(f"Stdout length: {len(result.stdout)}")
            print(f"Stderr length: {len(result.stderr)}")

            if result.stdout:
                print(f"\n{Colors.GREEN}Stdout:{Colors.RESET}")
                print(
                    result.stdout[:1000] + ("..." if len(result.stdout) > 1000 else "")
                )

            if result.stderr:
                print(f"\n{Colors.RED}Stderr:{Colors.RESET}")
                print(result.stderr)

        except subprocess.TimeoutExpired:
            print(f"{Colors.RED}Command timed out after 30 seconds{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Command failed: {e}{Colors.RESET}")

    def view_test_results(self):
        """View stored test results."""
        if not self.test_results:
            print(f"{Colors.YELLOW}No test results available{Colors.RESET}")
            return

        print(f"\n{Colors.BOLD}Test Results History:{Colors.RESET}")
        for i, result in enumerate(self.test_results, 1):
            status_color = Colors.GREEN if result["success"] else Colors.RED
            print(
                f"{i}. [{result['provider']}] {result['tool_name']} - {status_color}{result['status']}{Colors.RESET}"
            )
            if "decision" in result:
                print(
                    f"   Decision: {result['decision']['action']} (confidence: {result['decision']['confidence']:.1%})"
                )
            if "duration" in result:
                print(f"   Duration: {result['duration']:.2f}s")
            print()

    def clear_test_results(self):
        """Clear test results history."""
        self.test_results = []
        print(f"{Colors.GREEN}✓ Test results cleared{Colors.RESET}")

    def _execute_test(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        description: str,
        show_result: bool = True,
    ) -> dict[str, Any]:
        """Execute a test and return results."""
        demo = self.get_demo_instance(self.current_provider)
        if not demo:
            return {"success": False, "error": "Failed to create demo instance"}

        if show_result:
            print(
                f"\n{Colors.BLUE}Executing with {self.current_provider}...{Colors.RESET}"
            )

        start_time = time.time()
        try:
            result = demo.process_tool_request(tool_name, parameters, description)
            end_time = time.time()

            success = "error" not in result
            test_result = {
                "provider": self.current_provider,
                "tool_name": tool_name,
                "parameters": parameters,
                "description": description,
                "success": success,
                "status": "success" if success else "error",
                "duration": end_time - start_time,
                "timestamp": time.time(),
            }

            if success:
                test_result["decision"] = result["decision"]
            else:
                test_result["error"] = result.get("error", "Unknown error")

            self.test_results.append(test_result)

            if show_result:
                self._display_single_result(test_result, result)

            return test_result

        except Exception as e:
            end_time = time.time()
            test_result = {
                "provider": self.current_provider,
                "tool_name": tool_name,
                "parameters": parameters,
                "description": description,
                "success": False,
                "status": "exception",
                "error": str(e),
                "duration": end_time - start_time,
                "timestamp": time.time(),
            }

            self.test_results.append(test_result)

            if show_result:
                print(f"{Colors.RED}Exception: {e}{Colors.RESET}")

            return test_result

    def _display_single_result(
        self, test_result: dict[str, Any], raw_result: dict[str, Any]
    ):
        """Display results from a single test."""
        if test_result["success"]:
            decision = test_result["decision"]
            action = decision["action"]

            action_color = (
                Colors.GREEN
                if action == "allow"
                else Colors.RED
                if action == "deny"
                else Colors.YELLOW
            )
            print(f"\n{action_color}Decision: {action}{Colors.RESET}")
            print(f"Reason: {decision['reason']}")
            print(f"Confidence: {decision['confidence']:.1%}")
            print(f"Duration: {test_result['duration']:.2f}s")

            if decision.get("rule_id"):
                print(f"Rule: {decision['rule_id']}")
            if decision.get("ai_provider"):
                print(f"AI Provider: {decision['ai_provider']}")
                print(f"AI Model: {decision.get('ai_model', 'unknown')}")
        else:
            print(f"{Colors.RED}Error: {test_result['error']}{Colors.RESET}")
            print(f"Duration: {test_result['duration']:.2f}s")

    def _display_comparison(
        self,
        results: dict[str, dict[str, Any]],
        tool_name: str,
        parameters: dict[str, Any],
        description: str,
    ):
        """Display comparison results."""
        print(f"\n{Colors.BOLD}Comparison Results:{Colors.RESET}")
        print(f"Tool: {tool_name}")
        print(f"Parameters: {json.dumps(parameters, indent=2)}")
        print(f"Description: {description}")

        for provider, result in results.items():
            print(f"\n{Colors.CYAN}{Colors.BOLD}{provider.upper()}:{Colors.RESET}")

            if result["success"]:
                decision = result["decision"]
                action = decision["action"]
                action_color = (
                    Colors.GREEN
                    if action == "allow"
                    else Colors.RED
                    if action == "deny"
                    else Colors.YELLOW
                )

                print(f"  Status: {Colors.GREEN}SUCCESS{Colors.RESET}")
                print(f"  Decision: {action_color}{action}{Colors.RESET}")
                print(f"  Confidence: {decision['confidence']:.1%}")
                print(f"  Duration: {result['duration']:.2f}s")
                print(
                    f"  Reason: {decision['reason'][:100]}{'...' if len(decision['reason']) > 100 else ''}"
                )
            else:
                print(f"  Status: {Colors.RED}FAILED{Colors.RESET}")
                print(f"  Error: {result['error']}")
                print(f"  Duration: {result['duration']:.2f}s")

    def run(self):
        """Run the interactive tester."""
        print(f"{Colors.GREEN}Welcome to the Inference Provider Tester!{Colors.RESET}")
        print("This tool helps debug and compare inference providers.")

        while True:
            try:
                self.print_menu()
                choice = input(
                    f"\n{Colors.YELLOW}Select option (1-9): {Colors.RESET}"
                ).strip()

                if choice == "1":
                    self.select_provider()
                elif choice == "2":
                    self.test_single_request()
                elif choice == "3":
                    self.compare_providers()
                elif choice == "4":
                    self.use_preset_cases()
                elif choice == "5":
                    self.view_provider_details()
                elif choice == "6":
                    self.debug_cli_command()
                elif choice == "7":
                    self.view_test_results()
                elif choice == "8":
                    self.clear_test_results()
                elif choice == "9":
                    print(
                        f"\n{Colors.GREEN}Thanks for using the Inference Provider Tester!{Colors.RESET}"
                    )
                    break
                else:
                    print(f"{Colors.RED}Invalid option{Colors.RESET}")

                # Pause before showing menu again
                input(f"\n{Colors.CYAN}Press Enter to continue...{Colors.RESET}")

            except KeyboardInterrupt:
                print(
                    f"\n\n{Colors.GREEN}Thanks for using the Inference Provider Tester!{Colors.RESET}"
                )
                break
            except Exception as e:
                print(f"\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
                import traceback

                traceback.print_exc()


def main():
    """Main entry point."""
    tester = InferenceProviderTester()
    tester.run()


if __name__ == "__main__":
    main()
