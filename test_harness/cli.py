"""
Main CLI application for Superego MCP Test Harness.

Provides command-line interface for testing, evaluating, and interacting with
the Superego MCP Server using the Cyclopts framework.
"""

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import cyclopts

# Import placeholder command functions (to be implemented in tasks 151-152)
# These imports will be added once the command modules are created
# from .commands.evaluate import evaluate_command
# from .commands.hooks import hooks_command  
# from .commands.health import health_command
# from .commands.load import load_command
# from .commands.interactive import interactive_command
# from .commands.scenarios import scenarios_command

# Main Cyclopts Application
app = cyclopts.App(
    name="superego-test-harness",
    help="Test harness for the Superego MCP Server - provides CLI tools for testing, evaluation, and interaction",
    version="0.0.0",
)


@app.command
def evaluate(
    config: Annotated[
        Optional[Path],
        cyclopts.Parameter(
            help="Path to configuration file for evaluation settings"
        )
    ] = None,
    rules: Annotated[
        Optional[Path],
        cyclopts.Parameter(
            help="Path to security rules file to evaluate against"
        )
    ] = None,
    prompt: Annotated[
        Optional[str],
        cyclopts.Parameter(
            help="Direct prompt text to evaluate (alternative to --input-file)"
        )
    ] = None,
    input_file: Annotated[
        Optional[Path],
        cyclopts.Parameter(
            help="Path to file containing prompt/request to evaluate"
        )
    ] = None,
    output_format: Annotated[
        str,
        cyclopts.Parameter(
            help="Output format for evaluation results (json, yaml, table)"
        )
    ] = "table",
    verbose: Annotated[
        bool,
        cyclopts.Parameter(
            help="Enable verbose output with detailed rule matching information"
        )
    ] = False,
) -> None:
    """
    Evaluate prompts or tool requests against Superego security rules.
    
    This command allows testing of security policies by evaluating text prompts
    or tool requests against configured rule sets to see what decisions would be made.
    """
    # Implementation will be added in evaluate command module
    async def _evaluate() -> None:
        # Placeholder - will import and call evaluate_command function
        print("Evaluate command - implementation pending (Task 151)")
        print(f"Config: {config}")
        print(f"Rules: {rules}")
        print(f"Prompt: {prompt}")
        print(f"Input file: {input_file}")
        print(f"Output format: {output_format}")
        print(f"Verbose: {verbose}")
    
    asyncio.run(_evaluate())


@app.command
def hooks(
    action: Annotated[
        str,
        cyclopts.Parameter(
            help="Hook action to perform (install, uninstall, list, test)"
        )
    ],
    config: Annotated[
        Optional[Path],
        cyclopts.Parameter(
            help="Path to hook configuration file"
        )
    ] = None,
    target: Annotated[
        Optional[str],
        cyclopts.Parameter(
            help="Target application or environment for hook installation"
        )
    ] = None,
    dry_run: Annotated[
        bool,
        cyclopts.Parameter(
            help="Perform a dry run without making actual changes"
        )
    ] = False,
) -> None:
    """
    Manage Claude Code hooks for Superego integration.
    
    Install, configure, and test hooks that integrate Superego MCP Server
    with Claude Code for real-time tool request filtering and security.
    """
    # Implementation will be added in hooks command module
    async def _hooks() -> None:
        # Placeholder - will import and call hooks_command function
        print("Hooks command - implementation pending (Task 152)")
        print(f"Action: {action}")
        print(f"Config: {config}")
        print(f"Target: {target}")
        print(f"Dry run: {dry_run}")
    
    asyncio.run(_hooks())


@app.command
def health(
    server_url: Annotated[
        str,
        cyclopts.Parameter(
            help="URL of the Superego MCP Server to check"
        )
    ] = "http://localhost:8000",
    timeout: Annotated[
        float,
        cyclopts.Parameter(
            help="Request timeout in seconds"
        )
    ] = 30.0,
    detailed: Annotated[
        bool,
        cyclopts.Parameter(
            help="Show detailed health information including metrics"
        )
    ] = False,
    watch: Annotated[
        bool,
        cyclopts.Parameter(
            help="Continuously monitor health status"
        )
    ] = False,
    interval: Annotated[
        float,
        cyclopts.Parameter(
            help="Watch interval in seconds (only used with --watch)"
        )
    ] = 5.0,
) -> None:
    """
    Check health status of the Superego MCP Server.
    
    Performs health checks against a running server instance to verify
    that all components are functioning correctly.
    """
    # Implementation will be added in health command module
    async def _health() -> None:
        # Placeholder - will import and call health_command function
        print("Health command - implementation pending (Task 151)")
        print(f"Server URL: {server_url}")
        print(f"Timeout: {timeout}")
        print(f"Detailed: {detailed}")
        print(f"Watch: {watch}")
        print(f"Interval: {interval}")
    
    asyncio.run(_health())


