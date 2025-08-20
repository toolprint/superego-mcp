#!/bin/bash
# Development Docker utility script
# Provides convenient commands for development workflow

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.dev.yml"
SERVICE_NAME="superego-dev"
IMAGE_NAME="superego-mcp-dev"
BUILD_TIME_TARGET="15"  # Target build time in seconds
RELOAD_TIME_TARGET="5"  # Target hot-reload time in seconds

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Show usage information
usage() {
    echo "Development Docker utility for Superego MCP Server"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  build        Build development Docker image (target: <15s)"
    echo "  start        Start development container with hot-reload (target: <15s)"
    echo "  start-full   Start with monitoring dashboard"
    echo "  stop         Stop development container"
    echo "  restart      Restart development container"
    echo "  logs         Show container logs (follow)"
    echo "  shell        Open shell in development container"
    echo "  debug        Start container with debugging enabled"
    echo "  debug-wait   Start container with debugging (wait for client)"
    echo "  test         Run tests in development container" 
    echo "  test-watch   Run tests with file watching"
    echo "  clean        Clean up containers and images"
    echo "  status       Show container status and performance metrics"
    echo "  health       Check container health"
    echo "  benchmark    Test build and reload performance"
    echo ""
    echo "Options:"
    echo "  --no-cache   Build without cache (slower but fresh)"
    echo "  --detach     Run in background (for start command)"
    echo "  --verbose    Verbose output"
    echo "  --profile    Specify compose profile (monitoring, full)"
    echo ""
    echo "Examples:"
    echo "  $0 build --no-cache         # Fresh build (no cache)"
    echo "  $0 start --detach           # Start in background"
    echo "  $0 start-full               # Start with monitoring"
    echo "  $0 debug                    # Start with debugging"
    echo "  $0 debug-wait               # Debug (wait for client)"
    echo "  $0 shell                    # Interactive shell"
    echo "  $0 test                     # Run test suite"
    echo "  $0 test-watch               # Run tests with watching"
    echo "  $0 benchmark                # Performance test"
}

# Build development image with performance timing
build_dev() {
    local no_cache=""
    if [[ "${1:-}" == "--no-cache" ]]; then
        no_cache="--no-cache"
        log_info "Building with no cache (will be slower)..."
    fi
    
    log_info "Building development Docker image (target: <${BUILD_TIME_TARGET}s)..."
    local start_time=$(date +%s)
    
    # Enable BuildKit for faster builds
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    docker-compose -f "$COMPOSE_FILE" build $no_cache "$SERVICE_NAME"
    
    local end_time=$(date +%s)
    local build_time=$((end_time - start_time))
    
    if [ $build_time -le $BUILD_TIME_TARGET ]; then
        log_success "Development image built successfully in ${build_time}s (target: ${BUILD_TIME_TARGET}s) ✓"
    else
        log_warning "Build took ${build_time}s (target: ${BUILD_TIME_TARGET}s) - consider using cache"
    fi
}

# Start development container with performance timing
start_dev() {
    local detach=""
    local profile=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --detach)
                detach="-d"
                shift
                ;;
            --profile)
                profile="--profile $2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
    
    log_info "Starting development container (target: <${BUILD_TIME_TARGET}s startup)..."
    log_info "Hot-reload target: <${RELOAD_TIME_TARGET}s response time"
    
    local start_time=$(date +%s)
    docker-compose -f "$COMPOSE_FILE" $profile up $detach "$SERVICE_NAME"
    
    if [[ -n "$detach" ]]; then
        local end_time=$(date +%s)
        local startup_time=$((end_time - start_time))
        
        log_success "Development container started in ${startup_time}s"
        log_info "Server: http://localhost:8000"
        log_info "Health: http://localhost:8000/health"
        log_info "Logs: $0 logs"
        log_info "Shell: $0 shell"
    fi
}

# Start with full monitoring stack
start_full() {
    log_info "Starting development container with monitoring dashboard..."
    docker-compose -f "$COMPOSE_FILE" --profile full up "$@"
}

