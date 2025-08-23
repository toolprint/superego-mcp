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
    @echo "  url \"https://files.pythonhosted.org/packages/source/s/superego-mcp/superego-mcp-0.0.0.tar.gz\"" >> superego.rb
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
        pipx install --force ./dist/superego_mcp-0.0.0-py3-none-any.whl; \
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
    @echo "Verifying demo readiness..."
    cd demo && python setup_verification_cli.py

# Demo All - Run complete demo suite
demo-all: demo-scenarios demo-fastagent-simple
    @echo "Complete demo suite finished!"

# Show project info
info:
    @echo "Project: Superego MCP Server"
    @echo "Version: 0.0.0"
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

# =============================================================================
# CONTAINER TESTING TASKS
# Comprehensive testing for containerized deployment
# =============================================================================

# Validate container testing environment
test-container-validate:
    @echo "Validating container testing environment..."
    @echo "Installing container test dependencies..."
    @uv sync --extra container-test
    uv run python scripts/test_container_validation.py

# Build container image for testing
test-container-build:
    @echo "Building container image for testing..."
    docker build -t superego-mcp:latest -f docker/production/Dockerfile .
    @echo "✓ Container image built successfully"

# Run basic container tests
test-container:
    @echo "Running container tests..."
    @echo "Installing container test dependencies..."
    @uv sync --extra container-test
    uv run pytest tests/test_container.py -v --tb=short
    @echo "✓ Container tests completed"

# Run container tests with specific markers
test-container-startup:
    @echo "Running container startup tests..."
    uv run pytest tests/test_container.py::TestContainerStartup -v

test-container-transports:
    @echo "Running container transport tests..."
    uv run pytest tests/test_container.py::TestContainerTransports -v

test-container-performance:
    @echo "Running container performance tests..."
    uv run pytest tests/test_container.py::TestContainerPerformance -v

test-container-security:
    @echo "Running container security tests..."
    uv run pytest tests/test_container.py::TestContainerSecurity -v

test-container-limits:
    @echo "Running container resource limit tests..."
    uv run pytest tests/test_container.py::TestContainerResourceLimits -v

test-container-integration:
    @echo "Running container integration tests..."
    uv run pytest tests/test_container.py::TestContainerIntegration -v

test-container-scenarios:
    @echo "Running container deployment scenario tests..."
    uv run pytest tests/test_container.py::TestContainerScenarios -v

# Run performance benchmark tests (marked with @pytest.mark.performance)
test-container-benchmarks:
    @echo "Running container performance benchmarks..."
    uv run pytest tests/test_container.py::TestContainerPerformanceBenchmarks -v -m performance

# Run comprehensive container test suite
test-container-full: test-container-build test-container
    @echo "✓ Full container test suite completed"

# Run container tests in Docker Compose environment
test-container-compose:
    @echo "Testing container in Docker Compose environment..."
    @echo "Starting basic services..."
    docker-compose up -d superego-mcp redis
    @echo "Waiting for services to be ready..."
    sleep 30
    @echo "Running container validation tests..."
    docker-compose exec superego-mcp curl -f http://localhost:8000/v1/health || echo "Health check failed"
    docker-compose exec superego-mcp curl -f http://localhost:8000/v1/server-info || echo "Server info failed"
    @echo "Stopping services..."
    docker-compose down
    @echo "✓ Docker Compose container tests completed"

# Test container with resource limits
test-container-with-limits:
    @echo "Testing container with strict resource limits..."
    docker run --rm -d \
        --name test-superego-limits \
        --memory=512m \
        --cpus=1.0 \
        -p 8080:8000 \
        -e SUPEREGO_ENV=test \
        superego-mcp:latest
    @echo "Waiting for container to start..."
    sleep 15
    @echo "Testing container health..."
    curl -f http://localhost:8080/v1/health || echo "Health check failed"
    @echo "Stopping test container..."
    docker stop test-superego-limits
    @echo "✓ Resource limit tests completed"

