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

# =============================================================================
# PYPI PUBLISHING
# =============================================================================

# Validate package is ready for PyPI publishing
[group: 'publish']
pypi-check:
    #!/usr/bin/env bash
    just _info "Validating PyPI publishing requirements..."
    
    # Check if twine is available
    if ! command -v {{_uv}} run twine >/dev/null 2>&1; then
        just _error "twine" "twine not found. Run: {{_uv}} add --dev twine"
    fi
    
    # Check if .pypirc exists
    if [ ! -f ~/.pypirc ]; then
        just _error "credentials" "~/.pypirc not found. Create it with your PyPI API token"
    fi
    
    # Check if dist/ has distributions
    if [ ! -d "dist" ] || [ -z "$(ls -A dist/ 2>/dev/null)" ]; then
        just _info "No distributions found. Building..."
        just build
    fi
    
    # Validate distributions
    just _run "Validating distributions" "{{_uv}} run twine check dist/*"
    
    # Check if version already exists on PyPI (optional warning)
    VERSION=$(just _version)
    if {{_uv}} run python -c "import requests; r=requests.get('https://pypi.org/pypi/superego-mcp/$VERSION/json'); exit(0 if r.status_code==404 else 1)" >/dev/null 2>&1; then
        just _info "Version $VERSION not found on PyPI (good to publish)"
    else
        just _warn "Version $VERSION may already exist on PyPI"
    fi
    
    just _success "PyPI publishing validation complete!"

# Clean build for PyPI (ensures fresh distributions)
[group: 'publish']
pypi-build: clean
    #!/usr/bin/env bash
    just _info "Building fresh distributions for PyPI..."
    just _run "Building wheel and source distribution" "{{_uv}} run python -m build"
    just _run "Validating distributions" "{{_uv}} run twine check dist/*"
    
    # Show what was built
    echo ""
    just _info "Built distributions:"
    ls -la dist/
    just _success "PyPI build complete!"

# Publish to TestPyPI for testing
[group: 'publish']
pypi-test: pypi-build
    #!/usr/bin/env bash
    just _info "Publishing to TestPyPI..."
    
    if ! grep -q "testpypi" ~/.pypirc; then
        just _error "credentials" "TestPyPI configuration not found in ~/.pypirc"
    fi
    
    just _run "Uploading to TestPyPI" "{{_uv}} run twine upload --repository testpypi dist/*"
    
    VERSION=$(just _version)
    echo ""
    just _success "Published to TestPyPI!"
    just _info "Test installation with:"
    echo "  {{_uv}} pip install --index-url https://test.pypi.org/simple/ superego-mcp==$VERSION"

# Publish to PyPI (production)
[group: 'publish']
pypi-publish: pypi-check
    #!/usr/bin/env bash
    VERSION=$(just _version)
    PACKAGE_NAME="superego-mcp"
    
    echo "🚀 Ready to publish $PACKAGE_NAME version $VERSION to PyPI"
    echo ""
    echo "This will:"
    echo "  - Upload to the official PyPI repository"
    echo "  - Make the package publicly available"
    echo "  - Create git tag v$VERSION"
    echo ""
    
    # Interactive confirmation
    read -p "Continue with PyPI publish? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Publish cancelled"
        exit 1
    fi
    
    just _run "Uploading to PyPI" "{{_uv}} run twine upload dist/*"
    
    # Create git tag after successful upload
    if git tag -a "v$VERSION" -m "Release version $VERSION"; then
        just _run "Pushing git tag" "git push origin v$VERSION"
        just _success "Git tag v$VERSION created and pushed"
    else
        just _warn "Failed to create git tag (may already exist)"
    fi
    
    echo ""
    just _success "Successfully published $PACKAGE_NAME $VERSION to PyPI!"
    just _info "Package available at: https://pypi.org/project/$PACKAGE_NAME/$VERSION/"
    just _info "Install with: pip install $PACKAGE_NAME"

# Complete release workflow
[group: 'publish']
pypi-release: check pypi-publish
    #!/usr/bin/env bash
    VERSION=$(just _version)
    just _success "Release $VERSION completed successfully!"
    echo ""
    echo "📦 Package: https://pypi.org/project/superego-mcp/$VERSION/"
    echo "🏷️  Git tag: v$VERSION"
    echo "💾 Install: pip install superego-mcp"

# Show PyPI publishing status
[group: 'publish']
pypi-status:
    #!/usr/bin/env bash
    just _info "PyPI Publishing Status"
    echo "======================="
    echo ""
    
    VERSION=$(just _version)
    echo "📦 Current version: $VERSION"
    
    # Check twine
    if command -v {{_uv}} run twine >/dev/null 2>&1; then
        echo "✅ twine: Available"
    else
        echo "❌ twine: Not found (run: {{_uv}} add --dev twine)"
    fi
    
    # Check .pypirc
    if [ -f ~/.pypirc ]; then
        echo "✅ credentials: ~/.pypirc exists"
        if grep -q "pypi" ~/.pypirc; then
            echo "  - PyPI configuration found"
        fi
        if grep -q "testpypi" ~/.pypirc; then
            echo "  - TestPyPI configuration found"
        fi
    else
        echo "❌ credentials: ~/.pypirc not found"
    fi
    
    # Check distributions
    if [ -d "dist" ] && [ -n "$(ls -A dist/ 2>/dev/null)" ]; then
        echo "✅ distributions: Available in dist/"
        ls -la dist/
    else
        echo "❌ distributions: None found (run: just pypi-build)"
    fi
    
    # Check if published
    echo ""
    echo "🔍 Checking PyPI status..."
    if {{_uv}} run python -c "import requests; r=requests.get('https://pypi.org/pypi/superego-mcp/json'); print('✅ Package exists on PyPI') if r.status_code==200 else print('📦 Package not yet on PyPI')" 2>/dev/null; then
        :
    else
        echo "❓ Unable to check PyPI status"
    fi