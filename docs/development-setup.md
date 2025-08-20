# Superego MCP Development Setup

## Local Development Environment

### Prerequisites
- Python 3.9+
- Docker Desktop
- VS Code (recommended)
- Git
- Poetry (Python dependency management)

### Development Tools
- Justfile for task automation
- DevContainer support
- Integrated testing framework
- Type checking with mypy
- Linting with ruff

### Setup Steps

#### 1. Clone Repository
```bash
git clone https://github.com/your-org/superego-mcp.git
cd superego-mcp
```

#### 2. Install Dependencies
```bash
# Install Poetry if not already installed
pip install poetry

# Install project dependencies
poetry install

# Activate virtual environment
poetry shell
```

#### 3. DevContainer Setup
1. Install VS Code Remote - Containers extension
2. Open project in VS Code
3. Press Cmd+Shift+P (macOS) or Ctrl+Shift+P (Windows/Linux)
4. Select "Remote-Containers: Reopen in Container"

### Development Workflows

#### Running the Project
```bash
# Use Justfile for common tasks
just run-dev        # Start development server
just test           # Run tests
just lint           # Run linters
just typecheck      # Run type checking
```

#### Testing
- Unit tests: `just test`
- Coverage report: `just test-cov`
- Performance tests: `just test-performance`

#### Continuous Integration
- GitHub Actions configured for:
  - Unit testing
  - Type checking
  - Linting
  - Security scanning

### Best Practices
- Always work in feature branches
- Write comprehensive tests
- Follow PEP 8 style guidelines
- Use type hints
- Document new features

### Debugging
- Use `poetry run python -m debugpy` for remote debugging
- Leverage VS Code's integrated debugger
- Check logs in `.vscode/launch.json`

### Environment Variables
- Copy `.env.example` to `.env`
- Never commit sensitive information
- Use environment-specific configurations

### Performance Profiling
```bash
just profile       # Run performance profiler
just benchmark     # Run benchmarks
```

## Recommended VS Code Extensions
- Python
- Pylance
- Docker
- GitLens
- Markdown All in One