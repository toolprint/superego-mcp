# AI Inference Options Architecture

## Overview

This document describes the architecture for extending the AI Review step in Superego MCP Server to support multiple inference modes beyond the existing MCP Sampling feature. The design provides a clean abstraction layer that allows choosing between different inference providers while maintaining backward compatibility.

## Motivation

The current implementation only supports AI inference through MCP Sampling API calls. This design introduces:

1. **CLI Mode**: Direct integration with Claude Code CLI for non-interactive inference
2. **API Mode**: Direct API calls to inference providers (future enhancement)
3. **Extensible Framework**: Easy addition of new inference providers

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    SecurityPolicyEngine                      │
│                           (Domain)                           │
└─────────────────────┬───────────────────────────────────────┘
                      │ Uses
┌─────────────────────▼───────────────────────────────────────┐
│                 InferenceStrategyManager                     │
│                    (Infrastructure)                          │
│  - Selects appropriate provider based on configuration       │
│  - Handles fallback logic                                    │
│  - Manages provider lifecycle                                │
└─────────────────────┬───────────────────────────────────────┘
                      │ Delegates to
┌─────────────────────▼───────────────────────────────────────┐
│              InferenceProvider (Interface)                   │
│  + evaluate(request: InferenceRequest) -> InferenceDecision │
│  + get_provider_info() -> ProviderInfo                      │
│  + health_check() -> HealthStatus                           │
└─────────────────────────────────────────────────────────────┘
                      │ Implemented by
        ┌─────────────┴──────────────┬─────────────────────┐
        │                            │                     │
┌───────▼──────────┐ ┌──────────────▼──────────┐ ┌────────▼────────┐
│MCPSamplingProvider│ │    CLIProvider         │ │   APIProvider   │
│   (Existing)      │ │  (Claude CLI, etc)    │ │    (Future)     │
└──────────────────┘ └─────────────────────────┘ └─────────────────┘
```

### Component Details

#### 1. InferenceProvider Interface

```python
from abc import ABC, abstractmethod
from typing import Protocol
from pydantic import BaseModel, Field

