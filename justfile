# Superego MCP Server Development Tasks
# Run with: just <task-name>

# Default task - show available commands
default:
    @just --list

# Development setup
dev:
    @echo "Setting up development environment..."
    uv sync --all-extras
    @echo "Development environment ready!"

# Install dependencies
install:
    @echo "Installing dependencies..."
    uv sync

# Run the server
run:
    @echo "Starting Superego MCP Server..."
    uv run superego mcp

# Run the server (legacy entry point)
run-legacy:
    @echo "Starting Superego MCP Server (legacy)..."
    uv run superego-mcp

# Test CLI evaluation
test-advise:
    @echo "Testing CLI evaluation..."
    @echo '{"tool_name": "ls", "tool_input": {"directory": "/tmp"}, "session_id": "test", "transcript_path": "", "cwd": "/tmp", "hook_event_name": "PreToolUse"}' | uv run superego advise

# Run tests
test:
    @echo "Running tests..."
    uv run pytest

# Run tests with coverage
test-cov:
    @echo "Running tests with coverage..."
    uv run pytest --cov=superego_mcp --cov-report=html --cov-report=term-missing

# Run specific test file
test-file file:
    @echo "Running tests in {{file}}..."
    uv run pytest {{file}}

# Lint code
lint:
    @echo "Linting code..."
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

# Fix linting issues
lint-fix:
    @echo "Fixing linting issues..."
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

# Type check with mypy
typecheck:
    @echo "Type checking..."
    uv run mypy src/

# Run all quality checks
check: lint typecheck test
    @echo "All checks completed!"

# Clean build artifacts
clean:
    @echo "Cleaning build artifacts..."
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info/
    rm -rf .pytest_cache/
    rm -rf .mypy_cache/
    rm -rf .ruff_cache/
    rm -rf htmlcov/
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Build package
build: clean
    @echo "Building package..."
    uv build

