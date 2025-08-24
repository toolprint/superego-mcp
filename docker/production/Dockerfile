# Multi-stage production Dockerfile for superego-mcp
# Optimized for cross-platform builds, security, performance, and minimal size

# Build stage - includes build tools and dependencies
# Use cross-compilation optimization with buildx
FROM --platform=$BUILDPLATFORM python:3.12-slim AS builder

# Build arguments for cross-platform support
ARG BUILDPLATFORM
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

# Configure environment for non-interactive installs and ARM64 optimization
ENV DEBIAN_FRONTEND=noninteractive \
    DEBCONF_NONINTERACTIVE_SEEN=true \
    DEBIAN_PRIORITY=critical \
    APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pre-configure debconf to avoid frontend issues
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections && \
    echo 'APT::Get::Assume-Yes "true";' > /etc/apt/apt.conf.d/90assumeyes && \
    echo 'APT::Install-Recommends "false";' >> /etc/apt/apt.conf.d/90assumeyes && \
    echo 'APT::Install-Suggests "false";' >> /etc/apt/apt.conf.d/90assumeyes

# Install build dependencies with buildx cache optimization
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
        ca-certificates \
        nodejs npm \
        && apt-get clean

# Install UV with cache mount for pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir uv

WORKDIR /build

# Install Claude Code CLI with npm cache mount
RUN --mount=type=cache,target=/root/.npm \
    npm install -g @anthropic-ai/claude-code --production --no-optional && \
    # Verify installation and create symlink if needed
    (which claude || ln -s /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude /usr/local/bin/claude) && \
    # Test the installation
    claude --version || echo "Claude CLI installation needs manual verification"

# Copy project files
COPY pyproject.toml uv.lock hatch_build.py ./
COPY src/ ./src/
COPY config/ ./config/
COPY README.md ./

# Create virtual environment with UV cache mount optimization
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install build tools with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-cache-dir hatchling build wheel

# Install all dependencies in optimized layers for cross-compilation
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/tmp/.uv-cache \
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

# Install project dependencies with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-cache-dir -e . --no-deps

# Build wheel package (disable custom hooks)
ENV HATCH_BUILD_HOOKS_ENABLE=false
RUN python -m build --wheel --outdir /build/dist

# Runtime stage - minimal production image with cross-platform support  
FROM --platform=$TARGETPLATFORM python:3.12-slim AS runtime

# Configure environment for non-interactive installs
ENV DEBIAN_FRONTEND=noninteractive \
    DEBCONF_NONINTERACTIVE_SEEN=true \
    DEBIAN_PRIORITY=critical \
    APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pre-configure debconf for runtime stage
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections && \
    echo 'APT::Get::Assume-Yes "true";' > /etc/apt/apt.conf.d/90assumeyes && \
    echo 'APT::Install-Recommends "false";' >> /etc/apt/apt.conf.d/90assumeyes && \
    echo 'APT::Install-Suggests "false";' >> /etc/apt/apt.conf.d/90assumeyes

# Install runtime dependencies with buildx cache optimization
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        curl \
        tini \
        ca-certificates \
        nodejs npm \
        && apt-get clean

# Install UV with cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir uv

# Create non-root user for security
RUN groupadd -r superego && useradd -r -g superego -d /app -s /bin/bash superego

# Set up application directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Claude CLI with npm cache mount 
RUN --mount=type=cache,target=/root/.npm \
    npm install -g @anthropic-ai/claude-code --production --no-optional && \
    # Verify installation and create symlink if needed
    (which claude || ln -s /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude /usr/local/bin/claude) && \
    # Test the installation
    claude --version || echo "Claude CLI runtime verification: will be tested at container startup"

# Copy the built wheel and install it
COPY --from=builder /build/dist/*.whl /tmp/
RUN uv pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

# Copy configuration files
COPY --from=builder /build/config/ ./config/

# Copy entrypoint script
COPY docker/production/docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Create data directory for configuration and logs
RUN mkdir -p /app/data /app/logs && chown -R superego:superego /app

# Switch to non-root user
USER superego

# Environment configuration
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SUPEREGO_HOST=0.0.0.0
ENV SUPEREGO_PORT=8000
ENV SUPEREGO_LOG_LEVEL=info
ENV SUPEREGO_CONFIG_PATH=/app/data/server.yaml

# Health check - verify server is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${SUPEREGO_PORT:-8000}/health || exit 1

# Expose the server port
EXPOSE 8000

# Use tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--", "./docker-entrypoint.sh"]

# Labels for metadata
LABEL org.opencontainers.image.title="Superego MCP Server" \
      org.opencontainers.image.description="Intelligent tool-call review system for AI agents" \
      org.opencontainers.image.vendor="toolprint" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/toolprint/superego-mcp"