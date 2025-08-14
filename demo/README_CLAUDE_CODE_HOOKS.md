# Claude Code Hook Integration with Superego MCP

This document describes how to use Claude Code's hook system to integrate with Superego MCP for real-time security evaluation of MCP tool calls.

## Overview

Instead of relying on CLI inference, this integration uses **Claude Code hooks** to intercept MCP tool calls and send them to Superego MCP for security evaluation before execution. This provides:

- **Real-time interception**: Security checks happen automatically for all MCP tool calls
- **No API key required**: Works with Claude Code's OAuth authentication
- **Seamless integration**: No changes needed to existing MCP servers
- **Comprehensive coverage**: All MCP tools are automatically evaluated

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Claude Code       │───▶│  PreToolUse Hook     │───▶│  Superego MCP       │
│   (MCP Tool Call)   │    │  (security_hook.py)  │    │  (Security Server)  │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
         ▲                           │                           │
         │                           ▼                           ▼
         │                 ┌──────────────────────┐    ┌─────────────────────┐
         └─────────────────│   Allow/Deny         │◀───│   Evaluation        │
                           │   Decision           │    │   (Rules + CLI)     │
                           └──────────────────────┘    └─────────────────────┘
```

## Quick Setup

1. **Start Superego MCP server**:
   ```bash
   cd superego-mcp/demo
   python -m superego_mcp.main --config claude-code-demo.yaml
   ```

2. **Configure Claude Code hooks**:
   ```bash
   ./setup_claude_hooks.sh
   ```

3. **Test the integration**:
   ```bash
   claude "List files in the current directory using filesystem MCP"
   ```

## Authentication Options

### Option A: OAuth (Recommended)
```bash
# Login via OAuth - no API key needed
claude auth login
claude auth status  # Verify authentication
```

### Option B: API Key (Fallback)
```bash
# Only if OAuth is unavailable
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

## Hook Configuration

The setup script creates `~/.claude/hooks.json` with the following configuration:

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

### Key Components:

- **Matcher**: `mcp__.*` captures all MCP tool calls
- **PreToolUse**: Security evaluation before execution
- **PostToolUse**: Audit logging after execution
- **Timeout**: Maximum time for hook execution (fail-closed if exceeded)

## Security Workflow

### 1. Tool Call Initiated
```bash
claude "Delete file /tmp/test.txt using filesystem MCP"
```

### 2. Hook Intercepts Call
The `security_hook.py` receives:
```json
{
  "event": {
    "toolCall": {
      "name": "mcp__filesystem__delete_file",
      "parameters": {"path": "/tmp/test.txt"}
    }
  },
  "sessionId": "abc123"
}
```

### 3. Security Evaluation
Hook sends HTTP POST to Superego MCP:
```bash
POST http://localhost:8000/webhook/tool-intercept
{
  "tool_name": "mcp__filesystem__delete_file",
  "parameters": {"path": "/tmp/test.txt"},
  "metadata": {"session_id": "abc123", "source": "claude_code_hook"}
}
```

### 4. Decision Response
Superego MCP evaluates and responds:
```json
{
  "decision": "allow",
  "reason": "File deletion in temporary directory is permitted",
  "confidence": 0.9,
  "rule_id": "allow_tmp_operations"
}
```

### 5. Enforcement
- **Allow**: Hook exits with code 0, tool executes
- **Deny**: Hook exits with code 1, tool is blocked

### 6. Audit Logging
After execution, `audit_hook.py` logs the result for security audit.

## Example Scenarios

### Safe File Read (Allowed)
```bash
claude "Read /etc/hosts using filesystem MCP"
# ✅ Allowed: Safe system file read
```

### Dangerous Command (Blocked)
```bash
claude "Execute 'rm -rf /' using system MCP"
# ❌ Blocked: Dangerous system command
```

### API Request (Evaluated)
```bash
claude "Fetch data from https://api.github.com using web MCP"
# 🔍 Evaluated: Uses CLI inference to assess risk
```

## Monitoring and Debugging