# Build and test package installation
build-test: build
    @echo "Testing package installation..."
    # Test wheel installation
    @echo "Installing wheel to temporary environment..."
    python -m venv /tmp/superego-test-env
    /tmp/superego-test-env/bin/pip install dist/*.whl
    @echo "Testing CLI installation..."
    /tmp/superego-test-env/bin/superego --version
    /tmp/superego-test-env/bin/superego --help
    @echo "Cleaning up test environment..."
    rm -rf /tmp/superego-test-env
    @echo "Package installation test completed!"

# Test installation with various methods
test-install: build
    @echo "Testing installation methods..."
    @echo "Testing uvx installation..."
    uvx --from ./dist/*.whl superego --version
    @echo "Testing uv run installation..."
    uv run --from ./dist/*.whl superego --version
    @echo "All installation methods tested successfully!"

# Prepare release
prepare-release:
    @echo "Preparing release..."
    @echo "Running all quality checks..."
    just check
    @echo "Building package..."
    just build
    @echo "Testing installation..."
    just build-test
    @echo "Release preparation completed!"

# Generate release notes
release-notes version:
    @echo "Generating release notes for version {{version}}..."
    @echo "# Release {{version}}" > RELEASE_NOTES.md
    @echo "" >> RELEASE_NOTES.md
    @echo "## Changes" >> RELEASE_NOTES.md
    @echo "" >> RELEASE_NOTES.md
    git log --oneline --grep="^(feat|fix|docs|style|refactor|test|chore)" --since="$(git describe --tags --abbrev=0)..HEAD" >> RELEASE_NOTES.md
    @echo "Release notes generated in RELEASE_NOTES.md"

# Create homebrew formula
homebrew-formula: build
    @echo "Generating Homebrew formula..."
    @echo "class Superego < Formula" > superego.rb
    @echo "  desc \"Intelligent tool request interception for AI agents\"" >> superego.rb
    @echo "  homepage \"https://github.com/toolprint/superego-mcp\"" >> superego.rb
    @echo "  url \"https://files.pythonhosted.org/packages/source/s/superego-mcp/superego-mcp-0.1.0.tar.gz\"" >> superego.rb
    @echo "  sha256 \"$(sha256sum dist/*.tar.gz | cut -d' ' -f1)\"" >> superego.rb
    @echo "  license \"MIT\"" >> superego.rb
    @echo "" >> superego.rb
    @echo "  depends_on \"python@3.11\"" >> superego.rb
    @echo "" >> superego.rb
    @echo "  def install" >> superego.rb
    @echo "    virtualenv_install_with_resources" >> superego.rb
    @echo "  end" >> superego.rb
    @echo "" >> superego.rb
    @echo "  test do" >> superego.rb
    @echo "    system bin/\"superego\", \"--version\"" >> superego.rb
    @echo "  end" >> superego.rb
    @echo "end" >> superego.rb
    @echo "Homebrew formula generated: superego.rb"

# Install local development build with pipx
install-dev: build
    @echo "Installing local development build with pipx..."
    @if command -v pipx >/dev/null 2>&1; then \
        echo "Checking if superego-mcp is already installed..."; \
        if pipx list | grep -q "superego-mcp"; then \
            echo "Uninstalling existing version..."; \
            pipx uninstall superego-mcp; \
        fi; \
        echo "Installing from local wheel..."; \
        pipx install --force ./dist/superego_mcp-0.1.0-py3-none-any.whl; \
        echo "✓ Installed superego-mcp with pipx"; \
        echo "Testing installation..."; \
        superego --version; \
        echo ""; \
        echo "Superego is now available globally as 'superego'"; \
        echo "Try: superego --help"; \
    else \
        echo "Error: pipx not found. Install with:"; \
        echo "  brew install pipx  # macOS"; \
        echo "  python -m pip install --user pipx  # Other systems"; \
        exit 1; \
    fi

# Uninstall development build from pipx
uninstall-dev:
    @echo "Uninstalling superego-mcp from pipx..."
    @if command -v pipx >/dev/null 2>&1; then \
        if pipx list | grep -q "superego-mcp"; then \
            pipx uninstall superego-mcp; \
            echo "✓ Uninstalled superego-mcp from pipx"; \
        else \
            echo "superego-mcp is not installed via pipx"; \
        fi; \
    else \
        echo "pipx not found - nothing to uninstall"; \
    fi

# Reinstall development build (clean install)
reinstall-dev: uninstall-dev install-dev
    @echo "✓ Reinstalled development build"

# Show pipx installation status
pipx-status:
    @echo "Checking pipx installation status..."
    @if command -v pipx >/dev/null 2>&1; then \
        echo "pipx is installed: $(which pipx)"; \
        echo "pipx version: $(pipx --version)"; \
        echo ""; \
        echo "Installed packages:"; \
        pipx list; \
        echo ""; \
        if pipx list | grep -q "superego-mcp"; then \
            echo "✓ superego-mcp is installed via pipx"; \
            echo "Testing command:"; \
            superego --version 2>/dev/null || echo "Command not found in PATH"; \
        else \
            echo "✗ superego-mcp is not installed via pipx"; \
        fi; \
    else \
        echo "✗ pipx is not installed"; \
        echo "Install with:"; \
        echo "  brew install pipx  # macOS"; \
        echo "  python -m pip install --user pipx  # Other systems"; \
    fi

# Demo - run legacy HTTP client demo
demo:
    @echo "Starting demo with legacy HTTP client..."
    uv run --extra demo python -m demo.client

# FastAgent Demo - Simple CLI-based demo (recommended)
demo-fastagent-simple:
    @echo "Starting FastAgent Simple Demo..."
    @echo "This will run security scenarios and interactive mode"
    cd demo && uv run --extra demo python simple_fastagent_demo.py

# FastAgent Demo - Full integration demo
demo-fastagent-full:
    @echo "Starting FastAgent Full Demo..."
    @echo "This requires the complete fast-agent-mcp package"
    cd demo && uv run --extra demo python fastagent_demo.py

# Demo Scenarios - Run just the security scenarios
demo-scenarios:
    @echo "Running security scenarios demonstration..."
    cd demo && uv run --extra demo python security_scenarios.py

# Interactive FastAgent Demo
demo-interactive:
    @echo "Starting interactive FastAgent session..."
    @echo "Make sure Superego MCP server is running first!"
    cd demo && uv run --extra demo fast-agent go demo_agent.py --config fastagent.config.yaml

# Demo Setup - Check dependencies and setup
demo-setup:
    @echo "Setting up demo environment..."
    uv sync --extra demo
    @echo "Checking FastAgent availability..."
    uv run --extra demo fast-agent --version || echo "FastAgent not available - install with 'uv sync --extra demo'"
    @echo "Demo setup complete!"

# Demo Verify - Check demo readiness
demo-verify:
    @echo "Verifying FastAgent demo readiness..."
    cd demo && uv run --extra demo python verify_demo.py

# Demo All - Run complete demo suite
demo-all: demo-scenarios demo-fastagent-simple
    @echo "Complete demo suite finished!"

# Show project info
info:
    @echo "Project: Superego MCP Server"
    @echo "Version: 0.1.0"
    @echo "Python: $(python --version)"
    @echo "UV: $(uv --version)"
    @echo ""
    @echo "Dependencies:"
    @uv tree
    @echo ""
    @echo "Development Commands:"
    @echo "  just install-dev     Install local build with pipx"
    @echo "  just uninstall-dev   Uninstall from pipx"
    @echo "  just reinstall-dev   Clean reinstall"
    @echo "  just pipx-status     Show pipx installation status"

# Format code
format:
    @echo "Formatting code..."
    uv run ruff format src/ tests/

# Watch for changes and run tests
watch:
    @echo "Watching for changes..."
    uv run watchfiles "just test" src/ tests/

# Generate requirements.txt for compatibility
requirements:
    @echo "Generating requirements.txt..."
    uv export --format requirements-txt --no-hashes > requirements.txt
    @echo "Generated requirements.txt"

# Update dependencies
update:
    @echo "Updating dependencies..."
    uv lock --upgrade

# Security check
security:
    @echo "Running security checks..."
    uv run pip-audit

# Performance Tasks

# Run server with performance optimizations
run-optimized:
    @echo "Starting Superego MCP Server with performance optimizations..."
    uv run python -m superego_mcp.main_optimized

# Run performance tests
test-performance:
    @echo "Running performance tests..."
    uv run pytest tests/test_performance_optimization.py -v

# Run load tests
load-test:
    @echo "Running load tests..."
    @echo "Make sure server is running with: just run-optimized"
    uv run python tests/load_test_performance.py

# Run performance demo
demo-performance:
    @echo "Running performance optimization demo..."
    @echo "Make sure server is running with: just run-optimized"
    uv run python demo/performance_demo.py

# Start monitoring dashboard only
monitor:
    @echo "Starting monitoring dashboard on http://localhost:9090/dashboard"
    @echo "Metrics available at http://localhost:9090/metrics"
    uv run python -c "from superego_mcp.presentation.monitoring import MonitoringDashboard; import asyncio; d = MonitoringDashboard(None, None, None); asyncio.run(d.start()); input('Press Enter to stop...')"

# Multi-transport performance test
test-multi-transport-perf:
    @echo "Testing multi-transport performance..."
    uv run python demo/multi_transport_demo.py --performance

# Benchmark rule evaluation
benchmark-rules:
    @echo "Benchmarking rule evaluation performance..."
    uv run python -m timeit -s "from superego_mcp.domain.models import ToolRequest; from superego_mcp.domain.security_policy import SecurityPolicyEngine; import asyncio; engine = SecurityPolicyEngine('config/rules.yaml'); request = ToolRequest(tool_name='ls', parameters={}, session_id='test', agent_id='test', cwd='/tmp')" "asyncio.run(engine.evaluate(request))"

# Profile server performance
profile:
    @echo "Profiling server performance..."
    uv run python -m cProfile -o profile.stats -m superego_mcp.main_optimized

# Analyze profile results
profile-analyze:
    @echo "Analyzing profile results..."
    uv run python -m pstats profile.stats