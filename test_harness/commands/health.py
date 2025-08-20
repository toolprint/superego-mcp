"""Health check command for monitoring Superego MCP Server status.

This module provides functionality for checking server health, including
watch mode for continuous monitoring and comprehensive health validation.
"""

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
import structlog

from ..client.superego_client import SuperegoTestClient, SuperegoClientError
from ..client.response_formatter import ResponseFormatter, TestResult, create_test_result
from ..config.loader import TestHarnessConfig, load_config

logger = structlog.get_logger(__name__)


class HealthMonitor:
    """Monitors health status of Superego MCP Server with various checks."""
    
    def __init__(self, client: SuperegoTestClient, console: Console):
        self.client = client
        self.console = console
        self.logger = logger.bind(component="health_monitor")
        self.health_history: List[Dict[str, Any]] = []
    
    async def basic_health_check(self) -> TestResult:
        """Perform basic health check against the server.
        
        Returns:
            TestResult containing health check results
        """
        self.logger.info("Performing basic health check")
        start_time = time.perf_counter()
        
        try:
            health_data = await self.client.check_health()
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Validate health response structure
            status = health_data.get('status', 'unknown')
            success = (status.lower() in ['healthy', 'ok', 'up', 'running'])
            
            result = create_test_result(
                success=success,
                response_data=health_data,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Basic Health Check",
                endpoint="/v1/health",
                method="GET",
                error_message=None if success else f"Unhealthy status: {status}",
                tags=["health", "basic"]
            )
            
            self.logger.info(
                "Basic health check completed",
                status=status,
                success=success,
                response_time_ms=round(response_time_ms, 2)
            )
            
            return result
            
        except SuperegoClientError as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            self.logger.error(
                "Basic health check failed",
                error=str(e),
                error_type=type(e).__name__
            )
            
            return create_test_result(
                success=False,
                response_time_ms=response_time_ms,
                test_name="Basic Health Check",
                endpoint="/v1/health",
                method="GET",
                error_message=str(e),
                error_type=type(e).__name__,
                tags=["health", "basic", "failed"]
            )
    
    async def detailed_health_check(self) -> List[TestResult]:
        """Perform comprehensive health checks including multiple endpoints.
        
        Returns:
            List of TestResult objects from various health checks
        """
        self.logger.info("Performing detailed health checks")
        results = []
        
        # Basic health check
        basic_result = await self.basic_health_check()
        results.append(basic_result)
        
        # Server info check
        try:
            start_time = time.perf_counter()
            server_info = await self.client.get_server_info()
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            results.append(create_test_result(
                success=True,
                response_data=server_info,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Server Info Check",
                endpoint="/v1/server-info",
                method="GET",
                tags=["health", "detailed", "server_info"]
            ))
            
        except SuperegoClientError as e:
            results.append(create_test_result(
                success=False,
                test_name="Server Info Check",
                endpoint="/v1/server-info",
                method="GET",
                error_message=str(e),
                error_type=type(e).__name__,
                tags=["health", "detailed", "server_info", "failed"]
            ))
        
        # Rules configuration check
        try:
            start_time = time.perf_counter()
            rules_config = await self.client.get_current_rules()
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            results.append(create_test_result(
                success=True,
                response_data=rules_config,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Rules Configuration Check",
                endpoint="/v1/config/rules",
                method="GET",
                tags=["health", "detailed", "rules"]
            ))
            
        except SuperegoClientError as e:
            results.append(create_test_result(
                success=False,
                test_name="Rules Configuration Check",
                endpoint="/v1/config/rules",
                method="GET",
                error_message=str(e),
                error_type=type(e).__name__,
                tags=["health", "detailed", "rules", "failed"]
            ))
        
        # Metrics check
        try:
            start_time = time.perf_counter()
            metrics = await self.client.get_metrics()
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            results.append(create_test_result(
                success=True,
                response_data=metrics,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Metrics Check",
                endpoint="/v1/metrics",
                method="GET",
                tags=["health", "detailed", "metrics"]
            ))
            
        except SuperegoClientError as e:
            results.append(create_test_result(
                success=False,
                test_name="Metrics Check",
                endpoint="/v1/metrics",
                method="GET",
                error_message=str(e),
                error_type=type(e).__name__,
                tags=["health", "detailed", "metrics", "failed"]
            ))
        
        # Test evaluation endpoint with simple request
        try:
            start_time = time.perf_counter()
            eval_result = await self.client.evaluate_tool(
                tool_name="health_check_test",
                parameters={"test": True},
                agent_id="health-monitor",
                session_id=f"health-{int(time.time())}"
            )
            response_time_ms = (time.perf_counter() - start_time) * 1000
            
            results.append(create_test_result(
                success=True,
                response_data=eval_result,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Evaluation Endpoint Check",
                endpoint="/v1/evaluate",
                method="POST",
                tags=["health", "detailed", "evaluation"]
            ))
            
        except SuperegoClientError as e:
            results.append(create_test_result(
                success=False,
                test_name="Evaluation Endpoint Check",
                endpoint="/v1/evaluate",
                method="POST",
                error_message=str(e),
                error_type=type(e).__name__,
                tags=["health", "detailed", "evaluation", "failed"]
            ))
        
        self.logger.info(
            "Detailed health checks completed",
            total_checks=len(results),
            passed_checks=sum(1 for r in results if r.success)
        )
        
        return results
    
    def create_health_summary(self, results: List[TestResult]) -> Dict[str, Any]:
        """Create a summary of health check results.
        
        Args:
            results: List of TestResult objects from health checks
            
        Returns:
            Health summary dictionary
        """
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        
        avg_response_time = sum(r.response_time_ms for r in results) / total if total > 0 else 0
        
        # Determine overall health status
        if failed == 0:
            overall_status = "healthy"
            status_color = "green"
        elif failed < total / 2:
            overall_status = "degraded"
            status_color = "yellow"
        else:
            overall_status = "unhealthy"
            status_color = "red"
        
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": overall_status,
            "status_color": status_color,
            "total_checks": total,
            "passed_checks": passed,
            "failed_checks": failed,
            "success_rate": (passed / total * 100) if total > 0 else 0,
            "average_response_time_ms": round(avg_response_time, 2),
            "check_details": [
                {
                    "name": r.test_name,
                    "success": r.success,
                    "response_time_ms": r.response_time_ms,
                    "error": r.error_message
                }
                for r in results
            ]
        }
        
        return summary
    
    def format_health_status(self, summary: Dict[str, Any]) -> Panel:
        """Format health status as a Rich panel.
        
        Args:
            summary: Health summary dictionary
            
        Returns:
            Rich Panel with formatted health status
        """
        status = summary["overall_status"]
        color = summary["status_color"]
        
        # Status header
        status_text = Text(f"Status: {status.upper()}", style=f"bold {color}")
        
        # Build content lines
        content_lines = [
            status_text,
            "",
            f"Checks: {summary['passed_checks']}/{summary['total_checks']} passed",
            f"Success Rate: {summary['success_rate']:.1f}%",
            f"Avg Response Time: {summary['average_response_time_ms']:.1f}ms",
            f"Last Updated: {datetime.now().strftime('%H:%M:%S')}"
        ]
        
        # Add failed checks if any
        failed_checks = [
            detail for detail in summary["check_details"]
            if not detail["success"]
        ]
        
        if failed_checks:
            content_lines.extend(["", "Failed Checks:"])
            for check in failed_checks:
                error_msg = check["error"] or "Unknown error"
                if len(error_msg) > 50:
                    error_msg = error_msg[:47] + "..."
                content_lines.append(f"  • {check['name']}: {error_msg}")
        
        text_lines: List[Text] = []
        for line in content_lines:
            if isinstance(line, str):
                text_lines.append(Text(line))
            elif isinstance(line, Text):
                text_lines.append(line)
        content = Text("\n").join(text_lines)
        
        return Panel(
            content,
            title="Superego MCP Server Health",
            border_style=color,
            padding=(1, 2)
        )
    
    def create_health_table(self, results: List[TestResult]) -> Table:
        """Create a health check results table.
        
        Args:
            results: List of TestResult objects
            
        Returns:
            Rich Table with health check details
        """
        table = Table(
            title="Health Check Details",
            show_header=True,
            header_style="bold magenta"
        )
        
        table.add_column("Check", style="cyan", min_width=20)
        table.add_column("Status", width=10)
        table.add_column("Response Time", width=15, justify="right")
        table.add_column("Endpoint", style="blue", min_width=15)
        table.add_column("Error", style="red", min_width=20)
        
        for result in results:
            # Status with color
            if result.success:
                status = "[green]✓ PASS[/green]"
            else:
                status = "[red]✗ FAIL[/red]"
            
            # Response time with color coding
            response_time = f"{result.response_time_ms:.1f}ms"
            if result.response_time_ms > 1000:
                response_time = f"[red]{response_time}[/red]"
            elif result.response_time_ms > 500:
                response_time = f"[yellow]{response_time}[/yellow]"
            else:
                response_time = f"[green]{response_time}[/green]"
            
            # Error message (truncated)
            error_msg = result.error_message or ""
            if len(error_msg) > 25:
                error_msg = error_msg[:22] + "..."
            
            table.add_row(
                result.test_name,
                status,
                response_time,
                result.endpoint,
                error_msg
            )
        
        return table


