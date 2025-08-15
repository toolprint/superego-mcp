# Superego MCP - Quick Start Guide

## Overview

Superego MCP provides intelligent tool request interception for AI agents with two primary modes:
- **`superego advise`**: One-off security evaluation (ideal for Claude Code hooks)
- **`superego mcp`**: Full MCP server with rule management and advanced features

## Installation

### Option 1: uvx (Recommended)
```bash
uvx superego-mcp
```

### Option 2: pipx
```bash
pipx install superego-mcp
```

### Option 3: pip
```bash
pip install superego-mcp
```

### Option 4: uv (for development)
```bash
git clone https://github.com/toolprint/superego-mcp
cd superego-mcp
uv sync
uv run superego --help
```

## Quick Test

Verify installation:
```bash
superego --version
superego --help
```

Test security evaluation:
```bash
echo '{"tool_name": "ls", "tool_input": {"directory": "/tmp"}, "session_id": "test", "transcript_path": "", "cwd": "/tmp", "hook_event_name": "PreToolUse"}' | superego advise
```

Expected output:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "No dangerous patterns detected, operation appears safe"
  },
  "decision": "approve",
  "reason": "No dangerous patterns detected, operation appears safe"
}
```

## Claude Code Integration

### Method 1: Automated Hook Management (Recommended)

Superego provides built-in Claude Code hooks management:

1. **Add a Superego hook:**
```bash
# Add hook for common dangerous tools (recommended)
superego hooks add --matcher "Bash|Write|Edit|MultiEdit"

# Or add hook for all tools
superego hooks add

# Custom timeout and event type
superego hooks add --matcher "Bash" --timeout 3000 --event-type "PreToolUse"
```

2. **Manage hooks:**
```bash
# List all Superego hooks
superego hooks list

# List in JSON format
superego hooks list --json

# Remove specific hook by ID
superego hooks remove --id 550e8400-e29b-41d4

# Remove all hooks with specific matcher
superego hooks remove --matcher "Bash|Write|Edit|MultiEdit"
```

3. **Hook Matchers:**
- `*` - All tools (default)
- `Bash|Write|Edit|MultiEdit` - Common dangerous tools (recommended)
- `Bash` - Shell commands only
- `Write|Edit|MultiEdit` - File modification tools
- `mcp__.*` - All MCP tools

### Method 2: Manual Hook Integration

1. **Create Claude Code hooks configuration manually:**
```bash
# Create Claude hooks directory
mkdir -p ~/.claude

# Create hooks configuration in settings.json
cat > ~/.claude/settings.json << 'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|MultiEdit",
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
EOF
```

2. **Test the hook:**
```bash
# Test with a sample tool request
echo '{"tool_name": "bash", "tool_input": {"command": "echo hello"}, "session_id": "test", "transcript_path": "", "cwd": "/tmp", "hook_event_name": "PreToolUse"}' | superego advise
```

### Method 3: HTTP Server Integration

1. **Start the MCP server:**
```bash
superego mcp
```

2. **Create HTTP-based hooks configuration:**
```bash
cat > ~/.claude/settings.json << 'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "curl --json @- http://localhost:8000/pretoolinputendpoint",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
EOF
```

## Configuration

### Default Configuration Path
Superego automatically creates and uses: `~/.toolprint/superego/config.yaml`

### Custom Configuration
```bash
# Use custom config file
superego advise -c /path/to/your/config.yaml < input.json
superego mcp -c /path/to/your/config.yaml
```

### Sample Configuration
Create `~/.toolprint/superego/config.yaml`:
```yaml
# AI Sampling Configuration (legacy)
ai_sampling:
  enabled: false
  primary_provider: "anthropic"
  fallback_provider: "openai"
  timeout_seconds: 10

# Inference Configuration (new system)
inference:
  timeout_seconds: 10
  provider_preference: ["claude_cli", "mcp_sampling"]
  cli_providers:
    - name: "claude_cli"
      enabled: true
      type: "claude"
      command: "claude"
      timeout_seconds: 5

# Transport Configuration
transport:
  http:
    enabled: true
    port: 8000
    host: "0.0.0.0"
  websocket:
    enabled: true
    port: 8001
  sse:
    enabled: false
    port: 8002
```

## Testing Claude Code Integration

### 1. Hooks Management Test
```bash
# Add a hook for common dangerous tools
superego hooks add --matcher "Bash|Write|Edit|MultiEdit"

# Verify the hook was added
superego hooks list

# Check the settings file was updated
cat ~/.claude/settings.json

