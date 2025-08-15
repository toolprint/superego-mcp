# Claude Code Integration with Superego MCP

## Overview

The Superego MCP provides a powerful, hook-based security evaluation system for Claude Code tool calls. This integration ensures real-time, intelligent security decisions across all MCP tool interactions.

## Key Features

- **Real-time Security**: Intercept and evaluate all MCP tool calls before execution
- **OAuth Compatible**: Works seamlessly with Claude's authentication
- **Comprehensive Coverage**: Supports all MCP tools
- **Flexible Configuration**: Easily customizable security rules

## Prerequisites

1. **Claude Code CLI**
   ```bash
   claude --version  # Verify installation
   ```

2. **Authentication**
   - **Recommended**: OAuth Authentication
     ```bash
     claude auth login
     claude auth status
     ```
   - **Fallback**: API Key
     ```bash
     export ANTHROPIC_API_KEY="sk-ant-..."
     ```

3. **Python 3.10+**
   ```bash
   python --version
   ```

## Quick Start

1. Start the Superego MCP server:
   ```bash
   python -m superego_mcp.main --config claude-code-demo.yaml
   ```

2. Configure Claude Code hooks:
   ```bash
   ./setup_claude_hooks.sh
   ```

3. Test the integration:
   ```bash
   claude "List files in the current directory using filesystem MCP"
   ```

## Security Workflow

1. **Tool Call Initiation**
   - Claude Code triggers an MCP tool call

2. **Hook Interception**
   - PreToolUse hook captures tool call details

3. **Security Evaluation**
   - Superego MCP server assesses the request
   - Uses predefined rules and CLI inference
   - Decides: Allow, Deny, or Sample

4. **Decision Enforcement**
   - Hook determines whether to proceed or block

5. **Optional Audit Logging**
   - Capture execution details for review

## Configuration

### Security Rules (`config/rules-cli-demo.yaml`)

```yaml
rules:
  - id: "block_system_damage"
    action: deny
    priority: 1
    conditions:
      parameters: "rm -rf /|sudo rm|chmod 777 /"
    reason: "Prevents system-damaging commands"
```

Rule Actions:
- `allow`: Immediately permit the operation
- `deny`: Immediately block the operation
- `sample`: Use Claude CLI for detailed evaluation

### Hook Configuration (`~/.claude/hooks.json`)

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
    ]
  }
}
```

## Common Scenarios

### Safe Operations (Allowed)
```bash
claude "Read /etc/hosts using filesystem MCP"
```

### Dangerous Operations (Blocked)
```bash
claude "Execute 'rm -rf /' using system MCP"
```

### Complex Operations (Evaluated)
```bash
claude "Fetch data from https://api.github.com using web MCP"
```

## Troubleshooting

### Authentication Issues
- Verify with `claude auth status`
- Ensure OAuth or API key is correctly set

### Timeout Problems
- Increase timeout in `claude-code-demo.yaml`
- Check network connectivity

### Hook Execution Failures
- Check hook script permissions
- Verify Python dependencies
- Review hook logs

## Best Practices

1. Always use OAuth authentication when possible
2. Customize security rules for your environment
3. Monitor hook and server logs
4. Regularly update Claude Code and Superego MCP

## Support

- **Documentation**: [Project README](../README.md)
- **Issues**: GitHub Issues
- **Community**: Project Discord Server

Remember: Superego MCP adds an intelligent security layer to your AI agent interactions, keeping your system safe while enabling productive work.