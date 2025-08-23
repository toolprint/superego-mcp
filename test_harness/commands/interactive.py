"""Interactive testing command module for the Superego MCP Test Harness.

This module provides a rich interactive interface for real-time testing,
exploration, and debugging of the Superego MCP Server with menu-driven
navigation and live feedback.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.json import JSON

from ..client.response_formatter import ResponseFormatter, TestResult, create_test_result
from ..client.superego_client import SuperegoTestClient, SuperegoClientError
from ..config.loader import TestHarnessConfig, load_config

logger = structlog.get_logger(__name__)


class InteractiveSession:
    """Interactive testing session manager."""
    
    def __init__(self, config: TestHarnessConfig, console: Optional[Console] = None):
        """Initialize interactive session.
        
        Args:
            config: Test harness configuration
            console: Rich console for output
        """
        self.config = config
        self.console = console or Console()
        self.formatter = ResponseFormatter(self.console)
        self.session_history: List[TestResult] = []
        self.current_session_id = "interactive-session"
        self.current_agent_id = "interactive-agent"
        self.auto_approve = False
        
        # Menu system state
        self.running = True
        self.client: Optional[SuperegoTestClient] = None
        
    async def start_session(
        self,
        server_url: str,
        auto_approve: bool = False,
        log_level: str = "info",
    ) -> None:
        """Start the interactive testing session.
        
        Args:
            server_url: Superego MCP Server URL
            auto_approve: Automatically approve safe requests
            log_level: Logging level for the session
        """
        self.auto_approve = auto_approve
        
        # Update config with server URL
        session_config = self.config.model_copy()
        session_config.server.base_url = server_url
        
        # Display welcome banner
        self._display_welcome_banner(server_url)
        
        # Initialize client
        self.client = SuperegoTestClient(session_config)
        
        try:
            async with self.client:
                # Test connection
                await self._test_connection()
                
                # Main interactive loop
                await self._main_menu_loop()
        
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Session interrupted by user[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Session error: {e}[/red]")
            logger.error("Interactive session error", error=str(e))
        finally:
            self._display_session_summary()
    
    def _display_welcome_banner(self, server_url: str) -> None:
        """Display welcome banner and session information."""
        banner_text = [
            "[bold cyan]Superego MCP Test Harness - Interactive Mode[/bold cyan]",
            "",
            f"Server URL: [green]{server_url}[/green]",
            f"Session ID: [blue]{self.current_session_id}[/blue]",
            f"Agent ID: [yellow]{self.current_agent_id}[/yellow]",
            f"Auto-approve: [{'green' if self.auto_approve else 'red'}]{self.auto_approve}[/{'green' if self.auto_approve else 'red'}]",
            "",
            "[dim]Type 'help' or 'h' for available commands[/dim]",
            "[dim]Type 'quit' or 'q' to exit[/dim]",
        ]
        
        self.console.print(Panel(
            "\n".join(banner_text),
            title="Welcome to Interactive Testing",
            border_style="blue",
            padding=(1, 2)
        ))
    
    async def _test_connection(self) -> None:
        """Test initial connection to the server."""
        assert self.client is not None, "Client should be initialized"
        
        self.console.print("[dim]Testing server connection...[/dim]")
        
        try:
            health_data = await self.client.check_health(timeout=10.0)
            
            self.console.print("[green]✓ Successfully connected to server[/green]")
            
            # Display server info
            if health_data:
                info_table = Table(show_header=False, box=None)
                info_table.add_column("Property", style="cyan")
                info_table.add_column("Value", style="green")
                
                for key, value in health_data.items():
                    if isinstance(value, (str, int, float, bool)):
                        info_table.add_row(key.replace("_", " ").title(), str(value))
                
                self.console.print(Panel(info_table, title="Server Information", border_style="green"))
        
        except Exception as e:
            self.console.print(f"[red]✗ Failed to connect to server: {e}[/red]")
            self.console.print("[yellow]Continuing in offline mode for demonstration[/yellow]")
    
    async def _main_menu_loop(self) -> None:
        """Main interactive menu loop."""
        while self.running:
            self.console.print()
            choice = Prompt.ask(
                "[bold cyan]Enter command[/bold cyan]",
                default="help",
                show_default=False
            ).strip().lower()
            
            if choice in ['quit', 'q', 'exit']:
                break
            elif choice in ['help', 'h', '?']:
                self._display_help()
            elif choice in ['status', 's']:
                await self._show_status()
            elif choice in ['eval', 'evaluate', '1']:
                await self._evaluate_tool_menu()
            elif choice in ['hook', 'hooks', '2']:
                await self._test_hook_menu()
            elif choice in ['health', '3']:
                await self._health_check_menu()
            elif choice in ['history', 'hist', '4']:
                self._show_history()
            elif choice in ['config', 'cfg', '5']:
                await self._config_menu()
            elif choice in ['scenario', 'scenarios', '6']:
                await self._scenario_menu()
            elif choice in ['monitor', 'live', '7']:
                await self._live_monitor_menu()
            elif choice in ['clear', 'cls']:
                self.console.clear()
            else:
                self.console.print(f"[red]Unknown command: {choice}[/red]")
                self.console.print("[dim]Type 'help' for available commands[/dim]")
    
    def _display_help(self) -> None:
        """Display help menu."""
        help_table = Table(title="Available Commands", show_header=True, header_style="bold magenta")
        help_table.add_column("Command", style="cyan", min_width=15)
        help_table.add_column("Aliases", style="blue", min_width=10)
        help_table.add_column("Description", style="white")
        
        commands = [
            ("evaluate", "eval, 1", "Test tool evaluation requests"),
            ("hooks", "hook, 2", "Test Claude Code hooks"),
            ("health", "3", "Check server health status"),
            ("history", "hist, 4", "View session history"),
            ("config", "cfg, 5", "View/modify configuration"),
            ("scenario", "scenarios, 6", "Run predefined scenarios"),
            ("monitor", "live, 7", "Live monitoring dashboard"),
            ("status", "s", "Show current session status"),
            ("clear", "cls", "Clear the screen"),
            ("help", "h, ?", "Show this help message"),
            ("quit", "q, exit", "Exit interactive mode"),
        ]
        
        for cmd, aliases, desc in commands:
            help_table.add_row(cmd, aliases, desc)
        
        self.console.print(help_table)
    
    async def _show_status(self) -> None:
        """Display current session status."""
        status_table = Table(title="Session Status", show_header=False, box=None)
        status_table.add_column("Property", style="cyan", min_width=20)
        status_table.add_column("Value", style="green")
        
        status_table.add_row("Server URL", self.config.server.base_url)
        status_table.add_row("Session ID", self.current_session_id)
        status_table.add_row("Agent ID", self.current_agent_id)
        status_table.add_row("Auto-approve", str(self.auto_approve))
        status_table.add_row("Requests sent", str(len(self.session_history)))
        
        # Calculate success statistics
        if self.session_history:
            successful = sum(1 for r in self.session_history if r.success)
            success_rate = successful / len(self.session_history) * 100
            avg_time = sum(r.response_time_ms for r in self.session_history) / len(self.session_history)
            
            status_table.add_row("Success rate", f"{success_rate:.1f}%")
            status_table.add_row("Avg response time", f"{avg_time:.1f}ms")
        
        self.console.print(status_table)
    
    async def _evaluate_tool_menu(self) -> None:
        """Tool evaluation submenu."""
        self.console.print(Panel("Tool Evaluation Testing", style="cyan"))
        
        # Get tool information
        tool_name = Prompt.ask("Tool name", default="TestTool")
        
        # Get parameters (JSON input)
        self.console.print("[dim]Enter tool parameters as JSON (or press Enter for empty object):[/dim]")
        params_input = Prompt.ask("Parameters", default="{}")
        
        try:
            parameters = json.loads(params_input)
        except json.JSONDecodeError:
            self.console.print("[red]Invalid JSON format[/red]")
            return
        
        # Optional agent/session ID override
        if Confirm.ask("Use custom agent/session IDs?", default=False):
            agent_id = Prompt.ask("Agent ID", default=self.current_agent_id)
            session_id = Prompt.ask("Session ID", default=self.current_session_id)
        else:
            agent_id = self.current_agent_id
            session_id = self.current_session_id
        
        # Execute request
        await self._execute_tool_evaluation(tool_name, parameters, agent_id, session_id)
    
    async def _execute_tool_evaluation(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        agent_id: str,
        session_id: str,
    ) -> None:
        """Execute a tool evaluation request."""
        assert self.client is not None, "Client should be initialized"
        
        self.console.print(f"[dim]Evaluating tool: {tool_name}...[/dim]")
        
        start_time = time_start = asyncio.get_event_loop().time()
        
        try:
            result_data = await self.client.evaluate_tool(
                tool_name=tool_name,
                parameters=parameters,
                agent_id=agent_id,
                session_id=session_id
            )
            
            response_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Create test result
            result = create_test_result(
                success=True,
                response_data=result_data,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name=f"Tool Evaluation: {tool_name}",
                endpoint="/v1/evaluate",
                method="POST",
                agent_id=agent_id,
                session_id=session_id,
                request_data={
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "agent_id": agent_id,
                    "session_id": session_id
                }
            )
            
        except SuperegoClientError as e:
            response_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            result = create_test_result(
                success=False,
                response_time_ms=response_time_ms,
                test_name=f"Tool Evaluation: {tool_name}",
                endpoint="/v1/evaluate",
                method="POST",
                error_message=str(e),
                error_type=type(e).__name__,
                agent_id=agent_id,
                session_id=session_id
            )
        
        # Store in history
        self.session_history.append(result)
        
        # Display result
        self.formatter.format_pretty(result)
        
        # Ask if user wants to see details
        if result.success and Confirm.ask("Show detailed response?", default=False):
            self._show_detailed_response(result)
    
    async def _test_hook_menu(self) -> None:
        """Claude Code hook testing submenu."""
        self.console.print(Panel("Claude Code Hook Testing", style="magenta"))
        
        # Get hook information
        event_name = Prompt.ask(
            "Event name",
            default="PreToolUse",
            choices=["PreToolUse", "PostToolUse", "PreRequest", "PostRequest"]
        )
        
        tool_name = Prompt.ask("Tool name", default="TestTool")
        
        # Get arguments (JSON input)
        self.console.print("[dim]Enter tool arguments as JSON (or press Enter for empty object):[/dim]")
        args_input = Prompt.ask("Arguments", default="{}")
        
        try:
            arguments = json.loads(args_input)
        except json.JSONDecodeError:
            self.console.print("[red]Invalid JSON format[/red]")
            return
        
        # Execute request
        await self._execute_hook_test(event_name, tool_name, arguments)
    
    async def _execute_hook_test(
        self,
        event_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> None:
        """Execute a hook test request."""
        assert self.client is not None, "Client should be initialized"
        
        self.console.print(f"[dim]Testing hook: {event_name} for {tool_name}...[/dim]")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            result_data = await self.client.test_claude_hook(
                event_name=event_name,
                tool_name=tool_name,
                arguments=arguments,
                agent_id=self.current_agent_id,
                session_id=self.current_session_id
            )
            
            response_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            result = create_test_result(
                success=True,
                response_data=result_data,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name=f"Hook Test: {event_name}",
                endpoint="/v1/hooks",
                method="POST",
                agent_id=self.current_agent_id,
                session_id=self.current_session_id
            )
            
        except SuperegoClientError as e:
            response_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            result = create_test_result(
                success=False,
                response_time_ms=response_time_ms,
                test_name=f"Hook Test: {event_name}",
                endpoint="/v1/hooks",
                method="POST",
                error_message=str(e),
                error_type=type(e).__name__,
                agent_id=self.current_agent_id,
                session_id=self.current_session_id
            )
        
        # Store in history
        self.session_history.append(result)
        
        # Display result
        self.formatter.format_pretty(result)
    
    async def _health_check_menu(self) -> None:
        """Health check submenu."""
        assert self.client is not None, "Client should be initialized"
        
        self.console.print("[dim]Checking server health...[/dim]")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            health_data = await self.client.check_health()
            response_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            result = create_test_result(
                success=True,
                response_data=health_data,
                status_code=200,
                response_time_ms=response_time_ms,
                test_name="Health Check",
                endpoint="/v1/health",
                method="GET"
            )
            
        except SuperegoClientError as e:
            response_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            result = create_test_result(
                success=False,
                response_time_ms=response_time_ms,
                test_name="Health Check",
                endpoint="/v1/health",
                method="GET",
                error_message=str(e),
                error_type=type(e).__name__
            )
        
        # Store in history
        self.session_history.append(result)
        
        # Display result
        self.formatter.format_pretty(result)
        
        # Show additional server info if available
        if result.success and result.response_data:
            if Confirm.ask("Fetch additional server information?", default=True):
                await self._fetch_server_info()
    
    async def _fetch_server_info(self) -> None:
        """Fetch additional server information."""
        assert self.client is not None, "Client should be initialized"
        
        info_tasks = [
            ("Server Info", self.client.get_server_info),
            ("Current Rules", self.client.get_current_rules),
            ("Metrics", self.client.get_metrics),
            ("Audit Entries", self.client.get_audit_entries),
        ]
        
        for name, func in info_tasks:
            try:
                self.console.print(f"[dim]Fetching {name.lower()}...[/dim]")
                data = await func()
                
                if data:
                    self.console.print(f"\n[bold]{name}:[/bold]")
                    self.console.print(JSON.from_data(data, indent=2))
                
            except Exception as e:
                self.console.print(f"[yellow]Could not fetch {name.lower()}: {e}[/yellow]")
    
    def _show_history(self) -> None:
        """Display session history."""
        if not self.session_history:
            self.console.print("[dim]No requests in session history[/dim]")
            return
        
        # Display summary table
        self.formatter.format_table(self.session_history)
        
        # Offer detailed view
        if Confirm.ask("\nView detailed history?", default=False):
            for i, result in enumerate(self.session_history, 1):
                self.console.print(f"\n[bold cyan]Request {i}:[/bold cyan]")
                self.formatter.format_pretty(result)
                
                if i < len(self.session_history):
                    if not Confirm.ask("Continue to next request?", default=True):
                        break
    
    async def _config_menu(self) -> None:
        """Configuration management submenu."""
        self.console.print(Panel("Configuration Management", style="blue"))
        
        config_options = [
            ("1", "View current configuration"),
            ("2", "Modify session settings"),
            ("3", "View server configuration"),
            ("4", "Test connection settings"),
        ]
        
        for key, desc in config_options:
            self.console.print(f"[cyan]{key}[/cyan]. {desc}")
        
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "4"], default="1")
        
        if choice == "1":
            self._show_current_config()
        elif choice == "2":
            await self._modify_session_settings()
        elif choice == "3":
            await self._show_server_config()
        elif choice == "4":
            await self._test_connection_settings()
    
    def _show_current_config(self) -> None:
        """Show current configuration."""
        config_data = {
            "server": {
                "base_url": self.config.server.base_url,
                "timeout": self.config.server.timeout,
                "max_retries": self.config.server.max_retries,
            },
            "session": {
                "agent_id": self.current_agent_id,
                "session_id": self.current_session_id,
                "auto_approve": self.auto_approve,
            },
            "client": {
                "pool_size": self.config.client.pool_size,
                "verify_ssl": self.config.client.verify_ssl,
                "http2": self.config.client.http2,
            }
        }
        
        self.console.print(JSON.from_data(config_data, indent=2))
    
    async def _modify_session_settings(self) -> None:
        """Modify session settings."""
        self.console.print("[bold]Current Settings:[/bold]")
        self.console.print(f"Agent ID: [yellow]{self.current_agent_id}[/yellow]")
        self.console.print(f"Session ID: [yellow]{self.current_session_id}[/yellow]")
        self.console.print(f"Auto-approve: [yellow]{self.auto_approve}[/yellow]")
        
        if Confirm.ask("Modify agent ID?", default=False):
            self.current_agent_id = Prompt.ask("New agent ID", default=self.current_agent_id)
        
        if Confirm.ask("Modify session ID?", default=False):
            self.current_session_id = Prompt.ask("New session ID", default=self.current_session_id)
        
        if Confirm.ask("Toggle auto-approve?", default=False):
            self.auto_approve = not self.auto_approve
        
        self.console.print("[green]Settings updated[/green]")
    
    async def _show_server_config(self) -> None:
        """Show server configuration."""
        assert self.client is not None, "Client should be initialized"
        
        try:
            server_info = await self.client.get_server_info()
            self.console.print(JSON.from_data(server_info, indent=2))
        except Exception as e:
            self.console.print(f"[red]Could not fetch server configuration: {e}[/red]")
    
    async def _test_connection_settings(self) -> None:
        """Test connection settings."""
        await self._test_connection()
    
    async def _scenario_menu(self) -> None:
        """Scenario testing submenu."""
        self.console.print(Panel("Scenario Testing", style="green"))
        
        # Load available scenarios
        scenarios = await self._load_available_scenarios()
        
        if not scenarios:
            self.console.print("[yellow]No scenarios available[/yellow]")
            return
        
        # Display scenarios
        scenario_table = Table(title="Available Scenarios", show_header=True)
        scenario_table.add_column("ID", style="cyan")
        scenario_table.add_column("Name", style="green")
        scenario_table.add_column("Description", style="white")
        
        for i, scenario in enumerate(scenarios, 1):
            scenario_table.add_row(
                str(i),
                scenario.get("name", "Unnamed"),
                scenario.get("description", "No description")[:50] + "..."
            )
        
        self.console.print(scenario_table)
        
        # Select scenario
        max_choice = len(scenarios)
        choice = IntPrompt.ask(
            "Select scenario to run",
            choices=[str(i) for i in range(1, max_choice + 1)]
        )
        
        selected_scenario = scenarios[choice - 1]
        await self._run_scenario(selected_scenario)
    
    async def _load_available_scenarios(self) -> List[Dict[str, Any]]:
        """Load available test scenarios."""
        # In a real implementation, this would load from scenario files
        # For now, return some predefined scenarios
        return [
            {
                "id": "basic_health",
                "name": "Basic Health Check",
                "description": "Simple server health verification",
                "type": "health_check"
            },
            {
                "id": "tool_eval_safe",
                "name": "Safe Tool Evaluation",
                "description": "Test evaluation of safe tools",
                "type": "tool_evaluation",
                "tool_name": "Read",
                "parameters": {"file_path": "/tmp/test.txt"}
            },
            {
                "id": "hook_pre_tool",
                "name": "PreToolUse Hook",
                "description": "Test Claude Code PreToolUse hook",
                "type": "hook_test",
                "event_name": "PreToolUse",
                "tool_name": "Bash",
                "arguments": {"command": "ls -la"}
            }
        ]
    
    async def _run_scenario(self, scenario: Dict[str, Any]) -> None:
        """Run a specific test scenario."""
        self.console.print(f"[bold]Running scenario: {scenario['name']}[/bold]")
        
        scenario_type = scenario.get("type", "unknown")
        
        if scenario_type == "health_check":
            await self._health_check_menu()
        elif scenario_type == "tool_evaluation":
            await self._execute_tool_evaluation(
                tool_name=scenario.get("tool_name", "TestTool"),
                parameters=scenario.get("parameters", {}),
                agent_id=self.current_agent_id,
                session_id=self.current_session_id
            )
        elif scenario_type == "hook_test":
            await self._execute_hook_test(
                event_name=scenario.get("event_name", "PreToolUse"),
                tool_name=scenario.get("tool_name", "TestTool"),
                arguments=scenario.get("arguments", {})
            )
        else:
            self.console.print(f"[red]Unknown scenario type: {scenario_type}[/red]")
    
    async def _live_monitor_menu(self) -> None:
        """Live monitoring dashboard."""
        self.console.print(Panel("Live Monitoring Dashboard", style="yellow"))
        self.console.print("[dim]Press Ctrl+C to stop monitoring[/dim]")
        
        try:
            with Live(self._create_monitor_layout(), refresh_per_second=1, console=self.console) as live:
                while True:
                    # Update dashboard
                    live.update(self._create_monitor_layout())
                    await asyncio.sleep(1)
        
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Monitoring stopped[/yellow]")
    
    def _create_monitor_layout(self) -> Layout:
        """Create live monitoring layout."""
        layout = Layout()
        
        # Session stats
        session_stats = Table(title="Session Statistics", show_header=False)
        session_stats.add_column("Metric", style="cyan")
        session_stats.add_column("Value", style="green")
        
        if self.session_history:
            total_requests = len(self.session_history)
            successful = sum(1 for r in self.session_history if r.success)
            success_rate = successful / total_requests * 100 if total_requests > 0 else 0
            avg_time = sum(r.response_time_ms for r in self.session_history) / total_requests
            
            session_stats.add_row("Total Requests", str(total_requests))
            session_stats.add_row("Success Rate", f"{success_rate:.1f}%")
            session_stats.add_row("Avg Response Time", f"{avg_time:.1f}ms")
        else:
            session_stats.add_row("Status", "No requests yet")
        
        layout.update(Panel(session_stats, border_style="blue"))
        return layout
    
    def _show_detailed_response(self, result: TestResult) -> None:
        """Show detailed response information."""
        if not result.response_data:
            self.console.print("[dim]No response data available[/dim]")
            return
        
        self.console.print(Panel(
            JSON.from_data(result.response_data, indent=2),
            title="Response Data",
            border_style="blue"
        ))
    
    def _display_session_summary(self) -> None:
        """Display session summary on exit."""
        if not self.session_history:
            self.console.print("\n[dim]No requests were made during this session[/dim]")
            return
        
        self.console.print("\n[bold cyan]Session Summary[/bold cyan]")
        self.formatter.format_summary(self.session_history)
        
        # Offer to save history
        if Confirm.ask("Save session history to file?", default=False):
            filename = Prompt.ask("Filename", default="interactive_session.json")
            self._save_session_history(Path(filename))
    
    def _save_session_history(self, filename: Path) -> None:
        """Save session history to file."""
        try:
            history_data = [result.to_dict() for result in self.session_history]
            
            with open(filename, 'w') as f:
                json.dump({
                    "session_id": self.current_session_id,
                    "agent_id": self.current_agent_id,
                    "server_url": self.config.server.base_url,
                    "requests": history_data
                }, f, indent=2)
            
            self.console.print(f"[green]Session history saved to: {filename}[/green]")
        
        except Exception as e:
            self.console.print(f"[red]Failed to save session history: {e}[/red]")


async def run_interactive_mode(
    config: Optional[Path] = None,
    server_url: str = "http://localhost:8000",
    auto_approve: bool = False,
    log_level: str = "info",
    config_profile: str = "default",
) -> None:
    """Main entry point for interactive testing command.
    
    Args:
        config: Path to interactive mode configuration file
        server_url: Superego MCP Server URL for interactive testing
        auto_approve: Automatically approve safe requests
        log_level: Logging level for interactive session
        config_profile: Configuration profile to use
    """
    # Load configuration
    test_config = load_config(config_profile)
    
    # Create console for output
    console = Console()
    
    # Create and start interactive session
    session = InteractiveSession(test_config, console)
    
    await session.start_session(
        server_url=server_url,
        auto_approve=auto_approve,
        log_level=log_level
    )