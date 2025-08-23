# Container Testing Guide

This document describes the comprehensive container testing suite for the Superego MCP Server.

## Overview

The container testing suite validates all aspects of containerized deployment including:

- **Container startup and health checks** - Ensures containers start correctly and become healthy
- **Multi-transport functionality** - Tests STDIO, HTTP, WebSocket, and SSE transports in containers
- **Performance benchmarks** - Validates startup time, hot-reload performance, and resource usage
- **Security configuration** - Tests non-root execution, port configuration, and environment security
- **Resource limit enforcement** - Verifies memory and CPU limits are properly enforced
- **Claude Code integration** - Tests hooks integration works in containerized environment

## Test Structure

The container tests are organized into the following test classes:

### TestContainerStartup
- `test_container_builds_successfully` - Validates image builds and has correct labels
- `test_container_starts_and_becomes_healthy` - Basic startup and health validation
- `test_container_startup_performance` - Ensures startup meets <30s requirement
- `test_container_health_endpoint` - Validates health check endpoint
- `test_container_runs_as_non_root` - Security validation for non-root execution

### TestContainerTransports
- `test_http_transport_functionality` - HTTP transport validation
- `test_claude_code_hooks_integration` - Claude Code hooks endpoint testing
- `test_websocket_support` - WebSocket connectivity testing
- `test_stdio_transport_available` - STDIO transport availability

### TestContainerPerformance
- `test_memory_usage_within_limits` - Memory usage validation
- `test_cpu_usage_reasonable` - CPU usage under normal load
- `test_hot_reload_performance` - Hot-reload meets <5s requirement

### TestContainerSecurity
- `test_container_port_configuration` - Port binding security
- `test_environment_variables_security` - API key security in logs
- `test_filesystem_permissions` - File system permission validation
- `test_network_isolation` - Network isolation testing

### TestContainerResourceLimits
- `test_memory_limit_enforcement` - Memory limit enforcement
- `test_cpu_limit_enforcement` - CPU limit enforcement
- `test_container_restart_policy` - Restart policy validation

### TestContainerIntegration
- `test_container_metrics_export` - Metrics endpoint validation
- `test_container_logging_configuration` - Logging configuration
- `test_container_volume_mounts` - Volume mount functionality

### TestContainerScenarios
- `test_production_deployment_scenario` - Complete production deployment test
- `test_development_deployment_scenario` - Development with hot-reload test

### TestContainerPerformanceBenchmarks
- `test_concurrent_request_handling` - Concurrent request performance
- `test_memory_usage_under_load` - Memory stability under load

## Running Container Tests

### Prerequisites

1. **Docker**: Ensure Docker is installed and running
2. **Python Dependencies**: Install test dependencies with `uv sync`
3. **Container Image**: Build the container image (automated by test tasks)

Validate your environment:
```bash
python scripts/test_container_validation.py
```

### Basic Test Execution

Run all container tests:
```bash
just test-container-full
```

### Specific Test Categories

```bash
# Container startup tests
just test-container-startup

# Multi-transport functionality
just test-container-transports

# Performance tests
just test-container-performance

# Security validation
just test-container-security

# Resource limit tests
just test-container-limits

# Integration tests
just test-container-integration

# Deployment scenarios
just test-container-scenarios

# Performance benchmarks
just test-container-benchmarks
```

### Manual Container Testing

```bash
# Test with resource limits
just test-container-with-limits

# Test startup performance
just test-container-startup-time

# Test in Docker Compose environment
just test-container-compose
```

## Test Configuration

Container tests use the `ContainerTestConfig` class for configuration:

```python
class ContainerTestConfig(BaseModel):
    image_name: str = "superego-mcp:latest"
    container_name_prefix: str = "test-superego-mcp"
    test_timeout: int = 120
    startup_timeout: int = 60
    health_check_timeout: int = 30
    performance_threshold_startup: float = 30.0  # seconds
    performance_threshold_hot_reload: float = 5.0  # seconds
    max_memory_mb: int = 2048
    max_cpu_percent: float = 200.0  # 2 CPUs
```

## Performance Requirements

The tests validate the following performance requirements:

| Metric | Requirement | Test Method |
|--------|-------------|-------------|
| Container startup time | < 30 seconds | `test_container_startup_performance` |
| Hot-reload time | < 5 seconds | `test_hot_reload_performance` |
| Memory usage (idle) | < 80% of limit | `test_memory_usage_within_limits` |
| CPU usage (normal load) | < 200% (2 CPUs) | `test_cpu_usage_reasonable` |
| Concurrent requests | 20 requests < 30s total | `test_concurrent_request_handling` |

## Security Validation

Security tests validate:

- **Non-root execution**: Container runs as `superego` user, not root
- **Port configuration**: Proper port binding and network isolation
- **Environment security**: API keys don't leak into logs
- **Filesystem permissions**: Correct ownership and permissions
- **Network isolation**: Containers are properly isolated

## Multi-Transport Testing

The test suite validates all transport protocols work in containers:

1. **HTTP Transport**: REST API endpoints for evaluation and hooks
2. **STDIO Transport**: MCP protocol over standard I/O
3. **WebSocket Support**: Real-time communication (unified server)
4. **SSE Transport**: Server-sent events for streaming

## Troubleshooting

### Common Issues

1. **Docker not available**:
   ```bash
   # Start Docker daemon
   sudo systemctl start docker  # Linux
   open -a Docker              # macOS
   ```

2. **Image build failures**:
   ```bash
   # Clean rebuild
   docker system prune -f
   just test-container-build
   ```

3. **Port conflicts**:
   ```bash
   # Clean up test containers
   just test-container-clean
   ```

4. **Memory/CPU limit issues**:
   ```bash
   # Check system resources
   docker system df
   docker stats
   ```

### Debug Container Issues

```bash
# View container logs
docker logs test-superego-mcp-<suffix>

# Inspect container
docker inspect test-superego-mcp-<suffix>

# Execute commands in container
docker exec -it test-superego-mcp-<suffix> /bin/bash

# Check container resource usage
docker stats test-superego-mcp-<suffix>
```

## Continuous Integration

The container tests are designed to run in CI/CD environments:

1. **Docker-in-Docker**: Tests can run in containerized CI systems
2. **Resource limits**: Tests respect CI resource constraints
3. **Timeout handling**: Appropriate timeouts for CI environments
4. **Cleanup**: Automatic cleanup of test artifacts

## Test Fixtures

The `ContainerTestFixtures` class provides:

- **Container lifecycle management**: Start, stop, cleanup containers
- **Network management**: Isolated test networks
- **Resource monitoring**: CPU, memory, network statistics
- **Health checking**: Wait for containers to become healthy
- **Log access**: Container log retrieval for debugging

## Architecture Validation

Tests validate the unified server architecture:

- **FastAPI + MCP integration**: Both protocols work simultaneously
- **Transport compatibility**: All transports function correctly
- **Configuration management**: Environment variables and config files
- **Monitoring endpoints**: Health, metrics, and status endpoints

## Performance Monitoring

Container tests include performance monitoring:

- **Startup time measurement**: Precise startup timing
- **Resource usage tracking**: Memory, CPU, network statistics
- **Load testing**: Concurrent request handling
- **Memory leak detection**: Long-running stability tests

## Compliance Validation

Tests ensure compliance with containerization best practices:

- **Security**: Non-root execution, proper permissions
- **Resource management**: Limits and reservations
- **Health checks**: Proper health check implementation
- **Signal handling**: Graceful shutdown with SIGTERM
- **Logging**: Structured logging to stdout/stderr