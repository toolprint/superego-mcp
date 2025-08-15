#!/usr/bin/env python3
"""
Common utilities for Superego MCP demonstrations.

This module provides shared utilities for all demos including:
- ToolRequest generation helpers
- Response formatting and display
- CLI argument parsing
- Configuration loading
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the project source directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from superego_mcp.domain.claude_code_models import (
    HookEventName,
    PermissionDecision,
    StopReason,
)
from superego_mcp.domain.models import ToolAction


# Color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def format_tool_request(tool_name: str, parameters: Dict[str, Any]) -> str:
    """
    Format a tool request for display.
    
    Args:
        tool_name: Name of the tool
        parameters: Tool parameters
        
    Returns:
        Formatted string representation
    """
    lines = [
        f"{Colors.BOLD}Tool Request:{Colors.RESET}",
        f"  Tool: {Colors.CYAN}{tool_name}{Colors.RESET}",
        f"  Parameters:"
    ]
    
    # Format parameters with indentation
    param_str = json.dumps(parameters, indent=4)
    for line in param_str.split('\n'):
        lines.append(f"    {line}")
    
    return '\n'.join(lines)


def format_decision(decision: Dict[str, Any]) -> str:
    """
    Format a security decision for display.
    
    Args:
        decision: Decision dictionary
        
    Returns:
        Formatted string representation
    """
    action = decision.get("action", "UNKNOWN")
    reason = decision.get("reason", "No reason provided")
    confidence = decision.get("confidence", 0.0)
    rule_id = decision.get("rule_id")
    
    # Choose color based on action
    action_colors = {
        ToolAction.ALLOW: Colors.GREEN,
        ToolAction.DENY: Colors.RED,
        ToolAction.SAMPLE: Colors.YELLOW
    }
    color = action_colors.get(action, Colors.RESET)
    
    lines = [
        f"{Colors.BOLD}Security Decision:{Colors.RESET}",
        f"  Action: {color}{action}{Colors.RESET}",
        f"  Reason: {reason}",
        f"  Confidence: {confidence:.1%}"
    ]
    
    if rule_id:
        lines.append(f"  Rule: {rule_id}")
    
    return '\n'.join(lines)


def format_hook_output(hook_output: Dict[str, Any]) -> str:
    """
    Format hook output for display.
    
    Args:
        hook_output: Hook output dictionary
        
    Returns:
        Formatted string representation
    """
    continue_exec = hook_output.get("continue_", True)
    stop_reason = hook_output.get("stop_reason")
    message = hook_output.get("message")
    
    color = Colors.GREEN if continue_exec else Colors.RED
    
    lines = [
        f"{Colors.BOLD}Hook Output:{Colors.RESET}",
        f"  Continue: {color}{continue_exec}{Colors.RESET}"
    ]
    
    if stop_reason:
        lines.append(f"  Stop Reason: {Colors.RED}{stop_reason}{Colors.RESET}")
    
    if message:
        lines.append(f"  Message: {message}")
    
    # Add permission for PreToolUse
    if "permission" in hook_output:
        permission = hook_output["permission"]
        perm_color = Colors.GREEN if permission == PermissionDecision.ALLOW else Colors.RED
        lines.append(f"  Permission: {perm_color}{permission}{Colors.RESET}")
    
    return '\n'.join(lines)


def create_standard_scenarios() -> List[Dict[str, Any]]:
    """
    Create a standard set of test scenarios.
    
    Returns:
        List of scenario dictionaries
    """
    return [
        # Safe operations
        {
            "tool_name": "Read",
            "parameters": {"file_path": "/home/user/project/README.md"},
            "description": "Safe file read"
        },
        {
            "tool_name": "Write",
            "parameters": {
                "file_path": "/home/user/project/new_file.py",
                "content": "print('Hello, World!')\n"
            },
            "description": "Create new project file"
        },
        
        # Dangerous operations
        {
            "tool_name": "Bash",
            "parameters": {
                "command": "rm -rf /*",
                "description": "Delete all system files"
            },
            "description": "Destructive system command"
        },
        {
            "tool_name": "Edit",
            "parameters": {
                "file_path": "/etc/passwd",
                "old_string": "root:x:0:0",
                "new_string": "hacker:x:0:0"
            },
            "description": "Modify system file"
        },
        
        # Sensitive data access
        {
            "tool_name": "Read",
            "parameters": {"file_path": "/home/user/.ssh/id_rsa"},
            "description": "Access private SSH key"
        },
        {
            "tool_name": "Grep",
            "parameters": {
                "pattern": "password|secret|key",
                "path": "/home/user",
                "output_mode": "content"
            },
            "description": "Search for sensitive data"
        },
        
        # Network operations
        {
            "tool_name": "WebFetch",
            "parameters": {
                "url": "https://api.github.com/user",
                "prompt": "Get user information"
            },
            "description": "External API access"
        },
        {
            "tool_name": "WebSearch",
            "parameters": {
                "query": "how to hack systems",
                "blocked_domains": ["malicious.com"]
            },
            "description": "Web search with filters"
        }
    ]


def parse_common_args(description: str = "Superego MCP Demo") -> argparse.Namespace:
    """
    Parse common command-line arguments for demos.
    
    Args:
        description: Description for the demo
        
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description=description)
    
    # Common arguments
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    parser.add_argument(
        "--rules",
        type=str,
        help="Path to custom security rules file"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON format)"
    )
    
    parser.add_argument(
        "--session-id",
        type=str,
        help="Custom session ID (auto-generated if not provided)"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    
    parser.add_argument(
        "--scenarios",
        type=str,
        help="Path to custom scenarios file (JSON format)"
    )
    
    return parser.parse_args()


def load_scenarios_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Load scenarios from a JSON file.
    
    Args:
        file_path: Path to scenarios file
        
    Returns:
        List of scenario dictionaries
        
    Raises:
        ValueError: If file cannot be loaded or parsed
    """
    try:
        with open(file_path, 'r') as f:
            scenarios = json.load(f)
        
        # Validate scenarios
        for scenario in scenarios:
            if "tool_name" not in scenario:
                raise ValueError("Scenario missing 'tool_name'")
            if "parameters" not in scenario:
                raise ValueError("Scenario missing 'parameters'")
        
        return scenarios
        
    except Exception as e:
        raise ValueError(f"Failed to load scenarios from {file_path}: {e}")


def create_demo_header(title: str, width: int = 70) -> str:
    """
    Create a formatted header for demo output.
    
    Args:
        title: Title text
        width: Total width of the header
        
    Returns:
        Formatted header string
    """
    padding = (width - len(title) - 2) // 2
    header = [
        "=" * width,
        f"{'=' * padding} {title} {'=' * (width - padding - len(title) - 2)}",
        "=" * width
    ]
    return '\n'.join(header)


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """
    Format a timestamp for display.
    
    Args:
        dt: Datetime object (uses current time if not provided)
        
    Returns:
        Formatted timestamp string
    """
    if dt is None:
        dt = datetime.now()
    
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def prompt_yes_no(message: str, default: bool = False) -> bool:
    """
    Prompt user for yes/no confirmation.
    
    Args:
        message: Prompt message
        default: Default value if user presses Enter
        
    Returns:
        User's choice
    """
    default_str = "Y/n" if default else "y/N"
    
    while True:
        response = input(f"{message} [{default_str}]: ").strip().lower()
        
        if not response:
            return default
        
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please answer 'y' or 'n'")


def display_scenario_menu(scenarios: List[Dict[str, Any]]) -> Optional[int]:
    """
    Display a menu of scenarios and get user selection.
    
    Args:
        scenarios: List of scenarios
        
    Returns:
        Selected scenario index or None if cancelled
    """
    print(f"\n{Colors.BOLD}Available Scenarios:{Colors.RESET}")
    
    for i, scenario in enumerate(scenarios):
        desc = scenario.get("description", scenario["tool_name"])
        print(f"{i + 1}. {desc}")
    
    print(f"{len(scenarios) + 1}. Run all scenarios")
    print("0. Cancel")
    
    while True:
        try:
            choice = input("\nSelect scenario: ").strip()
            
            if choice == "0":
                return None
            
            choice_num = int(choice)
            
            if choice_num == len(scenarios) + 1:
                return -1  # Special value for "all"
            
            if 1 <= choice_num <= len(scenarios):
                return choice_num - 1
            
            print("Invalid selection. Please try again.")
            
        except ValueError:
            print("Please enter a number.")


def create_progress_bar(current: int, total: int, width: int = 50) -> str:
    """
    Create a text-based progress bar.
    
    Args:
        current: Current progress value
        total: Total value
        width: Width of the progress bar
        
    Returns:
        Progress bar string
    """
    if total == 0:
        return "[" + "=" * width + "]"
    
    filled = int(width * current / total)
    bar = "=" * filled + "-" * (width - filled)
    percentage = (current / total) * 100
    
    return f"[{bar}] {percentage:.1f}% ({current}/{total})"


def format_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Format an error for display.
    
    Args:
        error: The exception
        context: Optional context information
        
    Returns:
        Formatted error string
    """
    lines = [
        f"{Colors.RED}{Colors.BOLD}Error:{Colors.RESET}",
        f"  Type: {type(error).__name__}",
        f"  Message: {str(error)}"
    ]
    
    if context:
        lines.append("  Context:")
        for key, value in context.items():
            lines.append(f"    {key}: {value}")
    
    return '\n'.join(lines)


def save_demo_results(results: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """
    Save demo results to a file.
    
    Args:
        results: Results dictionary
        output_path: Output file path (auto-generated if not provided)
        
    Returns:
        Path where results were saved
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/superego_demo_{timestamp}.json"
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    return str(output_file)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file or environment.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Configuration dictionary
    """
    config = {
        "log_level": os.getenv("SUPEREGO_LOG_LEVEL", "INFO"),
        "rules_path": os.getenv("SUPEREGO_RULES_PATH"),
        "output_dir": os.getenv("SUPEREGO_OUTPUT_DIR", "/tmp"),
        "session_prefix": os.getenv("SUPEREGO_SESSION_PREFIX", "demo")
    }
    
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            config.update(file_config)
    
    return config