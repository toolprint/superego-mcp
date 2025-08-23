# build.just - Build and packaging recipes

# Build package
[group: 'build']
build: clean
    @just _run "Building package" "{{_uv}} build"

# Build and test package installation
[group: 'build']
build-test: build
    #!/usr/bin/env bash
    just _info "Testing package installation..."
    # Test wheel installation
    just _run "Installing wheel to temporary environment" "python -m venv /tmp/superego-test-env"
    /tmp/superego-test-env/bin/pip install dist/*.whl
    just _run "Testing CLI installation" "/tmp/superego-test-env/bin/superego --version"
    /tmp/superego-test-env/bin/superego --help > /dev/null
    just _run "Cleaning up test environment" "rm -rf /tmp/superego-test-env"
    just _success "Package installation test completed!"

# =============================================================================
# PIPX INSTALLATION MANAGEMENT
# =============================================================================

# Install local development build with pipx
[group: 'build']
install-dev: build
    #!/usr/bin/env bash
    just _info "Installing local development build with pipx..."
    if command -v pipx >/dev/null 2>&1; then
        echo "Checking if superego-mcp is already installed..."
        if pipx list | grep -q "superego-mcp"; then
            just _info "Uninstalling existing version..."
            pipx uninstall superego-mcp
        fi
        just _run "Installing from local wheel" "pipx install --force ./dist/superego_mcp-$(just _version)-py3-none-any.whl"
        just _success "Installed superego-mcp with pipx"
        just _info "Testing installation..."
        superego --version
        echo ""
        echo "Superego is now available globally as 'superego'"
        echo "Try: superego --help"
    else
        just _error "pipx" "pipx not found. Install with: brew install pipx (macOS) or python -m pip install --user pipx"
    fi

# Uninstall development build from pipx
[group: 'build']
uninstall-dev:
    #!/usr/bin/env bash
    just _info "Uninstalling superego-mcp from pipx..."
    if command -v pipx >/dev/null 2>&1; then
        if pipx list | grep -q "superego-mcp"; then
            pipx uninstall superego-mcp
            just _success "Uninstalled superego-mcp from pipx"
        else
            just _info "superego-mcp is not installed via pipx"
        fi
    else
        just _info "pipx not found - nothing to uninstall"
    fi

# Reinstall development build (clean install)
[group: 'build']
reinstall-dev: uninstall-dev install-dev
    @just _success "Reinstalled development build"

# Show pipx installation status
[group: 'build']
pipx-status:
    #!/usr/bin/env bash
    just _info "Checking pipx installation status..."
    if command -v pipx >/dev/null 2>&1; then
        echo "pipx is installed: $(which pipx)"
        echo "pipx version: $(pipx --version)"
        echo ""
        echo "Installed packages:"
        pipx list
        echo ""
        if pipx list | grep -q "superego-mcp"; then
            echo "✅ superego-mcp is installed via pipx"
            echo "Testing command:"
            superego --version 2>/dev/null || echo "Command not found in PATH"
        else
            echo "❌ superego-mcp is not installed via pipx"
        fi
    else
        echo "❌ pipx is not installed"
        echo "Install with:"
        echo "  brew install pipx  # macOS"
        echo "  python -m pip install --user pipx  # Other systems"
    fi

# =============================================================================
# RELEASE PREPARATION
# =============================================================================

# Prepare release
[group: 'build']
prepare-release:
    @just _info "Preparing release..."
    @just _run "Running all quality checks" "just check"
    @just _run "Building package" "just build"
    @just _run "Testing installation" "just build-test"
    @just _success "Release preparation completed!"

# Generate release notes
[group: 'build']
release-notes version:
    #!/usr/bin/env bash
    just _info "Generating release notes for version {{version}}..."
    echo "# Release {{version}}" > RELEASE_NOTES.md
    echo "" >> RELEASE_NOTES.md
    echo "## Changes" >> RELEASE_NOTES.md
    echo "" >> RELEASE_NOTES.md
    git log --oneline --grep="^(feat|fix|docs|style|refactor|test|chore)" --since="$(git describe --tags --abbrev=0)..HEAD" >> RELEASE_NOTES.md
    just _success "Release notes generated in RELEASE_NOTES.md"

# Create homebrew formula
[group: 'build']
homebrew-formula: build
    #!/usr/bin/env bash
    just _info "Generating Homebrew formula..."
    VERSION=$(just _version)
    SHA256=$(sha256sum dist/*.tar.gz | cut -d' ' -f1)
    
    echo "class Superego < Formula" > superego.rb
    echo '  desc "Intelligent tool request interception for AI agents"' >> superego.rb
    echo '  homepage "https://github.com/toolprint/superego-mcp"' >> superego.rb
    echo "  url \"https://files.pythonhosted.org/packages/source/s/superego-mcp/superego-mcp-${VERSION}.tar.gz\"" >> superego.rb
    echo "  sha256 \"${SHA256}\"" >> superego.rb
    echo '  license "MIT"' >> superego.rb
    echo '' >> superego.rb
    echo '  depends_on "python@3.11"' >> superego.rb
    echo '' >> superego.rb
    echo '  def install' >> superego.rb
    echo '    virtualenv_install_with_resources' >> superego.rb
    echo '  end' >> superego.rb
    echo '' >> superego.rb
    echo '  test do' >> superego.rb
    echo '    system bin/"superego", "--version"' >> superego.rb
    echo '  end' >> superego.rb
    echo 'end' >> superego.rb
    
    just _success "Homebrew formula generated: superego.rb"