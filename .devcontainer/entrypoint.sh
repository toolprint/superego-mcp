#!/bin/bash
# DevContainer Entrypoint Script
# Initializes the development environment with optimal performance
# Target: Complete setup in <30 seconds total

set -e

echo "🏗️  Superego MCP DevContainer Initialization Starting..."
echo "📅 $(date)"
echo "👤 User: $(whoami) ($(id))"
echo "🏠 Home: $HOME"
echo "📁 Workspace: $(pwd)"

# Performance timing
START_TIME=$(date +%s)

# 1. Environment Verification (2-3 seconds)
echo ""
echo "🔍 Verifying environment..."

# Check Python and UV
if ! command -v python >/dev/null 2>&1; then
    echo "❌ Python not found in PATH"
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "❌ UV not found in PATH" 
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1)
UV_VERSION=$(uv --version 2>&1)
echo "✅ $PYTHON_VERSION"
echo "✅ UV $UV_VERSION"

# 2. Project Structure Validation (1-2 seconds)
echo ""
echo "🔍 Validating project structure..."

REQUIRED_PATHS=(
    "/app/src/superego_mcp"
    "/app/config"
    "/app/tests" 
    "/app/pyproject.toml"
    "/app/uv.lock"
)

for path in "${REQUIRED_PATHS[@]}"; do
    if [ ! -e "$path" ]; then
        echo "❌ Missing required path: $path"
        exit 1
    fi
done

echo "✅ Project structure valid"

# 3. Virtual Environment Setup (5-10 seconds)
echo ""
echo "🔧 Setting up virtual environment..."

# Ensure virtual environment exists and is activated
if [ ! -d "/app/.venv" ]; then
    echo "📦 Creating virtual environment..."
    cd /app
    uv sync --frozen
else
    echo "✅ Virtual environment exists"
    
    # Quick dependency check and sync if needed
    if ! uv pip list | grep -q "fastmcp" >/dev/null 2>&1; then
        echo "📦 Syncing dependencies..."
        cd /app  
        uv sync --frozen
    fi
fi

# Verify key packages are installed
echo "🔍 Verifying key dependencies..."
REQUIRED_PACKAGES=("fastmcp" "pydantic" "pyyaml" "structlog")
for package in "${REQUIRED_PACKAGES[@]}"; do
    if uv pip list | grep -q "^$package " >/dev/null 2>&1; then
        echo "✅ $package installed"
    else
        echo "⚠️  $package not found, triggering sync..."
        cd /app
        uv sync --frozen
        break
    fi
done

# 4. Development Tools Configuration (3-5 seconds)
echo ""
echo "🛠️  Configuring development tools..."

# Set up Git configuration if needed
if [ -n "${GIT_USER_NAME:-}" ] && [ -n "${GIT_USER_EMAIL:-}" ]; then
    git config --global user.name "$GIT_USER_NAME" 2>/dev/null || true
    git config --global user.email "$GIT_USER_EMAIL" 2>/dev/null || true
    echo "✅ Git configuration applied"
fi

# Create development directories
mkdir -p /app/logs /app/tmp /app/.cache /app/.debugger
echo "✅ Development directories created"

# 5. VS Code Integration Setup (2-3 seconds)
echo ""
echo "📝 Setting up VS Code integration..."

# Create VS Code settings if they don't exist
VSCODE_DIR="/app/.vscode"
mkdir -p "$VSCODE_DIR"

# Python interpreter settings for VS Code
cat > "$VSCODE_DIR/settings.json" << 'EOF'
{
    "python.defaultInterpreterPath": "/app/.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests", "--verbose"],
    "ruff.enable": true,
    "ruff.organizeImports": true,
    "editor.formatOnSave": true,
    "files.watcherExclude": {
        "**/__pycache__/**": true,
        "**/htmlcov/**": true,
        "**/dist/**": true,
        "**/.cache/**": true,
        "**/logs/**": true
    }
}
EOF

# Launch configuration for debugging
cat > "$VSCODE_DIR/launch.json" << 'EOF'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug Superego Server",
            "type": "python",
            "request": "launch",
            "program": "/app/src/superego_mcp/main.py",
            "console": "integratedTerminal",
            "cwd": "/app",
            "env": {
                "PYTHONPATH": "/app/src",
                "DEVELOPMENT": "1",
                "LOG_LEVEL": "DEBUG"
            }
        },
        {
            "name": "Debug Tests",
            "type": "python", 
            "request": "launch",
            "module": "pytest",
            "args": ["tests/", "-v"],
            "console": "integratedTerminal",
            "cwd": "/app"
        },
        {
            "name": "Attach to Remote Debug",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5678
            },
            "pathMappings": [
                {
                    "localRoot": "/app",
                    "remoteRoot": "/app"
                }
            ]
        }
    ]
}
EOF

echo "✅ VS Code configuration created"

# 6. Health Check and Final Validation (2-3 seconds)
echo ""
echo "🏥 Running health checks..."

# Verify Python imports work
if ! python -c "import superego_mcp; print('✅ Package imports successfully')" 2>/dev/null; then
    echo "❌ Package import failed"
    echo "🔧 Attempting to fix..."
    cd /app
    uv sync --frozen --reinstall
    
    if ! python -c "import superego_mcp; print('✅ Package imports successfully')" 2>/dev/null; then
        echo "❌ Package import still failing"
        exit 1
    fi
fi

# Test basic functionality
if ! python -c "from superego_mcp.infrastructure.config import load_config; print('✅ Configuration system working')" 2>/dev/null; then
    echo "⚠️  Configuration system not fully functional"
fi

# 7. Performance and Timing Report
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "🎉 DevContainer initialization complete!"
echo "⏱️  Total time: ${ELAPSED}s"

if [ $ELAPSED -gt 30 ]; then
    echo "⚠️  Initialization took longer than 30s target"
else
    echo "✅ Initialization within 30s target"
fi

# 8. Development Environment Summary
echo ""
echo "📋 Development Environment Ready:"
echo "   🐍 Python: $(python --version | cut -d' ' -f2)"
echo "   📦 UV: $(uv --version | cut -d' ' -f2)"
echo "   🏠 Workspace: /app"
echo "   🔧 Virtual Env: /app/.venv"
echo "   📝 VS Code: Configured"
echo ""
echo "🚀 Available Commands:"
echo "   just run              # Start server"
echo "   just test             # Run tests"
echo "   just lint             # Code linting"
echo "   just format           # Code formatting"
echo "   just demo-setup       # Demo setup"
echo ""
echo "🌐 Development URLs (when server running):"
echo "   Server:  http://localhost:8002"
echo "   Monitor: http://localhost:8003" 
echo "   Debug:   Port 5679 (when DEBUGPY_ENABLED=1)"
echo ""
echo "📖 Quick Start:"
echo "   1. Open terminal in VS Code"
echo "   2. Run: just run"
echo "   3. Open: http://localhost:8002"
echo ""

# 9. Optional: Pre-build for faster subsequent runs
if [ "${PREBUILT_CACHE:-0}" = "1" ]; then
    echo "🔄 Pre-building cache for faster subsequent runs..."
    python -c "import superego_mcp.main" >/dev/null 2>&1 || true
    echo "✅ Cache pre-built"
fi

echo "🎯 Ready for development! Happy coding! 🎉"