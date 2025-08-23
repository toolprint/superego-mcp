"""Claude Code hooks command for testing Superego integration.

This module provides functionality for testing Claude Code hook integration
with the Superego MCP Server, including hook event simulation and validation.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
import structlog

from ..client.superego_client import SuperegoTestClient, SuperegoClientError
from ..client.response_formatter import ResponseFormatter, TestResult, create_test_result
from ..config.loader import TestHarnessConfig, load_config

logger = structlog.get_logger(__name__)


class HookEventSimulator:
    """Simulates Claude Code hook events for testing."""
    
    def __init__(self, console: Console):
        self.console = console
        self.logger = logger.bind(component="hook_simulator")
    
    def create_hook_event(
        self,
        event_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_id: str = "test-agent",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Claude Code hook event structure.
        
        Args:
            event_name: Hook event name (e.g., "pre_tool_use", "post_tool_use")
            tool_name: Name of the tool being used
            arguments: Tool arguments dictionary
            agent_id: Agent identifier
            session_id: Session identifier (auto-generated if None)
            
        Returns:
            Hook event dictionary in Claude Code format
        """
        if session_id is None:
            session_id = f"hook-test-{int(time.time())}"
        
        event = {
            "eventName": event_name,
            "toolName": tool_name,
            "arguments": arguments,
            "metadata": {
                "agentId": agent_id,
                "sessionId": session_id,
                "timestamp": time.time(),
                "source": "superego-test-harness"
            }
        }
        
        self.logger.debug(
            "Created hook event",
            event_name=event_name,
            tool_name=tool_name,
            agent_id=agent_id,
            session_id=session_id
        )
        
        return event
    
    def load_hook_scenarios_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load hook test scenarios from a JSON file.
        
        Args:
            file_path: Path to the JSON hook scenario file
            
        Returns:
            List of hook scenario dictionaries
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both direct scenario arrays and wrapped format
            if isinstance(data, list):
                scenarios = data
            elif isinstance(data, dict) and 'hook_scenarios' in data:
                scenarios = data['hook_scenarios']
            elif isinstance(data, dict) and 'scenarios' in data:
                scenarios = data['scenarios']
            else:
                raise ValueError(f"Invalid hook scenario file format in {file_path}")
            
            self.logger.info(
                "Loaded hook scenarios from file",
                file_path=str(file_path),
                scenario_count=len(scenarios)
            )
            
            return scenarios
            
        except FileNotFoundError:
            self.console.print(f"[red]Error: Hook scenario file not found: {file_path}[/red]")
            raise
        except json.JSONDecodeError as e:
            self.console.print(f"[red]Error: Invalid JSON in hook scenario file {file_path}: {e}[/red]")
            raise
        except Exception as e:
            self.console.print(f"[red]Error loading hook scenarios from {file_path}: {e}[/red]")
            raise


