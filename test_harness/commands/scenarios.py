"""Scenario management command module for the Superego MCP Test Harness.

This module provides comprehensive scenario management capabilities including
listing, validation, execution, and reporting with JSON schema validation.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ..client.response_formatter import ResponseFormatter, TestResult, create_test_result
from ..client.superego_client import SuperegoTestClient, SuperegoClientError
from ..config.loader import TestHarnessConfig, load_config

logger = structlog.get_logger(__name__)


# JSON Schema for scenario validation
SCENARIO_SCHEMA = {
    "type": "object",
    "required": ["scenarios"],
    "properties": {
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "description", "tool_name", "parameters", "expected_action"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-zA-Z0-9_]+$"},
                    "name": {"type": "string", "minLength": 1},
                    "description": {"type": "string", "minLength": 1},
                    "tool_name": {"type": "string", "minLength": 1},
                    "parameters": {"type": "object"},
                    "expected_action": {
                        "type": "string",
                        "enum": ["allow", "deny", "allow_with_warning", "allow_with_confirmation"]
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "hook_context": {
                        "type": "object",
                        "properties": {
                            "event_type": {"type": "string"},
                            "claude_session_id": {"type": "string"},
                            "user_id": {"type": "string"},
                            "tool_metadata": {"type": "object"}
                        }
                    },
                    "timeout": {"type": "number", "minimum": 0},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "skip_reason": {"type": "string"}
                },
                "additionalProperties": True
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "author": {"type": "string"},
                "description": {"type": "string"},
                "created": {"type": "string"},
                "updated": {"type": "string"}
            }
        }
    }
}


class ScenarioValidationError(Exception):
    """Error raised when scenario validation fails."""
    pass


class ScenarioRunner:
    """Test scenario execution engine."""
    
    def __init__(self, config: TestHarnessConfig, console: Optional[Console] = None):
        """Initialize scenario runner.
        
        Args:
            config: Test harness configuration
            console: Rich console for output
        """
        self.config = config
        self.console = console or Console()
        self.formatter = ResponseFormatter(self.console)
        
        # Execution state
        self.results: List[TestResult] = []
        self.skipped_scenarios: List[Dict[str, Any]] = []
        self.execution_start_time: float = 0.0
        self.execution_end_time: float = 0.0
    
    async def manage_scenarios(
        self,
        scenario_name: Optional[str] = None,
        config_dir: Optional[Path] = None,
        output_format: str = "table",
        parallel: bool = False,
        fail_fast: bool = False,
        tags: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Main scenario management interface.
        
        Args:
            scenario_name: Specific scenario name to run (None to list all)
            config_dir: Directory containing scenario files
            output_format: Output format for results
            parallel: Run scenarios in parallel
            fail_fast: Stop on first failure
            tags: Comma-separated tags to filter by
            
        Returns:
            Execution summary and results
        """
        # Determine scenario directory
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "scenarios"
        
        # Parse tag filters
        tag_filters = self._parse_tag_filters(tags)
        
        # Load and validate scenarios
        scenarios = await self._load_scenarios(config_dir)
        
        if not scenarios:
            self.console.print("[yellow]No scenarios found[/yellow]")
            return {"status": "no_scenarios", "results": []}
        
        # Validate scenarios
        validation_results = self._validate_scenarios(scenarios)
        self._display_validation_results(validation_results)
        
        # Filter scenarios
        filtered_scenarios = self._filter_scenarios(scenarios, scenario_name, tag_filters)
        
        if not filtered_scenarios:
            self.console.print("[yellow]No scenarios match the specified criteria[/yellow]")
            return {"status": "no_matching_scenarios", "results": []}
        
        # If no specific scenario, just list available scenarios
        if scenario_name is None:
            self._display_scenario_list(filtered_scenarios, output_format)
            return {"status": "listed", "scenarios": filtered_scenarios}
        
        # Execute scenarios
        return await self._execute_scenarios(
            filtered_scenarios,
            parallel=parallel,
            fail_fast=fail_fast,
            output_format=output_format
        )
    
    async def _load_scenarios(self, config_dir: Path) -> List[Dict[str, Any]]:
        """Load scenarios from JSON files in the config directory.
        
        Args:
            config_dir: Directory containing scenario files
            
        Returns:
            List of loaded scenarios
        """
        scenarios: List[Dict[str, Any]] = []
        
        if not config_dir.exists():
            self.console.print(f"[red]Scenario directory not found: {config_dir}[/red]")
            return scenarios
        
        # Find all JSON files in the directory
        json_files = list(config_dir.glob("*.json"))
        
        if not json_files:
            self.console.print(f"[yellow]No JSON scenario files found in: {config_dir}[/yellow]")
            return scenarios
        
        self.console.print(f"[dim]Loading scenarios from {len(json_files)} files...[/dim]")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract scenarios from the file
                file_scenarios = data.get("scenarios", [])
                
                # Add source file information to each scenario
                for scenario in file_scenarios:
                    scenario["_source_file"] = str(json_file)
                    scenario["_file_name"] = json_file.name
                
                scenarios.extend(file_scenarios)
                
                self.console.print(f"[green]✓[/green] Loaded {len(file_scenarios)} scenarios from [cyan]{json_file.name}[/cyan]")
                
            except json.JSONDecodeError as e:
                self.console.print(f"[red]✗ Invalid JSON in {json_file.name}: {e}[/red]")
            except Exception as e:
                self.console.print(f"[red]✗ Error loading {json_file.name}: {e}[/red]")
        
        self.console.print(f"[bold green]Total scenarios loaded: {len(scenarios)}[/bold green]")
        return scenarios
    
    def _validate_scenarios(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate scenarios against JSON schema.
        
        Args:
            scenarios: List of scenarios to validate
            
        Returns:
            Validation results summary
        """
        validation_results: Dict[str, Any] = {
            "total": len(scenarios),
            "valid": 0,
            "invalid": 0,
            "errors": [],
            "warnings": []
        }
        
        for i, scenario in enumerate(scenarios):
            try:
                # Basic schema validation
                self._validate_scenario_schema(scenario)
                
                # Additional business logic validation
                warnings = self._validate_scenario_logic(scenario)
                
                validation_results["valid"] = validation_results["valid"] + 1
                
                if warnings:
                    validation_results["warnings"].append({
                        "scenario_id": scenario.get("id", f"scenario_{i}"), 
                        "warnings": warnings
                    })
                
            except ScenarioValidationError as e:
                validation_results["invalid"] = validation_results["invalid"] + 1
                validation_results["errors"].append({
                    "scenario_id": scenario.get("id", f"scenario_{i}"),
                    "error": str(e)
                })
        
        return validation_results
    
    def _validate_scenario_schema(self, scenario: Dict[str, Any]) -> None:
        """Validate individual scenario against schema.
        
        Args:
            scenario: Scenario to validate
            
        Raises:
            ScenarioValidationError: If validation fails
        """
        # Check required fields
        required_fields = ["id", "name", "description", "tool_name", "parameters", "expected_action"]
        
        for field in required_fields:
            if field not in scenario:
                raise ScenarioValidationError(f"Missing required field: {field}")
            
            if not scenario[field]:
                raise ScenarioValidationError(f"Empty required field: {field}")
        
        # Validate expected_action values
        valid_actions = ["allow", "deny", "allow_with_warning", "allow_with_confirmation"]
        if scenario["expected_action"] not in valid_actions:
            raise ScenarioValidationError(
                f"Invalid expected_action: {scenario['expected_action']}. "
                f"Must be one of: {', '.join(valid_actions)}"
            )
        
        # Validate ID format
        scenario_id = scenario["id"]
        if not isinstance(scenario_id, str) or not scenario_id.replace("_", "").isalnum():
            raise ScenarioValidationError(f"Invalid scenario ID format: {scenario_id}")
        
        # Validate parameters is a dict
        if not isinstance(scenario["parameters"], dict):
            raise ScenarioValidationError("Parameters must be a dictionary")
    
    def _validate_scenario_logic(self, scenario: Dict[str, Any]) -> List[str]:
        """Validate scenario business logic and return warnings.
        
        Args:
            scenario: Scenario to validate
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check for potentially problematic tool/parameter combinations
        tool_name = scenario["tool_name"]
        parameters = scenario["parameters"]
        expected_action = scenario["expected_action"]
        
        # Warning for dangerous operations that are expected to be allowed
        if tool_name.lower() in ["bash", "write", "delete"] and expected_action == "allow":
            if "system" in str(parameters).lower() or "root" in str(parameters).lower():
                warnings.append("Dangerous operation with 'allow' expected action")
        
        # Warning for missing tags
        if not scenario.get("tags"):
            warnings.append("No tags specified - consider adding tags for better organization")
        
        # Warning for missing hook context when it might be relevant
        if "claude" in scenario.get("name", "").lower() and not scenario.get("hook_context"):
            warnings.append("Scenario appears to be Claude-related but missing hook_context")
        
        return warnings
    
    def _display_validation_results(self, results: Dict[str, Any]) -> None:
        """Display scenario validation results.
        
        Args:
            results: Validation results to display
        """
        total = results["total"]
        valid = results["valid"]
        invalid = results["invalid"]
        
        # Summary
        if invalid == 0:
            status_text = f"[green]✓ All {total} scenarios are valid[/green]"
        else:
            status_text = f"[yellow]⚠ {valid}/{total} scenarios are valid ({invalid} invalid)[/yellow]"
        
        self.console.print(status_text)
        
        # Show errors
        if results["errors"]:
            self.console.print("\n[bold red]Validation Errors:[/bold red]")
            for error_info in results["errors"]:
                self.console.print(f"  [red]•[/red] {error_info['scenario_id']}: {error_info['error']}")
        
        # Show warnings
        if results["warnings"]:
            self.console.print("\n[bold yellow]Validation Warnings:[/bold yellow]")
            for warning_info in results["warnings"]:
                scenario_id = warning_info["scenario_id"]
                for warning in warning_info["warnings"]:
                    self.console.print(f"  [yellow]•[/yellow] {scenario_id}: {warning}")
    
    def _parse_tag_filters(self, tags: Optional[str]) -> Set[str]:
        """Parse comma-separated tag filters.
        
        Args:
            tags: Comma-separated tag string
            
        Returns:
            Set of tag filters
        """
        if not tags:
            return set()
        
        return {tag.strip().lower() for tag in tags.split(",") if tag.strip()}
    
    def _filter_scenarios(
        self,
        scenarios: List[Dict[str, Any]],
        scenario_name: Optional[str],
        tag_filters: Set[str],
    ) -> List[Dict[str, Any]]:
        """Filter scenarios by name and tags.
        
        Args:
            scenarios: List of all scenarios
            scenario_name: Specific scenario name to filter by
            tag_filters: Set of tags to filter by
            
        Returns:
            Filtered list of scenarios
        """
        filtered = scenarios
        
        # Filter by scenario name
        if scenario_name:
            filtered = [
                s for s in filtered
                if scenario_name.lower() in s.get("name", "").lower()
                or scenario_name.lower() in s.get("id", "").lower()
            ]
        
        # Filter by tags
        if tag_filters:
            filtered = [
                s for s in filtered
                if any(
                    tag.lower() in tag_filters
                    for tag in s.get("tags", [])
                )
            ]
        
        return filtered
    
    def _display_scenario_list(
        self,
        scenarios: List[Dict[str, Any]],
        output_format: str,
    ) -> None:
        """Display list of available scenarios.
        
        Args:
            scenarios: List of scenarios to display
            output_format: Output format (table, json, tree)
        """
        if output_format == "json":
            self._display_scenarios_json(scenarios)
        elif output_format == "tree":
            self._display_scenarios_tree(scenarios)
        else:  # table
            self._display_scenarios_table(scenarios)
    
    def _display_scenarios_table(self, scenarios: List[Dict[str, Any]]) -> None:
        """Display scenarios as a table."""
        table = Table(title="Available Test Scenarios", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", min_width=12)
        table.add_column("Name", style="green", min_width=20)
        table.add_column("Tool", style="blue", min_width=10)
        table.add_column("Expected", style="yellow", min_width=12)
        table.add_column("Tags", style="dim", min_width=15)
        table.add_column("Source", style="dim", min_width=10)
        
        for scenario in scenarios:
            # Truncate long values
            name = scenario.get("name", "")[:30] + ("..." if len(scenario.get("name", "")) > 30 else "")
            tool_name = scenario.get("tool_name", "")[:15]
            expected = scenario.get("expected_action", "")[:15]
            tags = ", ".join(scenario.get("tags", [])[:3])
            if len(scenario.get("tags", [])) > 3:
                tags += "..."
            source = scenario.get("_file_name", "unknown")[:15]
            
            # Color code expected action
            if expected == "allow":
                expected = f"[green]{expected}[/green]"
            elif expected == "deny":
                expected = f"[red]{expected}[/red]"
            elif "warning" in expected:
                expected = f"[yellow]{expected}[/yellow]"
            
            table.add_row(
                scenario.get("id", ""),
                name,
                tool_name,
                expected,
                tags,
                source
            )
        
        self.console.print(table)
        
        # Summary
        self.console.print(f"\n[dim]Total scenarios: {len(scenarios)}[/dim]")
    
    def _display_scenarios_json(self, scenarios: List[Dict[str, Any]]) -> None:
        """Display scenarios as JSON."""
        # Remove internal fields before display
        clean_scenarios = []
        for scenario in scenarios:
            clean_scenario = {k: v for k, v in scenario.items() if not k.startswith("_")}
            clean_scenarios.append(clean_scenario)
        
        self.console.print(json.dumps(clean_scenarios, indent=2))
    
    def _display_scenarios_tree(self, scenarios: List[Dict[str, Any]]) -> None:
        """Display scenarios as a tree grouped by source file."""
        # Group by source file
        file_groups: Dict[str, List[Dict[str, Any]]] = {}
        for scenario in scenarios:
            file_name = scenario.get("_file_name", "unknown")
            if file_name not in file_groups:
                file_groups[file_name] = []
            file_groups[file_name].append(scenario)
        
        # Create tree
        tree = Tree("Test Scenarios")
        
        for file_name, file_scenarios in sorted(file_groups.items()):
            file_node = tree.add(f"[cyan]{file_name}[/cyan] ({len(file_scenarios)} scenarios)")
            
            for scenario in file_scenarios:
                scenario_id = scenario.get("id", "unknown")
                scenario_name = scenario.get("name", "")
                expected = scenario.get("expected_action", "")
                
                # Color code by expected action
                if expected == "allow":
                    color = "green"
                elif expected == "deny":
                    color = "red"
                else:
                    color = "yellow"
                
                scenario_text = f"[{color}]{scenario_id}[/{color}]: {scenario_name}"
                file_node.add(scenario_text)
        
        self.console.print(tree)
    
    async def _execute_scenarios(
        self,
        scenarios: List[Dict[str, Any]],
        parallel: bool = False,
        fail_fast: bool = False,
        output_format: str = "table",
    ) -> Dict[str, Any]:
        """Execute filtered scenarios.
        
        Args:
            scenarios: List of scenarios to execute
            parallel: Run scenarios in parallel
            fail_fast: Stop on first failure
            output_format: Output format for results
            
        Returns:
            Execution summary and results
        """
        self.console.print(Panel(
            f"[bold]Executing {len(scenarios)} scenarios[/bold]\n\n"
            f"Parallel execution: [{'green' if parallel else 'red'}]{parallel}[/{'green' if parallel else 'red'}]\n"
            f"Fail fast: [{'green' if fail_fast else 'red'}]{fail_fast}[/{'green' if fail_fast else 'red'}]",
            title="Scenario Execution",
            border_style="blue"
        ))
        
        # Initialize execution state
        self.results = []
        self.skipped_scenarios = []
        self.execution_start_time = time.time()
        
        # Create progress tracking
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        )
        
        task_id: Optional[TaskID] = None
        
        try:
            with progress:
                task_id = progress.add_task("Executing scenarios", total=len(scenarios))
                
                if parallel:
                    await self._execute_scenarios_parallel(scenarios, progress, task_id, fail_fast)
                else:
                    await self._execute_scenarios_sequential(scenarios, progress, task_id, fail_fast)
        
        finally:
            self.execution_end_time = time.time()
        
        # Display results
        await self._display_execution_results(output_format)
        
        # Return summary
        return self._generate_execution_summary()
    
    async def _execute_scenarios_sequential(
        self,
        scenarios: List[Dict[str, Any]],
        progress: Progress,
        task_id: TaskID,
        fail_fast: bool,
    ) -> None:
        """Execute scenarios sequentially."""
        async with SuperegoTestClient(self.config) as client:
            for i, scenario in enumerate(scenarios):
                # Check if we should skip due to previous failure
                if fail_fast and any(not r.success for r in self.results):
                    self.skipped_scenarios.append(scenario)
                    continue
                
                # Execute scenario
                result = await self._execute_single_scenario(client, scenario)
                self.results.append(result)
                
                # Update progress
                progress.update(task_id, completed=i + 1)
                
                # Short delay between requests
                await asyncio.sleep(0.1)
    
    async def _execute_scenarios_parallel(
        self,
        scenarios: List[Dict[str, Any]],
        progress: Progress,
        task_id: TaskID,
        fail_fast: bool,
    ) -> None:
        """Execute scenarios in parallel."""
        # Create semaphore to limit concurrency
        max_concurrent = self.config.scenarios.max_concurrent
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_with_semaphore(scenario: Dict[str, Any]) -> TestResult:
            async with semaphore:
                async with SuperegoTestClient(self.config) as client:
                    return await self._execute_single_scenario(client, scenario)
        
        # Create tasks
        tasks = [asyncio.create_task(execute_with_semaphore(scenario)) for scenario in scenarios]
        
        # Execute with progress tracking
        completed = 0
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                self.results.append(result)
                
                # Check fail-fast condition
                if fail_fast and not result.success:
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    break
                
            except Exception as e:
                logger.error("Scenario execution error", error=str(e))
            
            completed += 1
            progress.update(task_id, completed=completed)
    
    async def _execute_single_scenario(
        self,
        client: SuperegoTestClient,
        scenario: Dict[str, Any],
    ) -> TestResult:
        """Execute a single test scenario.
        
        Args:
            client: Superego test client
            scenario: Scenario to execute
            
        Returns:
            Test result
        """
        scenario_id = scenario.get("id", "unknown")
        scenario_name = scenario.get("name", "")
        tool_name = scenario.get("tool_name", "")
        parameters = scenario.get("parameters", {})
        expected_action = scenario.get("expected_action", "")
        
        # Check if scenario should be skipped
        if scenario.get("skip_reason"):
            return create_test_result(
                success=False,
                test_name=f"Scenario: {scenario_name}",
                endpoint="/v1/evaluate",
                method="POST",
                error_message=f"Skipped: {scenario['skip_reason']}",
                tags=scenario.get("tags", [])
            )
        
        start_time = time.perf_counter()
        
        try:
            # Determine execution method based on scenario type
            if scenario.get("hook_context"):
                # Execute as Claude Code hook
                result_data = await client.test_claude_hook(
                    event_name=scenario["hook_context"].get("event_type", "PreToolUse"),
                    tool_name=tool_name,
                    arguments=parameters,
                    timeout=scenario.get("timeout")
                )
                endpoint = "/v1/hooks"
            else:
                # Execute as tool evaluation
                result_data = await client.evaluate_tool(
                    tool_name=tool_name,
                    parameters=parameters,
                    agent_id=scenario.get("agent_id", "scenario-test"),
                    session_id=f"scenario-{scenario_id}",
                    timeout=scenario.get("timeout")
                )
                endpoint = "/v1/evaluate"
            
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Analyze result against expected action
            success, analysis = self._analyze_scenario_result(result_data, expected_action)
            
            result = create_test_result(
                success=success,
                response_data=result_data,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name=f"Scenario: {scenario_name}",
                endpoint=endpoint,
                method="POST",
                agent_id=scenario.get("agent_id", "scenario-test"),
                session_id=f"scenario-{scenario_id}",
                tags=scenario.get("tags", []),
                request_data={
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "expected_action": expected_action,
                    "scenario_id": scenario_id
                }
            )
            
            # Add analysis to response data
            if result.response_data:
                result.response_data["_scenario_analysis"] = analysis
            
            return result
            
        except SuperegoClientError as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            return create_test_result(
                success=False,
                response_time_ms=response_time_ms,
                test_name=f"Scenario: {scenario_name}",
                endpoint="/v1/evaluate",
                method="POST",
                error_message=str(e),
                error_type=type(e).__name__,
                agent_id=scenario.get("agent_id", "scenario-test"),
                session_id=f"scenario-{scenario_id}",
                tags=scenario.get("tags", [])
            )
    
    def _analyze_scenario_result(
        self,
        result_data: Dict[str, Any],
        expected_action: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Analyze scenario result against expected action.
        
        Args:
            result_data: Response data from server
            expected_action: Expected action from scenario
            
        Returns:
            Tuple of (success, analysis_details)
        """
        analysis: Dict[str, Any] = {
            "expected_action": expected_action,
            "actual_action": "unknown",
            "match": False,
            "details": {}
        }
        
        # Extract actual action from response
        if not result_data:
            analysis["actual_action"] = "error"
            analysis["details"]["error"] = "No response data"
            return False, analysis
        
        # Look for decision in various possible response formats
        decision = result_data.get("decision")
        if not decision:
            decision = result_data.get("action")
        if not decision:
            decision = result_data.get("result")
        
        if isinstance(decision, dict):
            actual_action = decision.get("action", "unknown")
        elif isinstance(decision, str):
            actual_action = decision
        else:
            actual_action = "unknown"
        
        analysis["actual_action"] = actual_action
        
        # Normalize actions for comparison
        expected_normalized = expected_action.lower().replace("_", " ")
        actual_normalized = actual_action.lower().replace("_", " ")
        
        # Check for match (flexible matching)
        if expected_normalized == actual_normalized:
            analysis["match"] = True
        elif expected_action == "allow" and actual_action in ["allow", "approved", "permitted"]:
            analysis["match"] = True
        elif expected_action == "deny" and actual_action in ["deny", "denied", "blocked", "rejected"]:
            analysis["match"] = True
        elif "warning" in expected_action and "warning" in actual_action:
            analysis["match"] = True
        
        # Add additional analysis details
        if result_data.get("reasons"):
            analysis["details"]["reasons"] = result_data["reasons"]
        if result_data.get("rules_matched"):
            analysis["details"]["rules_matched"] = result_data["rules_matched"]
        if result_data.get("confidence"):
            analysis["details"]["confidence"] = result_data["confidence"]
        
        return analysis["match"], analysis
    
    async def _display_execution_results(self, output_format: str) -> None:
        """Display scenario execution results.
        
        Args:
            output_format: Output format for results
        """
        if not self.results and not self.skipped_scenarios:
            self.console.print("[yellow]No scenarios were executed[/yellow]")
            return
        
        # Display results based on format
        if output_format == "json":
            self._display_results_json()
        elif output_format == "tree":
            self._display_results_tree()
        else:  # table
            self._display_results_table()
        
        # Display summary
        self._display_execution_summary()
    
    def _display_results_table(self) -> None:
        """Display results as a table."""
        if self.results:
            self.formatter.format_table(self.results)
        
        # Show skipped scenarios if any
        if self.skipped_scenarios:
            self.console.print("\n[bold yellow]Skipped Scenarios:[/bold yellow]")
            skip_table = Table(show_header=True, header_style="bold yellow")
            skip_table.add_column("ID", style="cyan")
            skip_table.add_column("Name", style="white")
            skip_table.add_column("Reason", style="yellow")
            
            for scenario in self.skipped_scenarios:
                skip_table.add_row(
                    scenario.get("id", "unknown"),
                    scenario.get("name", "")[:40],
                    scenario.get("skip_reason", "Failed fast execution")
                )
            
            self.console.print(skip_table)
    
    def _display_results_json(self) -> None:
        """Display results as JSON."""
        results_data = {
            "executed": [result.to_dict() for result in self.results],
            "skipped": self.skipped_scenarios,
            "summary": self._generate_execution_summary()
        }
        
        self.console.print(json.dumps(results_data, indent=2))
    
    def _display_results_tree(self) -> None:
        """Display results as a tree grouped by success/failure."""
        tree = Tree("Scenario Results")
        
        # Group by success/failure
        passed = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        
        if passed:
            passed_node = tree.add(f"[green]Passed ({len(passed)})[/green]")
            for result in passed:
                passed_node.add(f"[green]✓[/green] {result.test_name}")
        
        if failed:
            failed_node = tree.add(f"[red]Failed ({len(failed)})[/red]")
            for result in failed:
                error_msg = result.error_message or "Unknown error"
                failed_node.add(f"[red]✗[/red] {result.test_name}: [dim]{error_msg[:50]}[/dim]")
        
        if self.skipped_scenarios:
            skipped_node = tree.add(f"[yellow]Skipped ({len(self.skipped_scenarios)})[/yellow]")
            for scenario in self.skipped_scenarios:
                reason = scenario.get("skip_reason", "Failed fast execution")
                skipped_node.add(f"[yellow]⚠[/yellow] {scenario.get('name', 'Unknown')}: [dim]{reason}[/dim]")
        
        self.console.print(tree)
    
    def _display_execution_summary(self) -> None:
        """Display execution summary."""
        total_scenarios = len(self.results) + len(self.skipped_scenarios)
        passed = sum(1 for r in self.results if r.success)
        failed = len(self.results) - passed
        skipped = len(self.skipped_scenarios)
        
        duration = self.execution_end_time - self.execution_start_time
        
        summary_table = Table(title="Execution Summary", show_header=False)
        summary_table.add_column("Metric", style="cyan", min_width=20)
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Total Scenarios", str(total_scenarios))
        summary_table.add_row("Executed", str(len(self.results)))
        summary_table.add_row("Passed", f"[green]{passed}[/green]")
        summary_table.add_row("Failed", f"[red]{failed}[/red]")
        summary_table.add_row("Skipped", f"[yellow]{skipped}[/yellow]")
        summary_table.add_row("Execution Time", f"{duration:.2f}s")
        
        if self.results:
            avg_time = sum(r.response_time_ms for r in self.results) / len(self.results)
            success_rate = passed / len(self.results) * 100
            summary_table.add_row("Success Rate", f"{success_rate:.1f}%")
            summary_table.add_row("Avg Response Time", f"{avg_time:.1f}ms")
        
        self.console.print()
        self.console.print(summary_table)
    
    def _generate_execution_summary(self) -> Dict[str, Any]:
        """Generate execution summary for return value."""
        total_scenarios = len(self.results) + len(self.skipped_scenarios)
        passed = sum(1 for r in self.results if r.success)
        failed = len(self.results) - passed
        skipped = len(self.skipped_scenarios)
        
        duration = self.execution_end_time - self.execution_start_time
        
        summary = {
            "status": "completed",
            "total_scenarios": total_scenarios,
            "executed": len(self.results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": passed / len(self.results) if self.results else 0,
            "execution_time_seconds": duration,
            "results": [r.to_dict() for r in self.results],
            "skipped_scenarios": self.skipped_scenarios
        }
        
        if self.results:
            response_times = [r.response_time_ms for r in self.results]
            summary["performance"] = {
                "avg_response_time_ms": sum(response_times) / len(response_times),
                "min_response_time_ms": min(response_times),
                "max_response_time_ms": max(response_times),
            }
        
        return summary


async def manage_scenarios(
    scenario_name: Optional[str] = None,
    config_dir: Optional[Path] = None,
    output_format: str = "table",
    parallel: bool = False,
    fail_fast: bool = False,
    tags: Optional[str] = None,
    config_profile: str = "default",
) -> Dict[str, Any]:
    """Main entry point for scenario management command.
    
    Args:
        scenario_name: Specific scenario name to run (None to list all)
        config_dir: Directory containing scenario files
        output_format: Output format for results
        parallel: Run scenarios in parallel
        fail_fast: Stop on first failure
        tags: Comma-separated tags to filter by
        config_profile: Configuration profile to use
        
    Returns:
        Execution summary and results
    """
    # Load configuration
    config = load_config(config_profile)
    
    # Create console for output
    console = Console()
    
    # Create and run scenario manager
    runner = ScenarioRunner(config, console)
    
    return await runner.manage_scenarios(
        scenario_name=scenario_name,
        config_dir=config_dir,
        output_format=output_format,
        parallel=parallel,
        fail_fast=fail_fast,
        tags=tags,
    )