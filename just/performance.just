# performance.just - Performance testing and optimization

# Run performance tests
[group: 'performance']
test-performance:
    @just _run "Running performance tests" "{{_uv}} run pytest tests/test_performance_optimization.py -v"

# Run load tests
[group: 'performance']
load-test:
    @just _info "Running load tests..."
    @just _info "Make sure server is running with: just run-optimized"
    {{_uv}} run python tests/load_test_performance.py

# Run performance demo
[group: 'performance']
demo-performance:
    @just _info "Running performance optimization demo..."
    @just _info "Make sure server is running with: just run-optimized"
    {{_uv}} run python demo/performance_demo.py

# Start monitoring dashboard only
[group: 'performance']
monitor:
    @just _info "Starting monitoring dashboard on http://localhost:9090/dashboard"
    @just _info "Metrics available at http://localhost:9090/metrics"
    {{_uv}} run python -c "from superego_mcp.presentation.monitoring import MonitoringDashboard; import asyncio; d = MonitoringDashboard(None, None, None); asyncio.run(d.start()); input('Press Enter to stop...')"

# Multi-transport performance test
[group: 'performance']
test-multi-transport-perf:
    @just _run "Testing multi-transport performance" "{{_uv}} run python demo/multi_transport_demo.py --performance"

# Benchmark rule evaluation
[group: 'performance']
benchmark-rules:
    @just _info "Benchmarking rule evaluation performance..."
    {{_uv}} run python -m timeit -s "from superego_mcp.domain.models import ToolRequest; from superego_mcp.domain.security_policy import SecurityPolicyEngine; import asyncio; engine = SecurityPolicyEngine('config/rules.yaml'); request = ToolRequest(tool_name='ls', parameters={}, session_id='test', agent_id='test', cwd='/tmp')" "asyncio.run(engine.evaluate(request))"

# Profile server performance
[group: 'performance']
profile:
    @just _run "Profiling server performance" "{{_uv}} run python -m cProfile -o profile.stats -m superego_mcp.main_optimized"

# Analyze profile results
[group: 'performance']
profile-analyze:
    @just _info "Analyzing profile results..."
    {{_uv}} run python -m pstats profile.stats