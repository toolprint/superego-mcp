#!/usr/bin/env python3
"""
Unified CLI interface for Superego MCP.

This module provides a unified command-line interface with subcommands:
- superego advise: One-off security evaluation for Claude Code hooks
- superego mcp: Launch the FastMCP server

Usage:
    superego advise < hook_input.json
    superego advise -c ~/.toolprint/superego/config.yaml < hook_input.json
    superego mcp
    superego mcp -c ~/.toolprint/superego/config.yaml
    superego --version
    superego --help
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .cli_client import SuperegoHTTPClient
from .cli_eval import CLIEvaluator
from .infrastructure.logging_config import configure_stderr_logging
from .main import async_main as mcp_async_main


async def mcp_async_main_with_config(
    config_path: Path, transport: str | None = None, port: int | None = None
) -> None:
    """Run MCP server with custom config path and optional CLI overrides.

    This is a wrapper around the main async_main that sets up
    a custom ConfigManager before launching the server.
    """
    # Import here to avoid circular imports
    from .infrastructure.config import ConfigManager

    # Create config manager with custom path
    config_manager = ConfigManager(str(config_path))
    _ = config_manager.load_config()  # Load config but don't use it yet

    # For now, we'll monkey-patch the config loading in main.py
    # This is a temporary solution until we refactor main.py
    import os

    os.environ["SUPEREGO_CONFIG_PATH"] = str(config_path)

    # Run the main server with CLI overrides
    await mcp_async_main(transport=transport, port=port)


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="superego",
        description="Intelligent tool request interception for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run security evaluation (for Claude Code hooks) - local mode
  echo '{"tool_name": "bash", "tool_input": {"command": "rm -rf /"}}' | superego advise

  # Run evaluation with custom config - local mode
  superego advise -c ~/.toolprint/superego/config.yaml < hook_input.json

  # Run evaluation via remote server - client mode
  superego advise --url http://localhost:8000 < hook_input.json

  # Client mode with authentication and custom timeout
  superego advise --url https://superego.company.com --token abc123 --timeout 10 < hook_input.json

  # Launch MCP server (default: stdio transport)
  superego mcp

  # Launch MCP server with HTTP transport on custom port
  superego mcp -t http -p 9000

  # Launch MCP server with custom config
  superego mcp -c ~/.toolprint/superego/config.yaml

  # Launch MCP server with explicit stdio transport
  superego mcp -t stdio

  # Manage Claude Code hooks (local mode)
  superego hooks add --matcher "Bash|Write|Edit|MultiEdit"
  superego hooks list
  superego hooks remove --matcher "*"

  # Centralized server mode
  superego hooks add --matcher "Bash|Write|Edit" --url http://localhost:8000
  superego hooks add --matcher "*" --url https://superego.company.com --token <auth-token>

Claude Code Hook Integration:
  # Add as a direct hook command:
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "superego advise",
            "timeout": 5000
          }
        ]
      }
    ]
  }

  # Or use with HTTP server:
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "curl --json @- http://localhost:8000/pretoolinputendpoint",
            "timeout": 5000
          }
        ]
      }
    ]
  }

For more information on Claude Code hooks, see:
https://docs.anthropic.com/en/docs/claude-code/hooks-guide
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"superego {__version__}",
    )

    # Create subparsers for subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        metavar="{advise,mcp,hooks}",
    )

    # Create the advise subcommand
    advise_parser = subparsers.add_parser(
        "advise",
        help="Run one-off security evaluation (for Claude Code hooks)",
        description="""
Run a security evaluation on tool input provided via stdin.
Reads JSON hook input from stdin and outputs decision JSON to stdout.
Designed for use as a Claude Code PreToolUse hook.

Local Mode (default): Evaluates requests locally using mock provider.
Client Mode (--url): Forwards requests to a remote Superego MCP server.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0: Success with JSON output on stdout
  1: Non-blocking error (stderr shown to user)
  2: Blocking error (stderr fed back to Claude)

Input Format (Claude Code PreToolUse hook):
  {
    "session_id": "string",
    "transcript_path": "string",
    "cwd": "string",
    "hook_event_name": "PreToolUse",
    "tool_name": "string",
    "tool_input": {...}
  }

