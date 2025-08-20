#!/bin/bash
# Production Security Validation Script
# Validates security configuration before and after deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TRIVY_CONFIG="$PROJECT_ROOT/trivy.yaml"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
SECURITY_COMPOSE="$SCRIPT_DIR/docker-compose.security.yml"

# Logging
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

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Validate environment setup
validate_environment() {
    log_info "Validating environment setup..."
    
    local errors=0
    
    # Check required commands
    local required_commands=("docker" "docker-compose" "trivy" "curl" "jq")
    for cmd in "${required_commands[@]}"; do
        if ! command_exists "$cmd"; then
            log_error "Required command not found: $cmd"
            ((errors++))
        fi
    done
    
    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running or not accessible"
        ((errors++))
    fi
    
    # Check required files
    local required_files=(
        "$COMPOSE_FILE"
        "$SECURITY_COMPOSE"
        "$TRIVY_CONFIG"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Required file not found: $file"
            ((errors++))
        fi
    done
    
    if [[ $errors -eq 0 ]]; then
        log_success "Environment validation passed"
    else
        log_error "Environment validation failed with $errors errors"
        return 1
    fi
}

# Validate environment variables
validate_env_vars() {
    log_info "Validating environment variables..."
    
    local errors=0
    local warnings=0
    
    # Critical environment variables
    local critical_vars=(
        "ANTHROPIC_API_KEY"
        "SUPEREGO_API_KEY"
    )
    
    # Important environment variables  
    local important_vars=(
        "SUPEREGO_ENV"
        "SUPEREGO_LOG_LEVEL"
        "SUPEREGO_CORS_ORIGINS"
        "SUPEREGO_RATE_LIMIT_ENABLED"
    )
    
    # Check critical variables
    for var in "${critical_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            log_error "Critical environment variable not set: $var"
            ((errors++))
        elif [[ ${#!var} -lt 32 ]]; then
            log_error "Environment variable too short: $var (minimum 32 characters)"
            ((errors++))
        fi
    done
    
    # Check important variables
    for var in "${important_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            log_warning "Important environment variable not set: $var"
            ((warnings++))
        fi
    done
    
    # Validate specific values
    if [[ "${SUPEREGO_ENV:-}" != "production" ]]; then
        log_warning "SUPEREGO_ENV should be 'production' for production deployment"
        ((warnings++))
    fi
    
    if [[ "${SUPEREGO_DEBUG:-}" == "true" ]]; then
        log_error "SUPEREGO_DEBUG should be 'false' in production"
        ((errors++))
    fi
    
    log_info "Environment variables check: $errors errors, $warnings warnings"
    return $errors
}

# Validate Docker configuration
validate_docker_config() {
    log_info "Validating Docker configuration..."
    
    local errors=0
    
    # Validate docker-compose configuration
    if ! docker-compose -f "$COMPOSE_FILE" -f "$SECURITY_COMPOSE" config >/dev/null 2>&1; then
        log_error "Docker Compose configuration validation failed"
        ((errors++))
    else
        log_success "Docker Compose configuration is valid"
    fi
    
    # Check for common security misconfigurations
    local config_output
    config_output=$(docker-compose -f "$COMPOSE_FILE" -f "$SECURITY_COMPOSE" config)
    
    # Check for privileged containers
    if echo "$config_output" | grep -q "privileged.*true"; then
        log_error "Privileged containers detected - security risk"
        ((errors++))
    fi
    
    # Check for host network mode
    if echo "$config_output" | grep -q "network_mode.*host"; then
        log_error "Host network mode detected - security risk"
        ((errors++))
    fi
    
    # Check for volume mounts to sensitive paths
    if echo "$config_output" | grep -q ":/etc\|:/var/run/docker.sock"; then
        log_warning "Sensitive volume mounts detected - review required"
    fi
    
    return $errors
}

# Run vulnerability scan
run_vulnerability_scan() {
    log_info "Running vulnerability scan..."
    
    local scan_target="${1:-filesystem}"
    local exit_code=0
    
    case "$scan_target" in
        "filesystem")
            trivy fs --config "$TRIVY_CONFIG" --format table "$PROJECT_ROOT" || exit_code=$?
            ;;
        "image")
            if docker image ls superego-mcp:latest >/dev/null 2>&1; then
                trivy image --config "$TRIVY_CONFIG" --format table superego-mcp:latest || exit_code=$?
            else
                log_warning "superego-mcp:latest image not found, skipping image scan"
            fi
            ;;
        "config")
            trivy config --config "$TRIVY_CONFIG" --format table "$PROJECT_ROOT" || exit_code=$?
            ;;
        *)
            log_error "Invalid scan target: $scan_target"
            return 1
            ;;
    esac
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "Vulnerability scan completed successfully"
    else
        log_warning "Vulnerability scan found issues (exit code: $exit_code)"
    fi
    
    return $exit_code
}

