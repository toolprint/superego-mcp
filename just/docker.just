# docker.just - Docker container operations and workflows

# =============================================================================
# DOCKER BUILD TASKS
# =============================================================================

# Build Docker images (production and development)
[group: 'docker']
docker-build target="all":
    #!/usr/bin/env bash
    just _info "Building Docker images with optimized cross-compilation for: {{target}}"
    echo "🚀 Using enhanced multi-platform builds (6-10x faster ARM64)"
    
    export BUILD_DATE=$(just _build_date)
    export GIT_COMMIT=$(just _git_commit)
    export VERSION=$(just _version)
    
    if [ "{{target}}" = "all" ] || [ "{{target}}" = "production" ]; then
        just _run "Building production image with optimized docker-bake" "docker buildx bake production"
    fi
    if [ "{{target}}" = "all" ] || [ "{{target}}" = "development" ]; then
        just _run "Building development image with optimized docker-bake" "docker buildx bake development"
    fi
    just _success "Docker images built successfully with cross-compilation for {{target}}"

# Build production image only  
[group: 'docker']
docker-build-prod:
    @just docker-build production

# Build development image only
[group: 'docker']
docker-build-dev:
    @just docker-build development

# Fast multi-platform build (recommended - builds both AMD64 and ARM64)
[group: 'docker']
docker-build-multi-arch:
    #!/usr/bin/env bash
    just _info "Building multi-platform images with cross-compilation..."
    echo "🚀 Optimized for both AMD64 and ARM64 simultaneously (6-10x faster than native builds)"
    
    export BUILD_DATE=$(just _build_date)
    export GIT_COMMIT=$(just _git_commit)
    export VERSION=$(just _version)
    
    docker buildx bake multi-arch

# Test optimized multi-platform build
[group: 'docker']
test-multi-arch-build:
    #!/usr/bin/env bash
    just _info "Testing optimized multi-platform Docker build..."
    echo "🔧 Verifying buildx cross-compilation setup..."
    
    if [ "$(uname -m)" = "arm64" ] || [ "$(uname -m)" = "aarch64" ]; then
        echo "✅ Running on native ARM64 architecture"
    else
        echo "✅ Running on AMD64 with ARM64 emulation (6-10x faster)"
    fi
    
    just _info "Verifying Docker Buildx multi-platform support..."
    if docker buildx inspect --bootstrap | grep -q "linux/arm64"; then
        just _success "ARM64 platform support confirmed"
    else
        just _error "docker" "ARM64 platform support not available. Run: docker buildx create --use --driver docker-container"
    fi
    
    just _info "Running quick multi-platform build test..."
    just docker-build-multi-arch

# =============================================================================
# DOCKER DEVELOPMENT ENVIRONMENT
# =============================================================================

# Start development environment with hot-reload
[group: 'docker']
docker-dev action="up":
    #!/usr/bin/env bash
    just _info "Managing development Docker environment..."
    case "{{action}}" in
        up)
            echo "Starting development environment with hot-reload..."
            echo "🔥 Hot-reload enabled for: src/, config/, tests/"
            echo "🐛 Debug port available: 5678 (set DEBUGPY_ENABLED=1)"
            echo "📊 Server: http://localhost:8002"
            echo "📈 Monitor: http://localhost:8003 (with --profile monitoring)"
            echo ""
            echo "Use Ctrl+C to stop, or run 'just docker-dev stop' from another terminal"
            docker-compose -f docker-compose.dev.yml up superego-dev
            ;;
        start)
            just _run "Starting development environment in background" "docker-compose -f docker-compose.dev.yml up -d superego-dev"
            echo "📊 Server: http://localhost:8002"
            echo "📋 Logs: just docker-dev logs"
            echo "🔧 Shell: just docker-dev shell"
            ;;
        stop)
            just _run "Stopping development environment" "docker-compose -f docker-compose.dev.yml down"
            ;;
        restart)
            just _run "Restarting development environment" "docker-compose -f docker-compose.dev.yml restart superego-dev"
            ;;
        logs)
            just _info "Showing development environment logs (Ctrl+C to exit)..."
            docker-compose -f docker-compose.dev.yml logs -f superego-dev
            ;;
        shell)
            just _info "Opening shell in development container..."
            docker-compose -f docker-compose.dev.yml exec superego-dev bash
            ;;
        status)
            echo "Development environment status:"
            docker-compose -f docker-compose.dev.yml ps superego-dev
            if docker-compose -f docker-compose.dev.yml ps superego-dev | grep -q "Up"; then
                echo "📊 Server: http://localhost:8002"
                echo "🏥 Health: http://localhost:8002/health"
                curl -sf http://localhost:8002/health > /dev/null 2>&1 && echo "✅ Health check: PASSED" || echo "❌ Health check: FAILED"
            fi
            ;;
        *)
            just _error "docker-dev" "Invalid action: {{action}}. Available: up, start, stop, restart, logs, shell, status"
            ;;
    esac

