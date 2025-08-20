#!/bin/bash
# Test script for development Docker infrastructure
# Verifies acceptance criteria for Task 117

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
BUILD_TIME_TARGET=15
RELOAD_TIME_TARGET=5
IMAGE_SIZE_TARGET_GB=1

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

# Function to test build time
test_build_time() {
    log_info "Testing build time (target: <${BUILD_TIME_TARGET}s)"
    
    # Clean build test
    docker-compose -f docker-compose.dev.yml down > /dev/null 2>&1 || true
    docker rmi superego-mcp-dev > /dev/null 2>&1 || true
    
    local start_time=$(date +%s)
    docker-compose -f docker-compose.dev.yml build superego-dev --no-cache > /dev/null 2>&1
    local end_time=$(date +%s)
    local build_time=$((end_time - start_time))
    
    if [ $build_time -le $BUILD_TIME_TARGET ]; then
        log_success "Build time: ${build_time}s (target: ≤${BUILD_TIME_TARGET}s) ✓"
        return 0
    else
        log_warning "Build time: ${build_time}s (target: ≤${BUILD_TIME_TARGET}s) - slower than target"
        return 1
    fi
}

# Function to test image size
test_image_size() {
    log_info "Testing image size (target: <${IMAGE_SIZE_TARGET_GB}GB)"
    
    local image_size_mb=$(docker images superego-mcp-dev:latest --format "{{.Size}}" | grep -o '^[0-9.]*' | head -1)
    local image_size_gb=$(echo "scale=2; $image_size_mb / 1024" | bc -l 2>/dev/null || echo "unknown")
    
    log_info "Image size: ${image_size_gb}GB"
    
    if [ "$image_size_gb" != "unknown" ] && (( $(echo "$image_size_gb < $IMAGE_SIZE_TARGET_GB" | bc -l) )); then
        log_success "Image size: ${image_size_gb}GB (target: <${IMAGE_SIZE_TARGET_GB}GB) ✓"
        return 0
    else
        log_warning "Image size check - manual verification needed"
        return 1
    fi
}

# Function to test startup time
test_startup_time() {
    log_info "Testing container startup time (target: <${BUILD_TIME_TARGET}s)"
    
    local start_time=$(date +%s)
    docker-compose -f docker-compose.dev.yml up -d superego-dev > /dev/null 2>&1
    
    # Wait for health check to pass
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
        log_success "Startup time: ${startup_time}s (target: ≤${BUILD_TIME_TARGET}s) ✓"
        return 0
    else
        log_warning "Startup time: ${startup_time}s (target: ≤${BUILD_TIME_TARGET}s) - slower than target"
        return 1
    fi
}

# Function to test UV integration
test_uv_integration() {
    log_info "Testing UV package manager integration"
    
    # Check UV is installed and working
    local uv_version=$(docker-compose -f docker-compose.dev.yml exec -T superego-dev uv --version 2>/dev/null || echo "failed")
    
    if [ "$uv_version" != "failed" ]; then
        log_success "UV integration: $uv_version ✓"
        return 0
    else
        log_error "UV integration: failed"
        return 1
    fi
}

# Function to test debugging support
test_debugging_support() {
    log_info "Testing debugging tools installation"
    
    # Check debugpy is available
    local debugpy_check=$(docker-compose -f docker-compose.dev.yml exec -T superego-dev uv run python -c "import debugpy; print('debugpy available')" 2>/dev/null || echo "failed")
    
    if [ "$debugpy_check" = "debugpy available" ]; then
        log_success "Debugging support: debugpy available ✓"
        return 0
    else
        log_error "Debugging support: debugpy not available"
        return 1
    fi
}

# Function to test volume mounts
test_volume_mounts() {
    log_info "Testing volume mount configuration"
    
    # Test if source code is mounted correctly
    local mount_check=$(docker-compose -f docker-compose.dev.yml exec -T superego-dev ls /app/src/superego_mcp/main.py 2>/dev/null || echo "failed")
    
    if [ "$mount_check" != "failed" ]; then
        log_success "Volume mounts: source code accessible ✓"
        return 0
    else
        log_error "Volume mounts: source code not accessible"
        return 1
    fi
}

# Main test execution
main() {
    log_info "🚀 Starting Development Docker Infrastructure Tests"
    log_info "Testing acceptance criteria for Task 117"
    echo ""
    
    local test_results=0
    
    # Test 1: Build time
    if ! test_build_time; then
        test_results=$((test_results + 1))
    fi
    echo ""
    
    # Test 2: Image size
    if ! test_image_size; then
        test_results=$((test_results + 1))
    fi
    echo ""
    
    # Test 3: Startup time
    if ! test_startup_time; then
        test_results=$((test_results + 1))
    fi
    echo ""
    
    # Test 4: UV integration
    if ! test_uv_integration; then
        test_results=$((test_results + 1))
    fi
    echo ""
    
    # Test 5: Debugging support
    if ! test_debugging_support; then
        test_results=$((test_results + 1))
    fi
    echo ""
    
    # Test 6: Volume mounts
    if ! test_volume_mounts; then
        test_results=$((test_results + 1))
    fi
    echo ""
    
    # Cleanup
    log_info "Cleaning up test containers..."
    docker-compose -f docker-compose.dev.yml down > /dev/null 2>&1 || true
    
    # Summary
    if [ $test_results -eq 0 ]; then
        log_success "🎉 All tests passed! Development Docker infrastructure meets acceptance criteria"
        exit 0
    else
        log_warning "⚠️  ${test_results} test(s) failed or need manual verification"
        log_info "Infrastructure is functional but may not meet all performance targets"
        exit 1
    fi
}

# Check if required tools are available
if ! command -v docker-compose > /dev/null 2>&1; then
    log_error "docker-compose is required but not installed"
    exit 1
fi

if ! command -v curl > /dev/null 2>&1; then
    log_error "curl is required but not installed"
    exit 1
fi

# Run main test
main "$@"