class HookTester:
    """Tests Claude Code hook integration with Superego MCP Server."""
    
    def __init__(self, client: SuperegoTestClient, console: Console, formatter: ResponseFormatter):
        self.client = client
        self.console = console
        self.formatter = formatter
        self.logger = logger.bind(component="hook_tester")
    
    async def test_hook_event(
        self,
        event_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        expected_result: Optional[str] = None,
        agent_id: str = "test-agent",
        test_name: Optional[str] = None
    ) -> TestResult:
        """Test a single hook event.
        
        Args:
            event_name: Hook event name
            tool_name: Tool name
            arguments: Tool arguments
            expected_result: Expected hook result (allow, deny, etc.)
            agent_id: Agent identifier
            test_name: Custom test name
            
        Returns:
            TestResult containing hook test results
        """
        if test_name is None:
            test_name = f"Hook Test: {event_name} - {tool_name}"
        
        session_id = f"hook-{event_name}-{int(time.time())}"
        
        self.logger.info(
            "Testing hook event",
            event_name=event_name,
            tool_name=tool_name,
            agent_id=agent_id,
            session_id=session_id
        )
        
        start_time = time.perf_counter()
        
        try:
            # Send hook event to Superego MCP Server
            response_data = await self.client.test_claude_hook(
                event_name=event_name,
                tool_name=tool_name,
                arguments=arguments,
                agent_id=agent_id,
                session_id=session_id
            )
            
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Determine success based on expected result
            success = True
            error_message = None
            
            if expected_result:
                actual_result = response_data.get('action', response_data.get('decision', 'unknown'))
                if actual_result != expected_result:
                    success = False
                    error_message = f"Expected result '{expected_result}', got '{actual_result}'"
            
            result = create_test_result(
                success=success,
                response_data=response_data,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name=test_name,
                endpoint="/v1/hooks",
                method="POST",
                error_message=error_message,
                request_data={
                    "eventName": event_name,
                    "toolName": tool_name,
                    "arguments": arguments
                },
                agent_id=agent_id,
                session_id=session_id,
                tags=["hook_test", event_name]
            )
            
            self.logger.info(
                "Hook event test completed",
                event_name=event_name,
                tool_name=tool_name,
                success=success,
                response_time_ms=round(response_time_ms, 2)
            )
            
            return result
            
        except SuperegoClientError as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            self.logger.error(
                "Hook event test failed",
                event_name=event_name,
                tool_name=tool_name,
                error=str(e),
                error_type=type(e).__name__
            )
            
            return create_test_result(
                success=False,
                response_time_ms=response_time_ms,
                test_name=test_name,
                endpoint="/v1/hooks",
                method="POST",
                error_message=str(e),
                error_type=type(e).__name__,
                request_data={
                    "eventName": event_name,
                    "toolName": tool_name,
                    "arguments": arguments
                },
                agent_id=agent_id,
                session_id=session_id,
                tags=["hook_test", event_name, "failed"]
            )
    
    async def test_hook_scenario(self, scenario: Dict[str, Any]) -> TestResult:
        """Test a hook scenario from configuration.
        
        Args:
            scenario: Hook scenario dictionary
            
        Returns:
            TestResult containing scenario test results
        """
        event_name = str(scenario.get('event_name', 'pre_tool_use'))
        tool_name = str(scenario.get('tool_name', ''))
        arguments = scenario.get('arguments', {})
        expected_result = scenario.get('expected_result')
        if expected_result is not None:
            expected_result = str(expected_result)
        agent_id = str(scenario.get('agent_id', 'test-agent'))
        test_name = str(scenario.get('name', f"Hook Scenario: {scenario.get('id', 'unknown')}"))
        
        return await self.test_hook_event(
            event_name=event_name,
            tool_name=tool_name,
            arguments=arguments,
            expected_result=expected_result,
            agent_id=agent_id,
            test_name=test_name
        )
    
    async def test_claude_code_integration(self) -> List[TestResult]:
        """Test basic Claude Code integration scenarios.
        
        Returns:
            List of TestResult objects from integration tests
        """
        self.console.print("[cyan]Testing Claude Code integration scenarios...[/cyan]")
        
        # Define basic integration test scenarios
        integration_scenarios = [
            {
                "event_name": "pre_tool_use",
                "tool_name": "bash",
                "arguments": {"command": "ls -la"},
                "expected_result": "allow",
                "test_name": "Safe bash command pre-hook"
            },
            {
                "event_name": "pre_tool_use", 
                "tool_name": "bash",
                "arguments": {"command": "rm -rf /"},
                "expected_result": "deny",
                "test_name": "Dangerous bash command pre-hook"
            },
            {
                "event_name": "post_tool_use",
                "tool_name": "file_read",
                "arguments": {"path": "/etc/passwd"},
                "expected_result": "log",
                "test_name": "Sensitive file read post-hook"
            }
        ]
        
        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            for scenario in integration_scenarios:
                test_name = str(scenario["test_name"])
                task = progress.add_task(f"Testing {test_name}...", total=None)
                
                arguments = scenario["arguments"]
                if not isinstance(arguments, dict):
                    arguments = {}
                
                result = await self.test_hook_event(
                    event_name=str(scenario["event_name"]),
                    tool_name=str(scenario["tool_name"]),
                    arguments=arguments,
                    expected_result=str(scenario["expected_result"]) if scenario["expected_result"] else None,
                    test_name=test_name
                )
                results.append(result)
                
                progress.update(task, completed=True)
                progress.remove_task(task)
        
        return results