# Start development environment with full monitoring
[group: 'docker']
docker-dev-full:
    @just _info "Starting development environment with monitoring dashboard..."
    @echo "📊 Server: http://localhost:8002"
    @echo "📈 Monitor: http://localhost:8003"
    docker-compose -f docker-compose.dev.yml --profile full up

# Start development environment with debugging enabled
[group: 'docker']
docker-dev-debug wait="false":
    #!/usr/bin/env bash
    just _info "Starting development environment with debugging..."
    if [ "{{wait}}" = "true" ]; then
        echo "🐛 Server will WAIT for debugger client on port 5678"
        echo "Configure your IDE to connect to localhost:5678 before server starts"
        export DEBUGPY_ENABLED=1
        export DEBUGPY_WAIT_FOR_CLIENT=1
    else
        echo "🐛 Debugger available on port 5678 (non-blocking)"
        echo "Configure your IDE to connect to localhost:5678"
        export DEBUGPY_ENABLED=1
        export DEBUGPY_WAIT_FOR_CLIENT=0
    fi
    docker-compose -f docker-compose.dev.yml up superego-dev

# =============================================================================
# DOCKER PRODUCTION ENVIRONMENT  
# =============================================================================

# Start production environment
[group: 'docker']
docker-prod action="up" profile="basic":
    #!/usr/bin/env bash
    just _info "Managing production Docker environment..."
    case "{{action}}" in
        up)
            echo "Starting production environment..."
            echo "🏭 Production stack with profile: {{profile}}"
            echo "🌐 Server: http://localhost (via nginx)"
            echo "📊 Metrics: http://localhost/prometheus (monitoring profile)"
            echo "📈 Grafana: http://localhost/grafana (monitoring profile)"
            
            case "{{profile}}" in
                basic) docker-compose -f docker-compose.yml up ;;
                monitoring) docker-compose -f docker-compose.yml --profile monitoring up ;;
                full) docker-compose -f docker-compose.yml --profile full up ;;
                *) just _error "docker-prod" "Invalid profile: {{profile}}. Use: basic, monitoring, full" ;;
            esac
            ;;
        start)
            just _run "Starting production environment in background ({{profile}} profile)" "docker-compose -f docker-compose.yml $([ '{{profile}}' != 'basic' ] && echo '--profile {{profile}}') up -d"
            echo "🌐 Server: http://localhost"
            echo "📋 Logs: just docker-prod logs"
            ;;
        stop)
            just _run "Stopping production environment" "docker-compose -f docker-compose.yml down"
            ;;
        restart)
            just _run "Restarting production environment" "docker-compose -f docker-compose.yml restart"
            ;;
        logs)
            just _info "Showing production environment logs (Ctrl+C to exit)..."
            docker-compose -f docker-compose.yml logs -f
            ;;
        status)
            echo "Production environment status:"
            docker-compose -f docker-compose.yml ps
            echo ""
            if docker-compose -f docker-compose.yml ps | grep -q "Up"; then
                echo "🌐 Server: http://localhost"
                echo "🏥 Health check:"
                curl -sf http://localhost/health > /dev/null 2>&1 && echo "✅ HTTP endpoint: PASSED" || echo "❌ HTTP endpoint: FAILED"
            fi
            ;;
        *)
            just _error "docker-prod" "Invalid action: {{action}}. Available: up, start, stop, restart, logs, status"
            ;;
    esac