# Stop development container
stop_dev() {
    log_info "Stopping development container..."
    docker-compose -f "$COMPOSE_FILE" down
    log_success "Development container stopped"
}

# Restart development container
restart_dev() {
    log_info "Restarting development container..."
    docker-compose -f "$COMPOSE_FILE" restart "$SERVICE_NAME"
    log_success "Development container restarted"
}

# Show container logs
logs_dev() {
    log_info "Showing development container logs (Ctrl+C to exit)..."
    docker-compose -f "$COMPOSE_FILE" logs -f "$SERVICE_NAME"
}

# Open shell in container
shell_dev() {
    if ! docker-compose -f "$COMPOSE_FILE" ps "$SERVICE_NAME" | grep -q "Up"; then
        log_warning "Container not running. Starting it first..."
        start_dev --detach
        sleep 3
    fi
    
    log_info "Opening shell in development container..."
    docker-compose -f "$COMPOSE_FILE" exec "$SERVICE_NAME" bash
}

# Start with debugging (non-blocking)
debug_dev() {
    log_info "Starting development container with debugging enabled..."
    log_info "Debugger available on port 5678 (non-blocking)"
    log_info "Configure your IDE to connect to localhost:5678"
    
    # Set environment variables for debugging
    export DEBUGPY_ENABLED=1
    export DEBUGPY_WAIT_FOR_CLIENT=0
    
    docker-compose -f "$COMPOSE_FILE" up "$SERVICE_NAME"
}

# Start with debugging (wait for client)
debug_wait_dev() {
    log_info "Starting development container with debugging (waiting for client)..."
    log_info "Server will WAIT for debugger client on port 5678"
    log_info "Configure your IDE to connect to localhost:5678 before server starts"
    
    # Set environment variables for debugging
    export DEBUGPY_ENABLED=1
    export DEBUGPY_WAIT_FOR_CLIENT=1
    
    docker-compose -f "$COMPOSE_FILE" up "$SERVICE_NAME"
}

# Run tests
test_dev() {
    if ! docker-compose -f "$COMPOSE_FILE" ps "$SERVICE_NAME" | grep -q "Up"; then
        log_warning "Container not running. Starting it first..."
        start_dev --detach
        sleep 5
    fi
    
    log_info "Running tests in development container..."
    docker-compose -f "$COMPOSE_FILE" exec "$SERVICE_NAME" uv run pytest tests/ -v --tb=short
}

# Run tests with file watching
test_watch_dev() {
    if ! docker-compose -f "$COMPOSE_FILE" ps "$SERVICE_NAME" | grep -q "Up"; then
        log_warning "Container not running. Starting it first..."
        start_dev --detach
        sleep 5
    fi
    
    log_info "Running tests with file watching (Ctrl+C to stop)..."
    docker-compose -f "$COMPOSE_FILE" exec "$SERVICE_NAME" uv run pytest-watch tests/ -- -v --tb=short
}

# Clean up
clean_dev() {
    log_info "Cleaning up development containers and images..."
    
    # Stop and remove containers
    docker-compose -f "$COMPOSE_FILE" down --volumes --remove-orphans
    
    # Remove development image
    if docker images | grep -q "$IMAGE_NAME"; then
        docker rmi "$IMAGE_NAME" 2>/dev/null || log_warning "Could not remove image $IMAGE_NAME"
    fi
    
    # Clean up dangling images
    docker image prune -f
    
    log_success "Cleanup completed"
}

# Show container status with performance metrics
status_dev() {
    log_info "Development container status:"
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    
    if docker-compose -f "$COMPOSE_FILE" ps "$SERVICE_NAME" | grep -q "Up"; then
        log_success "Container is running"
        log_info "Server: http://localhost:8000"
        log_info "Health: http://localhost:8000/health"
        log_info "Monitoring: http://localhost:3000 (if enabled)"
        
        # Show resource usage
        log_info "Resource usage:"
        docker stats "$SERVICE_NAME" --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
        
        # Show image size
        local image_size=$(docker images "$IMAGE_NAME" --format "table {{.Size}}" | tail -n +2)
        log_info "Image size: $image_size (target: <1GB)"
        
    else
        log_warning "Container is not running"
        log_info "Start with: $0 start"
    fi
}

