# Superego MCP Server - Main Development Tasks
# Run 'just' to see available commands

# Import modular justfiles
import 'just/common.just'
import 'just/dev.just'
import 'just/quality.just'
import 'just/test.just'
import 'just/build.just'
import 'just/docker.just'
import 'just/demo.just'
import 'just/deploy.just'
import 'just/performance.just'

# Default recipe - show comprehensive help
default:
    @just help

# =============================================================================
# UNIFIED INTERFACES (aliases for imported recipes)
# =============================================================================

# Start development server
dev:
    @just run

# =============================================================================
# QUICK WORKFLOWS
# =============================================================================

# Quick start for new developers
[group: 'workflows']
quickstart: setup
    @just _success "Project setup complete! Try 'just dev' to start the server"

# Pre-commit checks
[group: 'workflows']  
pre-commit: format lint typecheck test-fast
    @just _success "All pre-commit checks passed!"

# CI simulation
[group: 'workflows']
ci: check test build
    @just _success "CI pipeline complete"

# Development workflow
[group: 'workflows']
start: 
    @just _info "Starting full development environment..."
    @just setup
    @just _info "Ready for development! Run 'just dev' to start the server"


# =============================================================================
# HELP AND DISCOVERY
# =============================================================================

# Comprehensive help system
[group: 'help']
help:
    #!/usr/bin/env bash
    echo "🚀 Superego MCP Server Development Commands"
    echo "==========================================="
    echo ""
    echo "🎯 QUICK START:"
    echo "  just quickstart    - Complete setup for new developers"
    echo "  just start         - Start full dev environment"  
    echo "  just pre-commit    - Run all checks before committing"
    echo "  just ci            - Simulate CI pipeline"
    echo ""
    echo "🔧 DEVELOPMENT:"
    echo "  just dev           - Start development server"
    echo "  just setup         - Setup development environment"
    echo "  just install       - Install dependencies"
    echo "  just watch         - Watch files and run tests"
    echo ""
    echo "🧪 TESTING:"
    echo "  just test [type]   - Run tests (all, unit, integration, fast)"
    echo "  just test-cov      - Run tests with coverage"
    echo "  just test-advise   - Test CLI evaluation"
    echo ""
    echo "✅ QUALITY:"
    echo "  just format        - Format code"
    echo "  just lint [fix]    - Lint code (set fix=true to auto-fix)"
    echo "  just typecheck     - Type check with mypy"
    echo "  just check[-fast]  - Run quality checks"
    echo ""
    echo "📦 BUILD & RELEASE:"
    echo "  just build         - Build package"
    echo "  just install-dev   - Install with pipx for global use"
    echo "  just prepare-release - Prepare release"
    echo ""
    echo "🐳 DOCKER:"
    echo "  just docker-build  - Build Docker images"
    echo "  just docker-dev    - Start development container"
    echo "  just docker-prod   - Start production environment"
    echo ""
    echo "🚀 DEMO:"
    echo "  just demo-setup    - Setup demo environment"
    echo "  just demo-all      - Run complete demo suite"
    echo ""
    echo "🔍 DISCOVERY & NAVIGATION:"
    echo "  just --list              - List all recipes organized by groups"
    echo "  just --groups            - List all recipe groups"
    echo "  just --summary           - Compact list of recipe names only"
    echo "  just --show <recipe>     - Show recipe source code"
    echo "  just --choose            - Interactive recipe picker (requires fzf)"
    echo ""
    echo "💡 TIPS:"
    echo "  Use 'just --show <recipe>' to see how recipes work"
    echo "  Recipes are organized by logical groups (development, testing, quality, etc.)"
    echo "  Most recipes have helpful parameters - check with 'just --show <recipe>'"

# Native Just command wrappers for convenience
[group: 'help']
groups:
    @just --groups

[group: 'help']
list:
    @just --list


# =============================================================================
# ALIASES FOR COMMON TASKS
# =============================================================================

# Test shortcuts
test-fast:
    @just test fast

test-unit:
    @just test unit

test-integration:
    @just test integration

# Quality shortcuts  
lint-auto-fix:
    @just lint true

# Docker shortcuts
docker:
    @just docker-dev

docker-start:
    @just docker-dev start

docker-stop:
    @just docker-dev stop

# Demo shortcuts
demo-simple:
    @just demo-fastagent-simple