#!/bin/bash
"""
Setup Claude Code Hooks for Superego MCP Integration

This script configures Claude Code to send MCP tool calls to Superego
for security evaluation via hooks.
"""

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_CONFIG_DIR="$HOME/.claude"
HOOKS_CONFIG_FILE="$CLAUDE_CONFIG_DIR/hooks.json"
DEMO_HOOKS_DIR="$SCRIPT_DIR/hooks"

echo "🔧 Setting up Claude Code hooks for Superego MCP integration..."

# Create Claude config directory if it doesn't exist
if [ ! -d "$CLAUDE_CONFIG_DIR" ]; then
    echo "📁 Creating Claude config directory: $CLAUDE_CONFIG_DIR"
    mkdir -p "$CLAUDE_CONFIG_DIR"
fi

# Make hook scripts executable
echo "🔒 Making hook scripts executable..."
chmod +x "$DEMO_HOOKS_DIR/security_hook.py"
chmod +x "$DEMO_HOOKS_DIR/audit_hook.py"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required for hooks but not found in PATH"
    exit 1
fi

# Check if requests module is available
if ! python3 -c "import requests" &> /dev/null; then
    echo "⚠️  Warning: 'requests' module not found. Installing..."
    pip3 install requests
fi

# Create hooks configuration
echo "📝 Creating hooks configuration..."

# Get absolute paths for hook scripts
SECURITY_HOOK_PATH="$(realpath "$DEMO_HOOKS_DIR/security_hook.py")"
AUDIT_HOOK_PATH="$(realpath "$DEMO_HOOKS_DIR/audit_hook.py")"

cat > "$HOOKS_CONFIG_FILE" << EOF
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__.*",
        "description": "Intercept all MCP tool calls for security evaluation",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["$SECURITY_HOOK_PATH"],
            "timeout": 15,
            "description": "Send tool call to Superego MCP for security evaluation"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__.*",
        "description": "Log completed MCP tool executions for audit",
        "hooks": [
          {
            "type": "command",
            "command": "python3", 
            "args": ["$AUDIT_HOOK_PATH"],
            "timeout": 5,
            "description": "Log tool execution result for security audit"
          }
        ]
      }
    ]
  }
}
EOF

echo "✅ Hooks configuration created at: $HOOKS_CONFIG_FILE"

# Verify Claude Code can read the hooks config
echo "🔍 Verifying Claude Code hooks configuration..."
if command -v claude &> /dev/null; then
    if claude settings show | grep -q "hooks"; then
        echo "✅ Claude Code hooks are configured and detected"
    else
        echo "⚠️  Warning: Claude Code may not have detected the hooks configuration"
        echo "   Try restarting Claude Code or check the configuration manually"
    fi
else
    echo "⚠️  Warning: Claude Code CLI not found. Please ensure it's installed and in PATH"
fi

# Show configuration summary
echo ""
echo "📋 Configuration Summary:"
echo "   Hooks config: $HOOKS_CONFIG_FILE"
echo "   Security hook: $SECURITY_HOOK_PATH"
echo "   Audit hook: $AUDIT_HOOK_PATH"
echo "   Matcher pattern: mcp__.*"
echo ""

# Provide next steps
echo "🚀 Next Steps:"
echo "1. Start the Superego MCP server:"
echo "   python -m superego_mcp.main --config config/superego/claude-code-demo.yaml"
echo ""
echo "2. Test the integration:"
echo "   claude \"List files in the current directory using filesystem MCP\""
echo ""
echo "3. Check logs for hook activity:"
echo "   tail -f /tmp/superego_hook.log"
echo "   tail -f /tmp/superego_audit.log"
echo ""
echo "✨ Setup complete! Claude Code will now send MCP tool calls to Superego for security evaluation."