# quality.just - Code quality checks and formatting

# Lint code
[group: 'quality']
lint fix="false":
    #!/usr/bin/env bash
    if [ "{{fix}}" = "true" ]; then
        just _run "Auto-fixing linting issues" "{{_uv}} run ruff check --fix src/ tests/"
    else
        just _run "Linting code" "{{_uv}} run ruff check src/ tests/"
    fi
    just _run "Checking code format" "{{_uv}} run ruff format --check src/ tests/"

# Fix linting issues
[group: 'quality']
lint-fix:
    @just _run "Fixing linting issues" "{{_uv}} run ruff check --fix src/ tests/"
    @just _run "Formatting code" "{{_uv}} run ruff format src/ tests/"

# Format code
[group: 'quality']
format:
    @just _run "Formatting code" "{{_uv}} run ruff format src/ tests/"

# Type check with mypy
[group: 'quality']
typecheck:
    @just _run "Type checking" "{{_uv}} run mypy src/"

# Security check
[group: 'quality']
security:
    @just _run "Running security checks" "{{_uv}} run pip-audit"

# Clean build artifacts
[group: 'quality']
clean:
    @just _info "Cleaning build artifacts..."
    @rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/
    @find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete
    @just _success "Build artifacts cleaned"

# Run all quality checks
[group: 'quality']
check: lint typecheck
    @just _success "All quality checks completed!"

# Quick checks (fast)
[group: 'quality']
check-fast: format lint
    @just _success "Fast checks complete"

# Full checks including tests
[group: 'quality']
check-all: check
    @just test
    @just _success "All checks complete"