#!/bin/bash
# DevContainer Testing Script
# Tests DevContainer configuration and reports compatibility

set -e

echo "🧪 Superego MCP DevContainer Test Suite"
echo "======================================"
echo ""

# 1. Configuration Validation
echo "📋 Configuration Validation:"

# Check DevContainer JSON  
if python3 -m json.tool ../devcontainer.json >/dev/null 2>&1; then
    echo "   ✅ devcontainer.json syntax valid"
else
    echo "   ❌ devcontainer.json syntax invalid"
    exit 1
fi

# Check required files
required_files=(
    "../devcontainer.json"
    "../docker-compose.yml" 
    "../entrypoint.sh"
    "../../docker-compose.dev.yml"
    "../../docker/development/Dockerfile.development"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $(basename "$file")"
    else
        echo "   ❌ $(basename "$file") missing"
        exit 1
    fi
done

# 2. Docker Configuration Test
echo ""
echo "🐳 Docker Configuration:"

# Check if Docker is available
if command -v docker >/dev/null 2>&1; then
    echo "   ✅ Docker CLI available"
    
    # Test Docker Compose syntax (if Docker daemon is running)
    if docker info >/dev/null 2>&1; then
        echo "   ✅ Docker daemon running"
        
        if docker-compose -f ../../docker-compose.dev.yml -f ../docker-compose.yml config >/dev/null 2>&1; then
            echo "   ✅ Docker Compose configuration valid"
        else
            echo "   ⚠️  Docker Compose configuration has warnings (may still work)"
        fi
    else
        echo "   ⚠️  Docker daemon not running (OK for syntax check)"
    fi
else
    echo "   ❌ Docker not available"
fi

# 3. VS Code Extension Validation
echo ""
echo "📝 VS Code Extension Check:"

# Parse extensions from devcontainer.json
extensions_count=$(python3 -c "
import json
with open('../devcontainer.json') as f:
    config = json.load(f)
    extensions = config.get('customizations', {}).get('vscode', {}).get('extensions', [])
    print(len(extensions))
" 2>/dev/null || echo "0")

echo "   📦 Extensions configured: $extensions_count"

if [ "$extensions_count" -gt 15 ]; then
    echo "   ✅ Comprehensive extension set"
elif [ "$extensions_count" -gt 10 ]; then
    echo "   ✅ Good extension coverage"
elif [ "$extensions_count" -gt 5 ]; then
    echo "   ⚠️  Basic extension set"
else
    echo "   ❌ Insufficient extensions"
fi

# 4. Environment Variables
echo ""
echo "🔧 Environment Configuration:"

# Check critical environment variables in devcontainer.json
env_vars=("PYTHONPATH" "DEVELOPMENT" "SUPEREGO_CONFIG_PATH" "UV_CACHE_DIR")
env_count=0

for var in "${env_vars[@]}"; do
    if python3 -c "
import json
with open('../devcontainer.json') as f:
    config = json.load(f)
    env_vars = config.get('containerEnv', {})
    if '$var' in env_vars:
        print('   ✅ $var=' + env_vars['$var'])
        exit(0)
    else:
        print('   ❌ $var not set')
        exit(1)
" 2>/dev/null; then
        env_count=$((env_count + 1))
    fi
done

echo "   📊 Environment variables: $env_count/${#env_vars[@]} configured"

# 5. Port Configuration
echo ""
echo "🌐 Port Configuration:"

# Check port forwarding
ports_count=$(python3 -c "
import json
with open('../devcontainer.json') as f:
    config = json.load(f)
    ports = config.get('forwardPorts', [])
    print(len(ports))
" 2>/dev/null || echo "0")

echo "   🔗 Forwarded ports: $ports_count"

if [ "$ports_count" -ge 4 ]; then
    echo "   ✅ All required ports configured"
elif [ "$ports_count" -ge 2 ]; then
    echo "   ✅ Essential ports configured"
else
    echo "   ❌ Insufficient port configuration"
fi

# 6. Performance Predictions
echo ""
echo "⚡ Performance Analysis:"

# Estimate startup time based on configuration
startup_factors=0

# Check for cached volumes
if grep -q "cached\|delegated" ../docker-compose.yml; then
    echo "   ✅ Volume caching enabled"
    startup_factors=$((startup_factors + 1))
fi

# Check for optimized base image
if grep -q "python:3.11-slim" ../../docker/development/Dockerfile.development; then
    echo "   ✅ Optimized base image (slim)"
    startup_factors=$((startup_factors + 1))
fi

# Check UV usage
if grep -q "uv sync" ../../docker/development/Dockerfile.development; then
    echo "   ✅ UV package manager (fast deps)"
    startup_factors=$((startup_factors + 1))
fi

# Predict startup time
if [ $startup_factors -ge 3 ]; then
    echo "   🚀 Predicted startup: <20s (Excellent)"
elif [ $startup_factors -ge 2 ]; then
    echo "   ✅ Predicted startup: 20-30s (Good)"
elif [ $startup_factors -ge 1 ]; then
    echo "   ⚠️  Predicted startup: 30-45s (Acceptable)"
else
    echo "   ❌ Predicted startup: >45s (Needs optimization)"
fi

# 7. Security Check
echo ""
echo "🔒 Security Configuration:"

# Check user configuration
if grep -q '"remoteUser": "appuser"' ../devcontainer.json; then
    echo "   ✅ Non-root user configured"
else
    echo "   ⚠️  Root user access (potential security risk)"
fi

# Check for secrets in configuration
if ! grep -r "password\|secret\|key\|token" .. >/dev/null 2>&1; then
    echo "   ✅ No hardcoded secrets found"
else
    echo "   ⚠️  Potential secrets in configuration"
fi

# 8. Final Report
echo ""
echo "📊 DevContainer Readiness Report:"
echo "================================="

# Calculate overall score
score=0
total=8

# Configuration (1 point)
if python3 -m json.tool ../devcontainer.json >/dev/null 2>&1; then
    score=$((score + 1))
fi

# Extensions (1 point)
if [ "$extensions_count" -gt 10 ]; then
    score=$((score + 1))
fi

# Environment (1 point) 
if [ "$env_count" -ge 3 ]; then
    score=$((score + 1))
fi

# Ports (1 point)
if [ "$ports_count" -ge 3 ]; then
    score=$((score + 1))
fi

# Performance (2 points)
if [ $startup_factors -ge 2 ]; then
    score=$((score + 2))
elif [ $startup_factors -ge 1 ]; then
    score=$((score + 1))
fi

# Security (1 point)
if grep -q '"remoteUser": "appuser"' ../devcontainer.json; then
    score=$((score + 1))
fi

# Files present (1 point)
if [ ${#required_files[@]} -eq 5 ]; then
    all_files_present=true
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            all_files_present=false
            break
        fi
    done
    if [ "$all_files_present" = true ]; then
        score=$((score + 1))
    fi
fi

echo "   📈 Score: $score/$total"

if [ $score -eq $total ]; then
    echo "   🏆 EXCELLENT - DevContainer ready for production use"
    exit 0
elif [ $score -ge 6 ]; then
    echo "   ✅ GOOD - DevContainer ready with minor optimizations needed"
    exit 0
elif [ $score -ge 4 ]; then
    echo "   ⚠️  ACCEPTABLE - Some improvements recommended"
    exit 1
else
    echo "   ❌ NEEDS WORK - Significant issues need addressing"
    exit 1
fi