# common.just - Shared utilities and helpers

# Validate choice against list of valid options
_validate choice valid_options:
    #!/usr/bin/env bash
    if [[ ! " {{valid_options}} " =~ " {{choice}} " ]]; then
        echo "❌ Invalid option: '{{choice}}'"
        echo "   Valid options: {{valid_options}}"
        exit 1
    fi

# Consistent error handling
_error context message:
    #!/usr/bin/env bash
    echo "❌ {{context}}: {{message}}" >&2
    exit 1

# Success messages
_success message:
    @echo "✅ {{message}}"

# Info messages
_info message:
    @echo "ℹ️  {{message}}"

# Warning messages
_warn message:
    @echo "⚠️  {{message}}"

# Check command exists
_require-command command:
    #!/usr/bin/env bash
    if ! command -v {{command}} &> /dev/null; then
        echo "❌ {{command}} is required but not installed"
        exit 1
    fi

# Run with pretty output
_run description command:
    @echo "🔄 {{description}}..."
    @{{command}}
    @echo "✅ {{description}} complete"

# Tool detection - uv vs python
_python := if path_exists(".venv/bin/python") == "true" { ".venv/bin/python" } else { "uv run python" }
_uv := "uv"

# Get project version (handles dynamic versions)
_version:
    @{{_uv}} run python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb')).get('project', {}).get('version', '0.0.0'))" 2>/dev/null || echo "0.0.0"

# Get git commit hash
_git_commit:
    @git rev-parse --short HEAD 2>/dev/null || echo "unknown"

# Get current date in ISO format
_build_date:
    @date -u +'%Y-%m-%dT%H:%M:%SZ'