async def run_health_check(
    server_url: str = "http://localhost:8000",
    config_file: Optional[Path] = None,
    detailed: bool = False,
    watch: bool = False,
    interval: float = 5.0,
    output_format: str = "pretty",
    timeout: float = 30.0
) -> None:
    """Run health checks against Superego MCP Server.
    
    Args:
        server_url: URL of the Superego MCP Server
        config_file: Path to test harness configuration file
        detailed: Whether to perform detailed health checks
        watch: Whether to continuously monitor health
        interval: Watch interval in seconds
        output_format: Output format (pretty, table, json)
        timeout: Request timeout in seconds
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
        
        # Override server URL if provided
        if server_url != "http://localhost:8000":
            config.server.base_url = server_url
        
        # Override timeout if provided
        if timeout != 30.0:
            config.client.timeout = int(timeout)
        
        formatter = ResponseFormatter(console)
        
        async with SuperegoTestClient(config) as client:
            monitor = HealthMonitor(client, console)
            
            if watch:
                # Continuous monitoring mode
                console.print(f"[cyan]Starting health monitoring (interval: {interval}s, press Ctrl+C to stop)...[/cyan]")
                console.print()
                
                try:
                    with Live(console=console, refresh_per_second=1) as live:
                        while True:
                            if detailed:
                                results = await monitor.detailed_health_check()
                            else:
                                results = [await monitor.basic_health_check()]
                            
                            summary = monitor.create_health_summary(results)
                            monitor.health_history.append(summary)
                            
                            # Keep only last 100 entries
                            if len(monitor.health_history) > 100:
                                monitor.health_history.pop(0)
                            
                            if output_format == "table" and detailed:
                                display_content: Union[Table, Panel] = monitor.create_health_table(results)
                            else:
                                display_content = monitor.format_health_status(summary)
                            
                            live.update(display_content)
                            
                            await asyncio.sleep(interval)
                            
                except KeyboardInterrupt:
                    console.print("\n[yellow]Health monitoring stopped by user[/yellow]")
                    
                    # Show final summary if we have history
                    if monitor.health_history:
                        recent_summaries = monitor.health_history[-10:]  # Last 10 checks
                        avg_success_rate = sum(s["success_rate"] for s in recent_summaries) / len(recent_summaries)
                        avg_response_time = sum(s["average_response_time_ms"] for s in recent_summaries) / len(recent_summaries)
                        
                        final_summary = Panel(
                            f"Monitoring Summary:\n"
                            f"Total Checks: {len(monitor.health_history)}\n"
                            f"Recent Avg Success Rate: {avg_success_rate:.1f}%\n"
                            f"Recent Avg Response Time: {avg_response_time:.1f}ms",
                            title="Final Health Summary",
                            border_style="blue"
                        )
                        console.print(final_summary)
            else:
                # Single health check
                if detailed:
                    console.print("[cyan]Performing detailed health checks...[/cyan]")
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        TimeElapsedColumn(),
                        console=console
                    ) as progress:
                        task = progress.add_task("Running health checks...", total=None)
                        results = await monitor.detailed_health_check()
                        progress.update(task, completed=True)
                else:
                    console.print("[cyan]Performing basic health check...[/cyan]")
                    results = [await monitor.basic_health_check()]
                
                # Display results
                console.print()
                
                if output_format == "pretty":
                    summary = monitor.create_health_summary(results)
                    console.print(monitor.format_health_status(summary))
                    
                    if detailed:
                        console.print()
                        console.print(monitor.create_health_table(results))
                        
                elif output_format == "table":
                    console.print(monitor.create_health_table(results))
                    
                elif output_format == "json":
                    json_output = formatter.format_json(results)
                    console.print(json_output)
                    
                else:
                    console.print(f"[red]Unknown output format: {output_format}[/red]")
                    return
                
                # Display summary for non-pretty formats
                if output_format != "pretty":
                    summary = monitor.create_health_summary(results)
                    status_style = summary["status_color"]
                    status_text = f"Overall Status: {summary['overall_status'].upper()}"
                    
                    summary_panel = Panel(
                        Text(status_text, style=f"bold {status_style}"),
                        border_style=status_style,
                        padding=(0, 1)
                    )
                    console.print()
                    console.print(summary_panel)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Health check interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        logger.error("Health check failed", error=str(e), error_type=type(e).__name__)
        raise