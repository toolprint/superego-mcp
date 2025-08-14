# Inference Provider System

This document describes the new extensible inference provider system in Superego MCP Server, which allows for multiple AI inference modes beyond the original MCP Sampling feature.

## Overview

The inference provider system provides a clean abstraction layer for AI-based security evaluation. It supports:

1. **MCP Sampling** (existing): API-based inference through MCP protocol
2. **CLI Provider** (new): Direct integration with Claude CLI for non-interactive inference
3. **API Provider** (planned): Direct API calls to inference providers
4. **Extensible Framework**: Easy addition of new inference providers

## Architecture

```
SecurityPolicyEngine
        ↓
InferenceStrategyManager
        ↓
InferenceProvider (Interface)
    ↓           ↓           ↓
MCPSampling  CLIProvider  APIProvider
```

### Key Components

- **InferenceProvider**: Abstract base class defining the standard interface
- **InferenceStrategyManager**: Manages provider selection, fallback, and lifecycle
- **MCPSamplingProvider**: Wrapper for existing MCP Sampling functionality
- **CLIProvider**: New CLI integration for direct command-line inference
- **APIProvider**: Placeholder for future direct API integration

## Configuration

### Basic Configuration

Add the `inference` section to your `server.yaml`:

```yaml
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
      command: "claude"
      model: "claude-3-sonnet-20240229"
      system_prompt: |
        You are a security evaluation system...
      api_key_env_var: "ANTHROPIC_API_KEY"
      max_retries: 2
      retry_delay_ms: 1000
      timeout_seconds: 10
```

### Per-Rule Provider Selection

You can specify a preferred inference provider for individual security rules:

```yaml
rules:
  - id: "sample-file-ops"
    priority: 10
    conditions:
      tool_name: "file_operations"
    action: "sample"
    inference_provider: "claude_cli"  # Force CLI for this rule
    sampling_guidance: "Evaluate file operation safety..."
```

### Backward Compatibility

The system maintains full backward compatibility. Existing configurations work without changes:

- If no `inference` section is provided, the system uses MCP sampling as before
- Existing `ai_sampling` configuration continues to work
- Rules without `inference_provider` use the default preference order

## Provider Types

### MCP Sampling Provider

This wraps the existing AI service functionality for backward compatibility.

**Capabilities:**
- ✅ Caching
- ✅ Fallback between Claude/OpenAI
- ✅ Circuit breaker protection
- ✅ Request queuing

**Configuration:**
Uses existing `ai_sampling` configuration section.

### CLI Provider

Integrates with Claude CLI for direct, non-interactive inference.

**Capabilities:**
- ✅ Non-interactive mode
- ✅ JSON output parsing
- ✅ Security restrictions (no file access)
- ✅ Input sanitization
- ✅ Retry logic
- ✅ Health monitoring

**Configuration:**
```yaml
cli_providers:
  - name: "claude_cli"
    enabled: true
    type: "claude"
    command: "claude"
    model: "claude-3-sonnet-20240229"
    system_prompt: "Custom system prompt..."
    api_key_env_var: "ANTHROPIC_API_KEY"
    max_retries: 2
    retry_delay_ms: 1000
    timeout_seconds: 10
```

**Requirements:**
- Claude CLI must be installed and in PATH
- API key must be available in environment
- CLI must support `--output-format json` and `--permission-mode none`

### API Provider (Planned)

Direct API integration with AI providers (not yet implemented).

**Planned Capabilities:**
- 🔄 Direct API calls
- 🔄 Multiple provider support
- 🔄 Request/response transformation
- 🔄 Authentication strategies

## Provider Selection Logic

1. **Rule-specific provider**: If a rule specifies `inference_provider`, try that first
2. **Preference order**: Follow the order in `provider_preference`
3. **Fallback**: If a provider fails, try the next one in the list
4. **Fail-closed**: If all providers fail, deny the request for security

## Security Features

### CLI Provider Security

- **Command injection protection**: All inputs are sanitized
- **No file system access**: CLI runs with `--permission-mode none`
- **Environment isolation**: Dangerous environment variables are removed
- **Timeout protection**: All CLI calls have strict timeouts
- **Retry limits**: Configurable retry attempts with exponential backoff

### Input Sanitization

