# Docker Bake configuration for Superego MCP Server
# Multi-platform builds with cache optimization and environment parameterization
# Supports: linux/amd64, linux/arm64

# =============================================================================
# VARIABLES AND FUNCTIONS
# =============================================================================

# Environment variable defaults with fallbacks
variable "REGISTRY" {
  default = "ghcr.io/toolprint"
}

variable "IMAGE_NAME" {
  default = "superego-mcp"
}

variable "TAG" {
  default = "latest"
}

variable "VERSION" {
  default = ""
}

variable "BUILD_DATE" {
  default = ""
}

variable "GIT_COMMIT" {
  default = ""
}

variable "BUILD_CACHE" {
  default = "inline"
}

variable "CACHE_FROM" {
  default = ""
}

variable "CACHE_TO" {
  default = ""
}

variable "PLATFORMS" {
  default = "linux/amd64,linux/arm64"
}

variable "PUSH" {
  default = false
}

# GitHub Actions cache configuration
variable "GITHUB_CACHE_SCOPE" {
  default = "superego-mcp"
}

# Development mode toggle
variable "DEV_MODE" {
  default = false
}

# Function to generate image tags
function "tags" {
  params = [image, tag, version]
  result = version != "" ? [
    "${REGISTRY}/${image}:${tag}",
    "${REGISTRY}/${image}:${version}",
    "${REGISTRY}/${image}:latest"
  ] : [
    "${REGISTRY}/${image}:${tag}",
    "${REGISTRY}/${image}:latest"
  ]
}

# Function to filter empty strings from a list
function "filter_empty" {
  params = [list]
  result = [for item in list : item if item != ""]
}

# Environment variable for Docker Metadata tags (when set by CI)
variable "DOCKER_METADATA_TAGS" {
  default = ""
}

# Function to generate cache configuration for GitHub Actions
function "github_cache" {
  params = [scope, mode]
  result = [
    "type=gha,scope=${scope}-${mode}",
    "type=gha,scope=${scope}-shared"
  ]
}

# Function to generate registry cache configuration
function "registry_cache" {
  params = [image, mode]
  result = [
    "type=registry,ref=${REGISTRY}/${image}:cache-${mode}",
    "type=registry,ref=${REGISTRY}/${image}:cache-shared"
  ]
}

# =============================================================================
# BUILD TARGETS
# =============================================================================

# Default target - production build for local platform
target "default" {
  inherits = ["production"]
  platforms = ["local"]
  output = ["type=docker"]
}

# Single platform target for CI testing
target "production-single" {
  inherits = ["production"]
  platforms = ["linux/amd64"]
  output = ["type=image"]
}

# Production target - optimized for cross-platform builds with enhanced performance
target "production" {
  dockerfile = "docker/production/Dockerfile"
  context = "."
  
  # Multi-platform support with cross-compilation optimization
  platforms = split(",", PLATFORMS)
  
  # Image tags - use metadata tags from CI if available, otherwise use function
  # Docker metadata action outputs newline-separated tags, so split by newline and filter empty strings
  tags = DOCKER_METADATA_TAGS != "" ? filter_empty(split("\n", DOCKER_METADATA_TAGS)) : tags(IMAGE_NAME, TAG, VERSION)
  
  # Build arguments optimized for cross-compilation
  args = {
    BUILDKIT_INLINE_CACHE = 1
    BUILD_DATE = BUILD_DATE
    GIT_COMMIT = GIT_COMMIT
    VERSION = VERSION
    # Cross-compilation optimizations
    BUILDKIT_MULTI_PLATFORM = 1
    DEBIAN_FRONTEND = "noninteractive"
    # Enhanced cache settings for faster builds
    UV_CACHE_DIR = "/tmp/.uv-cache"
    PIP_CACHE_DIR = "/tmp/.pip-cache"
  }
  
  # Enhanced cache configuration for multi-platform builds
  cache-from = CACHE_FROM != "" ? split(",", CACHE_FROM) : [
    "type=gha,scope=${GITHUB_CACHE_SCOPE}-deps",
    "type=gha,scope=${GITHUB_CACHE_SCOPE}-prod", 
    "type=registry,ref=${REGISTRY}/${IMAGE_NAME}:cache"
  ]
  cache-to = CACHE_TO != "" ? split(",", CACHE_TO) : [
    "type=gha,scope=${GITHUB_CACHE_SCOPE}-deps,mode=max",
    "type=gha,scope=${GITHUB_CACHE_SCOPE}-prod,mode=max",
    "type=registry,ref=${REGISTRY}/${IMAGE_NAME}:cache,mode=max"
  ]
  
  # Output configuration - avoid type=docker for multi-platform builds
  output = PUSH ? ["type=registry"] : ["type=image"]
  
  # Labels for metadata
  labels = {
    "org.opencontainers.image.title" = "Superego MCP Server"
    "org.opencontainers.image.description" = "Intelligent tool-call review system for AI agents"
    "org.opencontainers.image.vendor" = "toolprint"
    "org.opencontainers.image.licenses" = "MIT"
    "org.opencontainers.image.source" = "https://github.com/toolprint/superego-mcp"
    "org.opencontainers.image.documentation" = "https://github.com/toolprint/superego-mcp/blob/main/README.md"
    "org.opencontainers.image.created" = BUILD_DATE
    "org.opencontainers.image.revision" = GIT_COMMIT
    "org.opencontainers.image.version" = VERSION
    "io.buildpacks.builder.metadata" = "{\"description\":\"Cross-platform production build with optimized performance\"}"
  }
}

