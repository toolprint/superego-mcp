# Superego MCP DevContainer

A complete development environment for Superego MCP Server with VS Code integration.

## Features

- ✅ **Fast Startup**: <30 second initialization
- 🔄 **Hot Reload**: Instant code changes with file watching
- 🐛 **Integrated Debugging**: Python debugger with VS Code integration
- 📦 **UV Package Management**: Fast dependency management
- 🧪 **Testing Framework**: pytest with coverage reporting
- 📊 **Monitoring Dashboard**: Real-time server metrics
- 🔍 **Code Quality**: Ruff linting, mypy type checking
- 🐳 **Docker Integration**: Leverages existing development infrastructure

## Quick Start

### Prerequisites

- Docker Desktop or Docker Engine
- VS Code with Dev Containers extension
- 4GB+ RAM, 2+ CPU cores recommended

### Launch DevContainer

1. **Open in VS Code**:
   ```bash
   code /path/to/superego-mcp
   ```

2. **Open in Container**:
   - Press `F1` → "Dev Containers: Open Folder in Container"
   - Or click "Reopen in Container" notification

3. **Wait for Setup** (~15-30 seconds):
   - Container builds and starts
   - Dependencies sync via UV
   - VS Code extensions install
   - Development tools configure

### Development Workflow

#### Start the Server
```bash
# Quick start
just run

# Or with debugging
DEBUGPY_ENABLED=1 just run

# Or with monitoring
docker-compose --profile full up
```

#### Access Services
- **Server**: http://localhost:8002
- **Monitoring**: http://localhost:8003  
- **Debug Port**: 5679 (when enabled)

#### Run Tests
```bash
# All tests
just test

# With coverage
just test-cov

# Specific test file
just test-file tests/test_security_policy.py
```

#### Code Quality
```bash
# Lint and format
just format
just lint

# Type checking  
just typecheck

# All quality checks
just check
```

## Development Tools

### VS Code Integration

**Pre-configured Extensions**:
- Python development (ms-python.python)
- Ruff linting/formatting (charliermarsh.ruff)
- Pytest testing (ms-python.pytest)
- Docker tools (ms-azuretools.vscode-docker)
- GitLens (eamodio.gitlens)
- YAML support (redhat.vscode-yaml)

**Debugger Configuration**:
- Debug Superego Server
- Debug Tests
- Attach to Remote Debug

**Terminal Integration**:
- Python virtual environment auto-activation
- UV package management commands
- Just task runner integration

### File Structure

```
.devcontainer/
├── devcontainer.json       # Main DevContainer configuration
├── docker-compose.yml      # Container orchestration overrides
├── entrypoint.sh          # Initialization script
└── README.md              # This documentation
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVELOPMENT` | `1` | Enable development mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `HOT_RELOAD` | `1` | Enable file watching |
| `DEBUGPY_ENABLED` | `0` | Enable remote debugging |
| `PYTHONPATH` | `/app/src` | Python module path |

### Port Forwarding

| Port | Service | Access |
|------|---------|--------|
| 8002 | HTTP Server | http://localhost:8002 |
| 8003 | Monitoring | http://localhost:8003 |
| 5679 | Debug Port | VS Code debugger |
| 8082 | Alt HTTP | http://localhost:8082 |

### Volume Mounts

**Source Code** (cached):
- `src/` → `/app/src`
- `config/` → `/app/config`
- `tests/` → `/app/tests`
- `demo/` → `/app/demo`

**Performance** (tmpfs):
- `logs/` → In-memory logging
- `tmp/` → Temporary files
- `.cache/` → UV and tool caches

## Customization

### Override Settings

Create `.devcontainer/devcontainer.local.json`:
```json
{
  "customizations": {
    "vscode": {
      "extensions": [
        "your.additional.extension"
      ],
      "settings": {
        "your.custom.setting": "value"
      }
    }
  },
  "containerEnv": {
    "YOUR_ENV_VAR": "value"
  }
}
```

### Add Development Tools

Edit `.devcontainer/entrypoint.sh`:
```bash
# Add your setup commands
echo "Installing additional tools..."
uv add your-dev-tool --dev
```

## Performance Optimization

### Fast Startup Tips

1. **Pre-built Images**: Use `docker-compose build` to cache layers
2. **Volume Caching**: Named volumes for persistent data
3. **Minimal Installs**: Only essential packages in container
4. **Parallel Setup**: Dependencies sync while container starts

### Resource Allocation

**Minimum Requirements**:
- 2 CPU cores
- 4GB RAM  
- 8GB storage

**Recommended**:
- 4+ CPU cores
- 8GB+ RAM
- 20GB+ storage

## Troubleshooting

### Slow Startup (>30s)

1. **Check Resources**: Ensure adequate CPU/memory
2. **Clean Cache**: `docker system prune`
3. **Rebuild**: `docker-compose build --no-cache`
4. **Update Base**: Pull latest development image

### Import Errors

```bash
# Fix Python path
export PYTHONPATH=/app/src

# Reinstall dependencies
uv sync --frozen --reinstall
```

### Port Conflicts

```bash
# Check port usage
sudo lsof -i :8002

# Use alternative ports
SUPEREGO_PORT=8004 just run
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R $USER:$USER .
```

## Integration Testing

### Manual Verification

1. **Container Startup**: Time from `code .` to ready prompt
2. **Hot Reload**: Edit file, verify server restarts
3. **Debugging**: Set breakpoint, attach debugger
4. **Testing**: Run tests, view coverage
5. **Port Access**: Verify all services accessible

### Automated Testing

```bash
# Test DevContainer build
docker-compose -f .devcontainer/docker-compose.yml build

# Test startup performance  
time docker-compose -f .devcontainer/docker-compose.yml up -d

# Test health checks
docker-compose -f .devcontainer/docker-compose.yml ps
```

## Support

- **Issues**: [GitHub Issues](https://github.com/toolprint/superego-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/toolprint/superego-mcp/discussions)
- **Documentation**: [Project README](../README.md)

---

**Happy coding with Superego MCP! 🚀**