@app.command
def load(
    target_url: Annotated[
        str,
        cyclopts.Parameter(
            help="Target server URL for load testing"
        )
    ] = "http://localhost:8000",
    requests: Annotated[
        int,
        cyclopts.Parameter(
            help="Number of requests to send during load test"
        )
    ] = 100,
    concurrency: Annotated[
        int,
        cyclopts.Parameter(
            help="Number of concurrent requests"
        )
    ] = 10,
    duration: Annotated[
        Optional[float],
        cyclopts.Parameter(
            help="Test duration in seconds (alternative to --requests)"
        )
    ] = None,
    ramp_up: Annotated[
        float,
        cyclopts.Parameter(
            help="Ramp-up time in seconds to reach full concurrency"
        )
    ] = 0.0,
    scenario: Annotated[
        Optional[str],
        cyclopts.Parameter(
            help="Load test scenario name to execute"
        )
    ] = None,
    output_file: Annotated[
        Optional[Path],
        cyclopts.Parameter(
            help="File to save load test results"
        )
    ] = None,
) -> None:
    """
    Run load tests against the Superego MCP Server.
    
    Generates configurable load patterns to test server performance,
    scalability, and stability under various traffic conditions.
    """
    # Implementation will be added in load command module
    async def _load() -> None:
        # Placeholder - will import and call load_command function
        print("Load command - implementation pending (Task 152)")
        print(f"Target URL: {target_url}")
        print(f"Requests: {requests}")
        print(f"Concurrency: {concurrency}")
        print(f"Duration: {duration}")
        print(f"Ramp up: {ramp_up}")
        print(f"Scenario: {scenario}")
        print(f"Output file: {output_file}")
    
    asyncio.run(_load())


@app.command
def interactive(
    config: Annotated[
        Optional[Path],
        cyclopts.Parameter(
            help="Path to interactive mode configuration file"
        )
    ] = None,
    server_url: Annotated[
        str,
        cyclopts.Parameter(
            help="Superego MCP Server URL for interactive testing"
        )
    ] = "http://localhost:8000",
    auto_approve: Annotated[
        bool,
        cyclopts.Parameter(
            help="Automatically approve safe requests in interactive mode"
        )
    ] = False,
    log_level: Annotated[
        str,
        cyclopts.Parameter(
            help="Logging level for interactive session (debug, info, warning, error)"
        )
    ] = "info",
) -> None:
    """
    Start interactive testing session with the Superego MCP Server.
    
    Provides a REPL-like interface for testing tool requests, exploring
    rule behavior, and debugging security policies in real-time.
    """
    # Implementation will be added in interactive command module
    async def _interactive() -> None:
        # Placeholder - will import and call interactive_command function
        print("Interactive command - implementation pending (Task 151)")
        print(f"Config: {config}")
        print(f"Server URL: {server_url}")
        print(f"Auto approve: {auto_approve}")
        print(f"Log level: {log_level}")
    
    asyncio.run(_interactive())


@app.command
def scenarios(
    scenario_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            help="Specific scenario name to run (leave empty to list available scenarios)"
        )
    ] = None,
    config_dir: Annotated[
        Optional[Path],
        cyclopts.Parameter(
            help="Directory containing scenario configuration files"
        )
    ] = None,
    output_format: Annotated[
        str,
        cyclopts.Parameter(
            help="Output format for scenario results (json, yaml, table)"
        )
    ] = "table",
    parallel: Annotated[
        bool,
        cyclopts.Parameter(
            help="Run scenarios in parallel when executing multiple scenarios"
        )
    ] = False,
    fail_fast: Annotated[
        bool,
        cyclopts.Parameter(
            help="Stop execution on first scenario failure"
        )
    ] = False,
    tags: Annotated[
        Optional[str],
        cyclopts.Parameter(
            help="Comma-separated list of scenario tags to filter by"
        )
    ] = None,
) -> None:
    """
    Run predefined test scenarios against the Superego MCP Server.
    
    Executes comprehensive test suites covering security policies,
    performance benchmarks, and integration testing scenarios.
    """
    # Implementation will be added in scenarios command module
    async def _scenarios() -> None:
        # Placeholder - will import and call scenarios_command function
        print("Scenarios command - implementation pending (Task 152)")
        print(f"Scenario name: {scenario_name}")
        print(f"Config dir: {config_dir}")
        print(f"Output format: {output_format}")
        print(f"Parallel: {parallel}")
        print(f"Fail fast: {fail_fast}")
        print(f"Tags: {tags}")
    
    asyncio.run(_scenarios())


def main() -> None:
    """Main entry point for the Superego Test Harness CLI."""
    app()


if __name__ == "__main__":
    main()