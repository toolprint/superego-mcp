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
    uv run superego-mcp

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