async def run_hook_test(
    action: str = "test",
    scenario_file: Optional[Path] = None,
    event_name: Optional[str] = None,
    tool_name: Optional[str] = None,
    arguments_json: Optional[str] = None,
    config_file: Optional[Path] = None,
    output_format: str = "pretty",
    integration_test: bool = False
) -> None:
    """Run Claude Code hook tests against Superego MCP Server.
    
    Args:
        action: Action to perform (test, integration, validate)
        scenario_file: Path to JSON file containing hook test scenarios
        event_name: Single hook event name to test
        tool_name: Tool name for single hook test
        arguments_json: JSON string containing tool arguments
        config_file: Path to test harness configuration file
        output_format: Output format (pretty, table, json, summary)
        integration_test: Whether to run integration test scenarios
    """
    console = Console()
    
    try:
        # Load configuration
        if config_file:
            # If a specific config file is provided, use the directory and default profile
            config_dir = config_file.parent
            config = load_config("default", config_dir)
        else:
            # Use default configuration
            config = load_config()
        
        # Initialize components
        simulator = HookEventSimulator(console)
        formatter = ResponseFormatter(console)
        
        async with SuperegoTestClient(config) as client:
            tester = HookTester(client, console, formatter)
            results = []
            
            if action == "integration" or integration_test:
                # Run integration tests
                results = await tester.test_claude_code_integration()
                
            elif scenario_file:
                # Load and run scenarios from file
                scenarios = simulator.load_hook_scenarios_from_file(scenario_file)
                
                console.print(f"[cyan]Running {len(scenarios)} hook scenario(s)...[/cyan]")
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=console
                ) as progress:
                    for scenario in scenarios:
                        scenario_name = scenario.get('name', f'Hook Scenario {scenario.get("id", "unknown")}')
                        task = progress.add_task(f"Running {scenario_name}...", total=None)
                        
                        result = await tester.test_hook_scenario(scenario)
                        results.append(result)
                        
                        progress.update(task, completed=True)
                        progress.remove_task(task)
                        
            elif event_name and tool_name and arguments_json:
                # Single hook test from command line
                try:
                    arguments = json.loads(arguments_json)
                    result = await tester.test_hook_event(
                        event_name=event_name,
                        tool_name=tool_name,
                        arguments=arguments,
                        test_name=f"CLI Hook Test: {event_name} - {tool_name}"
                    )
                    results = [result]
                except json.JSONDecodeError as e:
                    console.print(f"[red]Error: Invalid JSON in arguments: {e}[/red]")
                    return
                    
            else:
                console.print("[red]Error: Must specify action and appropriate parameters[/red]")
                console.print("Available actions:")
                console.print("  - integration: Run integration test scenarios")
                console.print("  - test: Test scenarios from file or single hook event")
                console.print("Use --help for parameter details")
                return
            
            # Display results
            if results:
                console.print()  # Add spacing
                
                if output_format == "pretty":
                    for result in results:
                        formatter.format_pretty(result)
                        console.print()  # Spacing between results
                elif output_format == "table":
                    formatter.format_table(results)
                elif output_format == "json":
                    json_output = formatter.format_json(results)
                    console.print(json_output)
                elif output_format == "summary":
                    formatter.format_summary(results)
                else:
                    console.print(f"[red]Unknown output format: {output_format}[/red]")
                    return
                
                # Display final summary
                total = len(results)
                passed = sum(1 for r in results if r.success)
                failed = total - passed
                
                if failed == 0:
                    summary_style = "green"
                    summary_text = f"All {total} hook test(s) passed!"
                else:
                    summary_style = "red"
                    summary_text = f"{failed} of {total} hook test(s) failed!"
                
                summary_panel = Panel(
                    Text(summary_text, style=f"bold {summary_style}"),
                    border_style=summary_style,
                    padding=(0, 1)
                )
                console.print(summary_panel)
            else:
                console.print("[yellow]No hook tests were executed[/yellow]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Hook testing interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Hook testing failed: {e}[/red]")
        logger.error("Hook testing failed", error=str(e), error_type=type(e).__name__)
        raise