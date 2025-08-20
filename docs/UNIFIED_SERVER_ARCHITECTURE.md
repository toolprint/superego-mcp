# Unified FastAPI + MCP Server Architecture

## Overview

The unified server architecture combines FastAPI (HTTP/WebSocket) and FastMCP (stdio) protocols in a single process, providing improved performance, simplified deployment, and backward compatibility with existing multi-transport systems.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Unified Server Process                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐        ┌─────────────────────────────────┐ │
│  │   FastAPI App   │        │        FastMCP App             │ │
│  │                 │        │                                 │ │
│  │ HTTP Endpoints  │        │     MCP Tools                   │ │
│  │ WebSocket       │        │     MCP Resources               │ │
│  │ OpenAPI Docs    │        │     STDIO Transport             │ │
│  └─────────────────┘        └─────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│              Shared Internal Evaluation Logic                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ • _evaluate_internal()    • _health_check_internal()        │ │
│  │ • _server_info_internal() • _get_rules_internal()           │ │
│  │ • _get_audit_entries_internal()                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                     Core Services                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │Security      │ │Audit         │ │Health Monitor           │ │
│  │Policy Engine │ │Logger        │ │Error Handler            │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Single Process Deployment
- Both MCP and HTTP protocols run in the same process
- Reduced resource overhead compared to multi-process architecture
- Simplified container deployment and orchestration

### 2. Unified Evaluation Logic
- Common internal methods shared between protocols:
  - `_evaluate_internal()` - Core security evaluation
  - `_health_check_internal()` - Health status monitoring
  - `_server_info_internal()` - Server information
  - `_get_rules_internal()` - Security rules retrieval
  - `_get_audit_entries_internal()` - Audit log access

### 3. Protocol Support
- **MCP Protocol**: FastMCP-based STDIO transport for Claude Code integration
- **HTTP Protocol**: RESTful API endpoints with OpenAPI documentation
- **WebSocket Protocol**: Real-time communication support (via FastAPI)

### 4. Backward Compatibility
- Maintains existing CLI interface
- Preserves all existing MCP tools and resources
- Compatible with existing configuration files
- Seamless migration from multi-transport architecture

## Transport Modes

The unified server supports three transport modes:

### STDIO Mode (Default)
```bash
superego mcp -t stdio
```
- Standard MCP protocol over STDIO
- Optimal for Claude Code hooks integration
- Uses stderr for logging to avoid interfering with MCP communication

### HTTP Mode
```bash
superego mcp -t http -p 8000
```
- Pure HTTP/WebSocket server using FastAPI
- RESTful API with OpenAPI documentation
- Suitable for remote evaluation and web integrations

### Unified Mode (Experimental)
```bash
superego mcp -t unified
```
- Both STDIO and HTTP protocols simultaneously
- Single process handling multiple transport protocols
- Maximum flexibility for diverse client needs

## HTTP API Endpoints

The unified server exposes these HTTP endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/evaluate` | Tool evaluation (same as MCP) |
| POST | `/v1/hooks` | Claude Code hook evaluation |
| GET | `/v1/health` | Health status check |
| GET | `/v1/config/rules` | Current security rules |
| GET | `/v1/audit/recent` | Recent audit entries |
| GET | `/v1/metrics` | Performance metrics |
| GET | `/v1/server-info` | Server information |
| GET | `/docs` | Interactive OpenAPI documentation |
| GET | `/redoc` | Alternative API documentation |
| POST | `/mcp/call` | MCP protocol bridge (planned) |

## MCP Tools and Resources

The unified server provides these MCP tools:

### Tools
- `evaluate_tool_request` - Evaluate security of tool requests
- `health_check` - Check server health status
- `get_server_info` - Get server configuration information

### Resources
- `config://rules` - Current security rules in YAML format
- `audit://recent` - Recent audit entries in JSON format

## Configuration

The unified server uses the existing configuration system:

```yaml
# ~/.toolprint/superego/config.yaml
transport:
  http:
    enabled: true
    host: "localhost"
    port: 8000
    cors_origins: ["*"]
  
inference:
  timeout_seconds: 30
  provider_preference: ["claude_cli"]

ai_sampling:
  enabled: true
  primary_provider: "anthropic"

hot_reload: true
health_check_enabled: true
```

## Performance Benefits

### Memory Efficiency
- Single process reduces memory overhead
- Shared evaluation logic eliminates duplication
- Common service instances across protocols

### Processing Speed
- No inter-process communication overhead
- Direct method calls instead of network requests
- Optimized request routing

### Deployment Simplicity
- Single container for both protocols
- Unified logging and monitoring
- Simplified service discovery

## Usage Examples

### Starting the Server

```bash
# Default STDIO mode for Claude Code
superego mcp

# HTTP mode for web integration
superego mcp -t http -p 8000

# Unified mode (both protocols)
superego mcp -t unified

# With custom configuration
superego mcp -c ~/.toolprint/superego/config.yaml -t unified
```

### HTTP API Usage

```bash
# Tool evaluation
curl -X POST http://localhost:8000/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "bash",
    "parameters": {"command": "ls -la"},
    "agent_id": "test_agent",
    "session_id": "test_session",
    "cwd": "/tmp"
  }'

# Health check
curl http://localhost:8000/v1/health

# View API documentation
open http://localhost:8000/docs
```

### Claude Code Hook Integration

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "curl --json @- http://localhost:8000/v1/hooks",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

## Migration Guide

### From MultiTransportServer

The unified server is a drop-in replacement:

```python
# Old
from superego_mcp.presentation.transport_server import MultiTransportServer
server = MultiTransportServer(...)

# New
from superego_mcp.presentation.unified_server import UnifiedServer
server = UnifiedServer(...)
```

### Configuration Changes

No configuration changes required - the unified server uses the existing configuration format.

### CLI Changes

The CLI maintains full backward compatibility with one addition:

```bash
# New unified transport option
superego mcp -t unified
```

## Testing

The unified server includes comprehensive tests:

```bash
# Run unified server tests
just test-file tests/test_unified_server.py

# Run integration tests
just test-file tests/test_mcp_server_integration.py

# Run all tests
just test
```

## Future Enhancements

### Planned Features
- WebSocket streaming for real-time evaluation
- GraphQL API endpoint for advanced queries
- MCP-over-HTTP bridge for remote MCP clients
- Performance metrics dashboard
- Auto-scaling based on request load

### Performance Optimizations
- Connection pooling for database operations
- Request caching for repeated evaluations
- Async batch processing for multiple requests
- Resource usage monitoring and optimization

## Compatibility

- **Python**: 3.11+
- **FastAPI**: 0.104.0+
- **FastMCP**: 2.0.0+
- **UV**: Compatible with `uv run python` execution model
- **Docker**: Single container deployment ready
- **Claude Code**: Full hook integration support

## Conclusion

The unified server architecture provides a robust, performant, and scalable foundation for the Superego MCP system while maintaining full backward compatibility and simplifying deployment scenarios.