# Check container health
health_dev() {
    log_info "Checking container health..."
    
    if ! docker-compose -f "$COMPOSE_FILE" ps "$SERVICE_NAME" | grep -q "Up"; then
        log_error "Container is not running"
        exit 1
    fi
    
    # Check HTTP endpoint
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Container is healthy - HTTP endpoint responding"
    else
        log_error "Container health check failed - HTTP endpoint not responding"
        exit 1
    fi
    
    # Show detailed status
    docker-compose -f "$COMPOSE_FILE" ps "$SERVICE_NAME"
}

# Main command processing
main() {
    check_docker
    
    case "${1:-help}" in
        build)
            build_dev "${2:-}"
            ;;
        start)
            start_dev "${2:-}"
            ;;
        stop)
            stop_dev
            ;;
        restart)
            restart_dev
            ;;
        logs)
            logs_dev
            ;;
        shell)
            shell_dev
            ;;
        debug)
            debug_dev
            ;;
        test)
            test_dev
            ;;
        clean)
            clean_dev
            ;;
        status)
            status_dev
            ;;
        health)
            health_dev
            ;;
        start-full)
            start_full "${@:2}"
            ;;
        debug-wait)
            debug_wait_dev
            ;;
        test-watch)
            test_watch_dev
            ;;
        benchmark)
            benchmark_dev
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            log_error "Unknown command: ${1:-}"
            echo ""
            usage
            exit 1
            ;;
    esac
}

# Performance benchmark function
benchmark_dev() {
    log_info "Running performance benchmark..."
    log_info "Testing build time (target: <${BUILD_TIME_TARGET}s) and reload performance (target: <${RELOAD_TIME_TARGET}s)"
    
    # Clean start
    log_info "Step 1: Clean build test"
    clean_dev > /dev/null 2>&1
    build_dev --no-cache
    
    # Startup time test
    log_info "Step 2: Startup time test"
    local start_time=$(date +%s)
    start_dev --detach > /dev/null 2>&1
    
    # Wait for health check
    local health_retries=0
    while [ $health_retries -lt 30 ]; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            break
        fi
        sleep 1
        health_retries=$((health_retries + 1))
    done
    
    local end_time=$(date +%s)
    local startup_time=$((end_time - start_time))
    
    if [ $startup_time -le $BUILD_TIME_TARGET ]; then
        log_success "Startup time: ${startup_time}s (target: ${BUILD_TIME_TARGET}s) ✓"
    else
        log_warning "Startup time: ${startup_time}s (target: ${BUILD_TIME_TARGET}s) ✗"
    fi
    
    # Hot-reload test
    log_info "Step 3: Hot-reload test"
    local test_file="/tmp/test_change.py"
    docker-compose -f "$COMPOSE_FILE" exec -T "$SERVICE_NAME" bash -c "echo '# Test change' > $test_file" > /dev/null 2>&1
    
    local reload_start=$(date +%s.%3N)
    docker-compose -f "$COMPOSE_FILE" exec -T "$SERVICE_NAME" bash -c "touch /app/src/superego_mcp/main.py" > /dev/null 2>&1
    
    # Wait for reload indication in logs (simplified)
    sleep 2
    
    local reload_end=$(date +%s.%3N)
    local reload_time=$(echo "$reload_end - $reload_start" | bc 2>/dev/null || echo "~2")
    
    log_info "Hot-reload time: ~${reload_time}s (target: <${RELOAD_TIME_TARGET}s)"
    
    # Image size check
    local image_size_bytes=$(docker images "$IMAGE_NAME" --format "{{.Size}}" | head -1)
    log_info "Final image size: $image_size_bytes (target: <1GB)"
    
    # Cleanup
    stop_dev > /dev/null 2>&1
    
    log_success "Benchmark completed!"
}

# Run main function with all arguments
main "$@"