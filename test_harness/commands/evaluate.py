"""Evaluation command for testing tool requests and scenarios against Superego MCP Server.

This module provides functionality for loading and executing test scenarios,
parsing JSON parameters, and displaying results with Rich console formatting.
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


class ScenarioLoader:
    """Loads and parses test scenarios from JSON files."""
    
    def __init__(self, console: Console):
        self.console = console
        self.logger = logger.bind(component="scenario_loader")
    
    def load_scenarios_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load scenarios from a JSON file.
        
        Args:
            file_path: Path to the JSON scenario file
            
        Returns:
            List of scenario dictionaries
            
        Raises:
            FileNotFoundError: If the scenario file doesn't exist
            json.JSONDecodeError: If the file contains invalid JSON
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both direct scenario arrays and wrapped format
            if isinstance(data, list):
                scenarios = data
            elif isinstance(data, dict) and 'scenarios' in data:
                scenarios = data['scenarios']
            else:
                raise ValueError(f"Invalid scenario file format in {file_path}")
            
            self.logger.info(
                "Loaded scenarios from file",
                file_path=str(file_path),
                scenario_count=len(scenarios)
            )
            
            return scenarios
            
        except FileNotFoundError:
            self.console.print(f"[red]Error: Scenario file not found: {file_path}[/red]")
            raise
        except json.JSONDecodeError as e:
            self.console.print(f"[red]Error: Invalid JSON in scenario file {file_path}: {e}[/red]")
            raise
        except Exception as e:
            self.console.print(f"[red]Error loading scenarios from {file_path}: {e}[/red]")
            raise
    
    def parse_json_parameters(self, json_str: str) -> Dict[str, Any]:
        """Parse JSON parameter string.
        
        Args:
            json_str: JSON string containing parameters
            
        Returns:
            Parsed parameters dictionary
            
        Raises:
            json.JSONDecodeError: If the JSON is invalid
        """
        try:
            params = json.loads(json_str)
            self.logger.debug("Parsed JSON parameters", param_count=len(params) if isinstance(params, dict) else 0)
            if isinstance(params, dict):
                return params
            else:
                raise ValueError("JSON parameters must be a dictionary")
        except json.JSONDecodeError as e:
            self.console.print(f"[red]Error: Invalid JSON parameters: {e}[/red]")
            raise


class ScenarioExecutor:
    """Executes test scenarios against the Superego MCP Server."""
    
    def __init__(self, client: SuperegoTestClient, console: Console, formatter: ResponseFormatter):
        self.client = client
        self.console = console
        self.formatter = formatter
        self.logger = logger.bind(component="scenario_executor")
    
    async def execute_scenario(self, scenario: Dict[str, Any]) -> TestResult:
        """Execute a single test scenario.
        
        Args:
            scenario: Scenario dictionary containing test configuration
            
        Returns:
            TestResult containing execution results
        """
        scenario_id = scenario.get('id', 'unknown')
        scenario_name = scenario.get('name', f'Scenario {scenario_id}')
        tool_name = scenario.get('tool_name', '')
        parameters = scenario.get('parameters', {})
        
        self.logger.info(
            "Executing scenario",
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            tool_name=tool_name
        )
        
        start_time = time.perf_counter()
        
        try:
            # Execute the tool evaluation request
            response_data = await self.client.evaluate_tool(
                tool_name=tool_name,
                parameters=parameters,
                agent_id=f"test-harness-{scenario_id}",
                session_id=f"scenario-{scenario_id}-{int(time.time())}"
            )
            
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Determine success based on expected action
            expected_action = scenario.get('expected_action', 'allow')
            actual_action = response_data.get('action', 'unknown')
            success = (actual_action == expected_action)
            
            result = create_test_result(
                success=success,
                response_data=response_data,
                status_code=200,  # HTTP client handles error status codes
                response_time_ms=response_time_ms,
                test_name=scenario_name,
                endpoint="/v1/evaluate",
                method="POST",
                request_data={
                    "tool_name": tool_name,
                    "parameters": parameters
                },
                agent_id=f"test-harness-{scenario_id}",
                session_id=f"scenario-{scenario_id}-{int(time.time())}",
                tags=scenario.get('tags', [])
            )
            
            if not success:
                result.error_message = f"Expected action '{expected_action}', got '{actual_action}'"
            
            self.logger.info(
                "Scenario execution completed",
                scenario_id=scenario_id,
                success=success,
                response_time_ms=round(response_time_ms, 2),
                expected_action=expected_action,
                actual_action=actual_action
            )
            
            return result
            
        except SuperegoClientError as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            self.logger.error(
                "Scenario execution failed",
                scenario_id=scenario_id,
                error=str(e),
                error_type=type(e).__name__
            )
            
            return create_test_result(
                success=False,
                response_time_ms=response_time_ms,
                test_name=scenario_name,
                endpoint="/v1/evaluate",
                method="POST",
                error_message=str(e),
                error_type=type(e).__name__,
                request_data={
                    "tool_name": tool_name,
                    "parameters": parameters
                },
                agent_id=f"test-harness-{scenario_id}",
                tags=scenario.get('tags', [])
            )
    
    async def execute_scenarios(self, scenarios: List[Dict[str, Any]], parallel: bool = False) -> List[TestResult]:
        """Execute multiple scenarios.
        
        Args:
            scenarios: List of scenario dictionaries
            parallel: Whether to execute scenarios in parallel
            
        Returns:
            List of TestResult objects
        """
        if not scenarios:
            self.console.print("[yellow]No scenarios to execute[/yellow]")
            return []
        
        self.console.print(f"[cyan]Executing {len(scenarios)} scenario(s)...[/cyan]")
        
        if parallel:
            # Execute scenarios in parallel
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("Running scenarios in parallel...", total=None)
                
                tasks = [self.execute_scenario(scenario) for scenario in scenarios]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Convert exceptions to failed TestResult objects
                final_results: List[TestResult] = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        scenario = scenarios[i]
                        final_results.append(create_test_result(
                            success=False,
                            test_name=scenario.get('name', f'Scenario {i}'),
                            error_message=str(result),
                            error_type=type(result).__name__
                        ))
                    else:
                        # All non-exception results should be TestResult objects
                        final_results.append(result)  # type: ignore[arg-type]
                
                progress.update(task, completed=True)
                return final_results
        else:
            # Execute scenarios sequentially
            sequential_results: List[TestResult] = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                for i, scenario in enumerate(scenarios):
                    scenario_name = scenario.get('name', f'Scenario {i+1}')
                    task = progress.add_task(f"Running {scenario_name}...", total=None)
                    
                    result = await self.execute_scenario(scenario)
                    sequential_results.append(result)
                    
                    progress.update(task, completed=True)
                    progress.remove_task(task)
            
            return sequential_results


async def run_evaluation(
    scenario_file: Optional[Path] = None,
    tool_name: Optional[str] = None,
    parameters_json: Optional[str] = None,
    config_file: Optional[Path] = None,
    output_format: str = "pretty",
    parallel: bool = False,
    tags_filter: Optional[List[str]] = None
) -> None:
    """Run tool evaluation against Superego MCP Server.
    
    Args:
        scenario_file: Path to JSON file containing test scenarios
        tool_name: Single tool name to test (requires parameters_json)
        parameters_json: JSON string containing tool parameters
        config_file: Path to test harness configuration file
        output_format: Output format (pretty, table, json, summary)
        parallel: Whether to execute scenarios in parallel
        tags_filter: List of tags to filter scenarios by
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
        loader = ScenarioLoader(console)
        formatter = ResponseFormatter(console)
        
        # Load scenarios
        scenarios = []
        
        if scenario_file:
            # Load scenarios from file
            all_scenarios = loader.load_scenarios_from_file(scenario_file)
            
            # Apply tag filtering if specified
            if tags_filter:
                scenarios = [
                    s for s in all_scenarios
                    if any(tag in s.get('tags', []) for tag in tags_filter)
                ]
                console.print(f"[cyan]Filtered to {len(scenarios)} scenarios matching tags: {', '.join(tags_filter)}[/cyan]")
            else:
                scenarios = all_scenarios
                
        elif tool_name and parameters_json:
            # Create single scenario from command-line parameters
            try:
                parameters = loader.parse_json_parameters(parameters_json)
                scenarios = [{
                    'id': 'cli_test',
                    'name': f'CLI Test: {tool_name}',
                    'tool_name': tool_name,
                    'parameters': parameters,
                    'expected_action': 'allow',  # Default expectation
                    'tags': ['cli_generated']
                }]
            except json.JSONDecodeError:
                console.print("[red]Error: Invalid JSON in parameters[/red]")
                return
        else:
            console.print("[red]Error: Must specify either --scenario-file or both --tool-name and --parameters[/red]")
            return
        
        if not scenarios:
            console.print("[yellow]No scenarios found to execute[/yellow]")
            return
        
        # Execute scenarios
        async with SuperegoTestClient(config) as client:
            executor = ScenarioExecutor(client, console, formatter)
            results = await executor.execute_scenarios(scenarios, parallel=parallel)
        
        # Display results
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
            summary_text = f"All {total} scenario(s) passed!"
        else:
            summary_style = "red"
            summary_text = f"{failed} of {total} scenario(s) failed!"
        
        summary_panel = Panel(
            Text(summary_text, style=f"bold {summary_style}"),
            border_style=summary_style,
            padding=(0, 1)
        )
        console.print(summary_panel)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Evaluation interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Evaluation failed: {e}[/red]")
        logger.error("Evaluation failed", error=str(e), error_type=type(e).__name__)
        raise