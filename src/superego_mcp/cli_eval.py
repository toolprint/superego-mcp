#!/usr/bin/env python3
"""
Standalone CLI evaluation tool for Superego MCP.

This module provides a simple command-line interface for one-off security
evaluations that can be used as a Claude Code PreToolUse hook. It reads
JSON input from stdin and returns decision JSON on stdout.

Usage:
    echo '{"hook_data"}' | superego advise

Exit Codes:
    0: Success with JSON output on stdout
    1: Non-blocking error (stderr shown to user)
    2: Blocking error (stderr fed back to Claude)
"""

import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import Any

import structlog

from .domain.claude_code_models import (
    HookEventName,
    PreToolUseHookSpecificOutput,
    PreToolUseOutput,
)
from .domain.hook_integration import HookIntegrationService
from .domain.models import ToolRequest
from .infrastructure.inference import (
    InferenceConfig,
    InferenceRequest,
    InferenceStrategyManager,
    MockInferenceProvider,
)
from .infrastructure.logging_config import configure_stderr_logging


class CLIEvaluator:
    """Standalone CLI evaluator for security decisions."""

    def __init__(self) -> None:
        """Initialize the CLI evaluator."""
        self.logger = structlog.get_logger("cli_eval")
        self.hook_integration = HookIntegrationService()
        self._setup_inference_provider()

    def _setup_inference_provider(self) -> None:
        """Set up the mock inference provider for standalone evaluation."""
        # Create mock inference provider
        self.mock_provider = MockInferenceProvider()

        # Create minimal inference config that uses the mock provider
        self.inference_config = InferenceConfig(
            timeout_seconds=5,  # Quick timeout for CLI usage
            provider_preference=["mock_inference"],
            cli_providers=[],  # No CLI providers needed
            api_providers=[],  # No API providers needed
        )

        # Create dependencies for inference manager
        dependencies = {
            "ai_service_manager": None,  # Not needed for mock provider
            "prompt_builder": None,  # Not needed for mock provider
        }

        # Create inference manager
        self.inference_manager = InferenceStrategyManager(
            self.inference_config, dependencies
        )

        # Manually add the mock provider since we're not using the standard initialization
        self.inference_manager.providers["mock_inference"] = self.mock_provider

    async def evaluate_from_stdin(self) -> dict[str, Any]:
        """Read hook input from stdin and return decision.

        Returns:
            Dictionary containing the hook output JSON in Claude Code format

        Raises:
            ValueError: If input is invalid
            RuntimeError: If evaluation fails
        """
        try:
            # Read JSON from stdin
            input_data = sys.stdin.read().strip()
            if not input_data:
                raise ValueError("No input data received on stdin")

            # Parse JSON
            try:
                hook_input_raw = json.loads(input_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON input: {e}") from e

            # Extract fields from raw input (Claude Code format)
            session_id = hook_input_raw.get("session_id", "cli_eval_session")
            hook_input_raw.get("transcript_path", "")
            cwd = hook_input_raw.get("cwd", str(Path.cwd()))
            hook_input_raw.get("hook_event_name", "PreToolUse")
            tool_name = hook_input_raw.get("tool_name")
            tool_input = hook_input_raw.get("tool_input", {})

            if not tool_name:
                raise ValueError("tool_name is required")

            # Create tool request for evaluation
            tool_request = ToolRequest(
                tool_name=tool_name,
                parameters=tool_input,
                session_id=session_id,
                agent_id="cli_eval",
                cwd=cwd,
            )

            # Create inference request
            inference_request = InferenceRequest(
                prompt=f"Security evaluation for {tool_name}: {json.dumps(tool_input)}",
                tool_request=tool_request,
                rule=None,  # No specific rule for standalone mode
                cache_key=f"cli_eval_{tool_name}_{hash(str(tool_input))}",
                timeout_seconds=5,
            )

            # Evaluate using mock provider
            decision = await self.mock_provider.evaluate(inference_request)

            # Convert to Claude Code hook output format
            hook_output = self._convert_decision_to_hook_output(decision)

            return hook_output.model_dump(by_alias=True)

        except ValueError:
            # Re-raise ValueError for input validation errors
            raise
        except Exception as e:
            self.logger.error(
                "Evaluation failed", error=str(e), traceback=traceback.format_exc()
            )
            raise RuntimeError(f"Evaluation failed: {e}") from e

    def _convert_decision_to_hook_output(self, decision: Any) -> PreToolUseOutput:
        """Convert inference decision to Claude Code hook output.

        Args:
            decision: InferenceDecision from provider

        Returns:
            PreToolUseOutput formatted for Claude Code
        """
        # Map decision to permission decision
        if hasattr(decision, "decision"):
            decision_str = decision.decision
        else:
            # Fallback for unexpected decision format
            decision_str = "deny"  # Safe default

        # Convert to PermissionDecision enum
        if decision_str == "allow":
            pass
        elif decision_str == "ask":
            pass
        else:
            pass  # Safe default

        # Get reasoning
        reasoning = getattr(
            decision,
            "reasoning",
            f"Security evaluation completed (provider: {getattr(decision, 'provider', 'unknown')})",
        )

        # Create hook-specific output
        hook_specific_output = PreToolUseHookSpecificOutput(
            hookEventName=HookEventName.PRE_TOOL_USE,
            permissionDecision=decision_str,
            permissionDecisionReason=reasoning,
        )

        return PreToolUseOutput(
            hookSpecificOutput=hook_specific_output,
            decision="approve" if decision_str == "allow" else "block",
            reason=reasoning,
        )


def main() -> None:
    """Main entry point for the CLI evaluator."""
    try:
        # Configure logging to stderr with minimal noise for CLI usage
        configure_stderr_logging(level="WARNING", json_logs=False)

        # Create evaluator
        evaluator = CLIEvaluator()

        # Run evaluation
        result = asyncio.run(evaluator.evaluate_from_stdin())

        # Output result as JSON to stdout
        print(json.dumps(result, separators=(",", ":")))

        # Exit with success
        sys.exit(0)

    except ValueError as e:
        # Input validation error - non-blocking error
        print(f"Input error: {e}", file=sys.stderr)
        sys.exit(1)

    except RuntimeError as e:
        # Evaluation error - blocking error (Claude should stop)
        print(f"Evaluation error: {e}", file=sys.stderr)
        sys.exit(2)

    except Exception as e:
        # Unexpected error - blocking error
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