# Development target - optimized for hot-reload and debugging
target "development" {
  dockerfile = "docker/development/Dockerfile.development"
  context = "."
  
  # Multi-platform support (hardcoded ARM64 for darwin-arm64 host development)
  platforms = DEV_MODE ? ["linux/arm64"] : split(",", PLATFORMS)
  
  # Image tags for development
  tags = [
    "${REGISTRY}/${IMAGE_NAME}-dev:${TAG}",
    "${REGISTRY}/${IMAGE_NAME}-dev:latest"
  ]
  
  # Build arguments optimized for development
  args = {
    BUILDKIT_INLINE_CACHE = 1
    BUILD_DATE = BUILD_DATE
    GIT_COMMIT = GIT_COMMIT
    VERSION = VERSION
    DEVELOPMENT = 1
  }
  
  # Development cache configuration
  cache-from = CACHE_FROM != "" ? split(",", CACHE_FROM) : github_cache(GITHUB_CACHE_SCOPE, "dev")
  cache-to = CACHE_TO != "" ? split(",", CACHE_TO) : [
    "type=gha,scope=${GITHUB_CACHE_SCOPE}-dev,mode=max"
  ]
  
  # Output configuration - typically local for development
  output = PUSH && !DEV_MODE ? ["type=registry"] : ["type=docker"]
  
  # Development-specific labels
  labels = {
    "org.opencontainers.image.title" = "Superego MCP Server (Development)"
    "org.opencontainers.image.description" = "Development build with hot-reload and debugging support"
    "org.opencontainers.image.vendor" = "toolprint"
    "org.opencontainers.image.licenses" = "MIT"
    "org.opencontainers.image.source" = "https://github.com/toolprint/superego-mcp"
    "org.opencontainers.image.created" = BUILD_DATE
    "org.opencontainers.image.revision" = GIT_COMMIT
    "org.opencontainers.image.version" = VERSION
    "io.buildpacks.builder.metadata" = "{\"description\":\"Development build with hot-reload support\"}"
  }
}

# All platforms production build
target "production-all" {
  inherits = ["production"]
  platforms = ["linux/amd64", "linux/arm64"]
  output = ["type=registry"]
}

# Single platform builds for testing (using optimized cross-compilation)
target "production-amd64" {
  inherits = ["production"]
  platforms = ["linux/amd64"]
}

target "production-arm64" {
  inherits = ["production"] 
  platforms = ["linux/arm64"]
  # Uses the same optimized Dockerfile with cross-compilation
}

# Local development build (ARM64 for darwin-arm64 host)
target "dev-local" {
  inherits = ["development"]
  platforms = ["linux/arm64"]
  output = ["type=docker"]
  
  # Override tags for local development
  tags = [
    "${IMAGE_NAME}-dev:local",
    "${IMAGE_NAME}-dev:latest"
  ]
}

# =============================================================================
# GROUP TARGETS
# =============================================================================

# Build all production targets (optimized for cross-compilation)
group "all-production" {
  targets = ["production"]
}

# Build all development targets  
group "all-development" {
  targets = ["development", "dev-local"]
}

