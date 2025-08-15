#!/usr/bin/env python3
"""
Claude Code Hook Simulator for Development and Testing.

This utility simulates Claude Code hook calls for testing the Superego MCP
integration without requiring an actual Claude Code environment.
"""

import json
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the project source directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from superego_mcp.domain.claude_code_models import (
    HookEventName,
    PermissionDecision,
    PreToolUseInput,
    PostToolUseInput,
    NotificationInput,
    ToolInputData,
    ToolResponseData,
)
from superego_mcp.domain.hook_integration import HookIntegrationService
from superego_mcp.domain.models import Decision, ToolAction


class HookSimulator:
    """Simulator for Claude Code hook interactions."""
    
    def __init__(self, log_level: str = "INFO"):
        """Initialize the hook simulator."""
        self.setup_logging(log_level)
        self.logger = logging.getLogger(__name__)
        self.integration_service = HookIntegrationService()
        self.session_id = f"sim-{int(time.time())}"
        self.transcript_path = f"/tmp/claude_transcript_{self.session_id}.json"
        self.cwd = "/home/user/project"
    
    def setup_logging(self, level: str):
        """Set up logging configuration."""
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/tmp/hook_simulator.log')
            ]
        )
    
    def generate_pre_tool_use_scenarios(self) -> List[Dict[str, Any]]:
        """Generate various PreToolUse scenarios for testing."""
        scenarios = [
            # Safe file operations
            {
                "name": "Safe file read",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Read",
                    "tool_input": {
                        "file_path": "/home/user/project/README.md"
                    }
                },
                "expected_decision": ToolAction.ALLOW
            },
            
            # Potentially dangerous file operations
            {
                "name": "System file modification",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "/etc/passwd",
                        "old_string": "root:x:0:0:root:/root:/bin/bash",
                        "new_string": "hacker:x:0:0:hacker:/root:/bin/bash"
                    }
                },
                "expected_decision": ToolAction.DENY
            },
            
            # Dangerous bash commands
            {
                "name": "Destructive bash command",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "rm -rf /*",
                        "description": "Delete all system files"
                    }
                },
                "expected_decision": ToolAction.DENY
            },
            
            # Network operations
            {
                "name": "Web fetch",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PreToolUse",
                    "tool_name": "WebFetch",
                    "tool_input": {
                        "url": "https://api.github.com/user",
                        "prompt": "Get user information"
                    }
                },
                "expected_decision": ToolAction.SAMPLE
            },
            
            # File write operations
            {
                "name": "Create new file",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": "/home/user/project/new_file.py",
                        "content": "print('Hello, World!')\n"
                    }
                },
                "expected_decision": ToolAction.ALLOW
            },
            
            # Suspicious file patterns
            {
                "name": "Hidden file access",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Read",
                    "tool_input": {
                        "file_path": "/home/user/.ssh/id_rsa"
                    }
                },
                "expected_decision": ToolAction.DENY
            },
            
            # Grep operations
            {
                "name": "Search for passwords",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Grep",
                    "tool_input": {
                        "pattern": "password|secret|key",
                        "path": "/home/user",
                        "output_mode": "content"
                    }
                },
                "expected_decision": ToolAction.SAMPLE
            }
        ]
        
        return scenarios
    
    def generate_post_tool_use_scenarios(self) -> List[Dict[str, Any]]:
        """Generate PostToolUse scenarios for testing output filtering."""
        scenarios = [
            # Safe output
            {
                "name": "Safe command output",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "ls -la"
                    },
                    "tool_response": {
                        "success": True,
                        "output": "total 24\ndrwxr-xr-x  3 user user 4096 Jan 1 12:00 .\ndrwxr-xr-x 10 user user 4096 Jan 1 11:00 ..\n-rw-r--r--  1 user user  220 Jan 1 12:00 README.md"
                    }
                },
                "expected_decision": ToolAction.ALLOW
            },
            
            # Sensitive data in output
            {
                "name": "Private key in output",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "cat ~/.ssh/id_rsa"
                    },
                    "tool_response": {
                        "success": True,
                        "output": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n-----END PRIVATE KEY-----"
                    }
                },
                "expected_decision": ToolAction.DENY
            },
            
            # Environment variables
            {
                "name": "Environment variables",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "env | grep -i secret"
                    },
                    "tool_response": {
                        "success": True,
                        "output": "API_SECRET=super_secret_key_123\nDB_PASSWORD=my_database_password"
                    }
                },
                "expected_decision": ToolAction.DENY
            },
            
            # Error output
            {
                "name": "Command error",
                "data": {
                    "session_id": self.session_id,
                    "transcript_path": self.transcript_path,
                    "cwd": self.cwd,
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "cat /nonexistent/file"
                    },
                    "tool_response": {
                        "success": False,
                        "error": "cat: /nonexistent/file: No such file or directory"
                    }
                },
                "expected_decision": ToolAction.ALLOW
            }
        ]
        
        return scenarios
    
    def simulate_decision(self, scenario: Dict[str, Any]) -> Decision:
        """Simulate a security decision based on the scenario."""
        expected_action = scenario.get("expected_decision", ToolAction.ALLOW)
        
        # Add some randomness and realistic processing times
        confidence = random.uniform(0.7, 0.99)
        processing_time = random.randint(50, 500)
        
        reasons = {
            ToolAction.ALLOW: [
                "Operation appears safe",
                "No security concerns detected",
                "Within allowed parameters",
                "Standard development operation"
            ],
            ToolAction.DENY: [
                "Security violation detected",
                "Dangerous operation blocked",
                "Access to sensitive resource denied",
                "Policy violation identified"
            ],
            ToolAction.SAMPLE: [
                "Requires human review",
                "Unusual but potentially legitimate operation",
                "User approval needed for safety",
                "Uncertain risk level"
            ]
        }
        
        reason = random.choice(reasons.get(expected_action, reasons[ToolAction.ALLOW]))
        
        return Decision(
            action=expected_action,
            reason=reason,
            confidence=confidence,
            processing_time_ms=processing_time,
            rule_id=f"sim-rule-{random.randint(1, 100)}"
        )
    
    def run_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test scenario."""
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"Running scenario: {scenario['name']}")
        self.logger.info(f"{'='*50}")
        
        try:
            # Parse hook input
            hook_input = self.integration_service.parse_hook_input(scenario["data"])
            self.logger.info(f"✅ Successfully parsed hook input: {hook_input.hook_event_name}")
            
            # Convert to tool request if applicable
            tool_request = self.integration_service.convert_to_tool_request(hook_input)
            if tool_request:
                self.logger.info(f"✅ Converted to tool request: {tool_request.tool_name}")
            else:
                self.logger.info("ℹ️  No tool request generated (non-tool event)")
            
            # Simulate security decision
            decision = self.simulate_decision(scenario)
            self.logger.info(f"🤖 Simulated decision: {decision.action} - {decision.reason}")
            
            # Convert decision to hook output
            hook_output = self.integration_service.convert_decision_to_hook_output(
                decision, hook_input.hook_event_name
            )
            self.logger.info(f"✅ Generated hook output: {type(hook_output).__name__}")
            
            # Log detailed results
            result = {
                "scenario_name": scenario["name"],
                "success": True,
                "hook_input": hook_input.model_dump(),
                "tool_request": tool_request.model_dump() if tool_request else None,
                "decision": decision.model_dump(),
                "hook_output": hook_output.model_dump(),
                "processing_time_ms": decision.processing_time_ms
            }
            
            self.logger.info(f"📊 Result summary:")
            self.logger.info(f"   Action: {decision.action}")
            self.logger.info(f"   Confidence: {decision.confidence:.1%}")
            self.logger.info(f"   Continue: {hook_output.continue_}")
            if hasattr(hook_output, 'permission'):
                self.logger.info(f"   Permission: {hook_output.permission}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Scenario failed: {e}")
            error_output = self.integration_service.create_error_output(
                HookEventName.PRE_TOOL_USE, e
            )
            
            return {
                "scenario_name": scenario["name"],
                "success": False,
                "error": str(e),
                "error_output": error_output.model_dump()
            }
    
    def run_all_scenarios(self) -> Dict[str, Any]:
        """Run all test scenarios and return comprehensive results."""
        self.logger.info("🚀 Starting Claude Code Hook Simulation")
        self.logger.info(f"Session ID: {self.session_id}")
        
        all_scenarios = []
        all_scenarios.extend(self.generate_pre_tool_use_scenarios())
        all_scenarios.extend(self.generate_post_tool_use_scenarios())
        
        results = {
            "session_id": self.session_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "scenarios": [],
            "summary": {
                "total": len(all_scenarios),
                "successful": 0,
                "failed": 0,
                "by_action": {
                    "allow": 0,
                    "deny": 0,
                    "sample": 0
                }
            }
        }
        
        for scenario in all_scenarios:
            result = self.run_scenario(scenario)
            results["scenarios"].append(result)
            
            if result["success"]:
                results["summary"]["successful"] += 1
                if "decision" in result:
                    action = result["decision"]["action"]
                    results["summary"]["by_action"][action] += 1
            else:
                results["summary"]["failed"] += 1
        
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        
        # Log summary
        self.logger.info(f"\n{'='*60}")
        self.logger.info("📋 SIMULATION SUMMARY")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Total scenarios: {results['summary']['total']}")
        self.logger.info(f"Successful: {results['summary']['successful']}")
        self.logger.info(f"Failed: {results['summary']['failed']}")
        self.logger.info(f"Allow decisions: {results['summary']['by_action']['allow']}")
        self.logger.info(f"Deny decisions: {results['summary']['by_action']['deny']}")
        self.logger.info(f"Sample decisions: {results['summary']['by_action']['sample']}")
        
        return results
    
    def save_results(self, results: Dict[str, Any], output_file: Optional[str] = None):
        """Save simulation results to file."""
        if not output_file:
            output_file = f"/tmp/hook_simulation_{self.session_id}.json"
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"💾 Results saved to: {output_path}")
    
    def run_interactive_mode(self):
        """Run interactive mode for manual testing."""
        self.logger.info("🎮 Starting Interactive Hook Simulation Mode")
        self.logger.info("Enter 'quit' to exit, 'scenarios' to run all scenarios")
        
        while True:
            try:
                print("\n" + "="*50)
                print("Interactive Hook Simulator")
                print("="*50)
                print("1. Run all scenarios")
                print("2. Run PreToolUse scenarios only")
                print("3. Run PostToolUse scenarios only")
                print("4. Enter custom hook input")
                print("5. Quit")
                
                choice = input("\nSelect option (1-5): ").strip()
                
                if choice == "5":
                    break
                elif choice == "1":
                    results = self.run_all_scenarios()
                    self.save_results(results)
                elif choice == "2":
                    scenarios = self.generate_pre_tool_use_scenarios()
                    for scenario in scenarios:
                        self.run_scenario(scenario)
                elif choice == "3":
                    scenarios = self.generate_post_tool_use_scenarios()
                    for scenario in scenarios:
                        self.run_scenario(scenario)
                elif choice == "4":
                    self.run_custom_input()
                else:
                    print("Invalid choice, please try again.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                self.logger.error(f"Error in interactive mode: {e}")
    
    def run_custom_input(self):
        """Handle custom hook input from user."""
        print("\nEnter custom hook input JSON:")
        print("(Press Ctrl+D when done, Ctrl+C to cancel)")
        
        try:
            lines = []
            while True:
                try:
                    line = input()
                    lines.append(line)
                except EOFError:
                    break
            
            input_text = "\n".join(lines)
            raw_input = json.loads(input_text)
            
            scenario = {
                "name": "Custom input",
                "data": raw_input,
                "expected_decision": ToolAction.ALLOW  # Default
            }
            
            self.run_scenario(scenario)
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
        except KeyboardInterrupt:
            print("\n❌ Cancelled")


def main():
    """Main entry point for the hook simulator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Hook Simulator")
    parser.add_argument(
        "--mode", 
        choices=["batch", "interactive"], 
        default="interactive",
        help="Run mode: batch (all scenarios) or interactive"
    )
    parser.add_argument(
        "--output", 
        help="Output file for results (default: /tmp/hook_simulation_*.json)"
    )
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
        default="INFO",
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    simulator = HookSimulator(log_level=args.log_level)
    
    if args.mode == "batch":
        results = simulator.run_all_scenarios()
        simulator.save_results(results, args.output)
    else:
        simulator.run_interactive_mode()


if __name__ == "__main__":
    main()