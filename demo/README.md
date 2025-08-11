# Superego MCP + FastAgent Demo

This directory contains demo implementations showcasing the integration between FastAgent and the Superego MCP Server for AI tool request security evaluation.

## Overview

The demo demonstrates how Superego MCP server evaluates AI tool requests for security compliance when integrated with FastAgent. All tool requests are intercepted and evaluated in real-time, with decisions to allow, block, or sample operations based on security policies.

## Files

### Configuration
- `fastagent.config.yaml` - FastAgent configuration with Superego MCP server setup
- `security_scenarios.py` - Comprehensive security test scenarios

### Demo Implementations  
- `fastagent_demo.py` - Full FastAgent integration demo (requires fast-agent-mcp package)
- `simple_fastagent_demo.py` - Simplified demo using FastAgent CLI
- `client.py` - Legacy HTTP client demo (for reference)

### Generated Files
- `demo_agent.py` - Auto-generated FastAgent agent definition
- `__init__.py` - Package initialization

## Setup

1. **Install dependencies** (from project root):
   ```bash
   uv sync --extra demo
   ```

2. **Verify FastAgent installation**:
   ```bash
   uv run --extra demo fast-agent --version
   ```

3. **Start Superego MCP server** (in another terminal):
   ```bash
   uv run superego-mcp
   ```

## Running Demos

### Option 1: Simple FastAgent Demo (Recommended)
```bash
cd demo
uv run --extra demo python simple_fastagent_demo.py
```

This provides:
- Automated security scenarios testing
- Interactive FastAgent chat mode
- Real-time security evaluation display

### Option 2: Full FastAgent Integration
```bash
cd demo  
uv run --extra demo python fastagent_demo.py
```

Requires the full fast-agent-mcp package with MCP sampling support.

### Option 3: Using justfile Tasks
```bash
# From project root
just demo-fastagent-simple    # Run simple demo
just demo-fastagent-full      # Run full demo
just demo-scenarios           # Run just the scenarios
```

## Security Scenarios

The demo includes comprehensive security scenarios in four categories:

### 🟢 Safe Operations (Should be ALLOWED)
- Reading user documents
- Directory listing  
- Text search in project files
- Basic system information
- File hash calculation

### 🔴 Dangerous Operations (Should be BLOCKED)
- Deleting system files (`/etc/passwd`)
- Destructive commands (`sudo rm -rf /`)
- Privilege escalation (`sudo su -`)
- Modifying system permissions
- Stopping critical services

### 🟡 Complex Operations (May require SAMPLING/APPROVAL)
- Writing executable scripts
- External API requests
- Database connections
- Package installation
- File encryption

### ⚠️ Suspicious Operations (Should be BLOCKED or heavily scrutinized)
- Obfuscated commands (base64 encoded)
- Credential harvesting attempts
- Covert network communications
- System fingerprinting
- Log manipulation

## Configuration Details

### MCP Server Configuration
The `fastagent.config.yaml` configures FastAgent to connect to Superego MCP via STDIO transport:

```yaml
mcp:
  servers:
    superego:
      command: "uv"
      args: ["run", "python", "-m", "superego_mcp.main"]
      cwd: "/path/to/superego-mcp"
  sampling:
    model: "claude-3-5-sonnet-20241022"
```

### Agent System Prompt
The demo agent is configured to:
- Explain actions before using tools
- Show understanding of security implications
- Demonstrate various operation types
- Respect security decisions
- Be educational about security concepts

## Expected Behavior

When you run the demo, you should see:

1. **Security Evaluation in Real-Time**: Every tool request shows the security decision (ALLOW/BLOCK/SAMPLE) with reasoning

2. **Rule Matching**: Security rules that match are displayed with explanations

3. **Confidence Scores**: Each decision includes a confidence level

4. **Processing Time**: Performance metrics for evaluation speed

5. **Audit Logging**: All decisions are logged for compliance and monitoring

## Troubleshooting

### FastAgent Not Available
If you see "FastAgent not available":
```bash
uv sync --extra demo
```

### MCP Server Connection Issues
Ensure the Superego MCP server is running:
```bash
uv run superego-mcp
```

Check the server is responding:
```bash
curl http://localhost:8000/health
```

### Configuration Issues
Verify the configuration file path and MCP server command in `fastagent.config.yaml`.

### Permission Issues
Make sure you have proper permissions to execute the MCP server and create temporary files.

## Integration Notes

### STDIO Transport
FastAgent connects to Superego MCP using STDIO transport:
- MCP server process is spawned by FastAgent
- Communication happens via stdin/stdout
- Server process terminates when FastAgent disconnects

### Sampling Support
When complex operations require evaluation:
- FastAgent sends sampling request to configured LLM
- Superego MCP provides security context and evaluation
- Human approval may be required for high-risk operations

### Error Handling
The demo includes comprehensive error handling:
- MCP server failures fall back to safe defaults
- Network issues are handled gracefully
- Invalid configurations show clear error messages

## Educational Value

This demo is designed to be educational, showing:
- How AI agents can be secured with policy-based evaluation
- Real-world security scenarios and their classifications
- The balance between functionality and security
- Best practices for AI tool request interception
- Compliance and audit logging requirements

Use this demo to understand and demonstrate enterprise-grade AI security practices.