# Test with a sample tool request
echo '{"tool_name": "bash", "tool_input": {"command": "echo hello"}, "session_id": "test", "transcript_path": "", "cwd": "/tmp", "hook_event_name": "PreToolUse"}' | superego advise
```

### 2. Basic Hook Test
```bash
# Create a test script
cat > test_hook.sh << 'EOF'
#!/bin/bash
echo '{"tool_name": "ls", "tool_input": {"directory": "."}, "session_id": "test", "transcript_path": "", "cwd": ".", "hook_event_name": "PreToolUse"}' | superego advise
EOF

chmod +x test_hook.sh
./test_hook.sh
```

### 3. Dangerous Command Test
```bash
echo '{"tool_name": "bash", "tool_input": {"command": "rm -rf /"}, "session_id": "test", "transcript_path": "", "cwd": "/tmp", "hook_event_name": "PreToolUse"}' | superego advise
```

Should return a "deny" decision for dangerous commands.

### 4. Interactive Claude Code Test
```bash
# Start Claude Code with hooks enabled
claude

# Try a command that would trigger the hook
# The hook should intercept and evaluate the request
```

### 5. Hook Cleanup Test
```bash
# Remove all Superego hooks
superego hooks remove --matcher "Bash|Write|Edit|MultiEdit"

# Verify hooks were removed
superego hooks list

# Check that settings file still has other configurations
cat ~/.claude/settings.json
```

## Troubleshooting

### Hooks Management Issues

1. **Check Superego hooks:**
```bash
# List all Superego hooks
superego hooks list

# Check if Claude directory exists
ls -la ~/.claude/

# Verify settings file format
cat ~/.claude/settings.json | python -m json.tool
```

2. **Hooks not working:**
```bash
# Verify hook command works directly
echo '{"tool_name": "test", "tool_input": {}, "session_id": "test", "transcript_path": "", "cwd": ".", "hook_event_name": "PreToolUse"}' | superego advise

# Check Claude Code settings
claude settings

# Restart Claude Code to reload settings
```

3. **Settings file corruption:**
```bash
# Check for backup files
ls ~/.claude/settings.backup.*.json

# Restore from backup if needed
cp ~/.claude/settings.backup.YYYYMMDD_HHMMSS.json ~/.claude/settings.json

# Or recreate with Superego
rm ~/.claude/settings.json
superego hooks add --matcher "Bash|Write|Edit|MultiEdit"
```

### Hook Not Triggering
1. **Verify hook is in settings:**
```bash
superego hooks list
cat ~/.claude/settings.json
```

2. **Check matcher patterns:**
```bash
# Make sure your tool name matches the pattern
# For example, "Bash" tool should match "Bash|Write|Edit|MultiEdit"
superego hooks list
```

3. **Test hook command directly:**
```bash
echo '{"tool_name": "bash", "tool_input": {"command": "echo test"}, "session_id": "test", "transcript_path": "", "cwd": ".", "hook_event_name": "PreToolUse"}' | superego advise
```

### Claude CLI Not Available
```bash
# Install Claude Code
# Visit: https://docs.anthropic.com/en/docs/claude-code

# Authenticate
claude auth

# Verify
claude --version
superego mcp --validate-claude
```

### Permission Issues
```bash
# Check superego installation
which superego
superego --version

# Check PATH
echo $PATH | grep -o ~/.local/bin
```

### Configuration Issues
```bash
# Check default config directory
ls -la ~/.toolprint/superego/

# Create default config manually
mkdir -p ~/.toolprint/superego
touch ~/.toolprint/superego/config.yaml

# Test with explicit config
superego advise -c ~/.toolprint/superego/config.yaml < test_input.json
```

## Advanced Usage

### MCP Server Mode
```bash
# Start with default config
superego mcp

# Start with custom config
superego mcp -c /path/to/config.yaml

# Start without Claude validation
superego mcp --no-validate-claude
```

### Development Mode
```bash
# Clone and setup
git clone https://github.com/toolprint/superego-mcp
cd superego-mcp
uv sync --all-extras

# Run from source
uv run superego advise < test_input.json
uv run superego mcp

# Development tasks
just test
just lint
just build
```

## Next Steps

- **Custom Rules**: Learn to configure security rules in `~/.toolprint/superego/config.yaml`
- **MCP Integration**: Explore full MCP server capabilities with `superego mcp`
- **Advanced Hooks**: Set up complex hook workflows with the HTTP server mode
- **Monitoring**: Use the MCP server's monitoring dashboard at `http://localhost:8000/dashboard`

## Support

- **Documentation**: https://github.com/toolprint/superego-mcp
- **Issues**: https://github.com/toolprint/superego-mcp/issues
- **Claude Code Hooks Guide**: https://docs.anthropic.com/en/docs/claude-code/hooks-guide