# =============================================================================
# DOCKER UTILITIES
# =============================================================================

# Clean up Docker containers, images, and volumes
[group: 'docker']
docker-clean target="all":
    #!/usr/bin/env bash
    just _info "Cleaning up Docker resources for target: {{target}}"
    
    if [ "{{target}}" = "all" ] || [ "{{target}}" = "containers" ]; then
        just _run "Stopping and removing containers" "docker-compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true; docker-compose -f docker-compose.dev.yml down --remove-orphans 2>/dev/null || true"
    fi
    
    if [ "{{target}}" = "all" ] || [ "{{target}}" = "images" ]; then
        echo "Removing Superego MCP images..."
        docker rmi superego-mcp:latest 2>/dev/null || true
        docker rmi superego-mcp-dev:latest 2>/dev/null || true
        docker rmi ghcr.io/toolprint/superego-mcp:latest 2>/dev/null || true
        docker rmi ghcr.io/toolprint/superego-mcp-dev:latest 2>/dev/null || true
        just _success "Images cleaned"
    fi
    
    if [ "{{target}}" = "all" ] || [ "{{target}}" = "volumes" ]; then
        echo "Removing named volumes..."
        docker volume rm superego-dev-logs superego-dev-tmp superego-dev-cache 2>/dev/null || true
        just _success "Volumes cleaned"
    fi
    
    if [ "{{target}}" = "all" ] || [ "{{target}}" = "system" ]; then
        just _run "Running Docker system cleanup" "docker system prune -f"
    fi
    
    just _success "Docker cleanup completed for {{target}}"

# Run test suite in containerized environment
[group: 'docker']
container-test mode="basic":
    #!/usr/bin/env bash
    just _info "Running tests in containerized environment..."
    case "{{mode}}" in
        basic)
            just _run "Starting development container for testing" "docker-compose -f docker-compose.dev.yml up -d superego-dev"
            sleep 5
            just _run "Running test suite" "docker-compose -f docker-compose.dev.yml exec -T superego-dev {{_uv}} run pytest tests/ -v --tb=short"
            just _run "Stopping container" "docker-compose -f docker-compose.dev.yml down"
            ;;
        coverage)
            just _run "Running tests with coverage in container" "docker-compose -f docker-compose.dev.yml up -d superego-dev"
            sleep 5
            docker-compose -f docker-compose.dev.yml exec -T superego-dev {{_uv}} run pytest tests/ --cov=superego_mcp --cov-report=html --cov-report=term-missing
            echo "Coverage report available in htmlcov/"
            just _run "Stopping container" "docker-compose -f docker-compose.dev.yml down"
            ;;
        watch)
            echo "Running tests with file watching (interactive mode)..."
            echo "Container will stay running - use Ctrl+C to stop"
            just _run "Starting development container" "docker-compose -f docker-compose.dev.yml up -d superego-dev"
            sleep 5
            docker-compose -f docker-compose.dev.yml exec superego-dev bash -c "{{_uv}} run watchfiles '{{_uv}} run pytest tests/ -v --tb=short' src/ tests/"
            ;;
        performance)
            just _run "Running performance tests in container" "docker-compose -f docker-compose.dev.yml up -d superego-dev"
            sleep 5
            just _run "Executing performance tests" "docker-compose -f docker-compose.dev.yml exec -T superego-dev {{_uv}} run pytest tests/test_performance_optimization.py -v"
            just _run "Stopping container" "docker-compose -f docker-compose.dev.yml down"
            ;;
        *)
            just _error "container-test" "Invalid mode: {{mode}}. Available: basic, coverage, watch, performance"
            ;;
    esac
    just _success "Container testing completed ({{mode}} mode)"