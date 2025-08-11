# Superego MCP Server

Intelligent tool request interception for AI agents using the Model Context Protocol (MCP).

## Overview

Superego MCP Server provides a configurable interception layer for AI agent tool requests. It analyzes incoming tool calls against a set of rules and can allow, block, modify, or require approval for requests based on configurable policies.

## Features

- **Rule-based interception**: Define flexible rules using YAML configuration
- **Multiple actions**: Allow, block, modify parameters, or require approval
- **Hot reload**: Configuration changes are applied without restart
- **Structured logging**: Comprehensive logging with structured output
- **Health monitoring**: Built-in health checks and metrics
- **MCP compatibility**: Full Model Context Protocol support

## Quick Start

1. **Install dependencies**:
   ```bash
   uv install
   ```

2. **Start the server**:
   ```bash
   just run
   # or
   uv run superego-mcp
   ```

3. **Run the demo**:
   ```bash
   just demo
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
```

### Project Structure
```
src/superego_mcp/
├── domain/          # Business logic and models
├── infrastructure/  # External services and data access
├── presentation/    # MCP server and HTTP endpoints
└── main.py         # Application entry point
```

### Configuration

Configure the server in `config/server.yaml`:
```yaml
host: "localhost"
port: 8000
debug: false
rules_file: "config/rules.yaml"
hot_reload: true
```

Define interception rules in `config/rules.yaml`:
```yaml
rules:
  - id: "block-dangerous-ops"
    name: "Block Dangerous Operations"
    pattern: "(rm|delete|remove)"
    action: "block"
    priority: 100
    enabled: true
```

## License

MIT License