### Hook Logs
```bash
# Security decisions
tail -f /tmp/superego_hook.log

# Audit trail  
tail -f /tmp/superego_audit.log
```

### Server Logs
```bash
# Start server with debug logging
python -m superego_mcp.main --config claude-code-demo.yaml --log-level DEBUG
```

### Health Checks
```bash
# Check server status
curl http://localhost:8000/health

# Check hook configuration
claude settings show | grep hooks
```

## Troubleshooting

### Common Issues

#### 1. "Hook command failed"
**Cause**: Python script not executable or dependencies missing
**Solution**:
```bash
chmod +x /path/to/security_hook.py
pip3 install requests
```

#### 2. "All tools blocked"
**Cause**: Superego server not running
**Solution**:
```bash
python -m superego_mcp.main --config claude-code-demo.yaml
curl http://localhost:8000/health  # Verify server
```

#### 3. "Authentication failed"
**Cause**: Neither OAuth nor API key configured
**Solution**:
```bash
claude auth login  # Preferred
# OR
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### 4. "Hook timeout"
**Cause**: Network issues or server overload
**Solution**:
```bash
# Increase timeout in hooks.json
"timeout": 30

# Check network connectivity
curl -w "@curl-format.txt" http://localhost:8000/health
```

### Debug Mode

Enable detailed logging by editing the hook scripts:

```python
# In security_hook.py and audit_hook.py
DEBUG = True  # Enable debug logging
```

## Configuration Customization

### Security Rules
Edit `demo/config/rules-cli-demo.yaml` to customize security policies:

```yaml
rules:
  - id: "allow_project_files"
    action: allow
    priority: 10
    conditions:
      parameters: "/home/myuser/myproject/"
    reason: "Allow access to my project directory"
```

### Hook Behavior
Modify hook scripts for custom behavior:

```python
# Skip security for certain tools
if tool_name in ['mcp__debug__ping', 'mcp__health__check']:
    sys.exit(0)  # Always allow

# Custom timeout per tool
timeout = 30 if 'complex_analysis' in tool_name else 10
```

### Server Configuration
Adjust `claude-code-demo.yaml` for your environment:

```yaml
inference:
  timeout_seconds: 20  # Increase for slower networks
  
server:
  port: 8080  # Change port (update hooks accordingly)
```

## Benefits vs CLI Inference

| Feature | Hook Integration | CLI Inference |
|---------|------------------|---------------|
| **API Key Required** | No (OAuth works) | Yes |
| **Tool Coverage** | All MCP tools | Manual per rule |
| **Setup Complexity** | One-time hook setup | Per-rule configuration |
| **Performance** | Network call per tool | CLI process per evaluation |
| **Real-time** | Automatic interception | Rule-based sampling |
| **Audit Trail** | Complete tool history | Evaluation decisions only |

## Security Considerations

1. **Fail-Closed**: Any hook failure blocks the tool call
2. **Timeout Protection**: Hooks have maximum execution time
3. **Network Security**: HTTP communication should use HTTPS in production
4. **Log Security**: Hook logs may contain sensitive tool parameters
5. **Authentication**: OAuth preferred over API keys for security

## Production Deployment

For production use:

1. **Use HTTPS**:
   ```yaml
   server:
     ssl_cert: "/path/to/cert.pem"
     ssl_key: "/path/to/key.pem"
   ```

2. **Secure logs**:
   ```bash
   chmod 600 /tmp/superego_*.log
   # Or use centralized logging
   ```

3. **Monitor performance**:
   ```bash
   curl http://localhost:8000/metrics
   ```

4. **Rate limiting**:
   ```yaml
   server:
     rate_limit: "100/minute"
   ```

## Conclusion

Claude Code's hook integration provides a seamless, OAuth-compatible way to add security evaluation to all MCP tool calls. This approach offers comprehensive coverage with minimal setup complexity, making it ideal for both development and production environments.

For questions or issues, check the [main setup guide](CLAUDE_CODE_SETUP.md) or the [troubleshooting guide](TROUBLESHOOTING_CLI.md).