class InferenceRequest(BaseModel):
    """Standard inference request format."""
    prompt: str
    tool_request: ToolRequest
    rule: SecurityRule
    cache_key: str
    timeout_seconds: int = 10

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
        """Evaluate an inference request."""
        pass
    
    @abstractmethod
    def get_provider_info(self) -> ProviderInfo:
        """Get provider information."""
        pass
    
    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check provider health."""
        pass
    
    async def initialize(self) -> None:
        """Initialize provider resources."""
        pass
    
    async def cleanup(self) -> None:
        """Cleanup provider resources."""
        pass
```

#### 2. MCPSamplingProvider (Existing Mode Wrapper)

```python
class MCPSamplingProvider(InferenceProvider):
    """Wrapper for existing MCP Sampling functionality."""
    
    def __init__(self, ai_service_manager: AIServiceManager, prompt_builder: PromptBuilder):
        self.ai_service_manager = ai_service_manager
        self.prompt_builder = prompt_builder
        self.logger = structlog.get_logger(__name__)
    
    async def evaluate(self, request: InferenceRequest) -> InferenceDecision:
        """Delegate to existing AI service manager."""
        try:
            # Use existing implementation
            ai_decision = await self.ai_service_manager.evaluate_with_ai(
                prompt=request.prompt,
                cache_key=request.cache_key
            )
            
            # Convert to standard format
            return InferenceDecision(
                decision=ai_decision.decision,
                confidence=ai_decision.confidence,
                reasoning=ai_decision.reasoning,
                risk_factors=ai_decision.risk_factors,
                provider=f"mcp_{ai_decision.provider.value}",
                model=ai_decision.model,
                response_time_ms=ai_decision.response_time_ms
            )
        except Exception as e:
            self.logger.error("MCP sampling failed", error=str(e))
            raise
```

#### 3. CLIProvider (New Claude CLI Integration)

```python
import asyncio
import json
import shlex
from pathlib import Path

class CLIProvider(InferenceProvider):
    """Claude Code CLI inference provider."""
    
    def __init__(self, config: CLIProviderConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self._validate_cli_availability()
    
    def _validate_cli_availability(self) -> None:
        """Check if Claude CLI is available."""
        try:
            result = subprocess.run(
                ["claude", "--version"], 
                capture_output=True, 
                text=True
            )
            if result.returncode != 0:
                raise RuntimeError("Claude CLI not available")
        except FileNotFoundError:
            raise RuntimeError("Claude CLI not found in PATH")
    
    async def evaluate(self, request: InferenceRequest) -> InferenceDecision:
        """Evaluate using Claude CLI in non-interactive mode."""
        start_time = time.perf_counter()
        
        # Build CLI command
        cmd = self._build_cli_command(request)
        
        try:
            # Execute CLI command
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._get_cli_env()
            )
            
            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=request.timeout_seconds
            )
            
            if proc.returncode != 0:
                raise RuntimeError(f"CLI failed: {stderr.decode()}")
            
            # Parse JSON response
            response = json.loads(stdout.decode())
            response_time_ms = int((time.perf_counter() - start_time) * 1000)
            
            return self._parse_cli_response(response, response_time_ms)
            
        except asyncio.TimeoutError:
            raise SuperegoError(
                ErrorCode.AI_SERVICE_TIMEOUT,
                "Claude CLI timeout",
                "Inference request timed out"
            )
        except Exception as e:
            self.logger.error("CLI execution failed", error=str(e))
            raise
    
    def _build_cli_command(self, request: InferenceRequest) -> list[str]:
        """Build Claude CLI command."""
        cmd = [
            "claude",
            "-p", request.prompt,  # Non-interactive mode
            "--output-format", "json",
            "--permission-mode", "none",  # No file system access
        ]
        
        # Add system prompt if configured
        if self.config.system_prompt:
            cmd.extend(["--append-system-prompt", self.config.system_prompt])
        
        # Add model if specified
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        
        # Restrict tools for security
        cmd.extend(["--allowedTools", "none"])
        
        return cmd
    
    def _get_cli_env(self) -> dict[str, str]:
        """Get environment for CLI execution."""
        env = os.environ.copy()
        
        # Ensure API key is set
        if self.config.api_key_env_var:
            api_key = os.getenv(self.config.api_key_env_var)
            if not api_key:
                raise RuntimeError(f"API key not found: {self.config.api_key_env_var}")
            env["ANTHROPIC_API_KEY"] = api_key
        
        return env
    
    def _parse_cli_response(self, response: dict, response_time_ms: int) -> InferenceDecision:
        """Parse CLI JSON response."""
        # Expected format from Claude CLI
        content = response.get("content", "")
        
        # Extract decision from response
        # The CLI response format would need to be standardized
        decision_data = self._extract_decision_from_content(content)
        
        return InferenceDecision(
            decision=decision_data.get("decision", "deny"),
            confidence=decision_data.get("confidence", 0.7),
            reasoning=decision_data.get("reasoning", content),
            risk_factors=decision_data.get("risk_factors", []),
            provider="claude_cli",
            model=self.config.model or "claude-3-sonnet",
            response_time_ms=response_time_ms
        )
```

#### 4. InferenceStrategyManager

```python
class InferenceStrategyManager:
    """Manages inference provider selection and execution."""
    
    def __init__(self, config: InferenceConfig, dependencies: dict[str, Any]):
        self.config = config
        self.dependencies = dependencies
        self.logger = structlog.get_logger(__name__)
        self.providers: dict[str, InferenceProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize configured providers."""
        # Always initialize MCP provider for backward compatibility
        if self.dependencies.get("ai_service_manager"):
            self.providers["mcp_sampling"] = MCPSamplingProvider(
                self.dependencies["ai_service_manager"],
                self.dependencies["prompt_builder"]
            )
        
        # Initialize CLI providers if configured
        for cli_config in self.config.cli_providers:
            if cli_config.enabled:
                provider = CLIProvider(cli_config)
                self.providers[cli_config.name] = provider
        
        # Future: Initialize API providers
        # for api_config in self.config.api_providers:
        #     if api_config.enabled:
        #         provider = APIProvider(api_config)
        #         self.providers[api_config.name] = provider
    
    async def evaluate(
        self, 
        request: ToolRequest, 
        rule: SecurityRule,
        prompt: str,
        cache_key: str
    ) -> InferenceDecision:
        """Evaluate using configured strategy."""
        # Build inference request
        inference_request = InferenceRequest(
            prompt=prompt,
            tool_request=request,
            rule=rule,
            cache_key=cache_key,
            timeout_seconds=self.config.timeout_seconds
        )
        
        # Try providers in order of preference
        providers_to_try = self._get_providers_by_preference(rule)
        
        last_error = None
        for provider_name in providers_to_try:
            provider = self.providers.get(provider_name)
            if not provider:
                continue
            
            try:
                self.logger.info(
                    "Attempting inference",
                    provider=provider_name,
                    tool=request.tool_name
                )
                
                decision = await provider.evaluate(inference_request)
                
                self.logger.info(
                    "Inference successful",
                    provider=provider_name,
                    decision=decision.decision,
                    confidence=decision.confidence
                )
                
                return decision
                
            except Exception as e:
                last_error = e
                self.logger.warning(
                    "Provider failed, trying next",
                    provider=provider_name,
                    error=str(e)
                )
                continue
        
        # All providers failed
        if last_error:
            raise SuperegoError(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                f"All inference providers failed: {last_error}",
                "Inference evaluation unavailable"
            )
        else:
            raise SuperegoError(
                ErrorCode.INVALID_CONFIGURATION,
                "No inference providers configured",
                "Inference evaluation not available"
            )
    
    def _get_providers_by_preference(self, rule: SecurityRule) -> list[str]:
        """Get ordered list of providers to try."""
        # Check if rule specifies preferred provider
        if rule.inference_provider:
            providers = [rule.inference_provider]
            # Add fallbacks
            providers.extend([
                p for p in self.config.provider_preference 
                if p != rule.inference_provider
            ])
            return providers
        
        # Use default preference order
        return self.config.provider_preference
    
    async def health_check(self) -> dict[str, Any]:
        """Check health of all providers."""
        health_status = {}
        
        for name, provider in self.providers.items():
            try:
                status = await provider.health_check()
                health_status[name] = status.model_dump()
            except Exception as e:
                health_status[name] = {
                    "healthy": False,
                    "message": str(e),
                    "error": True
                }
        
        return health_status
