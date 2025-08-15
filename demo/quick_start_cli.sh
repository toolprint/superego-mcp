#!/bin/bash
# Quick Start Script for Superego MCP with Claude CLI
# This script helps Claude Code users get started quickly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    color=$1
    message=$2
    echo -e "${color}${message}${NC}"
}

print_color "$BLUE" "🚀 Superego MCP Claude Code Quick Start"
echo "========================================"
echo

# Check if we're in the right directory
if [ ! -f "claude-code-demo.yaml" ]; then
    print_color "$RED" "❌ Error: Not in the demo directory"
    echo "Please run this script from the superego-mcp/demo directory"
    exit 1
fi

# Step 1: Check Claude CLI
print_color "$YELLOW" "Step 1: Checking Claude CLI..."
if command -v claude &> /dev/null; then
    print_color "$GREEN" "✅ Claude CLI found"
    claude --version
else
    print_color "$RED" "❌ Claude CLI not found"
    echo
    echo "Please install Claude CLI first:"
    echo "  macOS: brew install claude"
    echo "  Linux: curl -fsSL https://claude.ai/install.sh | sh"
    echo "  Or visit: https://claude.ai/cli"
    exit 1
fi
echo

# Step 2: Check API Key
print_color "$YELLOW" "Step 2: Checking API key..."
if [ -z "$ANTHROPIC_API_KEY" ]; then
    print_color "$RED" "❌ ANTHROPIC_API_KEY not set"
    echo
    echo "Please set your API key:"
    echo "  export ANTHROPIC_API_KEY='your-api-key-here'"
    echo
    read -p "Enter your API key now (or press Enter to skip): " api_key
    if [ ! -z "$api_key" ]; then
        export ANTHROPIC_API_KEY="$api_key"
        print_color "$GREEN" "✅ API key set for this session"
    else
        exit 1
    fi
else
    print_color "$GREEN" "✅ API key is set"
fi
echo

# Step 3: Test Claude CLI
print_color "$YELLOW" "Step 3: Testing Claude CLI..."
if claude -p non-interactive "Say OK" 2>&1 | grep -q "OK"; then
    print_color "$GREEN" "✅ Claude CLI is working"
else
    print_color "$RED" "❌ Claude CLI test failed"
    echo "Please check your API key and internet connection"
    exit 1
fi
echo

# Step 4: Check Python environment
print_color "$YELLOW" "Step 4: Checking Python environment..."
if python3 --version | grep -E "3\.(10|11|12)" > /dev/null; then
    print_color "$GREEN" "✅ Python $(python3 --version)"
else
    print_color "$RED" "❌ Python 3.10+ required"
    exit 1
fi

# Check if superego_mcp is installed
if python3 -c "import superego_mcp" 2>/dev/null; then
    print_color "$GREEN" "✅ Superego MCP is installed"
else
    print_color "$YELLOW" "⚠️  Superego MCP not installed"
    echo "Installing from parent directory..."
    cd ..
    pip install -e . > /dev/null 2>&1
    cd demo
    print_color "$GREEN" "✅ Superego MCP installed"
fi
echo

# Step 5: Start the server
print_color "$YELLOW" "Step 5: Starting Superego MCP server..."

# Check if server is already running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_color "$GREEN" "✅ Server is already running"
else
    echo "Starting server in background..."
    
    # Create log directory
    mkdir -p logs
    
    # Start server in background
    nohup python3 -m superego_mcp.main --config claude-code-demo.yaml > logs/server.log 2>&1 &
    SERVER_PID=$!
    
    # Wait for server to start
    echo -n "Waiting for server to start"
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo
            print_color "$GREEN" "✅ Server started (PID: $SERVER_PID)"
            echo "Server logs: demo/logs/server.log"
            break
        fi
        echo -n "."
        sleep 1
    done
    
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo
        print_color "$RED" "❌ Server failed to start"
        echo "Check logs at: demo/logs/server.log"
        exit 1
    fi
fi
echo

# Step 6: Run verification
print_color "$YELLOW" "Step 6: Running setup verification..."
python3 setup_verification_cli.py
echo

# Step 7: Ready to go!
print_color "$GREEN" "🎉 Setup complete! You're ready to use Superego MCP with Claude CLI"
echo
echo "To run the interactive demo:"
print_color "$BLUE" "  python3 claude_code_demo.py"
echo
echo "To stop the server later:"
print_color "$BLUE" "  pkill -f 'superego_mcp.main'"
echo
echo "For more information:"
echo "  • Setup Guide: CLAUDE_CODE_SETUP.md"
echo "  • CLI Scenarios: CLI_INFERENCE_SCENARIOS.md"
echo "  • Troubleshooting: TROUBLESHOOTING_CLI.md"
echo

# Optional: Start demo immediately
read -p "Would you like to start the interactive demo now? (y/N): " start_demo
if [[ $start_demo =~ ^[Yy]$ ]]; then
    echo
    python3 claude_code_demo.py
fi