# Validate container startup performance
test-container-startup-time:
    @echo "Testing container startup performance..."
    @echo "Starting container and measuring startup time..."
    start_time=$$(date +%s); \
    docker run --rm -d --name test-superego-startup -p 8081:8000 superego-mcp:latest; \
    while ! curl -s http://localhost:8081/v1/health >/dev/null 2>&1; do \
        sleep 1; \
        if [ $$(($(date +%s) - start_time)) -gt 60 ]; then \
            echo "❌ Startup timeout exceeded 60 seconds"; \
            docker stop test-superego-startup 2>/dev/null || true; \
            exit 1; \
        fi; \
    done; \
    end_time=$$(date +%s); \
    startup_time=$$((end_time - start_time)); \
    echo "✓ Container startup time: $${startup_time}s"; \
    docker stop test-superego-startup; \
    if [ $$startup_time -gt 30 ]; then \
        echo "⚠️  Startup time exceeds 30s threshold"; \
    fi

# Clean up container test artifacts
test-container-clean:
    @echo "Cleaning up container test artifacts..."
    @docker stop $$(docker ps -q --filter "name=test-superego") 2>/dev/null || true
    @docker rm $$(docker ps -aq --filter "name=test-superego") 2>/dev/null || true
    @docker network prune -f
    @echo "✓ Container test cleanup completed"

# ============================================================================= 
# DOCKER WORKFLOW TASKS
# Comprehensive Docker workflow for development and production deployment
# =============================================================================

# Build Docker images (production and development)
docker-build target="all":
    @echo "Building Docker images with optimized cross-compilation for: {{target}}"
    @echo "🚀 Using enhanced multi-platform builds (6-10x faster ARM64)" 
    @if [ "{{target}}" = "all" ] || [ "{{target}}" = "production" ]; then \
        echo "Building production image with optimized docker-bake..."; \
        export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ'); \
        export GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown"); \
        export VERSION=$(grep '^version' pyproject.toml | cut -d'"' -f2); \
        docker buildx bake production; \
    fi
    @if [ "{{target}}" = "all" ] || [ "{{target}}" = "development" ]; then \
        echo "Building development image with optimized docker-bake..."; \
        export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ'); \
        export GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown"); \
        export VERSION=$(grep '^version' pyproject.toml | cut -d'"' -f2); \
        docker buildx bake development; \
    fi
    @echo "✓ Docker images built successfully with cross-compilation for {{target}}"

# Build production image only  
docker-build-prod:
    @echo "Building production Docker image..."
    just docker-build production

# Build development image only
docker-build-dev:
    @echo "Building development Docker image..."
    just docker-build development

# Fast multi-platform build (recommended - builds both AMD64 and ARM64)
docker-build-multi-arch:
    @echo "Building multi-platform images with cross-compilation..."
    @echo "🚀 Optimized for both AMD64 and ARM64 simultaneously (6-10x faster than native builds)"
    @export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ'); \
    export GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown"); \
    export VERSION=$(grep '^version' pyproject.toml | cut -d'"' -f2); \
    docker buildx bake multi-arch

# Test optimized multi-platform build
test-multi-arch-build:
    @echo "Testing optimized multi-platform Docker build..."
    @echo "🔧 Verifying buildx cross-compilation setup..."
    @if [ "$(uname -m)" = "arm64" ] || [ "$(uname -m)" = "aarch64" ]; then \
        echo "✓ Running on native ARM64 architecture"; \
    else \
        echo "✓ Running on AMD64 with ARM64 emulation (6-10x faster)"; \
    fi
    @echo "Verifying Docker Buildx multi-platform support..."
    @docker buildx inspect --bootstrap | grep -q "linux/arm64" && \
        echo "✓ ARM64 platform support confirmed" || { \
        echo "❌ ARM64 platform support not available"; \
        echo "💡 Run: docker buildx create --use --driver docker-container"; \
        exit 1; \
    }
    @echo "🧪 Running quick multi-platform build test..."
    just docker-build-multi-arch