# Build everything (production + development)
group "all" {
  targets = ["production", "development", "dev-local"]
}

# CI/CD group - optimized for GitHub Actions with cross-compilation
group "ci" {
  targets = ["production-all"]
}

# Testing group - separate platform builds for validation (using cross-compilation)
group "test" {
  targets = ["production-amd64", "production-arm64"]
}

# Fast multi-platform build group (recommended for most use cases)
group "multi-arch" {
  targets = ["production"]
}

# =============================================================================
# SPECIAL TARGETS
# =============================================================================

# Cache warming target - builds dependencies only
target "cache-warm" {
  dockerfile-inline = <<EOF
FROM python:3.12-slim AS cache-warm
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --no-cache-dir hatchling build wheel && \
    uv pip install --no-cache-dir \
        "fastmcp>=2.0.0" \
        "pydantic>=2.0.0" \
        "pyyaml>=6.0" \
        "watchfiles>=0.20.0" \
        "jinja2>=3.1.0" \
        "httpx>=0.25.0" \
        "structlog>=23.0.0" \
        "psutil>=5.9.0" \
        "fastapi>=0.104.0" \
        "uvicorn[standard]>=0.24.0" \
        "jsonpath-ng>=1.6.0" \
        "python-dateutil>=2.8.0" \
        "prometheus-client>=0.19.0" \
        "aiohttp>=3.9.0" \
        "aiohttp-sse>=2.1.0"
EOF
  
  context = "."
  platforms = split(",", PLATFORMS)
  
  cache-to = [
    "type=gha,scope=${GITHUB_CACHE_SCOPE}-deps,mode=max"
  ]
  
  output = ["type=cacheonly"]
}

# Security scan target
target "security-scan" {
  inherits = ["production"]
  # Build for scanning - single platform is sufficient
  platforms = ["linux/amd64"]
  
  # Add security scanning labels
  labels = {
    "security.scan.enabled" = "true"
    "security.scan.timestamp" = BUILD_DATE
  }
  
  output = ["type=docker"]
}

# Size optimization target with distroless base
target "production-minimal" {
  dockerfile-inline = <<EOF
# Minimal production build using distroless base
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y build-essential git curl && \
    rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv
WORKDIR /build
COPY pyproject.toml uv.lock hatch_build.py ./
COPY src/ ./src/
COPY README.md ./
RUN uv venv /opt/venv && \
    /opt/venv/bin/uv pip install --no-cache-dir hatchling build wheel && \
    /opt/venv/bin/uv pip install --no-cache-dir -e . --no-deps && \
    /opt/venv/bin/uv pip install --no-cache-dir \
        "fastmcp>=2.0.0" "pydantic>=2.0.0" "pyyaml>=6.0" "watchfiles>=0.20.0" \
        "jinja2>=3.1.0" "httpx>=0.25.0" "structlog>=23.0.0" "psutil>=5.9.0" \
        "fastapi>=0.104.0" "uvicorn[standard]>=0.24.0" "jsonpath-ng>=1.6.0" \
        "python-dateutil>=2.8.0" "prometheus-client>=0.19.0" \
        "aiohttp>=3.9.0" "aiohttp-sse>=2.1.0" && \
    python -m build --wheel --outdir /build/dist

FROM gcr.io/distroless/python3-debian12:latest
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/dist/*.whl /tmp/
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["/opt/venv/bin/superego", "mcp", "--transport", "http", "--port", "8000"]
EOF
  
  context = "."
  platforms = split(",", PLATFORMS)
  
  tags = [
    "${REGISTRY}/${IMAGE_NAME}-minimal:${TAG}",
    "${REGISTRY}/${IMAGE_NAME}-minimal:latest"
  ]
  
  cache-from = github_cache(GITHUB_CACHE_SCOPE, "minimal")
  cache-to = [
    "type=gha,scope=${GITHUB_CACHE_SCOPE}-minimal,mode=max"
  ]
  
  output = PUSH ? ["type=registry"] : ["type=docker"]
  
  labels = {
    "org.opencontainers.image.title" = "Superego MCP Server (Minimal)"
    "org.opencontainers.image.description" = "Minimal distroless build for maximum security"
    "org.opencontainers.image.vendor" = "toolprint"
    "org.opencontainers.image.version" = VERSION
  }
}