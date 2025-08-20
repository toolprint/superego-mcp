#!/bin/bash
# Development Environment Status Script
# Quick health check for DevContainer environment

set -e

echo "🔍 Superego MCP DevContainer Status"
echo "=================================="
echo ""

# System Info
echo "📊 System Information:"
echo "   Container: $(hostname)"
echo "   User: $(whoami)"
echo "   PWD: $(pwd)"
echo "   Date: $(date)"
echo ""

# Python Environment
echo "🐍 Python Environment:"
python_version=$(python --version 2>&1)
echo "   Python: $python_version"

if command -v uv >/dev/null 2>&1; then
    uv_version=$(uv --version 2>&1)
    echo "   UV: $uv_version"
else
    echo "   UV: Not found"
fi

if [ -d "/app/.venv" ]; then
    echo "   Virtual Env: ✅ Active"
    echo "   Packages: $(uv pip list 2>/dev/null | wc -l || echo 'N/A') installed"
else
    echo "   Virtual Env: ❌ Not found"
fi
echo ""

# Project Structure
echo "📁 Project Structure:"
project_files=(
    "/app/src/superego_mcp/__init__.py"
    "/app/config/server.yaml"
    "/app/config/rules.yaml"
    "/app/pyproject.toml"
    "/app/uv.lock"
)

for file in "${project_files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $(basename "$file")"
    else
        echo "   ❌ $(basename "$file") - Missing"
    fi
done
echo ""

# Services Status
echo "🌐 Services Status:"

# Check if server is running
if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "   ✅ Superego Server (http://localhost:8000)"
else
    echo "   ❌ Superego Server - Not running"
fi

if curl -sf http://localhost:8001 >/dev/null 2>&1; then
    echo "   ✅ Monitoring Dashboard (http://localhost:8001)"
else
    echo "   ❌ Monitoring Dashboard - Not running"
fi

# Check debug port
if nc -z localhost 5678 >/dev/null 2>&1; then
    echo "   ✅ Debug Port (5678)"
else
    echo "   ❌ Debug Port - Not active"
fi
echo ""

# Development Tools
echo "🛠️  Development Tools:"
tools=("git" "curl" "wget" "just")

for tool in "${tools[@]}"; do
    if command -v "$tool" >/dev/null 2>&1; then
        version=$($tool --version 2>&1 | head -1 || echo "Available")
        echo "   ✅ $tool"
    else
        echo "   ❌ $tool - Not found"
    fi
done
echo ""

# Environment Variables
echo "🔧 Environment Variables:"
env_vars=(
    "PYTHONPATH"
    "DEVELOPMENT" 
    "LOG_LEVEL"
    "HOT_RELOAD"
    "SUPEREGO_CONFIG_PATH"
    "UV_CACHE_DIR"
)

for var in "${env_vars[@]}"; do
    if [ -n "${!var}" ]; then
        echo "   ✅ $var=${!var}"
    else
        echo "   ❌ $var - Not set"
    fi
done
echo ""

# Quick Import Test
echo "🧪 Quick Tests:"
if python -c "import superego_mcp; print('Package import: ✅')" 2>/dev/null; then
    echo "   ✅ Package imports successfully"
else
    echo "   ❌ Package import failed"
fi

if python -c "from superego_mcp.infrastructure.config import load_config; print('Config system: ✅')" 2>/dev/null; then
    echo "   ✅ Configuration system working"
else
    echo "   ❌ Configuration system issues"
fi
echo ""

# Performance Info
echo "⚡ Performance Info:"
if [ -f /proc/meminfo ]; then
    total_mem=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    available_mem=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    echo "   Memory: $((available_mem/1024))MB available / $((total_mem/1024))MB total"
fi

if [ -f /proc/cpuinfo ]; then
    cpu_count=$(grep -c processor /proc/cpuinfo)
    echo "   CPUs: $cpu_count cores"
fi

if [ -d "/app/.cache" ]; then
    cache_size=$(du -sh /app/.cache 2>/dev/null | cut -f1 || echo "N/A")
    echo "   Cache: $cache_size"
fi
echo ""

# Suggestions
echo "💡 Quick Actions:"
echo "   Start Server:     just run"
echo "   Run Tests:        just test"
echo "   Format Code:      just format"
echo "   View Logs:        just logs (if available)"
echo "   Monitor Health:   watch curl -s http://localhost:8000/health"
echo ""

echo "Status check complete! 🎉"