# Start development environment with hot-reload
docker-dev action="up":
    @echo "Managing development Docker environment..."
    @if [ "{{action}}" = "up" ]; then \
        echo "Starting development environment with hot-reload..."; \
        echo "🔥 Hot-reload enabled for: src/, config/, tests/"; \
        echo "🐛 Debug port available: 5678 (set DEBUGPY_ENABLED=1)"; \
        echo "📊 Server: http://localhost:8002"; \
        echo "📈 Monitor: http://localhost:8003 (with --profile monitoring)"; \
        echo ""; \
        echo "Use Ctrl+C to stop, or run 'just docker-dev stop' from another terminal"; \
        docker-compose -f docker-compose.dev.yml up superego-dev; \
    elif [ "{{action}}" = "start" ]; then \
        echo "Starting development environment in background..."; \
        docker-compose -f docker-compose.dev.yml up -d superego-dev; \
        echo "✓ Development environment started"; \
        echo "📊 Server: http://localhost:8002"; \
        echo "📋 Logs: just docker-dev logs"; \
        echo "🔧 Shell: just docker-dev shell"; \
    elif [ "{{action}}" = "stop" ]; then \
        echo "Stopping development environment..."; \
        docker-compose -f docker-compose.dev.yml down; \
        echo "✓ Development environment stopped"; \
    elif [ "{{action}}" = "restart" ]; then \
        echo "Restarting development environment..."; \
        docker-compose -f docker-compose.dev.yml restart superego-dev; \
        echo "✓ Development environment restarted"; \
    elif [ "{{action}}" = "logs" ]; then \
        echo "Showing development environment logs (Ctrl+C to exit)..."; \
        docker-compose -f docker-compose.dev.yml logs -f superego-dev; \
    elif [ "{{action}}" = "shell" ]; then \
        echo "Opening shell in development container..."; \
        docker-compose -f docker-compose.dev.yml exec superego-dev bash; \
    elif [ "{{action}}" = "status" ]; then \
        echo "Development environment status:"; \
        docker-compose -f docker-compose.dev.yml ps superego-dev; \
        if docker-compose -f docker-compose.dev.yml ps superego-dev | grep -q "Up"; then \
            echo "📊 Server: http://localhost:8002"; \
            echo "🏥 Health: http://localhost:8002/health"; \
            curl -sf http://localhost:8002/health > /dev/null 2>&1 && echo "✓ Health check: PASSED" || echo "✗ Health check: FAILED"; \
        fi; \
    else \
        echo "Invalid action: {{action}}"; \
        echo "Available actions: up, start, stop, restart, logs, shell, status"; \
        exit 1; \
    fi

# Start development environment with full monitoring
docker-dev-full:
    @echo "Starting development environment with monitoring dashboard..."
    @echo "📊 Server: http://localhost:8002"
    @echo "📈 Monitor: http://localhost:8003" 
    docker-compose -f docker-compose.dev.yml --profile full up

# Start development environment with debugging enabled
docker-dev-debug wait="false":
    @echo "Starting development environment with debugging..."
    @if [ "{{wait}}" = "true" ]; then \
        echo "🐛 Server will WAIT for debugger client on port 5678"; \
        echo "Configure your IDE to connect to localhost:5678 before server starts"; \
        export DEBUGPY_ENABLED=1; \
        export DEBUGPY_WAIT_FOR_CLIENT=1; \
    else \
        echo "🐛 Debugger available on port 5678 (non-blocking)"; \
        echo "Configure your IDE to connect to localhost:5678"; \
        export DEBUGPY_ENABLED=1; \
        export DEBUGPY_WAIT_FOR_CLIENT=0; \
    fi; \
    docker-compose -f docker-compose.dev.yml up superego-dev

