# Claude Code Setup Guide for Superego MCP

This guide will help you set up and configure the Superego MCP security layer with Claude Code using hook-based tool interception. This approach provides real-time security evaluation of MCP tool calls with seamless integration.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Overview: Hook-Based Security](#overview-hook-based-security)
3. [Quick Start](#quick-start)
4. [Hook Configuration](#hook-configuration)
5. [Detailed Setup](#detailed-setup)
6. [Security Workflow](#security-workflow)
7. [Configuration Walkthrough](#configuration-walkthrough)
8. [Verification](#verification)
9. [Common Issues](#common-issues)
10. [Next Steps](#next-steps)

## Prerequisites

Before starting, ensure you have:

1. **Claude Code installed and authenticated**
   ```bash
   # Verify Claude Code is installed
   claude --version
   
   # Check authentication status (OAuth preferred)
   claude auth status
   
   # If not authenticated, login with OAuth (recommended)
   claude auth login
   ```

2. **Authentication Options** (choose one):
   
   **Option A: OAuth Authentication (Recommended)**
   ```bash
   # Login via OAuth - no API key needed
   claude auth login
   ```
   
   **Option B: API Key Authentication**
   ```bash
   # Only if OAuth is not available
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

3. **Python 3.10+ installed**
   ```bash
   python --version  # Should show 3.10 or higher
   ```

4. **Superego MCP installed**
   ```bash
   # From the project root
   pip install -e .
   ```

5. **MCP servers configured** (for testing tool interception)
   ```bash
   # Example: Install a test MCP server
   pip install mcp-server-filesystem
   ```

## Overview: Hook-Based Security

Superego MCP integrates with Claude Code through hooks that intercept MCP tool calls in real-time:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Code   │───▶│  PreToolUse Hook │───▶│  Superego MCP   │
│                 │    │                  │    │   (Security)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         ▲                        │                       │
         │                        ▼                       ▼
         │              ┌──────────────────┐    ┌─────────────────┐
         └──────────────│   Allow/Deny     │◀───│   Evaluation    │
                        │   Decision       │    │   (CLI/API)     │
                        └──────────────────┘    └─────────────────┘
```

**Key Benefits:**
- **Real-time interception**: Security evaluation before tool execution
- **No API key required**: Works with OAuth authentication
- **Seamless integration**: No changes to existing MCP servers
- **Comprehensive coverage**: All MCP tool calls are evaluated

## Quick Start

Get up and running in under 3 minutes:

```bash
# 1. Navigate to the demo directory
cd superego-mcp/demo

# 2. Verify Claude Code authentication
claude auth status

# 3. Start the Superego MCP server
python -m superego_mcp.main --config claude-code-demo.yaml

# 4. Configure Claude Code hooks (one-time setup)
./setup_claude_hooks.sh

# 5. Test the integration
claude "List files in /etc using the filesystem MCP"
```

## Hook Configuration

The hook configuration file (`~/.claude/hooks.json`) defines how Claude Code intercepts MCP tool calls:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["/path/to/security_hook.py"],
            "timeout": 15
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["/path/to/audit_hook.py"],
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### Hook Components:

- **Matcher Pattern**: `mcp__.*` captures all MCP tool calls
- **PreToolUse**: Security evaluation before execution
- **PostToolUse**: Audit logging after execution
- **Timeout**: Maximum time for hook execution

### Automatic Setup:

Use the provided setup script for easy configuration:

```bash
./setup_claude_hooks.sh
```

This script:
1. Creates the `~/.claude/hooks.json` configuration
2. Makes hook scripts executable
3. Verifies Python dependencies
4. Tests the configuration

## Detailed Setup

### Step 1: Environment Preparation

Create a dedicated environment for the demo:

```bash
# Create and activate a virtual environment
python -m venv superego-demo
source superego-demo/bin/activate  # On Windows: superego-demo\Scripts\activate

# Install dependencies
pip install superego-mcp httpx rich
```

### Step 2: Hook Configuration Setup

Configure Claude Code to send MCP tool calls to Superego for security evaluation:

```bash
# Copy the hook configuration template
cp demo/claude-hooks-config.json ~/.claude/hooks.json

# Or create manually:
mkdir -p ~/.claude
cat > ~/.claude/hooks.json << 'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["/path/to/superego-mcp/demo/hooks/security_hook.py"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
EOF
```

**Verify Hook Configuration:**

```bash
# Check if hooks are configured
claude settings show | grep -i hook

# Test hook execution (with a test MCP server)
claude "List files using filesystem MCP" --dry-run
```

**Authentication Troubleshooting:**

1. **OAuth authentication (preferred)**:
   ```bash
   claude auth status
   # If not authenticated: claude auth login
   ```

2. **API key fallback** (if OAuth unavailable):
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   claude auth status
   ```

### Step 3: Configuration Files

The demo uses two main configuration files:

1. **claude-code-demo.yaml** - Server configuration
2. **config/rules-cli-demo.yaml** - Security rules

Review and customize these files:

```bash
# View the server configuration
cat claude-code-demo.yaml

# Key settings to note:
# - inference.cli_providers[0].command: "claude"
# - inference.cli_providers[0].api_key_env_var: "ANTHROPIC_API_KEY"
# - rules_file: "demo/config/rules-cli-demo.yaml"
```

### Step 4: Starting the Server

Start the Superego MCP server to receive hook notifications:

```bash
# From the demo directory
python -m superego_mcp.main --config claude-code-demo.yaml

# You should see:
# INFO:     Started server process [12345]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Hook endpoint available at /webhook/tool-intercept
```

**Server Options:**

```bash
# Run with debug logging to see hook requests
python -m superego_mcp.main --config claude-code-demo.yaml --log-level DEBUG

# Run on a different port (update hook config accordingly)
python -m superego_mcp.main --config claude-code-demo.yaml --port 8080

# Run with hot-reload (for development)
python -m superego_mcp.main --config claude-code-demo.yaml --reload
```

## Security Workflow

Here's how the complete security workflow operates:

### 1. Tool Call Initiation
```
Claude Code: "List files using filesystem MCP"
↓
MCP Tool Call: mcp__filesystem__list_directory
```

### 2. Hook Interception
```
PreToolUse Hook Triggered
↓
security_hook.py receives tool call data:
{
  "tool_name": "mcp__filesystem__list_directory",
  "parameters": {"path": "/etc"},
  "session_id": "abc123",
  "timestamp": 1703123456.789
}
```

### 3. Security Evaluation
```
Hook → HTTP POST → Superego MCP Server
↓
Superego evaluates using:
- Security rules (allow/deny/sample)
- CLI inference (if sampling required)
- Risk assessment
↓
Response: {"decision": "allow", "reason": "Safe directory listing"}
```

### 4. Decision Enforcement
```
Security Hook receives decision
↓
if decision == "allow":
    exit(0)  # Allow tool execution
else:
    exit(1)  # Block tool execution
```

### 5. Tool Execution (if allowed)
```
Claude Code proceeds with MCP tool call
↓
Filesystem MCP executes list_directory
↓
Results returned to Claude Code
```

### 6. Audit Logging
```
PostToolUse Hook Triggered
↓
audit_hook.py logs execution:
- Tool name and parameters
- Execution result
- Success/failure status
- Timing information
```

### Error Handling:

**Fail-Closed Security**: If any step fails, the system denies the operation:
- Superego MCP server unreachable → DENY
- Hook timeout → DENY
- Invalid response → DENY
- Network error → DENY

**Graceful Degradation**: Audit logging is best-effort and never blocks execution.

## Configuration Walkthrough

### Understanding the Configuration

The `claude-code-demo.yaml` file contains several key sections:

#### 1. Inference Configuration

```yaml
inference:
  timeout_seconds: 15
  provider_preference:
    - "claude_cli"  # Only CLI provider for this demo
  
  cli_providers:
    - name: "claude_cli"
      enabled: true
      command: "claude"
      args: ["-p", "non-interactive", "--format", "json"]
      # ... rest of configuration
```

This configures how Superego calls the Claude CLI for security evaluations.

#### 2. Security Rules

The `config/rules-cli-demo.yaml` file defines security policies:

```yaml
rules:
  - id: "block_system_damage"
    action: deny
    priority: 1
    conditions:
      parameters: "rm -rf /|sudo rm|chmod 777 /"
    reason: "Prevents system-damaging commands"
```

Rules can be:
- **allow**: Immediately allow the operation
- **deny**: Immediately block the operation
- **sample**: Use Claude CLI to evaluate

#### 3. Performance Settings

```yaml
performance:
  caching:
    response_cache_ttl: 600  # Cache for 10 minutes
  request_queue:
    max_size: 100
    timeout_seconds: 30
```

These settings optimize performance for CLI-based inference.

### Customizing for Your Use Case

1. **Adjust timeout values** based on your network speed:
   ```yaml
   inference:
     timeout_seconds: 20  # Increase for slower connections
   ```

2. **Modify security rules** for your environment:
   ```yaml
   rules:
     - id: "allow_my_project_files"
       action: allow
       priority: 10
       conditions:
         parameters: "/home/myuser/myproject/"
   ```

3. **Enable verbose logging** for debugging:
   ```yaml
   demo:
     verbose_inference_logs: true
     include_timing_info: true
   ```

## Verification

### Quick Verification Script

Run the setup verification:

```bash
python setup_verification.py
```

This checks:
- Claude CLI availability
- API key configuration
- Server connectivity
- Basic inference functionality

### Manual Verification Steps

1. **Test CLI inference directly**:
   ```bash
   # This mimics what Superego does internally
   echo '{"tool": "rm", "parameters": "-rf /"}' | \
   claude -p non-interactive --format json \
   "Is this command safe? Respond with JSON: {\"safe\": true/false, \"reason\": \"...\"}"
   ```

2. **Test server health**:
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy", "inference": {"claude_cli": "ready"}}
   ```

3. **Test a security evaluation**:
   ```bash
   curl -X POST http://localhost:8000/intercept \
     -H "Content-Type: application/json" \
     -d '{"tool_name": "read_file", "parameters": {"path": "/etc/passwd"}}'
   ```

## Common Issues

### Issue 1: "Claude CLI not found"

**Symptoms:**
- Error: `command not found: claude`
- Server fails to start with "claude_cli provider failed"

**Solutions:**
1. Ensure Claude CLI is in your PATH:
   ```bash
   export PATH="$PATH:/path/to/claude/bin"
   ```

2. Use full path in configuration:
   ```yaml
   cli_providers:
     - command: "/usr/local/bin/claude"
   ```

### Issue 2: "Authentication not configured"

**Symptoms:**
- Error: `Authentication required`
- CLI returns authentication errors
- Hooks fail with auth errors

**Solutions:**

**Option A: OAuth Authentication (Recommended)**
```bash
# Login via OAuth
claude auth login

# Verify authentication
claude auth status
```

**Option B: API Key Authentication**
```bash
# Set environment variable
export ANTHROPIC_API_KEY="sk-ant-..."

# Add to shell profile for persistence
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
source ~/.bashrc
```

**Hook-specific authentication:**
The security hook inherits authentication from the environment where Claude Code is running.

### Issue 3: "Timeout waiting for inference"

**Symptoms:**
- Requests timeout after 15 seconds
- "Inference timeout" errors in logs

**Solutions:**
1. Increase timeout in configuration:
   ```yaml
   inference:
     timeout_seconds: 30
   ```

2. Check network connectivity:
   ```bash
   time claude -p non-interactive "Hi"
   # Should complete in < 5 seconds
   ```

### Issue 4: "Hook execution failed"

**Symptoms:**
- Error: `Hook command failed`
- MCP tools execute without security checks
- Hook timeout errors

**Solutions:**
1. Check hook script permissions:
   ```bash
   chmod +x /path/to/security_hook.py
   ls -la ~/.claude/hooks.json
   ```

2. Verify Python dependencies:
   ```bash
   python3 -c "import requests, json, sys"
   pip3 install requests
   ```

3. Test hook manually:
   ```bash
   echo '{"event":{"toolCall":{"name":"test","parameters":{}}}}' | \
   python3 /path/to/security_hook.py
   ```

4. Check hook logs:
   ```bash
   tail -f /tmp/superego_hook.log
   tail -f /tmp/superego_audit.log
   ```

### Issue 5: "Superego MCP server unreachable"

**Symptoms:**
- All MCP tools blocked with "Security service unavailable"
- Connection refused errors in hook logs
- Hooks timeout waiting for response

**Solutions:**
1. Verify server is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check server logs:
   ```bash
   python -m superego_mcp.main --config claude-code-demo.yaml --log-level DEBUG
   ```

3. Update hook configuration if using different port:
   ```bash
   # Edit security_hook.py
   SUPEREGO_URL = "http://localhost:8080"  # Match your server port
   ```

## Next Steps

Now that you have Superego MCP running with Claude Code:

1. **Explore the demo scenarios**:
   ```bash
   python claude_code_demo.py --interactive
   ```

2. **Read the scenario documentation**:
   - [CLI Inference Scenarios](CLI_INFERENCE_SCENARIOS.md)
   - [Troubleshooting Guide](TROUBLESHOOTING_CLI.md)

3. **Customize security rules** for your specific use case

4. **Test different MCP tools**:
   ```bash
   # File operations
   claude "Read the contents of /etc/hosts using filesystem MCP"
   
   # System commands (should be blocked)
   claude "Execute 'rm -rf /' using system MCP"
   
   # Network requests
   claude "Fetch data from https://api.github.com using web MCP"
   ```

5. **Monitor hook activity**:
   ```bash
   # Watch security decisions in real-time
   tail -f /tmp/superego_hook.log
   
   # Monitor audit trail
   tail -f /tmp/superego_audit.log
   
   # Check server metrics
   curl http://localhost:8000/metrics
   ```

6. **Customize security rules** for your environment:
   ```yaml
   # Edit demo/config/rules-cli-demo.yaml
   rules:
     - id: "allow_my_project"
       action: allow
       conditions:
         parameters: "/home/myuser/myproject/"
   ```

5. **Monitor performance** at http://localhost:9090/metrics

## Support

- **Documentation**: [Full documentation](../README.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/superego-mcp/issues)
- **Community**: [Discord Server](https://discord.gg/your-server)

Remember: The goal of Superego MCP is to add an intelligent security layer to your AI agent interactions. With Claude Code's CLI inference, you get fast, reliable security evaluations that keep your system safe while allowing legitimate operations.