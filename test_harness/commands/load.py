"""Load testing command module for the Superego MCP Test Harness.

This module provides comprehensive load testing capabilities with concurrent
request handling, performance metrics collection, and detailed reporting.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from ..client.response_formatter import ResponseFormatter, TestResult, create_test_result
from ..client.superego_client import SuperegoTestClient
from ..config.loader import TestHarnessConfig, load_config

logger = structlog.get_logger(__name__)


class LoadTestMetrics:
    """Metrics collector for load testing."""
    
    def __init__(self) -> None:
        """Initialize metrics collection."""
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.response_times: List[float] = []
        self.status_codes: Dict[int, int] = {}
        self.error_types: Dict[str, int] = {}
        self.concurrent_users: int = 0
        self.requests_per_second: List[float] = []
        self.timestamps: List[float] = []
    
    def record_request(self, result: TestResult) -> None:
        """Record a completed request."""
        self.total_requests += 1
        
        if result.success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if result.error_type:
                self.error_types[result.error_type] = self.error_types.get(result.error_type, 0) + 1
        
        self.response_times.append(result.response_time_ms)
        
        if result.status_code:
            self.status_codes[result.status_code] = self.status_codes.get(result.status_code, 0) + 1
        
        self.timestamps.append(time.time())
    
    def calculate_rps(self, window_seconds: float = 1.0) -> float:
        """Calculate requests per second in the last window."""
        if not self.timestamps:
            return 0.0
        
        current_time = time.time()
        window_start = current_time - window_seconds
        recent_requests = [t for t in self.timestamps if t >= window_start]
        
        return len(recent_requests) / window_seconds
    
    def get_percentiles(self) -> Dict[str, float]:
        """Calculate response time percentiles."""
        if not self.response_times:
            return {}
        
        sorted_times = sorted(self.response_times)
        length = len(sorted_times)
        
        percentiles = {}
        for p in [50, 75, 90, 95, 99]:
            index = int(length * (p / 100))
            if index >= length:
                index = length - 1
            percentiles[f"p{p}"] = sorted_times[index]
        
        return percentiles
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary."""
        duration = self.end_time - self.start_time if self.end_time > 0 else time.time() - self.start_time
        avg_rps = self.total_requests / duration if duration > 0 else 0
        
        return {
            "duration_seconds": duration,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "requests_per_second": avg_rps,
            "avg_response_time_ms": sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            "min_response_time_ms": min(self.response_times) if self.response_times else 0,
            "max_response_time_ms": max(self.response_times) if self.response_times else 0,
            "percentiles": self.get_percentiles(),
            "status_codes": self.status_codes,
            "error_types": self.error_types,
            "concurrent_users": self.concurrent_users,
        }


class LoadTestScenario:
    """Individual load test scenario configuration."""
    
    def __init__(
        self,
        name: str,
        endpoint: str,
        method: str = "POST",
        payload: Optional[Dict[str, Any]] = None,
        weight: float = 1.0,
        timeout: Optional[float] = None,
    ):
        """Initialize load test scenario.
        
        Args:
            name: Scenario name
            endpoint: API endpoint to test
            method: HTTP method
            payload: Request payload
            weight: Relative weight for scenario selection
            timeout: Request timeout override
        """
        self.name = name
        self.endpoint = endpoint
        self.method = method
        self.payload = payload or {}
        self.weight = weight
        self.timeout = timeout