# Start production environment
docker-prod action="up" profile="basic":
    @echo "Managing production Docker environment..."
    @if [ "{{action}}" = "up" ]; then \
        echo "Starting production environment..."; \
        echo "🏭 Production stack with profile: {{profile}}"; \
        echo "🌐 Server: http://localhost (via nginx)"; \
        echo "📊 Metrics: http://localhost/prometheus (monitoring profile)"; \
        echo "📈 Grafana: http://localhost/grafana (monitoring profile)"; \
        if [ "{{profile}}" = "basic" ]; then \
            docker-compose -f docker-compose.yml up; \
        elif [ "{{profile}}" = "monitoring" ]; then \
            docker-compose -f docker-compose.yml --profile monitoring up; \
        elif [ "{{profile}}" = "full" ]; then \
            docker-compose -f docker-compose.yml --profile full up; \
        else \
            echo "Invalid profile: {{profile}}. Use: basic, monitoring, full"; \
            exit 1; \
        fi; \
    elif [ "{{action}}" = "start" ]; then \
        echo "Starting production environment in background ({{profile}} profile)..."; \
        if [ "{{profile}}" = "basic" ]; then \
            docker-compose -f docker-compose.yml up -d; \
        elif [ "{{profile}}" = "monitoring" ]; then \
            docker-compose -f docker-compose.yml --profile monitoring up -d; \
        elif [ "{{profile}}" = "full" ]; then \
            docker-compose -f docker-compose.yml --profile full up -d; \
        fi; \
        echo "✓ Production environment started ({{profile}} profile)"; \
        echo "🌐 Server: http://localhost"; \
        echo "📋 Logs: just docker-prod logs"; \
    elif [ "{{action}}" = "stop" ]; then \
        echo "Stopping production environment..."; \
        docker-compose -f docker-compose.yml down; \
        echo "✓ Production environment stopped"; \
    elif [ "{{action}}" = "restart" ]; then \
        echo "Restarting production environment..."; \
        docker-compose -f docker-compose.yml restart; \
        echo "✓ Production environment restarted"; \
    elif [ "{{action}}" = "logs" ]; then \
        echo "Showing production environment logs (Ctrl+C to exit)..."; \
        docker-compose -f docker-compose.yml logs -f; \
    elif [ "{{action}}" = "status" ]; then \
        echo "Production environment status:"; \
        docker-compose -f docker-compose.yml ps; \
        echo ""; \
        if docker-compose -f docker-compose.yml ps | grep -q "Up"; then \
            echo "🌐 Server: http://localhost"; \
            echo "🏥 Health check:"; \
            curl -sf http://localhost/health > /dev/null 2>&1 && echo "✓ HTTP endpoint: PASSED" || echo "✗ HTTP endpoint: FAILED"; \
        fi; \
    else \
        echo "Invalid action: {{action}}"; \
        echo "Available actions: up, start, stop, restart, logs, status"; \
        exit 1; \
    fi

# Clean up Docker containers, images, and volumes
docker-clean target="all":
    @echo "Cleaning up Docker resources for target: {{target}}"
    @if [ "{{target}}" = "all" ] || [ "{{target}}" = "containers" ]; then \
        echo "Stopping and removing containers..."; \
        docker-compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true; \
        docker-compose -f docker-compose.dev.yml down --remove-orphans 2>/dev/null || true; \
        echo "✓ Containers cleaned"; \
    fi
    @if [ "{{target}}" = "all" ] || [ "{{target}}" = "images" ]; then \
        echo "Removing Superego MCP images..."; \
        docker rmi superego-mcp:latest 2>/dev/null || true; \
        docker rmi superego-mcp-dev:latest 2>/dev/null || true; \
        docker rmi ghcr.io/toolprint/superego-mcp:latest 2>/dev/null || true; \
        docker rmi ghcr.io/toolprint/superego-mcp-dev:latest 2>/dev/null || true; \
        echo "✓ Images cleaned"; \
    fi
    @if [ "{{target}}" = "all" ] || [ "{{target}}" = "volumes" ]; then \
        echo "Removing named volumes..."; \
        docker volume rm superego-dev-logs 2>/dev/null || true; \
        docker volume rm superego-dev-tmp 2>/dev/null || true; \
        docker volume rm superego-dev-cache 2>/dev/null || true; \
        echo "✓ Volumes cleaned"; \
    fi
    @if [ "{{target}}" = "all" ] || [ "{{target}}" = "system" ]; then \
        echo "Running Docker system cleanup..."; \
        docker system prune -f; \
        echo "✓ System cleanup completed"; \
    fi
    @echo "🧹 Docker cleanup completed for {{target}}"