Output Format:
  {
    "hook_specific_output": {
      "hook_event_name": "PreToolUse",
      "permission_decision": "allow|ask|deny",
      "permission_decision_reason": "string"
    },
    "decision": "approve|block",
    "reason": "string"
  }
        """,
    )

    advise_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to configuration file (default: ~/.toolprint/superego/config.yaml)",
        metavar="PATH",
    )

    advise_parser.add_argument(
        "--url",
        type=str,
        help="Server URL for client mode (enables HTTP forwarding instead of local evaluation)",
        metavar="URL",
    )

    advise_parser.add_argument(
        "--token",
        type=str,
        help="Authentication token for server requests (use with --url)",
        metavar="TOKEN",
    )

    advise_parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="HTTP request timeout in seconds (default: 5)",
        metavar="SECONDS",
    )

    # Create the mcp subcommand
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Launch FastMCP server",
        description="""
Launch the Superego MCP server with multi-transport support.
Provides rule management and security evaluation tools for AI agents.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Default Configuration:
  - Config path: ~/.toolprint/superego/config.yaml
  - Inference provider: Claude CLI (requires Claude Code installation)
  - Architecture: Unified FastAPI + MCP server (single process)
  - Transport: STDIO mode (configurable with -t/--transport)
  - Port: 8000 for HTTP mode (configurable with -p/--port)

Transport Options:
  - stdio: Standard I/O transport for MCP (default, uses stderr for logging)
  - http: HTTP/WebSocket transport with FastAPI (uses stdout for logging)
  - unified: Both STDIO and HTTP in single process (experimental)

Architecture:
  The unified server combines FastAPI (HTTP/WebSocket) and FastMCP (stdio) in a single process.
  This provides better performance and simplified deployment while maintaining backward compatibility.

The server will validate Claude CLI availability on startup.
If Claude is not available, the server will exit with an error.
Signal handling: Ctrl-C (SIGINT) and SIGTERM will cleanly shut down the server.
        """,
    )

    mcp_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to configuration file (default: ~/.toolprint/superego/config.yaml)",
        metavar="PATH",
    )

    mcp_parser.add_argument(
        "--validate-claude",
        action="store_true",
        help="Validate Claude CLI availability on startup (default: true)",
        default=True,
    )

    mcp_parser.add_argument(
        "-t",
        "--transport",
        type=str,
        choices=["stdio", "http", "unified"],
        default="stdio",
        help="Transport mode for the MCP server (default: stdio)",
        metavar="TRANSPORT",
    )

    mcp_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP transport mode (default: 8000)",
        metavar="PORT",
    )

    # Create the hooks subcommand
    hooks_parser = subparsers.add_parser(
        "hooks",
        help="Manage Claude Code hooks for Superego integration",
        description="""
Manage Claude Code hooks that integrate Superego security evaluation.
Safely add, list, and remove hooks in ~/.claude/settings.json while
preserving existing Claude Code configurations.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local evaluation (default)
  superego hooks add
  superego hooks add --matcher "Bash|Write|Edit|MultiEdit"

  # Centralized server evaluation
  superego hooks add --matcher "*" --url http://localhost:8000
  superego hooks add --matcher "Bash|Write|Edit" --url https://superego.company.com --token abc123
  superego hooks add --matcher "*" --url http://localhost:8000 --fallback

  # List all superego-managed hooks
  superego hooks list

  # Remove a specific hook by ID
  superego hooks remove --id 550e8400-e29b-41d4

  # Remove all hooks with a specific matcher
  superego hooks remove --matcher "Bash|Write|Edit"

Common Matchers:
  *                           All tools (default)
  Bash|Write|Edit|MultiEdit   Common dangerous tools (recommended)
  Bash                        Shell commands only
  Write|Edit|MultiEdit        File modification tools
  mcp__.*                     All MCP tools

Centralized vs Local Mode:
  Local mode (default): Each hook spawns a 'superego advise' process
  Centralized mode (--url): Hooks send requests to a running MCP server via curl

  Centralized mode benefits:
  - Single evaluation process reduces overhead
  - Supports remote server deployment
  - Consistent security policies across team/organization
  - Optional authentication with Bearer tokens