```

### Configuration Schema

```yaml
# config/server.yaml
inference:
  # Default timeout for all inference requests
  timeout_seconds: 10
  
  # Provider preference order (first successful wins)
  provider_preference:
    - "claude_cli"      # Try CLI first
    - "mcp_sampling"    # Fallback to MCP
  
  # CLI provider configurations
  cli_providers:
    - name: "claude_cli"
      enabled: true
      type: "claude"
      command: "claude"  # Command to execute
      model: "claude-3-sonnet-20240229"
      system_prompt: |
        You are a security evaluation system. 
        Respond with JSON containing: 
        - decision (allow/deny)
        - confidence (0.0-1.0)
        - reasoning
        - risk_factors array
      api_key_env_var: "ANTHROPIC_API_KEY"
      max_retries: 2
      retry_delay_ms: 1000
  
  # Future: API provider configurations
  api_providers: []
  
  # Backward compatibility: Keep existing ai_sampling config
  ai_sampling:
    enabled: true
    primary_provider: "claude"
    fallback_provider: "openai"
    # ... existing config ...
```

### Integration with SecurityPolicyEngine

Update the `_handle_sampling` method to use the new InferenceStrategyManager:

```python
async def _handle_sampling(
    self, request: ToolRequest, rule: SecurityRule, start_time: float
) -> Decision:
    """Handle sampling action with AI evaluation."""
    # Check if inference is available
    if not self.inference_manager:
        # Fallback for backward compatibility
        if self.ai_service_manager and self.prompt_builder:
            # Use legacy implementation
            return await self._handle_sampling_legacy(request, rule, start_time)
        
        # No inference available
        return Decision(
            action="deny",
            reason=f"Rule {rule.id} requires inference but no providers configured",
            rule_id=rule.id,
            confidence=0.6,
            processing_time_ms=max(1, int((time.perf_counter() - start_time) * 1000))
        )
    
    try:
        # Build secure prompt
        prompt = self.prompt_builder.build_evaluation_prompt(request, rule)
        
        # Generate cache key
        cache_key = self._generate_cache_key(request, rule)
        
        # Get inference decision
        inference_decision = await self.inference_manager.evaluate(
            request=request,
            rule=rule,
            prompt=prompt,
            cache_key=cache_key
        )
        
        # Convert to domain Decision
        processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        
        return Decision(
            action=inference_decision.decision,
            reason=inference_decision.reasoning,
            rule_id=rule.id,
            confidence=inference_decision.confidence,
            processing_time_ms=processing_time_ms,
            ai_provider=inference_decision.provider,
            ai_model=inference_decision.model,
            risk_factors=inference_decision.risk_factors,
        )
        
    except Exception as e:
        self.logger.error(
            "Inference evaluation failed",
            error=str(e),
            rule_id=rule.id,
            tool=request.tool_name,
        )
        
        # Fail closed
        processing_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        return Decision(
            action="deny",
            reason=f"Inference evaluation failed for rule {rule.id} - denying for security",
            rule_id=rule.id,
            confidence=0.5,
            processing_time_ms=processing_time_ms,
        )
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create base `InferenceProvider` interface
2. Implement `InferenceStrategyManager`
3. Create `MCPSamplingProvider` wrapper for existing functionality
4. Update configuration schema

