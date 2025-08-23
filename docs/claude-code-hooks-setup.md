# Claude Code Hooks Setup Guide

Complete guide for setting up Superego security hooks with Claude Code.

## Quick Start

For the fastest setup, use the automated hook management:

```bash
# Add basic hook for all tools
superego hooks add

# Add hook for specific dangerous tools (recommended)
superego hooks add --matcher "Bash|Write|Edit|MultiEdit"

# Add hook with centralized server
superego hooks add --url http://localhost:8000
```

## Direct Integration Examples

If you prefer manual configuration, add these to your `~/.claude/settings.json`:

### Basic Local Evaluation

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
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

### Centralized Server Mode

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

### Advanced Multi-Matcher Configuration

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "superego advise",
            "timeout": 10000
          }
        ]
      },
      {
        "matcher": "mcp__.*",
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

## Server Integration

### Starting the MCP Server

For centralized evaluation, first start the Superego MCP server:

```bash
# Default configuration
superego mcp

# Custom configuration
superego mcp -c ~/.toolprint/superego/config.yaml

# HTTP mode on custom port
superego mcp -t http -p 9000
```

### HTTP Endpoint Details

- **Endpoint**: `/v1/hooks`
- **Method**: POST
- **Content-Type**: `application/json`
- **Authentication**: Optional Bearer token

Request format (matches Claude Code PreToolUse hook):
```json
{
  "session_id": "string",
  "transcript_path": "string", 
  "cwd": "string",
  "hook_event_name": "PreToolUse",
  "tool_name": "string",
  "tool_input": {...}
}
```

Response format:
```json
{
  "hook_specific_output": {
    "hook_event_name": "PreToolUse",
    "permission_decision": "allow|ask|deny",
    "permission_decision_reason": "string"
  },
  "decision": "approve|block",
  "reason": "string"
}
```

## Authentication

### Centralized Server with Authentication

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "curl --json @- -H 'Authorization: Bearer YOUR_TOKEN' http://localhost:8000/v1/hooks",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

### Using Environment Variables

```bash
# Set authentication token
export SUPEREGO_AUTH_TOKEN="your-secret-token"

# Hook command using environment variable
curl --json @- -H "Authorization: Bearer ${SUPEREGO_AUTH_TOKEN}" http://localhost:8000/v1/hooks
```

## Common Matchers

| Matcher | Description | Use Case |
|---------|-------------|----------|
| `*` | All tools | Maximum security |
| `Bash\|Write\|Edit\|MultiEdit` | High-risk tools | Recommended for most users |
| `Bash` | Shell commands only | Focus on command execution |
| `Write\|Edit\|MultiEdit` | File operations | Protect file system |
| `mcp__.*` | All MCP tools | MCP server protection |
| `mcp__git.*` | Git operations | Repository safety |

## Fallback Configuration

Enable fallback to local evaluation if server is unavailable:

```bash
# Add hook with fallback enabled
superego hooks add --url http://localhost:8000 --fallback
```

This generates a hook that tries the server first, then falls back to local evaluation:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "curl --json @- http://localhost:8000/v1/hooks --connect-timeout 2 --max-time 5 || superego advise",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

## Configuration Files

### Server Configuration

Create `~/.toolprint/superego/config.yaml`:

```yaml
# Basic server configuration
transport:
  http:
    enabled: true
    host: "localhost"
    port: 8000

# Security rules
rules_file: "~/.toolprint/superego/rules.yaml"

# Inference providers
inference:
  timeout_seconds: 30
  provider_preference: ["claude_cli", "api_fallback"]
  cli_providers:
    - name: "claude_cli"
      enabled: true
      type: "claude"
      command: "claude"
      timeout_seconds: 25
```

### Security Rules

Create `~/.toolprint/superego/rules.yaml`:

```yaml
rules:
  - id: "block_dangerous_commands"
    action: deny
    priority: 1
    conditions:
      parameters: "rm -rf /|sudo rm|chmod 777|dd if="
    reason: "Blocked potentially destructive command"

  - id: "allow_safe_reads"
    action: allow
    priority: 2
    conditions:
      tool_name: "Read"
      parameters: "(?!.*\\.env|.*password|.*secret).*"
    reason: "Safe file read operation"

  - id: "evaluate_complex_operations"
    action: sample
    priority: 3
    conditions:
      tool_name: "Bash|Write|Edit"
    reason: "Complex operation requires AI evaluation"
```

## Troubleshooting

### Hook Not Triggering

1. Check Claude Code settings location:
   ```bash
   ls -la ~/.claude/settings.json
   ```

2. Verify hook syntax:
   ```bash
   # Test hook configuration
   echo '{"tool_name":"test","tool_input":{}}' | superego advise
   ```

3. Check Claude Code logs for hook execution errors

### Server Connection Issues

1. Verify server is running:
   ```bash
   curl http://localhost:8000/v1/health
   ```

2. Check server logs for connection errors

3. Test connectivity:
   ```bash
   # Test the hooks endpoint
   echo '{"tool_name":"test","tool_input":{}}' | curl --json @- http://localhost:8000/v1/hooks
   ```

### Performance Issues

1. Increase hook timeout for complex evaluations
2. Use specific matchers instead of `*` to reduce overhead
3. Consider local mode for faster response times

### Authentication Failures

1. Verify token format and validity
2. Check server authentication configuration
3. Test with curl directly:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/v1/health
   ```

## Best Practices

1. **Start Simple**: Begin with basic local evaluation, then move to centralized if needed
2. **Use Specific Matchers**: Target high-risk tools instead of all tools for better performance
3. **Monitor Logs**: Keep an eye on both hook execution and server logs
4. **Test Thoroughly**: Verify hooks work with your typical Claude Code workflows
5. **Regular Updates**: Keep Superego and Claude Code updated for latest security features

## Migration from Manual Setup

If you have existing manual hooks, you can migrate to the managed system:

```bash
# List current hooks
superego hooks list

# Remove old manual hooks from ~/.claude/settings.json
# Add new managed hooks
superego hooks add --matcher "your-pattern"
```

## Enterprise Deployment

For team/organization deployment:

```bash
# Central server with authentication
superego hooks add --url https://superego.company.com --token ${COMPANY_TOKEN}

# Multiple environments
superego hooks add --url https://superego-dev.company.com --matcher "Bash|Write" 
superego hooks add --url https://superego-prod.company.com --matcher "*" --token ${PROD_TOKEN}
```

## Support

- **CLI Help**: `superego hooks --help`
- **Server Info**: `superego mcp --help`
- **Documentation**: [Project README](../README.md)
- **Issues**: Submit GitHub issues for bugs or feature requests

Remember: The goal is to balance security with productivity. Start with recommended configurations and adjust based on your specific needs and risk tolerance.