# Test container security
test_container_security() {
    log_info "Testing container security..."
    
    local container_name="superego-mcp-prod"
    local errors=0
    
    # Check if container is running
    if ! docker ps --format "table {{.Names}}" | grep -q "$container_name"; then
        log_warning "Container $container_name is not running, skipping security tests"
        return 0
    fi
    
    # Test non-root user
    local user_info
    user_info=$(docker exec "$container_name" id 2>/dev/null || true)
    if [[ "$user_info" =~ uid=0 ]]; then
        log_error "Container is running as root user"
        ((errors++))
    else
        log_success "Container is running as non-root user: $user_info"
    fi
    
    # Test read-only filesystem
    if docker exec "$container_name" touch /test-readonly 2>/dev/null; then
        log_error "Root filesystem is writable (should be read-only)"
        ((errors++))
        docker exec "$container_name" rm -f /test-readonly 2>/dev/null || true
    else
        log_success "Root filesystem is read-only"
    fi
    
    # Test capabilities
    if command_exists capsh && docker exec "$container_name" capsh --print 2>/dev/null | grep -q "cap_sys_admin"; then
        log_error "Container has dangerous capabilities"
        ((errors++))
    fi
    
    return $errors
}

# Test network security
test_network_security() {
    log_info "Testing network security..."
    
    local errors=0
    local base_url="http://localhost:8000"
    
    # Test health endpoint (should be accessible)
    if curl -sf "$base_url/health" >/dev/null 2>&1; then
        log_success "Health endpoint is accessible"
    else
        log_warning "Health endpoint is not accessible"
    fi
    
    # Test metrics endpoint (should be accessible)
    if curl -sf "http://localhost:8001/metrics" >/dev/null 2>&1; then
        log_success "Metrics endpoint is accessible"
    else
        log_warning "Metrics endpoint is not accessible"
    fi
    
    # Test API endpoint without authentication (should be rejected)
    if curl -sf "$base_url/advise" >/dev/null 2>&1; then
        log_error "API endpoint accessible without authentication"
        ((errors++))
    else
        log_success "API endpoint properly protected"
    fi
    
    # Test security headers
    local headers
    headers=$(curl -sI "$base_url/health" 2>/dev/null || true)
    
    local security_headers=(
        "X-Content-Type-Options"
        "X-Frame-Options" 
        "X-XSS-Protection"
    )
    
    for header in "${security_headers[@]}"; do
        if echo "$headers" | grep -qi "$header"; then
            log_success "Security header present: $header"
        else
            log_warning "Security header missing: $header"
        fi
    done
    
    return $errors
}

# Test rate limiting
test_rate_limiting() {
    log_info "Testing rate limiting..."
    
    local base_url="http://localhost:8000"
    local errors=0
    
    # Make rapid requests to trigger rate limiting
    local success_count=0
    local rate_limited_count=0
    
    for i in {1..20}; do
        local status_code
        status_code=$(curl -s -o /dev/null -w "%{http_code}" "$base_url/health" 2>/dev/null || echo "000")
        
        if [[ "$status_code" == "200" ]]; then
            ((success_count++))
        elif [[ "$status_code" == "429" ]]; then
            ((rate_limited_count++))
        fi
        
        sleep 0.1
    done
    
    if [[ $rate_limited_count -gt 0 ]]; then
        log_success "Rate limiting is working: $rate_limited_count/20 requests rate limited"
    else
        log_warning "Rate limiting may not be working properly"
    fi
    
    return $errors
}