### Phase 2: CLI Provider
1. Implement `CLIProvider` for Claude CLI
2. Add CLI-specific configuration options
3. Implement response parsing logic
4. Add comprehensive error handling

### Phase 3: Integration
1. Update `SecurityPolicyEngine` to use `InferenceStrategyManager`
2. Maintain backward compatibility with existing config
3. Update health check endpoints
4. Add monitoring and metrics

### Phase 4: Testing
1. Unit tests for each provider
2. Integration tests with mocked CLI
3. Fallback scenario testing
4. Performance benchmarks

### Phase 5: Future API Provider
1. Design direct API provider interface
2. Implement authentication strategies
3. Add request/response transformation
4. Support multiple API formats

## Security Considerations

1. **Command Injection**: CLI provider must properly escape all inputs
2. **API Key Management**: Secure storage and rotation of credentials
3. **Timeout Protection**: Prevent hanging requests
4. **Resource Limits**: Prevent resource exhaustion
5. **Audit Trail**: Log all inference decisions
6. **Fail Closed**: Default to deny on any error

## Monitoring and Observability

1. **Metrics**:
   - Inference request count by provider
   - Response times by provider
   - Success/failure rates
   - Cache hit rates
   - Fallback trigger frequency

2. **Logging**:
   - All inference requests and responses
   - Provider selection decisions
   - Errors and fallback events
   - Performance warnings

3. **Health Checks**:
   - Provider availability
   - Response time degradation
   - Error rate thresholds
   - CLI/API connectivity

## Benefits

1. **Flexibility**: Choose inference method based on requirements
2. **Extensibility**: Easy to add new providers
3. **Resilience**: Multiple fallback options
4. **Performance**: CLI mode may be faster for some use cases
5. **Cost Control**: Direct CLI calls may reduce API costs
6. **Future-Proof**: Ready for new inference technologies

## Migration Guide

### For Existing Users
No changes required. The system maintains full backward compatibility with existing `ai_sampling` configuration.

### For CLI Mode Adoption
1. Ensure Claude CLI is installed and accessible
2. Add `cli_providers` configuration
3. Update `provider_preference` to prioritize CLI
4. Test with non-critical rules first
5. Monitor performance and adjust timeouts

### Configuration Example
```yaml
inference:
  provider_preference:
    - "claude_cli"     # New CLI provider
    - "mcp_sampling"   # Existing fallback
  
  cli_providers:
    - name: "claude_cli"
      enabled: true
      model: "claude-3-sonnet-20240229"
  
  # Keep existing config unchanged
  ai_sampling:
    enabled: true
    primary_provider: "claude"
```

## Conclusion

This architecture provides a clean, extensible solution for multiple inference modes while maintaining backward compatibility. The abstraction layer allows for easy addition of new providers and graceful handling of failures, making the system more flexible and resilient.