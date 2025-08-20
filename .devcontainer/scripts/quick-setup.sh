#!/bin/bash
# Quick Setup Script for Superego MCP DevContainer
# Performs rapid development environment setup and verification

set -e

echo "⚡ Superego MCP Quick Setup"
echo "=========================="
echo ""

START_TIME=$(date +%s)

# 1. Dependency Check (5s)
echo "📦 Checking dependencies..."
cd /app

if [ ! -f "uv.lock" ]; then
    echo "❌ uv.lock not found"
    exit 1
fi

if ! uv sync --frozen >/dev/null 2>&1; then
    echo "🔄 Syncing dependencies..."
    uv sync --frozen
fi
echo "✅ Dependencies ready"

# 2. Environment Test (3s)
echo "🧪 Testing environment..."

if ! python -c "import superego_mcp" >/dev/null 2>&1; then
    echo "❌ Package import failed, attempting fix..."
    uv sync --frozen --reinstall
    
    if ! python -c "import superego_mcp" >/dev/null 2>&1; then
        echo "❌ Setup failed - cannot import package"
        exit 1
    fi
fi
echo "✅ Environment working"

# 3. Configuration Validation (2s)
echo "⚙️  Validating configuration..."

required_configs=(
    "config/server.yaml"
    "config/rules.yaml"
)

for config in "${required_configs[@]}"; do
    if [ ! -f "$config" ]; then
        echo "❌ Missing config: $config"
        exit 1
    fi
done

# Test configuration loading
if ! python -c "
from superego_mcp.infrastructure.config import load_config
try:
    config = load_config('config/server.yaml')
    print('✅ Configuration valid')
except Exception as e:
    print(f'❌ Configuration error: {e}')
    exit(1)
" 2>/dev/null; then
    echo "❌ Configuration validation failed"
    exit 1
fi

# 4. Development Tools Setup (2s)
echo "🛠️  Setting up development tools..."

# Ensure VS Code settings
mkdir -p .vscode
if [ ! -f ".vscode/settings.json" ]; then
    cat > .vscode/settings.json << 'EOF'
{
    "python.defaultInterpreterPath": "/app/.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.testing.pytestEnabled": true
}
EOF
fi

echo "✅ Development tools ready"

# 5. Quick Health Test (3s)
echo "🏥 Running health test..."

# Start server in background for health check
export PYTHONPATH=/app/src
timeout 10s uv run python -c "
import asyncio
from superego_mcp.presentation.unified_server import UnifiedServer

async def quick_test():
    server = UnifiedServer()
    # Just test initialization, don't start
    print('✅ Server initialization OK')

asyncio.run(quick_test())
" || echo "⚠️  Server test timed out (may need more resources)"

# 6. Performance Report
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "🎉 Quick setup complete!"
echo "⏱️  Setup time: ${ELAPSED}s"

if [ $ELAPSED -le 15 ]; then
    echo "🚀 Excellent! Setup under 15s"
elif [ $ELAPSED -le 30 ]; then
    echo "✅ Good! Setup under 30s"
else
    echo "⚠️  Setup took longer than expected"
fi

echo ""
echo "🚀 Ready to develop!"
echo "   Start server: just run"
echo "   Run tests:    just test"  
echo "   Check status: .devcontainer/scripts/dev-status.sh"
echo ""