# Superego MCP

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked](https://img.shields.io/badge/type_checked-mypy-blue)](http://mypy-lang.org/)

Intelligent tool-call review system for AI agents

## Overview

Superego MCP Server provides a configurable review system to AI agents to reduce the amount of manual approvals needed as well as provide automated guardrails against dangerous operations. It analyzes incoming tool calls against a set of rules and if no rule is matched it defers to another agent for review or escalation to a human.

## Features

- **Rule-based interception**: Define flexible rules using YAML configuration with advanced pattern matching (regex, glob, JSONPath)
- **Multiple actions**: Allow, block, or require approval (sampling) based on configurable policies
- **Claude Code Hooks Integration**: Direct integration with Claude Code for real-time security evaluation
- **Multi-transport Support**: STDIO, HTTP, and SSE transports for flexible deployment
- **Hot reload**: Configuration changes are applied without restart
- **AI-powered evaluation**: Optional AI inference for complex security decisions
- **Performance optimized**: Request batching, caching, and connection pooling
- **Comprehensive monitoring**: Built-in metrics, health checks, and performance dashboard
- **Structured logging**: Comprehensive logging with structured output
- **MCP compatibility**: Full Model Context Protocol support with FastMCP framework

## Quick Start

### Installation

```bash
# Install with uv (recommended)
uv pip install superego-mcp

# Or install from source
git clone https://github.com/toolprint/superego-mcp
cd superego-mcp
uv sync
```

### Basic Usage

1. **Run security evaluation (for Claude Code hooks)**:
   ```bash
   echo '{"tool_name": "bash", "tool_input": {"command": "ls"}}' | superego advise
   ```

2. **Start the MCP server**:
   ```bash
   # Default STDIO transport
   superego mcp
   
   # HTTP transport on custom port
   superego mcp -t http -p 9000
   
   # With custom config
   superego mcp -c ~/.toolprint/superego/config.yaml
   ```

3. **Run interactive demo**:
   ```bash
   just demo-fastagent-simple
   ```

## Claude Code Integration

Superego provides seamless integration with Claude Code through hooks:

### Setup Claude Code Hooks

```bash
# Add hooks for specific tools
superego hooks add --matcher "Bash|Write|Edit|MultiEdit"

# Add universal hook for all tools
superego hooks add --matcher "*"

# Use centralized server mode
superego hooks add --matcher "*" --url http://localhost:8000
```

### Direct Hook Configuration

Add to your Claude Code configuration:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "superego advise",
            "args": ["-c", "~/.toolprint/superego/config.yaml"]
          }
        ]
      }
    ]
  }
}
```

## Configuration

### Server Configuration (`config/server.yaml`)

```yaml
# Server settings
host: "localhost"
port: 8000
debug: false
log_level: "INFO"

# Rule engine settings
rules_file: "config/rules.yaml"
hot_reload: true

# Multi-transport configuration
transport:
  stdio:
    enabled: true
  http:
    enabled: true
    host: "0.0.0.0"
    port: 8000
  sse:
    enabled: true
    port: 8002

# AI inference configuration
inference:
  timeout_seconds: 30
  provider_preference:
    - "claude_cli"
    - "mcp_sampling"
  cli_providers:
    - name: "claude_cli"
      enabled: true
      type: "claude"
      command: "claude"
      model: "claude-sonnet-4-20250514"
```

### Security Rules (`config/rules.yaml`)

```yaml
rules:
  # Block dangerous commands
  - id: "block_destructive_commands"
    priority: 1
    conditions:
      tool_name:
        type: "regex"
        pattern: "^(rm|delete|remove|destroy).*"
    action: "deny"
    reason: "Destructive command pattern detected"
    
  # Protect system directories
  - id: "protect_system_files"
    priority: 2
    conditions:
      parameters:
        path:
          type: "glob"
          pattern: "/etc/**"
    action: "deny"
    reason: "System directory access denied"
    
  # Require approval for file operations
  - id: "sample_file_operations"
    priority: 10
    conditions:
      AND:
        - tool_name: ["edit", "write", "delete"]
        - parameters:
            path:
              type: "regex"
              pattern: "^(?!/tmp/).*$"
    action: "sample"
    reason: "File operation requires AI evaluation"
    sampling_guidance: "Evaluate if this file operation is safe"
