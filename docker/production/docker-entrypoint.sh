#!/bin/bash
set -e

# Docker entrypoint for superego-mcp production container
# Handles graceful shutdown, health checks, and initialization

# Default configuration
SUPEREGO_HOST="${SUPEREGO_HOST:-0.0.0.0}"
SUPEREGO_PORT="${SUPEREGO_PORT:-8000}"
SUPEREGO_LOG_LEVEL="${SUPEREGO_LOG_LEVEL:-info}"
SUPEREGO_CONFIG_PATH="${SUPEREGO_CONFIG_PATH:-/app/data/server.yaml}"

# Process ID for the main application
APP_PID=""

# Logging functions
log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1" >&2
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

log_warn() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] WARN: $1" >&2
}

# Signal handlers for graceful shutdown
shutdown() {
    log_info "Received shutdown signal, initiating graceful shutdown..."
    
    if [ -n "$APP_PID" ]; then
        log_info "Terminating main application process (PID: $APP_PID)"
        
        # Send SIGTERM to allow graceful shutdown
        kill -TERM "$APP_PID" 2>/dev/null || true
        
        # Wait up to 30 seconds for graceful shutdown
        local timeout=30
        while [ $timeout -gt 0 ] && kill -0 "$APP_PID" 2>/dev/null; do
            sleep 1
            timeout=$((timeout - 1))
        done
        
        # Force kill if still running
        if kill -0 "$APP_PID" 2>/dev/null; then
            log_warn "Graceful shutdown timeout, force killing process"
            kill -KILL "$APP_PID" 2>/dev/null || true
        fi
        
        wait "$APP_PID" 2>/dev/null || true
        log_info "Application shutdown complete"
    fi
    
    exit 0
}

# Setup signal traps
trap shutdown SIGTERM SIGINT SIGQUIT

# Health check function
health_check() {
    local url="http://localhost:${SUPEREGO_PORT}/health"
    if command -v curl >/dev/null 2>&1; then
        curl -f -s "$url" >/dev/null 2>&1
    else
        # Fallback using Python if curl is not available
        python3 -c "
import urllib.request
import sys
try:
    urllib.request.urlopen('$url', timeout=5)
    sys.exit(0)
except:
    sys.exit(1)
" >/dev/null 2>&1
    fi
}

# Wait for health check to pass
wait_for_health() {
    local max_attempts=30
    local attempt=1
    
    log_info "Waiting for server to become healthy..."
    
    while [ $attempt -le $max_attempts ]; do
        if health_check; then
            log_info "Server is healthy and ready to serve requests"
            return 0
        fi
        
        if [ $attempt -eq 1 ]; then
            log_info "Health check failed, waiting for server to start..."
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log_error "Server failed to become healthy within $((max_attempts * 2)) seconds"
    return 1
}

# Initialize configuration if needed
init_config() {
    local config_dir=$(dirname "$SUPEREGO_CONFIG_PATH")
    
    # Ensure config directory exists
    if [ ! -d "$config_dir" ]; then
        log_info "Creating configuration directory: $config_dir"
        mkdir -p "$config_dir"
    fi
    
    # Create minimal config if none exists
    if [ ! -f "$SUPEREGO_CONFIG_PATH" ]; then
        log_info "Creating default configuration at: $SUPEREGO_CONFIG_PATH"
        cat > "$SUPEREGO_CONFIG_PATH" << EOF
# Superego MCP Server Configuration
# This is a minimal default configuration for production deployment

server:
  host: "${SUPEREGO_HOST}"
  port: ${SUPEREGO_PORT}
  log_level: "${SUPEREGO_LOG_LEVEL}"
  
security:
  enabled: true
  
monitoring:
  enabled: true
  health_check_path: "/health"
  
# Add your custom rules and configuration here
EOF
    fi
}

# Validate environment
validate_environment() {
    log_info "Validating environment configuration..."
    
    # Check if Python environment is ready
    if ! python3 -c "import superego_mcp" 2>/dev/null; then
        log_error "Superego MCP package not found in Python environment"
        exit 1
    fi
    
    # Validate port
    if ! echo "$SUPEREGO_PORT" | grep -qE '^[0-9]+$' || [ "$SUPEREGO_PORT" -lt 1024 ] || [ "$SUPEREGO_PORT" -gt 65535 ]; then
        log_warn "Invalid port number: $SUPEREGO_PORT, using default 8000"
        SUPEREGO_PORT=8000
    fi
    
    log_info "Environment validation successful"
}

# Main execution function
main() {
    log_info "Starting Superego MCP Server container"
    log_info "Host: $SUPEREGO_HOST, Port: $SUPEREGO_PORT, Log Level: $SUPEREGO_LOG_LEVEL"
    
    # Initialize and validate
    validate_environment
    init_config
    
    # Start the server
    log_info "Launching Superego MCP Server..."
    
    # Use the superego MCP command from the installed package
    # Note: The server runs on HTTP transport for container deployment
    superego mcp \
        --transport http \
        --port "$SUPEREGO_PORT" \
        --config "$SUPEREGO_CONFIG_PATH" &
    
    APP_PID=$!
    log_info "Server started with PID: $APP_PID"
    
    # Wait for server to become healthy (in background to allow signal handling)
    (
        sleep 5  # Give server time to initialize
        if ! wait_for_health; then
            log_error "Server health check failed, container may not be functioning properly"
            # Don't exit here, let the main process handle it
        fi
    ) &
    
    # Wait for the main process
    wait $APP_PID
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        log_error "Server exited with code: $exit_code"
    else
        log_info "Server exited normally"
    fi
    
    exit $exit_code
}

# Handle special commands
case "${1:-}" in
    "health-check")
        # Manual health check command
        if health_check; then
            echo "Server is healthy"
            exit 0
        else
            echo "Server is not healthy"
            exit 1
        fi
        ;;
    "version")
        # Show version information
        python3 -c "import superego_mcp; print(f'Superego MCP Server v{superego_mcp.__version__}')"
        exit 0
        ;;
    "config-check")
        # Validate configuration
        log_info "Checking configuration..."
        validate_environment
        init_config
        log_info "Configuration check complete"
        exit 0
        ;;
    *)
        # Default: start the server
        main "$@"
        ;;
esac