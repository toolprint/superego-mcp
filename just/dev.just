# dev.just - Development workflows and setup

# Development setup
[group: 'development']
setup:
    @just _info "Setting up development environment..."
    @just _run "Syncing dependencies with all extras" "{{_uv}} sync --all-extras"
    @just _success "Development environment ready!"

# Install dependencies
[group: 'development']
install:
    @just _run "Installing dependencies" "{{_uv}} sync"

# Install with development extras
[group: 'development']
install-dev-deps:
    @just _run "Installing development dependencies" "{{_uv}} sync --extra dev"

# Run the server
[group: 'development']
run:
    @just _info "Starting Superego MCP Server..."
    {{_uv}} run superego mcp

# Run the server (legacy entry point)
[group: 'development']
run-legacy:
    @just _info "Starting Superego MCP Server (legacy)..."
    {{_uv}} run superego-mcp

# Run server with performance optimizations
[group: 'development']
run-optimized:
    @just _info "Starting Superego MCP Server with performance optimizations..."
    {{_uv}} run python -m superego_mcp.main_optimized

# Update dependencies
[group: 'development']
update:
    @just _run "Updating dependencies" "{{_uv}} lock --upgrade"

# Generate requirements.txt for compatibility
[group: 'development']
requirements:
    @just _run "Generating requirements.txt" "{{_uv}} export --format requirements-txt --no-hashes > requirements.txt"

# Watch for changes and run tests
[group: 'development']
watch:
    @just _info "Watching for changes..."
    {{_uv}} run watchfiles "just test" src/ tests/

# Show project info
[group: 'development']
info:
    @echo "Project: Superego MCP Server"
    @echo "Version: $(just _version)"
    @echo "Python: $(python --version)"
    @echo "UV: $({{_uv}} --version)"
    @echo ""
    @echo "Dependencies:"
    @{{_uv}} tree
    @echo ""
    @echo "Development Commands:"
    @echo "  just install-dev     Install local build with pipx"
    @echo "  just uninstall-dev   Uninstall from pipx"
    @echo "  just reinstall-dev   Clean reinstall"
    @echo "  just pipx-status     Show pipx installation status"