Claude Code Integration:
  Hooks are automatically configured in ~/.claude/settings.json
  and will be active the next time you use Claude Code.
        """,
    )

    # Create hooks subparsers
    hooks_subparsers = hooks_parser.add_subparsers(
        dest="hooks_command",
        help="Hooks management commands",
        metavar="{add,list,remove}",
    )

    # Add hook command
    add_parser = hooks_subparsers.add_parser(
        "add",
        help="Add a new Superego hook",
        description="Add a new hook to Claude Code settings for security evaluation.",
    )

    add_parser.add_argument(
        "-m",
        "--matcher",
        type=str,
        help="Tool pattern to match (default: '*' for all tools)",
        metavar="PATTERN",
    )

    add_parser.add_argument(
        "--timeout",
        type=int,
        default=5000,
        help="Hook timeout in milliseconds (default: 5000)",
        metavar="MS",
    )

    add_parser.add_argument(
        "--event-type",
        type=str,
        default="PreToolUse",
        help="Hook event type (default: PreToolUse)",
        metavar="TYPE",
    )

    add_parser.add_argument(
        "--url",
        type=str,
        help="Centralized server URL (enables centralized mode)",
        metavar="URL",
    )

    add_parser.add_argument(
        "--token",
        type=str,
        help="Authentication token for centralized server",
        metavar="TOKEN",
    )

    add_parser.add_argument(
        "--fallback",
        action="store_true",
        help="Enable fallback to local evaluation on HTTP failure",
    )

    # List hooks command
    list_parser = hooks_subparsers.add_parser(
        "list",
        help="List all Superego hooks",
        description="Display all superego-managed hooks in Claude Code settings.",
    )

    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output hooks as JSON",
    )

    list_parser.add_argument(
        "--event-type",
        type=str,
        help="Filter by event type",
        metavar="TYPE",
    )

    # Remove hooks command
    remove_parser = hooks_subparsers.add_parser(
        "remove",
        help="Remove Superego hooks",
        description="Remove superego-managed hooks from Claude Code settings.",
    )

    remove_group = remove_parser.add_mutually_exclusive_group(required=True)
    remove_group.add_argument(
        "--id",
        type=str,
        help="Remove hook with specific ID",
        metavar="ID",
    )

    remove_group.add_argument(
        "-m",
        "--matcher",
        type=str,
        help="Remove all hooks with this matcher pattern",
        metavar="PATTERN",
    )

    return parser


def get_default_config_path() -> Path:
    """Get the default configuration path."""
    return Path.home() / ".toolprint" / "superego" / "config.yaml"


def ensure_default_config_dir() -> Path:
    """Ensure the default config directory exists and return the config path."""
    config_path = get_default_config_path()
    config_dir = config_path.parent

    # Create the directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)

    return config_path


async def validate_claude_cli() -> bool:
    """Validate that Claude CLI is available and functional."""
    try:
        from .infrastructure.inference import CLIProvider, CLIProviderConfig

        # Create a Claude CLI provider configuration
        config = CLIProviderConfig(
            name="claude_cli_validator",
            type="claude",
            command="claude",
            timeout_seconds=5,
        )

        # Try to create a Claude provider - this will validate CLI availability
        provider = CLIProvider(config)

        # Run a health check
        health = await provider.health_check()

        if not health.healthy:
            print(f"Claude CLI health check failed: {health.message}", file=sys.stderr)
            return False

        return True

    except Exception as e:
        print(f"Claude CLI validation failed: {e}", file=sys.stderr)
        print(
            "Please ensure Claude Code is installed and authenticated:", file=sys.stderr
        )
        print(
            "  1. Install Claude Code: https://docs.anthropic.com/en/docs/claude-code",
            file=sys.stderr,
        )
        print("  2. Authenticate: claude auth", file=sys.stderr)
        return False


async def cmd_advise(args: argparse.Namespace) -> int:
    """Handle the advise subcommand."""
    try:
        # Configure logging to stderr with minimal noise for CLI usage
        configure_stderr_logging(level="WARNING", json_logs=False)

        # Check if client mode is requested
        if args.url:
            # Client mode: forward to remote server
            if not args.url.startswith(("http://", "https://")):
                print(
                    "Error: URL must start with http:// or https://",
                    file=sys.stderr,
                )
                return 1

            # Create HTTP client
            client = SuperegoHTTPClient(
                base_url=args.url,
                token=args.token,
                timeout=args.timeout,
            )

            # Run evaluation via HTTP client
            result = await client.evaluate_from_stdin()

            # Output result as JSON
            print(json.dumps(result))
            return 0

        else:
            # Local mode: use existing CLI evaluator
            # Get config path - if specified and exists, validate it
            config_path = args.config or ensure_default_config_dir()

            if args.config and not config_path.exists():
                print(
                    f"Error: Specified config file does not exist: {config_path}",
                    file=sys.stderr,
                )
                return 1

            # Load configuration if it exists
            if config_path.exists():
                try:
                    from .infrastructure.config import ConfigManager

                    config_manager = ConfigManager(str(config_path))
                    config_manager.load_config()
                except Exception as e:
                    print(
                        f"Warning: Failed to load config from {config_path}: {e}",
                        file=sys.stderr,
                    )
                    print("Continuing with default configuration...", file=sys.stderr)

            # Use the existing CLI evaluator
            evaluator = CLIEvaluator()

            # Run evaluation
            result = await evaluator.evaluate_from_stdin()

            # Output result as JSON
            print(json.dumps(result))
            return 0

    except ValueError as e:
        # Non-blocking error - show to user
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        # Blocking error - fed back to Claude
        print(f"Blocking error: {e}", file=sys.stderr)
        return 2


async def cmd_mcp(args: argparse.Namespace) -> int:
    """Handle the mcp subcommand."""
    try:
        # Get config path
        config_path = args.config or ensure_default_config_dir()

        if args.config and not config_path.exists():
            print(
                f"Error: Specified config file does not exist: {config_path}",
                file=sys.stderr,
            )
            return 1

        # Validate Claude CLI if requested
        if args.validate_claude:
            print("Validating Claude CLI availability...")
            if not await validate_claude_cli():
                print(
                    "Claude CLI validation failed. Server startup aborted.",
                    file=sys.stderr,
                )
                return 1
            print("Claude CLI validation successful.")

        # Handle unified transport mode (default to None for backward compatibility)
        transport_mode = args.transport if args.transport != "unified" else None

        # If unified mode is requested, start both transports
        if args.transport == "unified":
            print("Starting unified server (FastAPI + MCP in single process)")
            transport_mode = None  # Let the unified server handle both

        # Update main.py to use custom config path if provided
        if args.config:
            print(f"Using configuration from: {config_path}")
            await mcp_async_main_with_config(
                config_path, transport=transport_mode, port=args.port
            )
        else:
            # Check if default config path exists
            if config_path.exists():
                print(f"Using default configuration from: {config_path}")
                await mcp_async_main_with_config(
                    config_path, transport=transport_mode, port=args.port
                )
            else:
                print("Using default configuration (no config file found)")
                await mcp_async_main(transport=transport_mode, port=args.port)

        return 0

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        return 0

    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        return 1


async def cmd_hooks(args: argparse.Namespace) -> int:
    """Handle the hooks subcommand."""
    try:
        from .cli_hooks import (
            HooksManager,
        )

        # Initialize hooks manager
        hooks_manager = HooksManager()

        # Validate Claude Code installation
        if not hooks_manager.validate_claude_installation():
            print(
                "Warning: Claude Code installation not detected at ~/.claude/",
                file=sys.stderr,
            )
            print(
                "Hooks will be created but may not be active until Claude Code is installed.",
                file=sys.stderr,
            )

        # Route to appropriate hooks command
        if args.hooks_command == "add":
            return await cmd_hooks_add(args, hooks_manager)
        elif args.hooks_command == "list":
            return await cmd_hooks_list(args, hooks_manager)
        elif args.hooks_command == "remove":
            return await cmd_hooks_remove(args, hooks_manager)
        else:
            print(
                "Error: No hooks command specified. Use 'superego hooks --help' for usage.",
                file=sys.stderr,
            )
            return 1

    except Exception as e:
        print(f"Hooks command failed: {e}", file=sys.stderr)
        return 1


async def cmd_hooks_add(args: argparse.Namespace, hooks_manager: Any) -> int:
    """Handle the hooks add subcommand."""
    try:
        # Get matcher - use default if not specified
        matcher = args.matcher or "*"

        # Provide helpful suggestions for common matchers
        if matcher == "*":
            print("Adding hook for all tools (matcher: '*')")
            print(
                "Tip: For better security, consider using --matcher 'Bash|Write|Edit|MultiEdit'"
            )

        # Add the hook
        hook = hooks_manager.add_hook(
            matcher=matcher,
            event_type=args.event_type,
            timeout=args.timeout,
            url=getattr(args, "url", None),
            token=getattr(args, "token", None),
            fallback=getattr(args, "fallback", False),
        )

        print("✓ Successfully added Superego hook")
        print(f"  ID: {hook.id}")
        print(f"  Matcher: {hook.matcher}")
        print(f"  Event Type: {hook.event_type}")
        print(f"  Mode: {hook.mode}")
        if hook.url:
            print(f"  URL: {hook.url}")
            if hook.token:
                print("  Authentication: Bearer token configured")
            if hook.fallback_enabled:
                print("  Fallback: Enabled (will use local evaluation if HTTP fails)")
        print(f"  Command: {hook.command}")
        print(f"  Timeout: {hook.timeout}ms")
        print()
        if hook.mode == "centralized":
            print("The hook is configured for centralized evaluation.")
            print("Make sure the Superego MCP server is running at the specified URL.")
        else:
            print("The hook will be active the next time you use Claude Code.")
        print("Use 'superego hooks list' to view all installed hooks.")

        return 0

    except Exception as e:
        print(f"Failed to add hook: {e}", file=sys.stderr)
        return 1


async def cmd_hooks_list(args: argparse.Namespace, hooks_manager: Any) -> int:
    """Handle the hooks list subcommand."""
    try:
        hooks = hooks_manager.list_hooks(event_type=args.event_type)

        if not hooks:
            if args.event_type:
                print(f"No Superego hooks found for event type '{args.event_type}'")
            else:
                print("No Superego hooks found.")
                print("Use 'superego hooks add' to create your first hook.")
            return 0

        if args.json:
            # Output as JSON
            import json

            hook_data = [
                {
                    "id": hook.id,
                    "matcher": hook.matcher,
                    "event_type": hook.event_type,
                    "command": hook.command,
                    "timeout": hook.timeout,
                    "enabled": hook.enabled,
                    "created_at": hook.created_at.isoformat(),
                }
                for hook in hooks
            ]
            print(json.dumps(hook_data, indent=2))
        else:
            # Pretty table output
            print(f"Found {len(hooks)} Superego hook(s):")
            print()

            for i, hook in enumerate(hooks, 1):
                status = "Enabled" if hook.enabled else "Disabled"
                print(f"{i}. Hook ID: {hook.id}")
                print(f"   Matcher: {hook.matcher}")
                print(f"   Event Type: {hook.event_type}")
                print(f"   Command: {hook.command}")
                print(f"   Timeout: {hook.timeout}ms")
                print(f"   Status: {status}")
                print(
                    f"   Created: {hook.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )
                if i < len(hooks):
                    print()

        return 0

    except Exception as e:
        print(f"Failed to list hooks: {e}", file=sys.stderr)
        return 1


async def cmd_hooks_remove(args: argparse.Namespace, hooks_manager: Any) -> int:
    """Handle the hooks remove subcommand."""
    try:
        from .cli_hooks import HookNotFoundError

        # Confirm removal
        if args.id:
            print(f"Removing hook with ID: {args.id}")
        else:
            print(f"Removing all hooks with matcher: {args.matcher}")

        response = input("Are you sure? (y/N): ").strip().lower()
        if response not in ["y", "yes"]:
            print("Removal cancelled.")
            return 0

        # Remove the hook(s)
        removed_count = hooks_manager.remove_hook(hook_id=args.id, matcher=args.matcher)

        if removed_count == 1:
            print("✓ Successfully removed 1 hook")
        else:
            print(f"✓ Successfully removed {removed_count} hooks")

        return 0

    except HookNotFoundError as e:
        print(f"No hooks found: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"Failed to remove hook(s): {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for the unified CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # If no subcommand is provided, show help
    if not args.command:
        parser.print_help()
        return 1

    # Route to appropriate handler
    if args.command == "advise":
        return asyncio.run(cmd_advise(args))
    elif args.command == "mcp":
        return asyncio.run(cmd_mcp(args))
    elif args.command == "hooks":
        return asyncio.run(cmd_hooks(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
