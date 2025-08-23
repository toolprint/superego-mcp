# Building Python MCP Servers with Docker: A Complete Guide

This guide provides a comprehensive approach to building, packaging, and deploying Python MCP (Model Context Protocol) servers using Docker. Based on the Goaly MCP project architecture, it demonstrates best practices for creating production-ready MCP servers with FastMCP 2.0.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Python Packaging with Hatch](#python-packaging-with-hatch)
4. [Docker Strategy](#docker-strategy)
5. [Development Workflow](#development-workflow)
6. [Production Deployment](#production-deployment)
7. [CI/CD Integration](#cicd-integration)
8. [Best Practices](#best-practices)

## Architecture Overview

This architecture combines several modern Python development practices:

- **FastMCP 2.0**: FastAPI-based MCP server with async support
- **UV**: Ultra-fast Python package manager for dependency resolution
- **Hatch**: Modern Python build system with custom hooks
- **Docker Bake**: Multi-platform, multi-target Docker builds
- **DevContainers**: Consistent development environment with hot-reload

### Why This Architecture?

1. **Unified Server**: Single server handles both MCP protocol and web dashboard
2. **Wheel-based Deployment**: Pre-built wheels include all assets for faster Docker builds
3. **Multi-stage Builds**: Optimized images with minimal attack surface
4. **Development Parity**: DevContainers mirror production environment

## Project Structure

```
goaly-mcp/
├── src/
│   └── goaly_mcp/
│       ├── __init__.py
│       ├── app.py              # Unified FastAPI + MCP server
│       ├── main.py             # Server entry point
│       ├── mcp_tools.py        # MCP tool definitions
│       ├── models.py           # SQLAlchemy models
│       ├── api/                # REST API endpoints
│       ├── frontend_assets/    # Built frontend (populated by hatch)
│       └── migrations/         # Alembic database migrations
├── frontend/                   # React dashboard
│   ├── src/
│   ├── package.json
│   └── build/                  # Built assets (copied by hatch)
├── docker/
│   ├── production/
│   │   ├── Dockerfile          # Production image
│   │   └── docker-entrypoint.sh
│   └── development/
│       └── Dockerfile.development
├── .devcontainer/
│   └── devcontainer.json       # VS Code DevContainer config
├── pyproject.toml              # Python project configuration
├── hatch_build.py              # Custom build hook
├── docker-bake.hcl             # Docker Bake configuration
├── justfile                    # Task automation
└── uv.lock                     # Locked dependencies
```

## Python Packaging with Hatch

### pyproject.toml Configuration

```toml
[project]
name = "goaly-mcp"
version = "0.0.0"
description = "Goal and Task Management with Model Context Protocol"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "fastmcp>=2.0.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    # ... other dependencies
]

[project.scripts]
goaly-server = "goaly_mcp.main:main"
goaly-migrate = "goaly_mcp.migrations.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.hooks.custom]
path = "hatch_build.py"

[tool.hatch.build.targets.wheel]
packages = ["src/goaly_mcp"]
artifacts = [
  "src/goaly_mcp/migrations/**/*",
  "src/goaly_mcp/frontend_assets/**/*",
  "src/goaly_mcp/prompts/data/**/*",
]
```

### Custom Build Hook (hatch_build.py)

The build hook automatically includes frontend assets in the wheel:

```python
from pathlib import Path
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "frontend-build"
    
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel":
            return
            
        # Copy frontend build to package
        frontend_build = Path(self.root) / "frontend" / "build"
        target_dir = Path(self.root) / "src" / "goaly_mcp" / "frontend_assets"
        
        if frontend_build.exists():
            self._copy_frontend_assets(frontend_build, target_dir)
```

## Docker Strategy

### Production Dockerfile

The production Dockerfile uses a pre-built wheel for efficiency:

```dockerfile
FROM python:3.12-slim as runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# Create non-root user
RUN groupadd -r goaly && useradd -r -g goaly -d /app -s /bin/bash goaly

WORKDIR /app

# Create virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install from wheel
COPY dist/*.whl /tmp/
RUN uv pip install /tmp/*.whl && rm -f /tmp/*.whl

# Copy entrypoint
COPY docker/production/docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh && chown -R goaly:goaly /app

USER goaly

# Configure environment
ENV GOALY_HOST=0.0.0.0
ENV GOALY_PORT=8000
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--", "./docker-entrypoint.sh"]
```

### Docker Bake Configuration

Docker Bake enables multi-platform, multi-target builds:

```hcl
variable "REGISTRY" {
  default = "ghcr.io"
}

variable "PLATFORMS" {
  default = "linux/amd64,linux/arm64"
}

target "base" {
  context = "."
  dockerfile = "docker/production/Dockerfile"
  platforms = split(",", PLATFORMS)
  pull = true
}

target "production" {
  inherits = ["base"]
  tags = ["${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:latest"]
  cache-from = ["type=gha,scope=goaly-mcp-prod"]
  cache-to = ["type=gha,scope=goaly-mcp-prod,mode=max"]
}

target "development" {
  inherits = ["base"]
  dockerfile = "docker/development/Dockerfile.development"
  tags = ["${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:dev"]
}
```

### Entrypoint Script

The entrypoint handles database migrations and graceful shutdown:

```bash
#!/bin/bash
set -e

# Signal handlers
shutdown() {
    log_info "Received shutdown signal, cleaning up..."
    if [ -n "$APP_PID" ]; then
        kill -TERM "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi
    exit 0
}

trap shutdown SIGTERM SIGINT

# Database connectivity check with retries
# Run migrations
if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
    goaly-db-upgrade || exit 1
fi

# Start application
if [ "${GOALY_DEV_MODE:-false}" = "true" ]; then
    exec uvicorn goaly_mcp.main:app --reload --host 0.0.0.0 --port 8000 &
else
    exec goaly-server &
fi

APP_PID=$!
wait $APP_PID
```

## Development Workflow

### DevContainer Configuration

The DevContainer provides a consistent development environment:

```json
{
  "name": "Goaly MCP Development",
  "dockerFile": "../docker/development/Dockerfile.development",
  "workspaceFolder": "/app",
  
  "mounts": [
    "source=${localWorkspaceFolder}/src,target=/app/src,type=bind,consistency=cached",
    "source=${localWorkspaceFolder}/tests,target=/app/tests,type=bind,consistency=cached",
    "source=goaly-devcontainer-data,target=/app/data,type=volume"
  ],
  
  "containerEnv": {
    "GOALY_DEBUG": "true",
    "UVICORN_RELOAD": "true",
    "DATABASE_URL": "sqlite+aiosqlite:///./data/goaly.db"
  },
  
  "postStartCommand": "/workspaces/goaly-mcp/.devcontainer/entrypoint.sh &",
  
  "customizations": {
    "vscode": {
      "settings": {
        "python.defaultInterpreterPath": "/opt/venv/bin/python"
      },
      "extensions": [
        "ms-python.python",
        "charliermarsh.ruff"
      ]
    }
  }
}
```

### Development Dockerfile

Optimized for hot-reload development:

```dockerfile
FROM python:3.12-slim as development

# Install development tools
RUN apt-get update && apt-get install -y \
    build-essential git vim \
    && pip install uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip sync uv.lock

# Install debugging tools
RUN uv pip install debugpy ipdb

# Development environment variables
ENV GOALY_DEV_MODE=true
ENV UVICORN_RELOAD=true

EXPOSE 8000 5678

CMD ["uvicorn", "goaly_mcp.main:app", "--reload", "--host", "0.0.0.0"]
```

## Production Deployment

### Building for Production

1. **Build Frontend Assets**:
```bash
cd frontend
pnpm install
pnpm run build
```

2. **Build Python Wheel**:
```bash
# Hatch will automatically include frontend assets
uv build --wheel
```

3. **Build Docker Image**:
```bash
# Using Docker Bake
docker buildx bake production --push

# Or traditional build
docker build -f docker/production/Dockerfile -t goaly-mcp:latest .
```

### Deployment Configuration

Example docker-compose.yml for production:

```yaml
services:
  goaly-mcp:
    image: ghcr.io/toolprint/goaly-mcp:latest
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/goaly
      GOALY_DEBUG: "false"
      GOALY_MCP_SERVER_API_KEY: ${MCP_API_KEY}
    volumes:
      - goaly-data:/app/data
    depends_on:
      - db
    restart: unless-stopped
    
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: goaly
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres-data:/var/lib/postgresql/data
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          
      - name: Install uv
        uses: astral-sh/setup-uv@v3
        
      - name: Build frontend
        run: |
          cd frontend
          pnpm install
          pnpm run build
          
      - name: Build wheel
        run: uv build --wheel
        
      - name: Build Docker images
        uses: docker/bake-action@v5
        with:
          files: docker-bake.hcl
          targets: production
          push: true
```

## Best Practices

### 1. Security

- **Non-root User**: Always run containers as non-root
- **Minimal Base Images**: Use slim Python images
- **Secret Management**: Use environment variables for sensitive data
- **Health Checks**: Implement comprehensive health endpoints

### 2. Performance

- **Multi-stage Builds**: Separate build and runtime stages
- **Layer Caching**: Optimize Dockerfile for cache efficiency
- **Virtual Environments**: Use uv for fast dependency installation
- **Asset Optimization**: Pre-build frontend assets into wheel

### 3. Development Experience

- **Hot Reload**: Enable auto-reload in development
- **Consistent Environments**: Use DevContainers
- **Task Automation**: Leverage justfile for common tasks
- **Type Safety**: Use mypy and TypeScript

### 4. Deployment

- **Multi-platform Support**: Build for amd64 and arm64
- **Graceful Shutdown**: Handle signals properly
- **Database Migrations**: Run automatically on startup
- **Observability**: Implement logging and monitoring

### 5. MCP-Specific Considerations

- **Unified Server**: Combine MCP and web API in single process
- **Tool Registration**: Register MCP tools at startup
- **Async Support**: Use FastMCP's async capabilities
- **Error Handling**: Implement proper MCP error responses

## Example: Creating a New MCP Server

To create a new Python MCP server using this architecture:

1. **Initialize Project**:
```bash
mkdir my-mcp-server
cd my-mcp-server
git init
uv init --python 3.12
```

2. **Set Up Project Structure**:
```bash
mkdir -p src/my_mcp_server/{api,models,tools}
mkdir -p docker/{production,development}
mkdir -p .devcontainer
```

3. **Configure pyproject.toml**:
```toml
[project]
name = "my-mcp-server"
dependencies = [
    "fastmcp>=2.0.0",
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
]

[project.scripts]
my-mcp-server = "my_mcp_server.main:main"
```

4. **Create MCP Server**:
```python
# src/my_mcp_server/app.py
from fastmcp import FastMCP
from fastapi import FastAPI

# Create MCP server
mcp = FastMCP(name="My MCP Server")

# Register tools
@mcp.tool()
async def my_tool(query: str) -> str:
    """Example MCP tool"""
    return f"Processed: {query}"

# Create unified app
app = FastAPI()
app.mount("/mcp", mcp.http_app())
```

5. **Set Up Docker**:
- Copy Dockerfile templates from this guide
- Create docker-bake.hcl for multi-platform builds
- Add docker-entrypoint.sh for initialization

6. **Configure Development**:
- Set up .devcontainer/devcontainer.json
- Create justfile for task automation
- Configure pre-commit hooks

## Conclusion

This architecture provides a robust foundation for building Python MCP servers with Docker. It balances development speed, production reliability, and deployment flexibility while maintaining best practices for modern Python applications.

Key takeaways:
- Use wheel-based deployments for faster, more reliable builds
- Leverage Docker Bake for multi-platform support
- Implement proper DevContainer setup for consistent development
- Automate common tasks with justfile
- Follow security best practices with non-root users and minimal images

By following this guide, you can create production-ready MCP servers that are easy to develop, test, and deploy across various environments.