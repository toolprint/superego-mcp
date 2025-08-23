"""
Main CLI application for Superego MCP Test Harness.

Provides command-line interface for testing, evaluating, and interacting with
the Superego MCP Server using the Cyclopts framework.
"""

import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional

import cyclopts

# Import command functions from implemented modules
from .commands.evaluate import run_evaluation
from .commands.hooks import run_hook_test
from .commands.health import run_health_check
from .commands.load import run_load_test
from .commands.interactive import run_interactive_mode
from .commands.scenarios import manage_scenarios

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
    # Convert parameters to match run_evaluation function signature
    scenario_file = input_file
    parameters_json = None
    tool_name_param = None
    
    # If prompt is provided, treat it as a simple tool evaluation
    if prompt and not input_file:
        tool_name_param = "prompt_evaluation"
        parameters_json = json.dumps({"prompt": prompt})
    
    asyncio.run(run_evaluation(
        scenario_file=scenario_file,
        tool_name=tool_name_param,
        parameters_json=parameters_json,
        config_file=config,
        output_format=output_format,
        parallel=False,  # Default to sequential execution
        tags_filter=None
    ))


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
    asyncio.run(run_hook_test(
        action=action,
        scenario_file=None,  # Could be extended to support config-based scenarios
        event_name=None,
        tool_name=None,
        arguments_json=None,
        config_file=config,
        output_format="pretty",
        integration_test=(action == "test")  # Run integration tests for "test" action
    ))


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
    asyncio.run(run_health_check(
        server_url=server_url,
        config_file=None,  # Use default config
        detailed=detailed,
        watch=watch,
        interval=interval,
        output_format="pretty",
        timeout=timeout
    ))


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
    # Call the implemented load testing function
    async def _load() -> None:
        await run_load_test(
            target_url=target_url,
            requests=requests,
            concurrency=concurrency,
            duration=duration,
            ramp_up=ramp_up,
            scenario=scenario,
            output_file=output_file,
        )
    
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
    # Call the implemented interactive mode function
    async def _interactive() -> None:
        await run_interactive_mode(
            config=config,
            server_url=server_url,
            auto_approve=auto_approve,
            log_level=log_level,
        )
    
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
    # Call the implemented scenario management function
    async def _scenarios() -> None:
        await manage_scenarios(
            scenario_name=scenario_name,
            config_dir=config_dir,
            output_format=output_format,
            parallel=parallel,
            fail_fast=fail_fast,
            tags=tags,
        )
    
    asyncio.run(_scenarios())


def main() -> None:
    """Main entry point for the Superego Test Harness CLI."""
    app()


if __name__ == "__main__":
    main()