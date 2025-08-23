#!/usr/bin/env python3
"""
HTTP client for Superego MCP remote evaluation.

This module provides an HTTP client that forwards Claude Code hook data
to a remote Superego MCP server instance for evaluation instead of
performing local evaluation.
"""

import json
import sys
from typing import Any

import httpx
import structlog

from .domain.claude_code_models import PreToolUseInput, PreToolUseOutput


class SuperegoHTTPClient:
    """HTTP client for forwarding hook data to remote Superego MCP server."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: int = 5,
    ) -> None:
        """Initialize the HTTP client.

        Args:
            base_url: Server base URL (e.g., "http://localhost:8000")
            token: Optional authentication token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.logger = structlog.get_logger("superego_client")

        # Prepare headers
        self.headers = {"Content-Type": "application/json"}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    async def evaluate_hook(self, hook_input: dict[str, Any]) -> dict[str, Any]:
        """Forward hook input to remote server for evaluation.

        Args:
            hook_input: Raw hook input data from Claude Code

        Returns:
            Hook output data in Claude Code format

        Raises:
            httpx.HTTPError: If HTTP request fails
            ValueError: If server response is invalid
        """
        # Validate input format matches PreToolUseInput
        try:
            # Parse and validate input using Pydantic model
            pretool_input = PreToolUseInput.model_validate(hook_input)
        except Exception as e:
            self.logger.error("Invalid hook input format", error=str(e))
            raise ValueError(f"Invalid hook input format: {e}") from e

        endpoint = f"{self.base_url}/v1/hooks"

        self.logger.info(
            "Forwarding hook to server",
            endpoint=endpoint,
            tool_name=pretool_input.tool_name,
            session_id=pretool_input.session_id,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    headers=self.headers,
                    json=pretool_input.model_dump(by_alias=True),
                )

                # Raise for HTTP error status codes
                response.raise_for_status()

                # Parse response JSON
                response_data = response.json()

                # Validate response format using Pydantic model
                try:
                    pretool_output = PreToolUseOutput.model_validate(response_data)
                    return pretool_output.model_dump(by_alias=True)
                except Exception as e:
                    self.logger.error("Invalid server response format", error=str(e))
                    raise ValueError(f"Invalid server response format: {e}") from e

        except httpx.TimeoutException as e:
            self.logger.error("Server request timeout", timeout=self.timeout)
            raise httpx.HTTPError(f"Request timeout after {self.timeout}s") from e
        except httpx.HTTPStatusError as e:
            self.logger.error(
                "Server returned error status",
                status_code=e.response.status_code,
                response_text=e.response.text,
            )
            raise
        except httpx.RequestError as e:
            self.logger.error("HTTP request failed", error=str(e))
            raise

    async def evaluate_from_stdin(self) -> dict[str, Any]:
        """Read hook input from stdin and evaluate via remote server.

        Returns:
            Hook output data in Claude Code format

        Raises:
            ValueError: If input is invalid
            httpx.HTTPError: If HTTP request fails
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

            # Forward to server for evaluation
            return await self.evaluate_hook(hook_input_raw)

        except ValueError:
            # Re-raise ValueError for input validation errors
            raise
        except Exception as e:
            self.logger.error("Client evaluation failed", error=str(e))
            raise RuntimeError(f"Client evaluation failed: {e}") from e