```

## Development

### Setup
```bash
# Setup development environment
just dev

# Run tests
just test

# Run with coverage
just test-cov

# Lint and format
just lint
just format

# Type check
just typecheck

# Run all quality checks
just check
```

### Project Structure
```
src/superego_mcp/
├── __init__.py              # Package initialization
├── cli.py                   # Unified CLI interface
├── cli_eval.py              # Evaluation mode implementation  
├── cli_hooks.py             # Claude Code hooks management
├── main.py                  # MCP server entry point
├── main_optimized.py        # Performance-optimized server
├── stdio_main.py            # STDIO transport handler
├── domain/                  # Business logic and models
│   ├── models.py            # Core domain models
│   ├── pattern_engine.py    # Pattern matching engine
│   ├── security_policy.py   # Security evaluation engine
│   ├── services.py          # Domain services
│   ├── repositories.py      # Domain repositories
│   ├── claude_code_models.py # Claude Code hook models
│   └── hook_integration.py  # Hook integration service
├── infrastructure/          # External services and adapters
│   ├── config.py            # Configuration management
│   ├── config_watcher.py    # Hot reload implementation
│   ├── ai_service.py        # AI inference service
│   ├── inference.py         # Extensible inference system
│   ├── circuit_breaker.py   # Circuit breaker pattern
│   ├── metrics.py           # Prometheus metrics
│   ├── performance.py       # Performance optimization
│   └── logging_config.py    # Structured logging setup
└── presentation/            # API and transport layers
    ├── mcp_server.py        # FastMCP server implementation
    ├── http_transport.py    # HTTP/WebSocket transport
    ├── sse_transport.py     # Server-sent events transport
    ├── handlers.py          # Request handlers
    ├── monitoring.py        # Monitoring dashboard
    └── server.py            # Transport server orchestration
```

### Testing

```bash
# Run specific test file
just test-file tests/test_security_policy.py

# Run integration tests
uv run pytest tests/test_mcp_server_integration.py -v

# Run performance tests
just test-performance

# Run load tests
just load-test
```

### Performance Optimization

```bash
# Run optimized server
just run-optimized

# Run performance demo
just demo-performance

# Benchmark rule evaluation
just benchmark-rules
```

## API Documentation

### CLI Commands

- `superego advise` - One-off security evaluation for Claude Code hooks
- `superego mcp` - Launch the FastMCP server
- `superego hooks` - Manage Claude Code hook configurations

### Tool Request Format

```json
{
  "tool_name": "string",
  "tool_input": {
    "parameter1": "value1",
    "parameter2": "value2"
  },
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "hook_event_name": "PreToolUse"
}
```

### Security Decision Response

```json
{
  "decision": "allow|deny|sample",
  "confidence": 0.95,
  "reasoning": "Explanation of the decision",
  "risk_factors": ["risk1", "risk2"],
  "matched_rules": ["rule_id1", "rule_id2"]
}
```

## Monitoring

Access the monitoring dashboard at `http://localhost:9090/dashboard` when running with metrics enabled.

Metrics available:
- Request volume by tool type
- Decision distribution (allow/deny/sample)
- Processing times
- AI inference latency
- Error rates

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure proper Python path setup
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/src
   ```

2. **Hook timeouts**: Check Superego service availability
   ```bash
   superego mcp --debug
   ```

3. **AI inference failures**: Verify API keys are set
   ```bash
   export ANTHROPIC_API_KEY=your-key-here
   ```

### Debug Mode

Enable debug logging:
```bash
superego mcp --debug
```

### Logs Location

- Server logs: `stderr` (structured JSON format)
- Hook operations: `/tmp/superego_hook.log`
- Metrics: `http://localhost:9090/metrics`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow conventional commits format
- Ensure all tests pass (`just check`)
- Add tests for new features
- Update documentation as needed
- Maintain type safety with mypy

## License

MIT License - see [LICENSE](LICENSE) file for details

## Links

- [Repository](https://github.com/toolprint/superego-mcp)
- [Issues](https://github.com/toolprint/superego-mcp/issues)
- [PyPI Package](https://pypi.org/project/superego-mcp/)
- [Documentation](https://github.com/toolprint/superego-mcp/tree/main/docs)