# Generate security report
generate_security_report() {
    log_info "Generating security report..."
    
    local report_file="$SCRIPT_DIR/reports/security-validation-$(date +%Y%m%d-%H%M%S).txt"
    mkdir -p "$(dirname "$report_file")"
    
    {
        echo "# Superego MCP Security Validation Report"
        echo "Generated: $(date)"
        echo "Host: $(hostname)"
        echo "User: $(whoami)"
        echo ""
        
        echo "## Environment Information"
        echo "Docker version: $(docker --version)"
        echo "Docker Compose version: $(docker-compose --version)"
        echo "Trivy version: $(trivy --version)"
        echo ""
        
        echo "## Container Information"
        if docker ps --filter "name=superego" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" | grep -q superego; then
            docker ps --filter "name=superego" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
        else
            echo "No Superego containers running"
        fi
        echo ""
        
        echo "## Security Scan Summary"
        trivy fs --config "$TRIVY_CONFIG" --format table "$PROJECT_ROOT" 2>/dev/null || echo "Scan failed"
        echo ""
        
        echo "## Network Configuration"
        docker network ls --filter "name=superego" --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" || true
        echo ""
        
    } > "$report_file"
    
    log_success "Security report generated: $report_file"
}

# Main validation function
main() {
    log_info "Starting Superego MCP security validation"
    echo "========================================"
    
    local total_errors=0
    local start_time=$(date +%s)
    
    # Pre-deployment checks
    if ! validate_environment; then
        ((total_errors++))
    fi
    
    # Load environment variables if .env.production exists
    if [[ -f "$PROJECT_ROOT/.env.production" ]]; then
        log_info "Loading environment variables from .env.production"
        set -a
        source "$PROJECT_ROOT/.env.production"
        set +a
    else
        log_warning ".env.production file not found, using existing environment"
    fi
    
    if ! validate_env_vars; then
        ((total_errors++))
    fi
    
    if ! validate_docker_config; then
        ((total_errors++))
    fi
    
    # Run vulnerability scans
    log_info "Running security scans..."
    run_vulnerability_scan "filesystem" || true
    run_vulnerability_scan "config" || true
    
    # If containers are running, run runtime tests
    if docker ps --filter "name=superego" | grep -q superego; then
        log_info "Running runtime security tests..."
        
        if ! test_container_security; then
            ((total_errors++))
        fi
        
        if ! test_network_security; then
            ((total_errors++))
        fi
        
        test_rate_limiting || true
        
        run_vulnerability_scan "image" || true
    else
        log_info "No containers running, skipping runtime tests"
    fi
    
    # Generate report
    generate_security_report
    
    # Summary
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo "========================================"
    log_info "Security validation completed in ${duration}s"
    
    if [[ $total_errors -eq 0 ]]; then
        log_success "Security validation PASSED - no critical errors found"
        exit 0
    else
        log_error "Security validation FAILED - $total_errors critical errors found"
        exit 1
    fi
}

# Help function
show_help() {
    echo "Superego MCP Security Validation Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  validate          Run complete security validation (default)"
    echo "  scan [TARGET]     Run vulnerability scan (filesystem|image|config)"
    echo "  test-container    Test container security"
    echo "  test-network      Test network security"
    echo "  test-rate-limit   Test rate limiting"
    echo "  report            Generate security report only"
    echo "  help              Show this help message"
    echo ""
    echo "Options:"
    echo "  --env-file FILE   Load environment variables from file"
    echo "  --verbose         Enable verbose output"
    echo "  --no-scan         Skip vulnerability scans"
    echo ""
    echo "Examples:"
    echo "  $0                              # Run full validation"
    echo "  $0 scan image                   # Scan container image only"  
    echo "  $0 --env-file .env.prod         # Use specific env file"
    echo "  $0 test-container               # Test container security only"
}

# Command line argument parsing
case "${1:-validate}" in
    "validate")
        main
        ;;
    "scan")
        validate_environment
        run_vulnerability_scan "${2:-filesystem}"
        ;;
    "test-container")
        test_container_security
        ;;
    "test-network")
        test_network_security
        ;;
    "test-rate-limit")
        test_rate_limiting
        ;;
    "report")
        generate_security_report
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac