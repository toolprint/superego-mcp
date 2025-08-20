# Docker Bake Configuration Guide for Superego MCP

This guide covers the Docker Bake configuration for building multi-platform Superego MCP Server images with optimized caching and CI/CD integration.

## Overview

The `docker-bake.hcl` configuration provides:

- **Multi-platform builds**: `linux/amd64` and `linux/arm64` support
- **Build cache optimization**: GitHub Actions cache integration with >70% hit rates  
- **Multiple build targets**: Production, development, minimal, and testing variants
- **Environment parameterization**: Flexible configuration via variables
- **Registry publishing**: GitHub Container Registry (GHCR) integration
- **Dependency optimization**: Separate cache layers for dependencies vs. application code

## Quick Start

### Prerequisites

- Docker Desktop with BuildKit enabled
- Docker Buildx plugin installed
- Access to GitHub Container Registry (for publishing)

### Basic Commands

```bash
# Build production image locally (current platform)
docker buildx bake

# Build for specific platform  
docker buildx bake production-amd64
docker buildx bake production-arm64

# Build development image
docker buildx bake dev-local

# Build and push to registry
docker buildx bake --push production-all

# Build all variants for testing
docker buildx bake test
```

## Build Targets

### Production Targets

#### `production` (Default)
Multi-platform production build with security hardening and minimal attack surface.

```bash
docker buildx bake production
```

**Features:**
- Multi-stage build with separate builder and runtime stages  
- Non-root user execution
- Minimal dependencies (production only)
- Health checks and signal handling
- Comprehensive metadata labels

#### `production-all` 
Multi-platform registry push target for CI/CD.

```bash
docker buildx bake production-all
```

**Use case:** GitHub Actions automated builds

#### `production-amd64` / `production-arm64`
Single-platform builds for testing specific architectures.

```bash
docker buildx bake production-amd64
docker buildx bake production-arm64
```

#### `production-minimal`
Ultra-minimal distroless build for maximum security.

```bash
docker buildx bake production-minimal  
```

**Features:**
- Google Distroless base image
- No shell, package manager, or OS utilities
- Smallest possible attack surface
- Ideal for production security requirements

### Development Targets

#### `development`
Hot-reload development build with debugging support.

```bash
docker buildx bake development
```

**Features:**
- Development dependencies included
- Debugpy support for remote debugging
- Volume mount optimization for fast iteration
- Source code hot-reload capabilities

#### `dev-local`  
Local development build (current platform only).

```bash
docker buildx bake dev-local
```

**Optimized for:**
- Fast local development cycles
- Platform-specific builds (ARM64 on M1/M2 Macs)
- Docker Desktop integration

### Specialized Targets

#### `cache-warm`
Pre-builds and caches dependencies for faster subsequent builds.

```bash
docker buildx bake cache-warm
```

#### `security-scan`
Production build optimized for security scanning tools.

```bash
docker buildx bake security-scan
```

### Group Targets

#### `all-production`
Builds all production variants.

```bash
docker buildx bake all-production
```

#### `all-development` 
Builds all development variants.

```bash
docker buildx bake all-development
```

#### `test`
Builds both platforms separately for validation.

```bash
docker buildx bake test
```

#### `ci`
Optimized for CI/CD pipelines.

```bash
docker buildx bake ci
```

## Configuration Variables

### Environment Variables

Set these variables to customize builds:

```bash
# Registry and image configuration
export REGISTRY="ghcr.io/toolprint"
export IMAGE_NAME="superego-mcp"
export TAG="v1.0.0"
export VERSION="1.0.0"

# Build metadata
export BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export GIT_COMMIT="$(git rev-parse HEAD)"

# Platform configuration
export PLATFORMS="linux/amd64,linux/arm64"

# Cache configuration
export GITHUB_CACHE_SCOPE="superego-mcp"
export CACHE_FROM="type=gha,scope=superego-mcp-prod"
export CACHE_TO="type=gha,scope=superego-mcp-prod,mode=max"

# Output configuration
export PUSH="true"  # Set to true for registry push
```

### Build Examples with Variables

```bash
# Production build with version tagging
REGISTRY="ghcr.io/myorg" TAG="v1.2.3" VERSION="1.2.3" \
  docker buildx bake production

# Development build with custom registry
REGISTRY="localhost:5000" DEV_MODE="true" \
  docker buildx bake development

# Multi-platform build with push
PUSH="true" PLATFORMS="linux/amd64,linux/arm64" \
  docker buildx bake production-all
```

## GitHub Actions Integration

### Workflow Example

Create `.github/workflows/docker-build.yml`:

```yaml
name: Docker Build and Push

on:
  push:
    branches: [ main, develop ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
    - name: Checkout repository
      uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Container Registry
      if: github.event_name != 'pull_request'
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}

    - name: Build and push Docker images
      uses: docker/bake-action@v4
      env:
        REGISTRY: ${{ env.REGISTRY }}
        IMAGE_NAME: ${{ github.repository }}
        TAG: ${{ steps.meta.outputs.tags }}
        VERSION: ${{ steps.meta.outputs.version }}
        BUILD_DATE: ${{ fromJSON(steps.meta.outputs.json).labels['org.opencontainers.image.created'] }}
        GIT_COMMIT: ${{ github.sha }}
        PUSH: ${{ github.event_name != 'pull_request' }}
        GITHUB_CACHE_SCOPE: superego-mcp-${{ github.workflow }}
      with:
        files: |
          ./docker-bake.hcl
        targets: ${{ github.event_name == 'pull_request' && 'test' || 'ci' }}
        push: ${{ github.event_name != 'pull_request' }}
```

### Advanced CI Configuration

For more sophisticated caching and multi-job builds:

```yaml
name: Advanced Docker Build

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  cache-deps:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: docker/setup-buildx-action@v3
    - name: Cache dependencies
      uses: docker/bake-action@v4
      with:
        files: ./docker-bake.hcl
        targets: cache-warm

  build-test:
    needs: cache-deps
    strategy:
      matrix:
        platform: [amd64, arm64]
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: docker/setup-buildx-action@v3
    - name: Build ${{ matrix.platform }}
      uses: docker/bake-action@v4
      with:
        files: ./docker-bake.hcl  
        targets: production-${{ matrix.platform }}

  security-scan:
    needs: build-test
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: docker/setup-buildx-action@v3
    - name: Build for scanning
      uses: docker/bake-action@v4
      with:
        files: ./docker-bake.hcl
        targets: security-scan
        load: true
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: superego-mcp-dev:latest
        format: sarif
        output: trivy-results.sarif
```

## Cache Optimization

### Cache Strategy

The bake configuration implements a multi-layer cache strategy:

1. **Shared Base Layers**: OS packages and system dependencies  
2. **Dependency Cache**: Python packages and UV environment
3. **Application Cache**: Source code and built artifacts

### Cache Types

#### GitHub Actions Cache (Recommended)
```hcl
cache-from = [
  "type=gha,scope=superego-mcp-prod",
  "type=gha,scope=superego-mcp-shared"
]
cache-to = [
  "type=gha,scope=superego-mcp-prod,mode=max"
]
```

#### Registry Cache
```hcl
cache-from = [
  "type=registry,ref=ghcr.io/toolprint/superego-mcp:cache-prod"
]
cache-to = [
  "type=registry,ref=ghcr.io/toolprint/superego-mcp:cache-prod,mode=max"
]
```

### Cache Performance

Expected cache hit rates:
- **Dependencies**: >90% (changes infrequently)
- **Application**: >70% (with proper layer ordering)
- **Overall**: >70% for incremental builds

## Local Development Workflow

### Development Setup

1. **Initial Setup**
   ```bash
   # Build development image
   docker buildx bake dev-local
   
   # Start with docker-compose
   docker-compose -f docker-compose.dev.yml up
   ```

2. **Hot-Reload Development**
   ```bash
   # Source code changes are automatically reflected
   # No rebuild needed for code changes
   ```

3. **Debugging**
   ```bash
   # Enable remote debugging
   DEBUGPY_ENABLED=1 DEBUGPY_WAIT_FOR_CLIENT=1 \
     docker-compose up superego-dev
   ```

### Performance Optimization

#### Local Build Cache
```bash
# Use local registry cache for faster rebuilds
docker buildx bake --set *.cache-from=type=local,src=/tmp/buildx-cache \
                   --set *.cache-to=type=local,dest=/tmp/buildx-cache,mode=max \
                   dev-local
```

#### Build Parallelization
```bash
# Build multiple targets in parallel
docker buildx bake all-development &
docker buildx bake cache-warm &
wait
```

## Production Deployment

### Container Orchestration

#### Docker Compose (Production)

```yaml
services:
  superego-mcp:
    image: ghcr.io/toolprint/superego-mcp:latest
    ports:
      - "8000:8000"
    environment:
      - SUPEREGO_CONFIG_PATH=/app/config/production.yaml
      - SUPEREGO_LOG_LEVEL=info
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: superego-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: superego-mcp
  template:
    metadata:
      labels:
        app: superego-mcp
    spec:
      containers:
      - name: superego-mcp
        image: ghcr.io/toolprint/superego-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: SUPEREGO_CONFIG_PATH
          value: "/app/config/production.yaml"
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: superego-mcp-config
```

## Troubleshooting

### Common Issues

#### Platform Issues
```bash
# Error: no match for platform in manifest
# Solution: Use explicit platform specification
docker buildx bake --set *.platforms=linux/amd64 production
```

#### Cache Issues  
```bash
# Error: cache mount failed
# Solution: Clear cache and rebuild
docker buildx prune --all
docker buildx bake --no-cache production
```

#### Build Context Issues
```bash
# Error: failed to read dockerfile
# Solution: Ensure correct context path
docker buildx bake --file ./docker-bake.hcl production
```

### Performance Tuning

#### Build Speed Optimization
```bash
# Use parallel builds
export BUILDKIT_PROGRESS=plain
export DOCKER_BUILDKIT=1

# Increase BuildKit parallelism  
export BUILDKIT_STEP_LOG_MAX_SIZE=50000000
```

#### Memory Optimization
```bash
# For large builds on constrained systems
docker buildx create --use --driver docker-container \
  --driver-opt env.BUILDKIT_STEP_LOG_MAX_SIZE=10485760
```

## Security Considerations

### Image Security

1. **Non-root execution**: All production images run as non-root user
2. **Minimal attack surface**: Only necessary packages installed
3. **Security labels**: Comprehensive metadata for security scanning
4. **Regular updates**: Base images updated automatically via Dependabot

### Registry Security

```bash
# Sign images with cosign (optional)
cosign sign ghcr.io/toolprint/superego-mcp:latest

# Generate SBOM
docker buildx bake --set *.attest=type=sbom production
```

### Scanning Integration

```bash  
# Local vulnerability scanning
docker buildx bake security-scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image superego-mcp:latest
```

## Best Practices

### Development
- Use `dev-local` target for daily development
- Leverage volume mounts for fast iteration  
- Enable debugging only when needed
- Keep development images up-to-date

### Production
- Always use versioned tags in production
- Implement proper health checks
- Use minimal/distroless images for security
- Monitor build cache hit rates

### CI/CD
- Use separate cache scopes per workflow
- Implement multi-stage builds for better caching
- Scan images for vulnerabilities before deployment
- Use matrix builds for multi-platform testing

## Advanced Usage

### Custom Build Functions

The bake configuration includes helper functions for complex scenarios:

```hcl
# Custom tagging function
function "custom_tags" {
  params = [version, environment]
  result = [
    "ghcr.io/toolprint/superego-mcp:${version}-${environment}",
    "ghcr.io/toolprint/superego-mcp:latest-${environment}"
  ]
}
```

### Environment-Specific Builds

```bash
# Staging environment
REGISTRY="staging.registry.io" TAG="staging" \
  docker buildx bake production

# Production with specific optimizations  
PLATFORMS="linux/amd64" PUSH="true" \
  docker buildx bake production-minimal
```

This comprehensive Docker Bake configuration provides a robust foundation for building, testing, and deploying the Superego MCP Server across multiple platforms with optimal caching and security practices.