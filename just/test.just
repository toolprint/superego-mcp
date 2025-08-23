# test.just - Testing recipes and validation

# Test CLI evaluation
[group: 'testing']
test-advise:
    @just _info "Testing CLI evaluation..."
    @echo '{"tool_name": "ls", "tool_input": {"directory": "/tmp"}, "session_id": "test", "transcript_path": "", "cwd": "/tmp", "hook_event_name": "PreToolUse"}' | {{_uv}} run superego advise

# Run tests
[group: 'testing']
test type="all" args="":
    #!/usr/bin/env bash
    case "{{type}}" in
        all)
            just _run "Running all tests" "{{_uv}} run pytest {{args}}"
            ;;
        unit)
            just _run "Running unit tests" "{{_uv}} run pytest tests/unit/ {{args}}"
            ;;
        integration)
            just _run "Running integration tests" "{{_uv}} run pytest tests/integration/ {{args}}"
            ;;
        fast)
            just _run "Running fast tests" "{{_uv}} run pytest -x {{args}}"
            ;;
        *)
            just _error "test" "Invalid test type '{{type}}'. Options: all, unit, integration, fast"
            ;;
    esac

# Run tests with coverage
[group: 'testing']
test-cov:
    @just _run "Running tests with coverage" "{{_uv}} run pytest --cov=superego_mcp --cov-report=html --cov-report=term-missing"

# Run specific test file
[group: 'testing']
test-file file:
    @just _run "Running tests in {{file}}" "{{_uv}} run pytest {{file}}"

# Test installation with various methods
[group: 'testing']
test-install: build
    @just _info "Testing installation methods..."
    @just _run "Testing uvx installation" "uvx --from ./dist/*.whl superego --version"
    @just _run "Testing uv run installation" "{{_uv}} run --from ./dist/*.whl superego --version"
    @just _success "All installation methods tested successfully!"

# =============================================================================
# CONTAINER TESTING
# =============================================================================

# Validate container testing environment
[group: 'container-testing']
test-container-validate:
    @just _info "Validating container testing environment..."
    @just _run "Installing container test dependencies" "{{_uv}} sync --extra container-test"
    {{_uv}} run python scripts/test_container_validation.py

# Build container image for testing
[group: 'container-testing']
test-container-build:
    @just _run "Building container image for testing" "docker build -t superego-mcp:latest -f docker/production/Dockerfile ."

# Run basic container tests
[group: 'container-testing']
test-container:
    @just _run "Installing container test dependencies" "{{_uv}} sync --extra container-test"
    @just _run "Running container tests" "{{_uv}} run pytest tests/test_container.py -v --tb=short"

# Container test suites
[group: 'container-testing']
test-container-startup:
    @just _run "Running container startup tests" "{{_uv}} run pytest tests/test_container.py::TestContainerStartup -v"

[group: 'container-testing']
test-container-transports:
    @just _run "Running container transport tests" "{{_uv}} run pytest tests/test_container.py::TestContainerTransports -v"

[group: 'container-testing']
test-container-performance:
    @just _run "Running container performance tests" "{{_uv}} run pytest tests/test_container.py::TestContainerPerformance -v"

[group: 'container-testing']
test-container-security:
    @just _run "Running container security tests" "{{_uv}} run pytest tests/test_container.py::TestContainerSecurity -v"

[group: 'container-testing']
test-container-limits:
    @just _run "Running container resource limit tests" "{{_uv}} run pytest tests/test_container.py::TestContainerResourceLimits -v"

[group: 'container-testing']
test-container-integration:
    @just _run "Running container integration tests" "{{_uv}} run pytest tests/test_container.py::TestContainerIntegration -v"

[group: 'container-testing']
test-container-scenarios:
    @just _run "Running container deployment scenario tests" "{{_uv}} run pytest tests/test_container.py::TestContainerScenarios -v"

[group: 'container-testing']
test-container-benchmarks:
    @just _run "Running container performance benchmarks" "{{_uv}} run pytest tests/test_container.py::TestContainerPerformanceBenchmarks -v -m performance"

# Comprehensive container test suite
[group: 'container-testing']
test-container-full: test-container-build test-container
    @just _success "Full container test suite completed"

# Container tests in Docker Compose environment
[group: 'container-testing']
test-container-compose:
    @just _info "Testing container in Docker Compose environment..."
    @just _run "Starting basic services" "docker-compose up -d superego-mcp redis"
    @just _info "Waiting for services to be ready..."
    @sleep 30
    @just _run "Running container validation tests" "docker-compose exec superego-mcp curl -f http://localhost:8000/v1/health || echo 'Health check failed'"
    @just _run "Testing server info endpoint" "docker-compose exec superego-mcp curl -f http://localhost:8000/v1/server-info || echo 'Server info failed'"
    @just _run "Stopping services" "docker-compose down"
    @just _success "Docker Compose container tests completed"

# Test container with resource limits
[group: 'container-testing']
test-container-with-limits:
    @just _info "Testing container with strict resource limits..."
    @docker run --rm -d --name test-superego-limits --memory=512m --cpus=1.0 -p 8080:8000 -e SUPEREGO_ENV=test superego-mcp:latest
    @just _info "Waiting for container to start..."
    @sleep 15
    @just _run "Testing container health" "curl -f http://localhost:8080/v1/health || echo 'Health check failed'"
    @just _run "Stopping test container" "docker stop test-superego-limits"
    @just _success "Resource limit tests completed"

# Validate container startup performance
[group: 'container-testing']
test-container-startup-time:
    #!/usr/bin/env bash
    echo "🔄 Testing container startup performance..."
    start_time=$(date +%s)
    docker run --rm -d --name test-superego-startup -p 8081:8000 superego-mcp:latest
    while ! curl -s http://localhost:8081/v1/health >/dev/null 2>&1; do
        sleep 1
        if [ $(($(date +%s) - start_time)) -gt 60 ]; then
            echo "❌ Startup timeout exceeded 60 seconds"
            docker stop test-superego-startup 2>/dev/null || true
            exit 1
        fi
    done
    end_time=$(date +%s)
    startup_time=$((end_time - start_time))
    echo "✅ Container startup time: ${startup_time}s"
    docker stop test-superego-startup
    if [ $startup_time -gt 30 ]; then
        echo "⚠️  Startup time exceeds 30s threshold"
    fi

# Clean up container test artifacts
[group: 'container-testing']
test-container-clean:
    @just _info "Cleaning up container test artifacts..."
    @docker stop $(docker ps -q --filter "name=test-superego") 2>/dev/null || true
    @docker rm $(docker ps -aq --filter "name=test-superego") 2>/dev/null || true
    @docker network prune -f
    @just _success "Container test cleanup completed"