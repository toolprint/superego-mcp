"""Response formatting utilities for test harness results.

This module provides structured data models and formatting utilities for
displaying test results in various formats using Rich console integration.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich import box
from rich.syntax import Syntax


@dataclass
class TestResult:
    """Test result data structure with comprehensive metadata.
    
    This dataclass captures all relevant information about a test execution
    including timing, response data, status codes, and error information.
    """
    
    # Core result data
    success: bool
    response_data: Optional[Dict[str, Any]] = None
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    
    # Test metadata
    test_name: str = ""
    endpoint: str = ""
    method: str = "GET"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Request information
    request_data: Optional[Dict[str, Any]] = None
    request_headers: Optional[Dict[str, str]] = None
    
    # Error information
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # Performance metrics
    connection_time_ms: Optional[float] = None
    dns_time_ms: Optional[float] = None
    ssl_time_ms: Optional[float] = None
    
    # Validation results
    schema_valid: Optional[bool] = None
    validation_errors: List[str] = field(default_factory=list)
    
    # Additional context
    agent_id: str = ""
    session_id: str = ""
    retry_count: int = 0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert TestResult to dictionary format.
        
        Returns:
            Dictionary representation of the test result
        """
        return {
            "success": self.success,
            "response_data": self.response_data,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "test_name": self.test_name,
            "endpoint": self.endpoint,
            "method": self.method,
            "timestamp": self.timestamp.isoformat(),
            "request_data": self.request_data,
            "request_headers": self.request_headers,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "stack_trace": self.stack_trace,
            "connection_time_ms": self.connection_time_ms,
            "dns_time_ms": self.dns_time_ms,
            "ssl_time_ms": self.ssl_time_ms,
            "schema_valid": self.schema_valid,
            "validation_errors": self.validation_errors,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "retry_count": self.retry_count,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestResult":
        """Create TestResult from dictionary.
        
        Args:
            data: Dictionary containing test result data
            
        Returns:
            TestResult instance
        """
        # Handle timestamp parsing
        timestamp_str = data.get("timestamp")
        if isinstance(timestamp_str, str):
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            timestamp = datetime.now(timezone.utc)
        
        return cls(
            success=data.get("success", False),
            response_data=data.get("response_data"),
            status_code=data.get("status_code"),
            response_time_ms=data.get("response_time_ms", 0.0),
            test_name=data.get("test_name", ""),
            endpoint=data.get("endpoint", ""),
            method=data.get("method", "GET"),
            timestamp=timestamp,
            request_data=data.get("request_data"),
            request_headers=data.get("request_headers"),
            error_message=data.get("error_message"),
            error_type=data.get("error_type"),
            stack_trace=data.get("stack_trace"),
            connection_time_ms=data.get("connection_time_ms"),
            dns_time_ms=data.get("dns_time_ms"),
            ssl_time_ms=data.get("ssl_time_ms"),
            schema_valid=data.get("schema_valid"),
            validation_errors=data.get("validation_errors", []),
            agent_id=data.get("agent_id", ""),
            session_id=data.get("session_id", ""),
            retry_count=data.get("retry_count", 0),
            tags=data.get("tags", []),
        )
    
    def get_summary(self) -> str:
        """Get a brief summary of the test result.
        
        Returns:
            Summary string describing the test outcome
        """
        status = "PASS" if self.success else "FAIL"
        timing = f"{self.response_time_ms:.1f}ms"
        
        if self.test_name:
            return f"{status}: {self.test_name} ({timing})"
        else:
            return f"{status}: {self.method} {self.endpoint} ({timing})"


class ResponseFormatter:
    """Rich console formatter for test results and response data.
    
    This class provides multiple output formats for displaying test results
    using Rich console features including tables, JSON syntax highlighting,
    and pretty-printed formats.
    """
    
    def __init__(self, console: Optional[Console] = None, colors: bool = True):
        """Initialize the response formatter.
        
        Args:
            console: Rich console instance (creates new one if None)
            colors: Whether to enable colored output
        """
        self.console = console or Console(color_system="auto" if colors else None)
        self.colors = colors
    
    def format_pretty(self, result: TestResult) -> None:
        """Format test result in a pretty, human-readable format.
        
        Args:
            result: Test result to format
        """
        # Create status indicator
        if result.success:
            status_text = Text("✓ PASS", style="bold green")
            panel_style = "green"
        else:
            status_text = Text("✗ FAIL", style="bold red")
            panel_style = "red"
        
        # Build main content
        content = []
        
        # Test information
        if result.test_name:
            content.append(Text(f"Test: {result.test_name}", style="bold"))
        
        content.append(Text(f"Endpoint: {result.method} {result.endpoint}"))
        content.append(Text(f"Response Time: {result.response_time_ms:.1f}ms"))
        
        if result.status_code:
            status_style = "green" if 200 <= result.status_code < 300 else "red"
            content.append(Text(f"Status Code: {result.status_code}", style=status_style))
        
        if result.agent_id:
            content.append(Text(f"Agent ID: {result.agent_id}"))
        
        if result.session_id:
            content.append(Text(f"Session ID: {result.session_id}"))
        
        # Add error information if failed
        if not result.success and result.error_message:
            content.append(Text(""))  # Empty line
            content.append(Text("Error:", style="bold red"))
            content.append(Text(result.error_message, style="red"))
            
            if result.error_type:
                content.append(Text(f"Error Type: {result.error_type}", style="dim"))
        
        # Add validation errors if any
        if result.validation_errors:
            content.append(Text(""))  # Empty line
            content.append(Text("Validation Errors:", style="bold yellow"))
            for error in result.validation_errors:
                content.append(Text(f"  • {error}", style="yellow"))
        
        # Create main panel
        main_panel = Panel(
            Text("\n").join(content),
            title=status_text,
            border_style=panel_style,
            padding=(1, 2)
        )
        
        self.console.print(main_panel)
        
        # Show response data if available
        if result.response_data:
            self.console.print()
            response_json = JSON.from_data(result.response_data, indent=2)
            response_panel = Panel(
                response_json,
                title="Response Data",
                border_style="blue",
                padding=(1, 2)
            )
            self.console.print(response_panel)
    
    def format_json(self, result: Union[TestResult, List[TestResult]]) -> str:
        """Format test result(s) as JSON.
        
        Args:
            result: Single test result or list of results
            
        Returns:
            JSON string representation
        """
        if isinstance(result, list):
            data: Union[Dict[str, Any], List[Dict[str, Any]]] = [r.to_dict() for r in result]
        else:
            data = result.to_dict()
        
        return json.dumps(data, indent=2, default=str)
    
    def format_table(self, results: List[TestResult]) -> None:
        """Format test results as a Rich table.
        
        Args:
            results: List of test results to display
        """
        if not results:
            self.console.print("No test results to display.", style="dim")
            return
        
        table = Table(
            title="Test Results Summary",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        
        # Add columns
        table.add_column("Status", style="bold", width=8)
        table.add_column("Test Name", style="cyan", min_width=20)
        table.add_column("Endpoint", style="blue", min_width=15)
        table.add_column("Method", width=8)
        table.add_column("Status Code", width=12, justify="center")
        table.add_column("Response Time", width=14, justify="right")
        table.add_column("Errors", style="red", min_width=15)
        
        # Add rows
        for result in results:
            # Status
            if result.success:
                status = "[green]✓ PASS[/green]"
            else:
                status = "[red]✗ FAIL[/red]"
            
            # Test name (truncate if too long)
            test_name = result.test_name or "Unnamed Test"
            if len(test_name) > 25:
                test_name = test_name[:22] + "..."
            
            # Endpoint (truncate if too long)
            endpoint = result.endpoint
            if len(endpoint) > 20:
                endpoint = "..." + endpoint[-17:]
            
            # Status code with color
            if result.status_code:
                if 200 <= result.status_code < 300:
                    status_code = f"[green]{result.status_code}[/green]"
                elif 400 <= result.status_code < 500:
                    status_code = f"[yellow]{result.status_code}[/yellow]"
                else:
                    status_code = f"[red]{result.status_code}[/red]"
            else:
                status_code = "[dim]N/A[/dim]"
            
            # Response time with color coding
            response_time = f"{result.response_time_ms:.1f}ms"
            if result.response_time_ms > 1000:
                response_time = f"[red]{response_time}[/red]"
            elif result.response_time_ms > 500:
                response_time = f"[yellow]{response_time}[/yellow]"
            else:
                response_time = f"[green]{response_time}[/green]"
            
            # Error summary
            error_summary = ""
            if result.error_message:
                error_summary = result.error_message
                if len(error_summary) > 20:
                    error_summary = error_summary[:17] + "..."
            elif result.validation_errors:
                error_count = len(result.validation_errors)
                error_summary = f"{error_count} validation error(s)"
            
            table.add_row(
                status,
                test_name,
                endpoint,
                result.method,
                status_code,
                response_time,
                error_summary
            )
        
        self.console.print(table)
        
        # Print summary statistics
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        avg_time = sum(r.response_time_ms for r in results) / total if total > 0 else 0
        
        summary_text = [
            f"Total Tests: [bold]{total}[/bold]",
            f"Passed: [green]{passed}[/green]",
            f"Failed: [red]{failed}[/red]",
            f"Average Response Time: [cyan]{avg_time:.1f}ms[/cyan]"
        ]
        
        self.console.print()
        self.console.print(" | ".join(summary_text))
    
    def format_tree(self, results: List[TestResult], group_by: str = "endpoint") -> None:
        """Format test results as a tree structure grouped by specified field.
        
        Args:
            results: List of test results to display
            group_by: Field to group results by ('endpoint', 'agent_id', 'status', etc.)
        """
        if not results:
            self.console.print("No test results to display.", style="dim")
            return
        
        # Group results
        groups: Dict[str, List[TestResult]] = {}
        for result in results:
            key = getattr(result, group_by, "Unknown")
            if key not in groups:
                groups[key] = []
            groups[key].append(result)
        
        # Create tree
        tree = Tree(f"Test Results (grouped by {group_by})")
        
        for group_key, group_results in groups.items():
            # Calculate group statistics
            group_passed = sum(1 for r in group_results if r.success)
            group_total = len(group_results)
            group_avg_time = sum(r.response_time_ms for r in group_results) / group_total
            
            # Style group node based on success rate
            if group_passed == group_total:
                group_style = "green"
            elif group_passed == 0:
                group_style = "red"
            else:
                group_style = "yellow"
            
            group_node = tree.add(
                f"[{group_style}]{group_key}[/{group_style}] "
                f"({group_passed}/{group_total} passed, avg: {group_avg_time:.1f}ms)"
            )
            
            # Add individual test results
            for result in group_results:
                status_icon = "✓" if result.success else "✗"
                status_style = "green" if result.success else "red"
                
                test_label = result.test_name or f"{result.method} {result.endpoint}"
                result_text = (
                    f"[{status_style}]{status_icon}[/{status_style}] "
                    f"{test_label} "
                    f"({result.response_time_ms:.1f}ms)"
                )
                
                if result.error_message:
                    result_text += f" - [red]{result.error_message}[/red]"
                
                group_node.add(result_text)
        
        self.console.print(tree)
    
    def format_summary(self, results: List[TestResult]) -> None:
        """Format a comprehensive summary of test results.
        
        Args:
            results: List of test results to summarize
        """
        if not results:
            self.console.print("No test results to summarize.", style="dim")
            return
        
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        
        # Calculate statistics
        response_times = [r.response_time_ms for r in results]
        avg_time = sum(response_times) / total
        min_time = min(response_times)
        max_time = max(response_times)
        
        # Count by status code
        status_codes: Dict[int, int] = {}
        for result in results:
            if result.status_code:
                status_codes[result.status_code] = status_codes.get(result.status_code, 0) + 1
        
        # Count by endpoint
        endpoints: Dict[str, int] = {}
        for result in results:
            endpoint = result.endpoint or "Unknown"
            endpoints[endpoint] = endpoints.get(endpoint, 0) + 1
        
        # Create summary panel
        summary_lines = [
            f"[bold]Test Execution Summary[/bold]",
            "",
            f"Total Tests: [bold]{total}[/bold]",
            f"Passed: [green]{passed}[/green] ({passed/total*100:.1f}%)",
            f"Failed: [red]{failed}[/red] ({failed/total*100:.1f}%)",
            "",
            f"[bold]Response Time Statistics[/bold]",
            f"Average: [cyan]{avg_time:.1f}ms[/cyan]",
            f"Minimum: [green]{min_time:.1f}ms[/green]",
            f"Maximum: [red]{max_time:.1f}ms[/red]",
        ]
        
        if status_codes:
            summary_lines.extend(["", "[bold]Status Code Distribution[/bold]"])
            for code, count in sorted(status_codes.items()):
                color = "green" if 200 <= code < 300 else "yellow" if 400 <= code < 500 else "red"
                summary_lines.append(f"  {code}: [{color}]{count}[/{color}] tests")
        
        if len(endpoints) > 1:
            summary_lines.extend(["", "[bold]Endpoint Coverage[/bold]"])
            for endpoint, count in sorted(endpoints.items(), key=lambda x: x[1], reverse=True):
                summary_lines.append(f"  {endpoint}: {count} tests")
        
        # Add error summary for failed tests
        if failed > 0:
            error_types: Dict[str, int] = {}
            for result in results:
                if not result.success and result.error_type:
                    error_types[result.error_type] = error_types.get(result.error_type, 0) + 1
            
            if error_types:
                summary_lines.extend(["", "[bold red]Error Types[/bold red]"])
                for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                    summary_lines.append(f"  [red]{error_type}[/red]: {count} occurrences")
        
        summary_panel = Panel(
            "\n".join(summary_lines),
            title="Test Summary",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(summary_panel)


def create_test_result(
    success: bool,
    response_data: Optional[Dict[str, Any]] = None,
    status_code: Optional[int] = None,
    response_time_ms: float = 0.0,
    test_name: str = "",
    endpoint: str = "",
    method: str = "GET",
    error_message: Optional[str] = None,
    **kwargs: Any
) -> TestResult:
    """Convenience function to create a TestResult instance.
    
    Args:
        success: Whether the test passed
        response_data: Response data from server
        status_code: HTTP status code
        response_time_ms: Response time in milliseconds
        test_name: Name/description of the test
        endpoint: API endpoint tested
        method: HTTP method used
        error_message: Error message if test failed
        **kwargs: Additional fields for TestResult
        
    Returns:
        TestResult instance
    """
    return TestResult(
        success=success,
        response_data=response_data,
        status_code=status_code,
        response_time_ms=response_time_ms,
        test_name=test_name,
        endpoint=endpoint,
        method=method,
        error_message=error_message,
        **kwargs
    )