All prompts and parameters are sanitized to prevent:
- Control character injection
- Path traversal attempts
- Command injection
- DoS through excessive input length

### Response Validation

All inference responses are validated to ensure:
- Decision is either "allow" or "deny"
- Confidence is between 0.0 and 1.0
- Required fields are present
- JSON structure is valid

## Error Handling

The system implements comprehensive error handling:

1. **Provider-level errors**: Individual providers handle their own failures
2. **Fallback logic**: Failed providers trigger fallback to next provider
3. **Fail-closed behavior**: If all providers fail, deny the request
4. **Health monitoring**: Continuous health checks for all providers
5. **Graceful degradation**: System continues operating with reduced functionality

## Health Monitoring

### Provider Health Checks

Each provider implements health checks:

```python
@dataclass
class HealthStatus:
    healthy: bool
    message: str
    last_check: float
    error_count: int
```

### System Health

The `InferenceStrategyManager` provides aggregate health status:

```python
{
    "mcp_sampling": {"healthy": true, "message": "Available"},
    "claude_cli": {"healthy": true, "message": "CLI available"},
    "_summary": {
        "total_providers": 2,
        "healthy_providers": 2,
        "overall_healthy": true
    }
}
```

## Performance Considerations

### CLI Provider Performance

- **Startup cost**: CLI commands have initialization overhead
- **Response time**: Generally faster than API calls for simple requests
- **Concurrency**: Limited by system process limits
- **Caching**: No built-in caching (relies on CLI's caching)

### MCP Sampling Performance

- **Established connections**: Reuses HTTP connections
- **Built-in caching**: Request/response caching
- **Circuit breaker**: Prevents cascade failures
- **Request queuing**: Handles load spikes

### Optimization Tips

1. Order providers by expected performance in `provider_preference`
2. Use CLI providers for simple, fast evaluations
3. Use MCP sampling for complex evaluations requiring caching
4. Set appropriate timeouts based on your performance requirements
5. Monitor provider health and adjust configuration as needed

## Migration Guide

### From MCP Sampling Only

1. **No changes required**: System works with existing configuration
2. **Optional**: Add `inference` section to enable CLI providers
3. **Gradual adoption**: Start with CLI as secondary provider

### Enabling CLI Provider

1. **Install Claude CLI**: Ensure CLI is available in PATH
2. **Set API key**: Configure `ANTHROPIC_API_KEY` environment variable
3. **Update configuration**: Add CLI provider to `inference.cli_providers`
4. **Test configuration**: Verify provider health in monitoring endpoints

### Configuration Example

```yaml
# Add to existing server.yaml
inference:
  provider_preference:
    - "claude_cli"      # Try CLI first
    - "mcp_sampling"    # Keep existing as fallback
  
  cli_providers:
    - name: "claude_cli"
      enabled: true
      command: "claude"
      model: "claude-3-sonnet-20240229"
```

## Troubleshooting

### Common Issues

1. **CLI not found**: Ensure Claude CLI is installed and in PATH
2. **API key missing**: Check environment variable configuration
3. **Permission denied**: Verify CLI has execution permissions
4. **Timeout errors**: Increase timeout values in configuration
5. **JSON parsing errors**: Check CLI output format compatibility

### Debug Mode

Enable debug logging to see provider selection and execution details:

```yaml
log_level: "DEBUG"
```

### Health Check Endpoints

Monitor provider health through the `/health` endpoint:

```bash
curl http://localhost:8000/health
```

## Future Enhancements

### Planned Features

1. **API Provider**: Direct API integration with multiple providers
2. **Local Models**: Support for local inference models
3. **Provider Metrics**: Detailed performance and usage metrics
4. **Dynamic Configuration**: Hot-reload of provider configurations
5. **Load Balancing**: Distribute requests across multiple providers

### Extensibility

The system is designed for easy extension. To add a new provider:

1. Implement the `InferenceProvider` interface
2. Add configuration schema
3. Register in `InferenceStrategyManager`
4. Add tests and documentation

## Examples

See the example configuration files:
- `config/server-cli-example.yaml` - Full CLI provider setup
- `config/rules-inference-example.yaml` - Rules with provider preferences

## Support

For issues or questions about the inference provider system:
1. Check the troubleshooting section above
2. Review the health check endpoints
3. Enable debug logging for detailed diagnostics
4. Consult the example configurations