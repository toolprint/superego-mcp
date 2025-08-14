"""Inference provider system for AI-based security evaluation.

This module provides an extensible architecture for AI inference providers
that can be used for security policy evaluation. It supports multiple
inference modes including MCP Sampling, CLI integration, and direct API calls.
"""

import asyncio
import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Any

import structlog
from pydantic import BaseModel, Field

from ..domain.models import ErrorCode, SecurityRule, SuperegoError, ToolRequest
from .ai_service import AIServiceManager
from .prompt_builder import SecurePromptBuilder


class InferenceRequest(BaseModel):
    """Standard inference request format."""

    prompt: str
    tool_request: ToolRequest
    rule: SecurityRule | None
    cache_key: str
    timeout_seconds: int = 30


class InferenceDecision(BaseModel):
    """Standard inference decision response."""

    decision: str = Field(..., pattern="^(allow|deny)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    risk_factors: list[str] = Field(default_factory=list)
    provider: str
    model: str
    response_time_ms: int


class ProviderInfo(BaseModel):
    """Provider metadata."""

    name: str
    type: str  # "mcp_sampling", "cli", "api"
    models: list[str]
    capabilities: dict[str, Any]


class HealthStatus(BaseModel):
    """Provider health status."""

    healthy: bool
    message: str
    last_check: float
    error_count: int = 0


class InferenceProvider(ABC):
    """Abstract base class for all inference providers."""

    @abstractmethod
    async def evaluate(self, request: InferenceRequest) -> InferenceDecision:
        """Evaluate an inference request.

        Args:
            request: The inference request to evaluate

        Returns:
            InferenceDecision with evaluation results

        Raises:
            SuperegoError: If evaluation fails
        """
        pass

    @abstractmethod
    def get_provider_info(self) -> ProviderInfo:
        """Get provider information.

        Returns:
            ProviderInfo with metadata about this provider
        """
        pass

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check provider health.

        Returns:
            HealthStatus indicating provider health
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize provider resources.

        Called once when the provider is first created.
        Override if the provider needs initialization.
        """

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup provider resources.

        Called when the provider is being shut down.
        Override if the provider needs cleanup.
        """


class CLIProviderConfig(BaseModel):
    """Configuration for CLI-based inference providers."""

    name: str
    enabled: bool = True
    type: str = "claude"  # CLI type: "claude", etc.
    command: str = "claude"  # Command to execute
    model: str | None = None
    system_prompt: str | None = None
    api_key_env_var: str = "ANTHROPIC_API_KEY"
    max_retries: int = 2
    retry_delay_ms: int = 1000
    timeout_seconds: int = 30


class CLIProvider(InferenceProvider):
    """Claude Code CLI inference provider.

    This provider integrates with the Claude CLI for non-interactive
    inference requests with security-focused input sanitization.
    """

    def __init__(self, config: CLIProviderConfig):
        """Initialize CLI provider.

        Args:
            config: CLI provider configuration

        Raises:
            RuntimeError: If CLI is not available
        """
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self._error_count = 0
        self._last_health_check = 0.0
        self._validate_cli_availability()

    def _validate_cli_availability(self) -> None:
        """Check if Claude CLI is available.

        Raises:
            RuntimeError: If CLI is not available or not in PATH
        """
        try:
            result = subprocess.run(
                [self.config.command, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise RuntimeError(f"{self.config.command} CLI not available")
        except FileNotFoundError as e:
            raise RuntimeError(f"{self.config.command} CLI not found in PATH") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"{self.config.command} CLI timeout during version check"
            ) from e

    async def evaluate(self, request: InferenceRequest) -> InferenceDecision:
        """Evaluate using Claude CLI in non-interactive mode.

        Args:
            request: The inference request to evaluate

        Returns:
            InferenceDecision with evaluation results

        Raises:
            SuperegoError: If CLI evaluation fails
        """
        start_time = time.perf_counter()

        # Sanitize and build CLI command
        cmd, prompt_text = self._build_cli_command(request)
        
        # Debug: Log the CLI command being executed
        self.logger.info(
            "Executing CLI command",
            command=" ".join(cmd),
            prompt_length=len(prompt_text),
            prompt_preview=prompt_text[:100] + "..." if len(prompt_text) > 100 else prompt_text,
        )

        retry_count = 0
        last_error = None

        while retry_count <= self.config.max_retries:
            try:
                # Execute CLI command with pipe input
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=self._get_cli_env(),
                )

                # Send prompt via stdin and wait for completion with timeout
                actual_timeout = min(request.timeout_seconds, 30)  # Cap at 30 seconds for faster failure detection
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt_text.encode('utf-8')), timeout=actual_timeout
                )

                if proc.returncode != 0:
                    error_msg = stderr.decode("utf-8", errors="ignore")
                    if not error_msg.strip():
                        error_msg = "CLI command failed with no error output (possible timeout)"
                    raise RuntimeError(f"CLI failed: {error_msg}")

                # Parse JSON response
                response_text = stdout.decode("utf-8", errors="ignore")
                
                # Debug: Log the raw CLI response
                self.logger.info(
                    "Raw CLI response",
                    response_length=len(response_text),
                    response_preview=response_text[:500] if response_text else "(empty)",
                )
                
                if not response_text.strip():
                    raise RuntimeError("CLI returned empty response (possible timeout or execution failure)")
                    
                response = self._parse_json_response(response_text)
                response_time_ms = int((time.perf_counter() - start_time) * 1000)

                decision = self._parse_cli_response(response, response_time_ms)

                # Reset error count on success
                self._error_count = 0

                return decision

            except TimeoutError as e:
                last_error = e
                self._error_count += 1
                raise SuperegoError(
                    ErrorCode.AI_SERVICE_TIMEOUT,
                    f"{self.config.command} CLI timeout",
                    "Inference request timed out",
                ) from e
            except Exception as e:
                last_error = e
                self._error_count += 1
                retry_count += 1

                if retry_count <= self.config.max_retries:
                    self.logger.warning(
                        "CLI execution failed, retrying",
                        error=str(e),
                        retry=retry_count,
                        max_retries=self.config.max_retries,
                    )
                    await asyncio.sleep(self.config.retry_delay_ms / 1000.0)
                    continue

                self.logger.error("CLI execution failed", error=str(e))
                raise SuperegoError(
                    ErrorCode.AI_SERVICE_UNAVAILABLE,
                    f"CLI execution failed: {str(e)}",
                    "Inference service temporarily unavailable",
                ) from e

        # Should not reach here, but for type safety
        raise SuperegoError(
            ErrorCode.AI_SERVICE_UNAVAILABLE,
            f"CLI execution failed after {self.config.max_retries} retries: {str(last_error)}",
            "Inference service temporarily unavailable",
        )

    def _build_cli_command(self, request: InferenceRequest) -> tuple[list[str], str]:
        """Build Claude CLI command with security restrictions using streaming JSON input.

        Args:
            request: The inference request

        Returns:
            Tuple of (command arguments, JSON message for stdin)
        """
        # Sanitize prompt to prevent command injection
        sanitized_prompt = self._sanitize_prompt(request.prompt)

        # Create simplified prompt for better CLI compatibility
        simple_prompt = f"Should this operation be allowed? {sanitized_prompt[:500]}... Reply with JSON containing 'decision' (allow/deny), 'reasoning', and 'confidence' (0.0-1.0)."
        
        # Build streaming JSON command
        cmd = [
            self.config.command,
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
        ]

        # Add system prompt if configured
        if self.config.system_prompt:
            sanitized_system = self._sanitize_prompt(self.config.system_prompt)
            cmd.extend(["--append-system-prompt", sanitized_system])

        # Add model if specified
        if self.config.model:
            # Validate model name to prevent injection
            if self._is_valid_model_name(self.config.model):
                cmd.extend(["--model", self.config.model])

        # Create JSON message in Claude CLI streaming format
        json_message = {
            "type": "user",
            "message": {
                "role": "user", 
                "content": [
                    {
                        "type": "text",
                        "text": simple_prompt
                    }
                ]
            }
        }

        # Convert to JSONL format (single line JSON)
        import json
        jsonl_input = json.dumps(json_message, separators=(',', ':'))

        return cmd, jsonl_input

    def _sanitize_prompt(self, prompt: str) -> str:
        """Sanitize prompt text to prevent command injection.

        Args:
            prompt: Raw prompt text

        Returns:
            Sanitized prompt text safe for CLI usage
        """
        if not isinstance(prompt, str):
            prompt = str(prompt)

        # Remove null bytes and control characters that could cause issues
        sanitized = prompt.replace("\x00", "").replace("\r\n", "\n")

        # Remove other control characters except newlines and tabs
        sanitized = "".join(c for c in sanitized if c.isprintable() or c in "\n\t")

        # Limit length to prevent DoS
        if len(sanitized) > 10000:
            sanitized = sanitized[:10000] + "... [truncated for security]"

        return sanitized

    def _is_valid_model_name(self, model: str) -> bool:
        """Validate model name to prevent injection.

        Args:
            model: Model name to validate

        Returns:
            True if model name is safe to use
        """
        import re

        # Allow only alphanumeric, hyphens, underscores, and dots
        return bool(re.match(r"^[a-zA-Z0-9._-]+$", model)) and len(model) < 100

    def _get_cli_env(self) -> dict[str, str]:
        """Get environment for CLI execution.

        Returns:
            Environment variables for CLI execution

        Raises:
            RuntimeError: If required API key is not found
        """
        env = os.environ.copy()

        # Set API key if available (optional - CLI can use OAuth)
        if self.config.api_key_env_var:
            api_key = os.getenv(self.config.api_key_env_var)
            if api_key:
                # Don't expose the key in logs, just set it if available
                env["ANTHROPIC_API_KEY"] = api_key

        # Remove potentially dangerous environment variables
        dangerous_vars = [
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "PYTHON_PATH",
        ]
        for var in dangerous_vars:
            env.pop(var, None)

        return env

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """Parse streaming JSON response from CLI.

        Args:
            response_text: Raw response text from CLI (multiple JSON objects)

        Returns:
            Parsed JSON response (the result object)

        Raises:
            ValueError: If response is not valid JSON
        """
        try:
            response_text = response_text.strip()
            
            # Streaming JSON format returns multiple JSON objects, one per line
            # We want the final "result" object
            lines = response_text.split('\n')
            result_obj = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    json_obj = json.loads(line)
                    # Look for the final result object
                    if json_obj.get("type") == "result":
                        result_obj = json_obj
                        break
                    # Also look for assistant messages as fallback
                    elif json_obj.get("type") == "assistant":
                        result_obj = json_obj
                except json.JSONDecodeError:
                    continue
            
            if result_obj:
                return result_obj
            
            # Fallback: try to parse as single JSON object
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse CLI streaming JSON response",
                error=str(e),
                response_preview=response_text[:200],
            )
            raise ValueError(f"Invalid JSON response from CLI: {str(e)}") from e

    def _parse_cli_response(
        self, response: dict[str, Any], response_time_ms: int
    ) -> InferenceDecision:
        """Parse CLI streaming JSON response into InferenceDecision.

        Args:
            response: Parsed JSON response from CLI
            response_time_ms: Response time in milliseconds

        Returns:
            InferenceDecision object
        """
        # Claude CLI with --output-format stream-json returns different format
        # Look for content in message structure or fallback to result field
        content = ""
        
        if "message" in response and "content" in response["message"]:
            # Extract text content from message content array
            message_content = response["message"]["content"]
            if isinstance(message_content, list):
                for item in message_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        content += item.get("text", "")
            elif isinstance(message_content, str):
                content = message_content
        else:
            # Fallback to other possible content locations
            content = response.get("result", response.get("content", ""))

        # Extract decision from response content
        decision_data = self._extract_decision_from_content(content)

        return InferenceDecision(
            decision=decision_data.get(
                "decision", "deny"
            ),  # Default to deny for safety
            confidence=float(decision_data.get("confidence", 0.7)),
            reasoning=decision_data.get(
                "reasoning", content[:500] if content else "No reasoning provided"
            ),
            risk_factors=decision_data.get("risk_factors", []),
            provider=f"{self.config.type}_cli",
            model=self.config.model or f"{self.config.type}-default",
            response_time_ms=response_time_ms,
        )

    def _extract_decision_from_content(self, content: str) -> dict[str, Any]:
        """Extract structured decision data from response content.

        Args:
            content: Response content from CLI

        Returns:
            Dictionary with extracted decision data
        """
        decision_data: dict[str, Any] = {
            "decision": "deny",  # Safe default
            "confidence": 0.5,
            "reasoning": "Unable to parse response",
            "risk_factors": [],
        }

        if not content:
            return decision_data

        # Try to parse JSON from content first
        try:
            json_start = content.find("{")
            json_end = content.rfind("}")

            if json_start != -1 and json_end > json_start:
                json_str = content[json_start : json_end + 1]
                parsed = json.loads(json_str)
                if isinstance(parsed, dict):
                    decision_data.update(parsed)
                    return decision_data
        except json.JSONDecodeError:
            pass

        # Fallback to text parsing
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("DECISION:"):
                decision = line.split(":", 1)[1].strip().lower()
                decision_data["decision"] = "allow" if decision == "allow" else "deny"
            elif line.startswith("REASON:") or line.startswith("REASONING:"):
                decision_data["reasoning"] = line.split(":", 1)[1].strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence_str = line.split(":", 1)[1].strip()
                    decision_data["confidence"] = float(confidence_str)
                except (ValueError, IndexError):
                    pass

        # Use the full content as reasoning if no specific reasoning found
        if decision_data["reasoning"] == "Unable to parse response" and content:
            decision_data["reasoning"] = content[:500]

        return decision_data

    def get_provider_info(self) -> ProviderInfo:
        """Get provider information.

        Returns:
            ProviderInfo with metadata about this CLI provider
        """
        return ProviderInfo(
            name=self.config.name,
            type="cli",
            models=[self.config.model]
            if self.config.model
            else [f"{self.config.type}-default"],
            capabilities={
                "non_interactive": True,
                "json_output": True,
                "security_restricted": True,
                "command": self.config.command,
            },
        )

    async def health_check(self) -> HealthStatus:
        """Check provider health.

        Returns:
            HealthStatus indicating current health of the CLI provider
        """
        current_time = time.time()
        self._last_health_check = current_time

        try:
            # Quick version check to ensure CLI is available
            result = subprocess.run(
                [self.config.command, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # CLI is available - it could be using OAuth or API key
                api_key = os.getenv(self.config.api_key_env_var) if self.config.api_key_env_var else None
                auth_method = "API key" if api_key else "OAuth/CLI auth"
                
                return HealthStatus(
                    healthy=True,
                    message=f"{self.config.command} CLI available ({auth_method})",
                    last_check=current_time,
                    error_count=self._error_count,
                )
            else:
                return HealthStatus(
                    healthy=False,
                    message=f"{self.config.command} CLI check failed",
                    last_check=current_time,
                    error_count=self._error_count,
                )

        except Exception as e:
            return HealthStatus(
                healthy=False,
                message=f"Health check failed: {str(e)}",
                last_check=current_time,
                error_count=self._error_count,
            )

    async def initialize(self) -> None:
        """Initialize CLI provider resources."""
        # CLI provider is initialized in __init__, no additional setup needed
        pass

    async def cleanup(self) -> None:
        """Cleanup CLI provider resources."""
        # CLI provider doesn't maintain persistent resources
        pass


class MCPSamplingProvider(InferenceProvider):
    """Wrapper for existing MCP Sampling functionality.

    This provider wraps the existing AIServiceManager to provide
    backward compatibility with the new inference provider interface.
    """

    def __init__(
        self, ai_service_manager: AIServiceManager, prompt_builder: SecurePromptBuilder
    ):
        """Initialize MCP sampling provider.

        Args:
            ai_service_manager: Existing AI service manager
            prompt_builder: Secure prompt builder
        """
        self.ai_service_manager = ai_service_manager
        self.prompt_builder = prompt_builder
        self.logger = structlog.get_logger(__name__)

    async def evaluate(self, request: InferenceRequest) -> InferenceDecision:
        """Delegate to existing AI service manager.

        Args:
            request: The inference request to evaluate

        Returns:
            InferenceDecision with evaluation results from MCP sampling

        Raises:
            SuperegoError: If MCP sampling fails
        """
        try:
            # Use existing implementation
            ai_decision = await self.ai_service_manager.evaluate_with_ai(
                prompt=request.prompt, cache_key=request.cache_key
            )

            # Convert to standard format
            return InferenceDecision(
                decision=ai_decision.decision,
                confidence=ai_decision.confidence,
                reasoning=ai_decision.reasoning,
                risk_factors=ai_decision.risk_factors,
                provider=f"mcp_{ai_decision.provider.value}",
                model=ai_decision.model,
                response_time_ms=ai_decision.response_time_ms,
            )
        except Exception as e:
            self.logger.error("MCP sampling failed", error=str(e))
            raise

    def get_provider_info(self) -> ProviderInfo:
        """Get provider information.

        Returns:
            ProviderInfo with metadata about the MCP sampling provider
        """
        # Get health status to determine available models
        health = self.ai_service_manager.get_health_status()
        services = health.get("services_initialized", [])

        models = []
        if "claude" in str(services):
            models.append(self.ai_service_manager.config.claude_model)
        if "openai" in str(services):
            models.append(self.ai_service_manager.config.openai_model)

        return ProviderInfo(
            name="mcp_sampling",
            type="mcp_sampling",
            models=models,
            capabilities={
                "caching": True,
                "fallback": True,
                "circuit_breaker": health.get("circuit_breaker_state") is not None,
                "providers": services,
            },
        )

    async def health_check(self) -> HealthStatus:
        """Check provider health.

        Returns:
            HealthStatus indicating MCP sampling provider health
        """
        try:
            health_data = self.ai_service_manager.get_health_status()

            # Determine health based on service status
            enabled = health_data.get("enabled", False)
            services = health_data.get("services_initialized", [])

            if not enabled:
                return HealthStatus(
                    healthy=False,
                    message="MCP sampling is disabled",
                    last_check=time.time(),
                    error_count=0,
                )

            if not services:
                return HealthStatus(
                    healthy=False,
                    message="No AI services initialized",
                    last_check=time.time(),
                    error_count=0,
                )

            return HealthStatus(
                healthy=True,
                message=f"MCP sampling available with {len(services)} service(s)",
                last_check=time.time(),
                error_count=0,
            )

        except Exception as e:
            return HealthStatus(
                healthy=False,
                message=f"Health check failed: {str(e)}",
                last_check=time.time(),
                error_count=1,
            )

    async def initialize(self) -> None:
        """Initialize MCP sampling provider resources."""
        # MCP provider uses existing AI service manager, no additional setup needed
        pass

    async def cleanup(self) -> None:
        """Cleanup MCP sampling provider resources."""
        # MCP provider delegates to AI service manager for cleanup
        pass


class MockInferenceProvider(InferenceProvider):
    """Mock inference provider for testing and standalone evaluation.
    
    This provider implements simple rule-based evaluation without requiring
    external AI services. It's designed for quick validation and testing
    scenarios where deterministic behavior is desired.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize mock inference provider.

        Args:
            config: Optional configuration for mock behavior
        """
        self.config = config or {}
        self.logger = structlog.get_logger(__name__)
        
        # Configurable dangerous patterns
        self.dangerous_patterns = self.config.get("dangerous_patterns", [
            "rm -rf",
            "/etc/passwd", 
            "/etc/shadow",
            "sudo rm",
            "chmod 777",
            "wget http://",
            "curl http://",
            "nc -l",
            "netcat",
            "> /dev/",
            "dd if=",
            "mkfs",
            "fdisk",
            "format",
            "del /s",
            "rmdir /s"
        ])
        
        # Configurable system paths to protect
        self.protected_paths = self.config.get("protected_paths", [
            "/etc/",
            "/var/log/",
            "/boot/",
            "/sys/",
            "/proc/",
            "C:\\Windows\\",
            "C:\\Program Files\\",
            "C:\\System32\\"
        ])

    async def evaluate(self, request: InferenceRequest) -> InferenceDecision:
        """Evaluate using simple pattern matching rules.

        Args:
            request: The inference request to evaluate

        Returns:
            InferenceDecision with deterministic evaluation results
        """
        start_time = time.perf_counter()
        
        # Convert request to searchable text
        search_text = self._extract_searchable_text(request)
        
        # Check for dangerous patterns
        danger_found = None
        for pattern in self.dangerous_patterns:
            if pattern.lower() in search_text.lower():
                danger_found = pattern
                break
        
        # Check for protected paths
        protected_path_found = None
        for path in self.protected_paths:
            if path.lower() in search_text.lower():
                protected_path_found = path
                break
        
        response_time_ms = int((time.perf_counter() - start_time) * 1000)
        
        if danger_found:
            return InferenceDecision(
                decision="deny",
                confidence=0.9,
                reasoning=f"Detected dangerous pattern '{danger_found}' in tool request",
                risk_factors=["dangerous_command", "security_risk"],
                provider="mock_inference",
                model="pattern-matcher-v1",
                response_time_ms=response_time_ms,
            )
        elif protected_path_found:
            return InferenceDecision(
                decision="deny", 
                confidence=0.8,
                reasoning=f"Access to protected path '{protected_path_found}' is not allowed",
                risk_factors=["protected_path_access", "system_modification"],
                provider="mock_inference",
                model="pattern-matcher-v1",
                response_time_ms=response_time_ms,
            )
        else:
            return InferenceDecision(
                decision="allow",
                confidence=0.7,
                reasoning="No dangerous patterns detected, operation appears safe",
                risk_factors=[],
                provider="mock_inference", 
                model="pattern-matcher-v1",
                response_time_ms=response_time_ms,
            )

    def _extract_searchable_text(self, request: InferenceRequest) -> str:
        """Extract text from request for pattern matching.
        
        Args:
            request: The inference request
            
        Returns:
            Combined text for searching
        """
        text_parts = [
            request.prompt,
            request.tool_request.tool_name,
            str(request.tool_request.parameters)
        ]
        
        return " ".join(str(part) for part in text_parts if part)

    def get_provider_info(self) -> ProviderInfo:
        """Get provider information.

        Returns:
            ProviderInfo with mock provider metadata
        """
        return ProviderInfo(
            name="mock_inference",
            type="mock",
            models=["pattern-matcher-v1"],
            capabilities={
                "deterministic": True,
                "fast": True,
                "no_external_deps": True,
                "pattern_count": len(self.dangerous_patterns),
                "protected_paths_count": len(self.protected_paths),
            },
        )

    async def health_check(self) -> HealthStatus:
        """Check provider health.

        Returns:
            HealthStatus indicating mock provider is always healthy
        """
        return HealthStatus(
            healthy=True,
            message=f"Mock provider operational with {len(self.dangerous_patterns)} patterns",
            last_check=time.time(),
            error_count=0,
        )

    async def initialize(self) -> None:
        """Initialize mock provider resources."""
        # Mock provider needs no initialization
        self.logger.info("Mock inference provider initialized", 
                        patterns=len(self.dangerous_patterns),
                        protected_paths=len(self.protected_paths))

    async def cleanup(self) -> None:
        """Cleanup mock provider resources."""
        # Mock provider has no resources to cleanup
        pass


class APIProvider(InferenceProvider):
    """Placeholder for future direct API provider implementation.

    This is a placeholder class for direct API integration with
    AI providers. Implementation is planned for future releases.
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize API provider.

        Args:
            config: API provider configuration
        """
        self.config = config
        self.logger = structlog.get_logger(__name__)

    async def evaluate(self, request: InferenceRequest) -> InferenceDecision:
        """Evaluate using direct API calls.

        Args:
            request: The inference request to evaluate

        Returns:
            InferenceDecision with evaluation results

        Raises:
            NotImplementedError: This is a placeholder implementation
        """
        # TODO: Implement direct API provider
        raise NotImplementedError(
            "Direct API provider is not yet implemented. "
            "Please use MCP sampling or CLI providers."
        )

    def get_provider_info(self) -> ProviderInfo:
        """Get provider information.

        Returns:
            ProviderInfo indicating this is a placeholder
        """
        return ProviderInfo(
            name="api_placeholder",
            type="api",
            models=["TODO"],
            capabilities={"implemented": False, "planned": True},
        )

    async def health_check(self) -> HealthStatus:
        """Check provider health.

        Returns:
            HealthStatus indicating this is not implemented
        """
        return HealthStatus(
            healthy=False,
            message="API provider is not yet implemented",
            last_check=time.time(),
            error_count=0,
        )

    async def initialize(self) -> None:
        """Initialize API provider resources."""
        # API provider not yet implemented
        pass

    async def cleanup(self) -> None:
        """Cleanup API provider resources."""
        # API provider not yet implemented
        pass


class InferenceConfig(BaseModel):
    """Configuration for the inference system."""

    timeout_seconds: int = 30
    provider_preference: list[str] = Field(default_factory=lambda: ["mcp_sampling"])
    cli_providers: list[CLIProviderConfig] = Field(default_factory=list)
    api_providers: list[dict[str, Any]] = Field(default_factory=list)  # For future use


class InferenceStrategyManager:
    """Manages inference provider selection and execution.

    This class handles provider initialization, selection based on
    preferences, and fallback logic when providers fail.
    """

    def __init__(self, config: InferenceConfig, dependencies: dict[str, Any]):
        """Initialize inference strategy manager.

        Args:
            config: Inference configuration
            dependencies: Dictionary containing ai_service_manager, prompt_builder, etc.
        """
        self.config = config
        self.dependencies = dependencies
        self.logger = structlog.get_logger(__name__)
        self.providers: dict[str, InferenceProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize configured providers."""
        # Always initialize MCP provider for backward compatibility
        ai_service_manager = self.dependencies.get("ai_service_manager")
        prompt_builder = self.dependencies.get("prompt_builder")

        if ai_service_manager and prompt_builder:
            self.providers["mcp_sampling"] = MCPSamplingProvider(
                ai_service_manager, prompt_builder
            )
            self.logger.info("Initialized MCP sampling provider")
        else:
            self.logger.warning(
                "MCP sampling provider not available",
                has_ai_service=ai_service_manager is not None,
                has_prompt_builder=prompt_builder is not None,
            )

        # Initialize CLI providers if configured
        for cli_config in self.config.cli_providers:
            if cli_config.enabled:
                try:
                    provider = CLIProvider(cli_config)
                    self.providers[cli_config.name] = provider
                    self.logger.info("Initialized CLI provider", name=cli_config.name)
                except Exception as e:
                    self.logger.error(
                        "Failed to initialize CLI provider",
                        name=cli_config.name,
                        error=str(e),
                    )

        # Future: Initialize API providers
        # for api_config in self.config.api_providers:
        #     if api_config.get("enabled", False):
        #         provider = APIProvider(api_config)
        #         self.providers[api_config["name"]] = provider

        self.logger.info(
            "Inference provider initialization complete",
            total_providers=len(self.providers),
            provider_names=list(self.providers.keys()),
        )

    async def evaluate(
        self, request: ToolRequest, rule: SecurityRule, prompt: str, cache_key: str
    ) -> InferenceDecision:
        """Evaluate using configured strategy.

        Args:
            request: The tool request being evaluated
            rule: The security rule that triggered inference
            prompt: The evaluation prompt
            cache_key: Cache key for the request

        Returns:
            InferenceDecision from the first successful provider

        Raises:
            SuperegoError: If all providers fail or none are configured
        """
        # Build inference request
        inference_request = InferenceRequest(
            prompt=prompt,
            tool_request=request,
            rule=rule,
            cache_key=cache_key,
            timeout_seconds=self.config.timeout_seconds,
        )

        # Try providers in order of preference
        providers_to_try = self._get_providers_by_preference(rule)

        if not providers_to_try:
            raise SuperegoError(
                ErrorCode.INVALID_CONFIGURATION,
                "No inference providers available",
                "Inference evaluation not available",
            )

        last_error = None
        for provider_name in providers_to_try:
            provider = self.providers.get(provider_name)
            if not provider:
                self.logger.warning(
                    "Configured provider not available", provider=provider_name
                )
                continue

            try:
                self.logger.info(
                    "Attempting inference",
                    provider=provider_name,
                    tool=request.tool_name,
                )

                decision = await provider.evaluate(inference_request)

                self.logger.info(
                    "Inference successful",
                    provider=provider_name,
                    decision=decision.decision,
                    confidence=decision.confidence,
                    response_time_ms=decision.response_time_ms,
                )

                return decision

            except Exception as e:
                last_error = e
                self.logger.warning(
                    "Provider failed, trying next",
                    provider=provider_name,
                    error=str(e),
                    tool=request.tool_name,
                )
                continue

        # All providers failed
        if last_error:
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                f"All inference providers failed: {last_error}",
                "Inference evaluation unavailable",
            )
        else:
            raise SuperegoError(
                ErrorCode.INVALID_CONFIGURATION,
                "No working inference providers found",
                "Inference evaluation not available",
            )

    def _get_providers_by_preference(self, rule: SecurityRule) -> list[str]:
        """Get ordered list of providers to try.

        Args:
            rule: The security rule being evaluated

        Returns:
            List of provider names in preference order
        """
        # Check if rule specifies preferred provider
        preferred_provider = getattr(rule, "inference_provider", None)
        if preferred_provider and preferred_provider in self.providers:
            providers = [preferred_provider]
            # Add fallbacks
            providers.extend(
                [
                    p
                    for p in self.config.provider_preference
                    if p != preferred_provider and p in self.providers
                ]
            )
            return providers

        # Use default preference order, filtering by available providers
        return [p for p in self.config.provider_preference if p in self.providers]

    async def health_check(self) -> dict[str, Any]:
        """Check health of all providers.

        Returns:
            Dictionary with health status of all providers
        """
        health_status = {}

        for name, provider in self.providers.items():
            try:
                status = await provider.health_check()
                health_status[name] = status.model_dump()
            except Exception as e:
                health_status[name] = {
                    "healthy": False,
                    "message": str(e),
                    "error": True,
                    "last_check": time.time(),
                    "error_count": 1,
                }

        # Add summary
        healthy_count = sum(
            1 for status in health_status.values() if status.get("healthy", False)
        )
        health_status["_summary"] = {
            "total_providers": len(self.providers),
            "healthy_providers": healthy_count,
            "overall_healthy": healthy_count > 0,
        }

        return health_status

    async def cleanup(self) -> None:
        """Cleanup all providers."""
        for provider in self.providers.values():
            try:
                await provider.cleanup()
            except Exception as e:
                self.logger.error(
                    "Error during provider cleanup",
                    provider=provider.__class__.__name__,
                    error=str(e),
                )