class LoadTestRunner:
    """Main load test execution engine."""
    
    def __init__(self, config: TestHarnessConfig, console: Optional[Console] = None):
        """Initialize load test runner.
        
        Args:
            config: Test harness configuration
            console: Rich console for output
        """
        self.config = config
        self.console = console or Console()
        self.metrics = LoadTestMetrics()
        self.active_tasks: List[asyncio.Task[Any]] = []
        self.should_stop = False
        
        self.formatter = ResponseFormatter(self.console)
        
    async def run_load_test(
        self,
        target_url: str,
        requests: Optional[int] = None,
        duration: Optional[float] = None,
        concurrency: int = 10,
        ramp_up: float = 0.0,
        scenario_name: Optional[str] = None,
        output_file: Optional[Path] = None,
    ) -> LoadTestMetrics:
        """Run a comprehensive load test.
        
        Args:
            target_url: Target server URL
            requests: Total number of requests (conflicts with duration)
            duration: Test duration in seconds (conflicts with requests)
            concurrency: Number of concurrent users
            ramp_up: Ramp-up time in seconds
            scenario_name: Specific scenario to run
            output_file: File to save results
            
        Returns:
            Load test metrics
        """
        if requests is None and duration is None:
            requests = 100  # Default
        
        if requests is not None and duration is not None:
            raise ValueError("Cannot specify both requests and duration")
        
        # Load scenarios
        scenarios = await self._load_scenarios(scenario_name)
        if not scenarios:
            scenarios = [self._create_default_scenario()]
        
        # Update config with target URL
        test_config = self.config.model_copy()
        test_config.server.base_url = target_url
        
        self.console.print(Panel(
            f"[bold]Load Test Configuration[/bold]\n\n"
            f"Target URL: [cyan]{target_url}[/cyan]\n"
            f"Concurrency: [yellow]{concurrency}[/yellow] users\n"
            f"Requests: [green]{requests or 'unlimited'}[/green]\n"
            f"Duration: [green]{duration or 'unlimited'}[/green]s\n"
            f"Ramp-up: [blue]{ramp_up}[/blue]s\n"
            f"Scenarios: [magenta]{len(scenarios)}[/magenta]",
            title="Load Test Starting",
            border_style="green"
        ))
        
        # Initialize metrics
        self.metrics = LoadTestMetrics()
        self.metrics.concurrent_users = concurrency
        self.metrics.start_time = time.time()
        
        # Create progress tracking
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TextColumn("[cyan]{task.fields[rps]:.1f} req/s"),
            TextColumn("•"),
            TextColumn("[green]{task.fields[success_rate]:.1f}% success"),
            console=self.console
        )
        
        task_id: Optional[TaskID] = None
        
        try:
            with Live(self._create_live_dashboard(), console=self.console, refresh_per_second=2) as live:
                with progress:
                    if requests:
                        task_id = progress.add_task(
                            "Load Testing",
                            total=requests,
                            rps=0.0,
                            success_rate=100.0
                        )
                    else:
                        task_id = progress.add_task(
                            "Load Testing (duration-based)",
                            total=None,
                            rps=0.0,
                            success_rate=100.0
                        )
                    
                    # Start load test
                    await self._execute_load_test(
                        test_config,
                        scenarios,
                        concurrency,
                        requests,
                        duration,
                        ramp_up,
                        progress,
                        task_id,
                        live
                    )
        
        finally:
            self.metrics.end_time = time.time()
            
            # Clean up any remaining tasks
            await self._cleanup_tasks()
        
        # Display final results
        await self._display_results(output_file)
        
        return self.metrics
    
    async def _execute_load_test(
        self,
        config: TestHarnessConfig,
        scenarios: List[LoadTestScenario],
        concurrency: int,
        requests: Optional[int],
        duration: Optional[float],
        ramp_up: float,
        progress: Progress,
        task_id: TaskID,
        live: Live,
    ) -> None:
        """Execute the main load test loop."""
        async with SuperegoTestClient(config) as client:
            # Calculate ramp-up schedule
            ramp_delay = ramp_up / concurrency if ramp_up > 0 else 0
            
            # Start worker tasks
            for i in range(concurrency):
                if ramp_delay > 0:
                    await asyncio.sleep(ramp_delay)
                
                task = asyncio.create_task(
                    self._worker_loop(
                        client,
                        scenarios,
                        requests,
                        duration,
                        i
                    )
                )
                self.active_tasks.append(task)
            
            # Monitor progress
            await self._monitor_progress(progress, task_id, live, duration)
            
            # Signal workers to stop
            self.should_stop = True
            
            # Wait for all workers to complete
            await asyncio.gather(*self.active_tasks, return_exceptions=True)
    
    async def _worker_loop(
        self,
        client: SuperegoTestClient,
        scenarios: List[LoadTestScenario],
        max_requests: Optional[int],
        max_duration: Optional[float],
        worker_id: int,
    ) -> None:
        """Individual worker loop for generating load."""
        worker_logger = logger.bind(worker_id=worker_id)
        request_count = 0
        start_time = time.time()
        
        try:
            while not self.should_stop:
                # Check limits
                if max_requests and request_count >= max_requests // len(self.active_tasks):
                    break
                
                if max_duration and (time.time() - start_time) >= max_duration:
                    break
                
                # Select scenario (weighted random)
                scenario = self._select_scenario(scenarios)
                
                # Execute request
                start_request_time = time.perf_counter()
                try:
                    if scenario.method.upper() == "POST" and "/evaluate" in scenario.endpoint:
                        # Tool evaluation request
                        result_data = await client.evaluate_tool(
                            tool_name=scenario.payload.get("tool_name", "TestTool"),
                            parameters=scenario.payload.get("parameters", {}),
                            timeout=scenario.timeout
                        )
                        status_code = 200
                        success = True
                        error_msg = None
                        error_type = None
                        
                    elif scenario.method.upper() == "POST" and "/hooks" in scenario.endpoint:
                        # Hook request
                        result_data = await client.test_claude_hook(
                            event_name=scenario.payload.get("event_name", "PreToolUse"),
                            tool_name=scenario.payload.get("tool_name", "TestTool"),
                            arguments=scenario.payload.get("arguments", {}),
                            timeout=scenario.timeout
                        )
                        status_code = 200
                        success = True
                        error_msg = None
                        error_type = None
                        
                    elif scenario.method.upper() == "GET" and "/health" in scenario.endpoint:
                        # Health check
                        result_data = await client.check_health(timeout=scenario.timeout)
                        status_code = 200
                        success = True
                        error_msg = None
                        error_type = None
                        
                    else:
                        # Generic endpoint
                        response = await client._make_request(
                            method=scenario.method,
                            endpoint=scenario.endpoint,
                            data=scenario.payload if scenario.method.upper() in ("POST", "PUT") else None,
                            timeout_override=scenario.timeout
                        )
                        result_data = response.json() if response.text else {}
                        status_code = response.status_code
                        success = 200 <= status_code < 400
                        error_msg = None
                        error_type = None
                
                except Exception as e:
                    result_data = None
                    status_code = None
                    success = False
                    error_msg = str(e)
                    error_type = type(e).__name__
                    worker_logger.debug("Request failed", error=error_msg, scenario=scenario.name)
                
                response_time_ms = (time.perf_counter() - start_request_time) * 1000
                
                # Create test result
                result = create_test_result(
                    success=success,
                    response_data=result_data,
                    status_code=status_code,
                    response_time_ms=response_time_ms,
                    test_name=scenario.name,
                    endpoint=scenario.endpoint,
                    method=scenario.method,
                    error_message=error_msg,
                    error_type=error_type,
                    agent_id=f"load-worker-{worker_id}",
                    session_id=f"load-session-{worker_id}-{request_count}",
                )
                
                # Record metrics
                self.metrics.record_request(result)
                request_count += 1
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.001)
        
        except asyncio.CancelledError:
            worker_logger.debug("Worker cancelled")
        except Exception as e:
            worker_logger.error("Worker error", error=str(e))
    
    async def _monitor_progress(
        self,
        progress: Progress,
        task_id: TaskID,
        live: Live,
        duration: Optional[float],
    ) -> None:
        """Monitor and update progress during load test."""
        start_time = time.time()
        last_update = start_time
        
        while not self.should_stop:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Check duration limit
            if duration and elapsed >= duration:
                break
            
            # Update progress
            if current_time - last_update >= 0.5:  # Update every 500ms
                current_rps = self.metrics.calculate_rps()
                success_rate = (
                    self.metrics.successful_requests / self.metrics.total_requests * 100
                    if self.metrics.total_requests > 0 else 100.0
                )
                
                progress.update(
                    task_id,
                    completed=self.metrics.total_requests,
                    rps=current_rps,
                    success_rate=success_rate
                )
                
                # Update live dashboard
                live.update(self._create_live_dashboard())
                last_update = current_time
            
            await asyncio.sleep(0.1)
    
    def _create_live_dashboard(self) -> Panel:
        """Create live dashboard showing current metrics."""
        if self.metrics.total_requests == 0:
            return Panel("Initializing load test...", title="Load Test Dashboard")
        
        # Calculate current metrics
        current_rps = self.metrics.calculate_rps()
        success_rate = self.metrics.successful_requests / self.metrics.total_requests * 100
        avg_response_time = sum(self.metrics.response_times) / len(self.metrics.response_times)
        
        # Create metrics table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Requests", str(self.metrics.total_requests))
        table.add_row("Successful", f"{self.metrics.successful_requests} ({success_rate:.1f}%)")
        table.add_row("Failed", str(self.metrics.failed_requests))
        table.add_row("Current RPS", f"{current_rps:.1f}")
        table.add_row("Avg Response Time", f"{avg_response_time:.1f}ms")
        table.add_row("Active Workers", str(len(self.active_tasks)))
        
        return Panel(table, title="Load Test Dashboard", border_style="blue")
    
    def _select_scenario(self, scenarios: List[LoadTestScenario]) -> LoadTestScenario:
        """Select a scenario based on weights."""
        import random
        
        if len(scenarios) == 1:
            return scenarios[0]
        
        # Simple weighted selection
        total_weight = sum(s.weight for s in scenarios)
        rand_val = random.random() * total_weight
        
        current_weight = 0.0
        for scenario in scenarios:
            current_weight += scenario.weight
            if rand_val <= current_weight:
                return scenario
        
        return scenarios[-1]  # Fallback
    
    async def _load_scenarios(self, scenario_name: Optional[str]) -> List[LoadTestScenario]:
        """Load test scenarios from configuration."""
        scenarios = []
        
        # Load from predefined scenarios
        scenarios.extend([
            LoadTestScenario(
                name="Tool Evaluation",
                endpoint="/v1/evaluate",
                method="POST",
                payload={
                    "tool_name": "TestTool",
                    "parameters": {"test": "data"},
                    "agent_id": "load-test-agent",
                    "session_id": "load-test-session"
                },
                weight=3.0
            ),
            LoadTestScenario(
                name="Health Check",
                endpoint="/v1/health",
                method="GET",
                weight=1.0
            ),
            LoadTestScenario(
                name="Claude Hook",
                endpoint="/v1/hooks",
                method="POST",
                payload={
                    "event_name": "PreToolUse",
                    "tool_name": "TestTool",
                    "arguments": {"test": "data"}
                },
                weight=2.0
            ),
        ])
        
        # Filter by scenario name if specified
        if scenario_name:
            scenarios = [s for s in scenarios if scenario_name.lower() in s.name.lower()]
        
        return scenarios
    
    def _create_default_scenario(self) -> LoadTestScenario:
        """Create a default scenario for basic testing."""
        return LoadTestScenario(
            name="Default Health Check",
            endpoint="/v1/health",
            method="GET",
            weight=1.0
        )
    
    async def _cleanup_tasks(self) -> None:
        """Clean up any remaining async tasks."""
        if self.active_tasks:
            # Cancel remaining tasks
            for task in self.active_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for cancellation
            await asyncio.gather(*self.active_tasks, return_exceptions=True)
            self.active_tasks.clear()
    
    async def _display_results(self, output_file: Optional[Path]) -> None:
        """Display comprehensive test results."""
        summary = self.metrics.get_summary()
        
        # Create results table
        table = Table(title="Load Test Results", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", min_width=20)
        table.add_column("Value", style="green", min_width=15)
        
        # Add summary rows
        table.add_row("Duration", f"{summary['duration_seconds']:.2f}s")
        table.add_row("Total Requests", str(summary['total_requests']))
        table.add_row("Successful Requests", str(summary['successful_requests']))
        table.add_row("Failed Requests", str(summary['failed_requests']))
        table.add_row("Success Rate", f"{summary['success_rate']*100:.2f}%")
        table.add_row("Requests/Second", f"{summary['requests_per_second']:.2f}")
        table.add_row("Avg Response Time", f"{summary['avg_response_time_ms']:.2f}ms")
        table.add_row("Min Response Time", f"{summary['min_response_time_ms']:.2f}ms")
        table.add_row("Max Response Time", f"{summary['max_response_time_ms']:.2f}ms")
        
        # Add percentiles
        percentiles = summary['percentiles']
        if percentiles:
            for p, value in percentiles.items():
                table.add_row(f"Response Time {p.upper()}", f"{value:.2f}ms")
        
        self.console.print()
        self.console.print(table)
        
        # Status code distribution
        if summary['status_codes']:
            self.console.print()
            status_table = Table(title="Status Code Distribution", show_header=True, header_style="bold blue")
            status_table.add_column("Status Code", style="cyan")
            status_table.add_column("Count", style="green")
            status_table.add_column("Percentage", style="yellow")
            
            total = summary['total_requests']
            for code, count in sorted(summary['status_codes'].items()):
                percentage = count / total * 100 if total > 0 else 0
                color = "green" if 200 <= code < 300 else "yellow" if 400 <= code < 500 else "red"
                status_table.add_row(
                    f"[{color}]{code}[/{color}]",
                    str(count),
                    f"{percentage:.1f}%"
                )
            
            self.console.print(status_table)
        
        # Error types
        if summary['error_types']:
            self.console.print()
            error_table = Table(title="Error Distribution", show_header=True, header_style="bold red")
            error_table.add_column("Error Type", style="red")
            error_table.add_column("Count", style="yellow")
            
            for error_type, count in sorted(summary['error_types'].items(), key=lambda x: x[1], reverse=True):
                error_table.add_row(error_type, str(count))
            
            self.console.print(error_table)
        
        # Save results if requested
        if output_file:
            await self._save_results(output_file, summary)
    
    async def _save_results(self, output_file: Path, summary: Dict[str, Any]) -> None:
        """Save load test results to file."""
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump({
                    "load_test_results": summary,
                    "timestamp": time.time(),
                    "config": {
                        "concurrent_users": self.metrics.concurrent_users,
                        "total_requests": self.metrics.total_requests,
                    }
                }, f, indent=2)
            
            self.console.print(f"\n[green]Results saved to: {output_file}[/green]")
            
        except Exception as e:
            self.console.print(f"\n[red]Failed to save results: {e}[/red]")


async def run_load_test(
    target_url: str = "http://localhost:8000",
    requests: Optional[int] = None,
    concurrency: int = 10,
    duration: Optional[float] = None,
    ramp_up: float = 0.0,
    scenario: Optional[str] = None,
    output_file: Optional[Path] = None,
    config_profile: str = "default",
) -> LoadTestMetrics:
    """Main entry point for load testing command.
    
    Args:
        target_url: Target server URL for load testing
        requests: Number of requests to send
        concurrency: Number of concurrent users
        duration: Test duration in seconds
        ramp_up: Ramp-up time in seconds
        scenario: Specific scenario to run
        output_file: File to save results
        config_profile: Configuration profile to use
        
    Returns:
        Load test metrics
    """
    # Load configuration
    config = load_config(config_profile)
    
    # Create console for output
    console = Console()
    
    # Create and run load test
    runner = LoadTestRunner(config, console)
    
    return await runner.run_load_test(
        target_url=target_url,
        requests=requests,
        duration=duration,
        concurrency=concurrency,
        ramp_up=ramp_up,
        scenario_name=scenario,
        output_file=output_file,
    )