# Run test suite in containerized environment
container-test mode="basic":
    @echo "Running tests in containerized environment..."
    @if [ "{{mode}}" = "basic" ]; then \
        echo "Starting development container for testing..."; \
        docker-compose -f docker-compose.dev.yml up -d superego-dev; \
        echo "Waiting for container to be ready..."; \
        sleep 5; \
        echo "Running test suite..."; \
        docker-compose -f docker-compose.dev.yml exec -T superego-dev uv run pytest tests/ -v --tb=short; \
        echo "Stopping container..."; \
        docker-compose -f docker-compose.dev.yml down; \
    elif [ "{{mode}}" = "coverage" ]; then \
        echo "Running tests with coverage in container..."; \
        docker-compose -f docker-compose.dev.yml up -d superego-dev; \
        sleep 5; \
        docker-compose -f docker-compose.dev.yml exec -T superego-dev uv run pytest tests/ --cov=superego_mcp --cov-report=html --cov-report=term-missing; \
        echo "Coverage report available in htmlcov/"; \
        docker-compose -f docker-compose.dev.yml down; \
    elif [ "{{mode}}" = "watch" ]; then \
        echo "Running tests with file watching (interactive mode)..."; \
        echo "Container will stay running - use Ctrl+C to stop"; \
        docker-compose -f docker-compose.dev.yml up -d superego-dev; \
        sleep 5; \
        docker-compose -f docker-compose.dev.yml exec superego-dev bash -c "uv run watchfiles 'uv run pytest tests/ -v --tb=short' src/ tests/"; \
    elif [ "{{mode}}" = "performance" ]; then \
        echo "Running performance tests in container..."; \
        docker-compose -f docker-compose.dev.yml up -d superego-dev; \
        sleep 5; \
        docker-compose -f docker-compose.dev.yml exec -T superego-dev uv run pytest tests/test_performance_optimization.py -v; \
        docker-compose -f docker-compose.dev.yml down; \
    else \
        echo "Invalid mode: {{mode}}"; \
        echo "Available modes: basic, coverage, watch, performance"; \
        exit 1; \
    fi
    @echo "✓ Container testing completed ({{mode}} mode)"

# Production deployment automation
deploy-production environment="staging" check="true":
    @echo "🚀 Deploying to {{environment}} environment..."
    @if [ "{{check}}" = "true" ]; then \
        echo "Running pre-deployment checks..."; \
        echo "1. Running quality checks..."; \
        just check; \
        echo "2. Building production image..."; \
        just docker-build-prod; \
        echo "3. Running security scan..."; \
        docker buildx bake security-scan; \
        echo "4. Testing production image..."; \
        docker run --rm -d --name superego-deploy-test -p 8899:8000 superego-mcp:latest; \
        sleep 10; \
        curl -sf http://localhost:8899/health > /dev/null || (echo "Production image health check failed"; docker stop superego-deploy-test; exit 1); \
        docker stop superego-deploy-test; \
        echo "✓ Pre-deployment checks passed"; \
    fi
    @echo "Deploying with docker-compose ({{environment}} profile)..."
    @if [ "{{environment}}" = "staging" ]; then \
        export SUPEREGO_ENV=staging; \
        export SUPEREGO_DEBUG=false; \
        export SUPEREGO_LOG_LEVEL=info; \
        docker-compose -f docker-compose.yml --profile monitoring up -d; \
    elif [ "{{environment}}" = "production" ]; then \
        export SUPEREGO_ENV=production; \
        export SUPEREGO_DEBUG=false; \
        export SUPEREGO_LOG_LEVEL=warning; \
        docker-compose -f docker-compose.yml --profile full up -d; \
    else \
        echo "Invalid environment: {{environment}}. Use: staging, production"; \
        exit 1; \
    fi
    @echo "✅ Deployment to {{environment}} completed successfully"
    @echo "🌐 Server: http://localhost"
    @echo "📊 Monitoring: http://localhost/grafana (admin/admin)"
    @echo "📈 Metrics: http://localhost/prometheus"
    @echo ""
    @echo "Post-deployment verification:"
    @echo "  Health: curl -sf http://localhost/health"
    @echo "  Logs:   just docker-prod logs"
    @echo "  Status: just docker-prod status"

# Quick deployment without checks (for development)
deploy-quick:
    @echo "🚀 Quick deployment (skipping checks)..."
    just deploy-production staging false

# Rollback deployment (stop current, restart with previous image)
deploy-rollback:
    @echo "⏪ Rolling back deployment..."
    @echo "Stopping current deployment..."
    docker-compose -f docker-compose.yml down
    @echo "Starting with previous configuration..."
    docker-compose -f docker-compose.yml up -d
    @echo "✓ Rollback completed"
    @echo "Verify with: just docker-prod status"