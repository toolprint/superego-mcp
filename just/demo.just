# demo.just - Demo and example workflows

# Demo setup - Check dependencies and setup
[group: 'demo']
demo-setup:
    @just _run "Setting up demo environment" "{{_uv}} sync --extra demo"
    @just _info "Checking FastAgent availability..."
    @{{_uv}} run --extra demo fast-agent --version || echo "FastAgent not available - install with 'uv sync --extra demo'"
    @just _success "Demo setup complete!"

# Demo verify - Check demo readiness  
[group: 'demo']
demo-verify:
    @just _info "Verifying demo readiness..."
    cd demo && python setup_verification_cli.py

# Run legacy HTTP client demo
[group: 'demo']
demo:
    @just _info "Starting demo with legacy HTTP client..."
    {{_uv}} run --extra demo python -m demo.client

# FastAgent Demo - Simple CLI-based demo (recommended)
[group: 'demo']
demo-fastagent-simple:
    @just _info "Starting FastAgent Simple Demo..."
    @just _info "This will run security scenarios and interactive mode"
    cd demo && {{_uv}} run --extra demo python simple_fastagent_demo.py

# FastAgent Demo - Full integration demo
[group: 'demo']
demo-fastagent-full:
    @just _info "Starting FastAgent Full Demo..."
    @just _info "This requires the complete fast-agent-mcp package"
    cd demo && {{_uv}} run --extra demo python fastagent_demo.py

# Demo Scenarios - Run just the security scenarios
[group: 'demo']
demo-scenarios:
    @just _info "Running security scenarios demonstration..."
    cd demo && {{_uv}} run --extra demo python security_scenarios.py

# Interactive FastAgent Demo
[group: 'demo']
demo-interactive:
    @just _info "Starting interactive FastAgent session..."
    @just _info "Make sure Superego MCP server is running first!"
    cd demo && {{_uv}} run --extra demo fast-agent go demo_agent.py --config fastagent.config.yaml

# Demo All - Run complete demo suite
[group: 'demo']
demo-all: demo-scenarios demo-fastagent-simple
    @just _success "Complete demo suite finished!"