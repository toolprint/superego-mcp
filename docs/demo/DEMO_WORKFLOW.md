# Superego MCP Demo Workflow

This demo shows the complete integration between Claude Code hooks and Superego MCP server, demonstrating real-world security scenarios.

## Demo Setup

### 1. Start Superego MCP Server

```bash
# Terminal 1: Start Superego MCP
cd /path/to/superego-mcp
just run

# You should see:
# INFO: Starting Superego MCP Server on http://localhost:8000
# INFO: Loading rules from config/rules.yaml
# INFO: Hot reload enabled - watching for config changes
```

### 2. Configure Demo Rules

Create `config/demo-rules.yaml`:

```yaml
rules:
  # Scenario 1: Block dangerous system commands
  - id: "block-rm-rf"
    priority: 1
    conditions:
      tool_name: "Bash"
      parameters:
        command: "*rm -rf*"
    action: "DENY"
    reason: "Destructive command blocked for safety"
  
  # Scenario 2: Require AI evaluation for file modifications
  - id: "evaluate-file-writes"
    priority: 10
    conditions:
      tool_name: ["Write", "Edit", "MultiEdit"]
      parameters:
        file_path: "*.py"
    action: "SAMPLE"
    sampling_guidance: |
      Evaluate if this Python file modification is:
      1. Safe (no security vulnerabilities introduced)
      2. Necessary for the task
      3. Following best practices
  
  # Scenario 3: Modify parameters for safety
  - id: "sanitize-web-requests"
    priority: 20
    conditions:
      tool_name: "WebFetch"
      parameters:
        url: "*"
    action: "MODIFY"
    modifications:
      add_headers:
        "User-Agent": "Superego-MCP-Security-Scanner/1.0"
      validate_ssl: true
  
  # Scenario 4: Time-based restrictions
  - id: "restrict-after-hours"
    priority: 30
    conditions:
      tool_name: ["Bash", "Execute"]
      time_range: "18:00-08:00"  # After 6 PM, before 8 AM
    action: "DENY"
    reason: "Code execution restricted during off-hours"
  
  # Default: Allow read operations
  - id: "allow-safe-reads"
    priority: 100
    conditions:
      tool_name: ["Read", "LS", "Grep", "Glob"]
    action: "ALLOW"
```

### 3. Install and Configure Hooks

```bash
# Terminal 2: Set up Claude Code hooks
cd ~/.claude/hooks

# Copy hook scripts from demo
cp /path/to/superego-mcp/docs/demo/hooks/* .

# Enable hooks
claude hooks enable superego-security-check
claude hooks enable superego-audit-log

# Verify installation
claude hooks list
# ✓ superego-security-check (PreToolUse) - Enabled
# ✓ superego-audit-log (PostToolUse) - Enabled
```

## Demo Scenarios

### Scenario 1: Blocking Dangerous Commands

```python
# demo-scenario-1.py
"""Demonstrate blocking dangerous system commands"""

# This will be ALLOWED - safe command
print("Listing files...")
# Claude Code tool: Bash("ls -la")

# This will be BLOCKED - dangerous command
print("Attempting to remove files...")
# Claude Code tool: Bash("rm -rf /tmp/test")
# Expected: Security Policy: Destructive command blocked for safety

# This will be ALLOWED - safe removal with specific file
print("Removing specific file...")
# Claude Code tool: Bash("rm /tmp/single-file.txt")
```

**Run the demo:**
```bash
claude run demo-scenario-1.py
```

**Expected Output:**
```
Listing files...
[File listing output]

Attempting to remove files...
❌ Tool call blocked by security policy: Destructive command blocked for safety

Removing specific file...
[Command executes normally]
```

### Scenario 2: AI Evaluation for Code Changes

```python
# demo-scenario-2.py
"""Demonstrate AI evaluation of file modifications"""

code_content = '''
import os
import subprocess

def process_user_input(user_input):
    # This will trigger AI evaluation
    # AI should detect command injection vulnerability
    result = subprocess.run(f"echo {user_input}", shell=True)
    return result.stdout
'''

# This will trigger AI EVALUATION
print("Writing potentially unsafe code...")
# Claude Code tool: Write("unsafe_code.py", code_content)
# Expected: AI evaluates and likely blocks due to security risk

safe_code = '''
import subprocess
import shlex

def process_user_input(user_input):
    # Safe version with proper escaping
    cmd = ["echo", shlex.quote(user_input)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout
'''

# This should be ALLOWED after AI evaluation
print("Writing safe code...")
# Claude Code tool: Write("safe_code.py", safe_code)
```

**Monitor AI Evaluation:**
```bash
# Terminal 3: Watch Superego logs
tail -f logs/superego.log | grep -E "SAMPLE|AI_DECISION"
```

### Scenario 3: Parameter Modification

```python
# demo-scenario-3.py
"""Demonstrate parameter modification for safety"""

# Original request
print("Fetching web content...")
# Claude Code tool: WebFetch(url="http://example.com/api/data")

# Hook modifies this to:
# - Add security headers
# - Ensure SSL validation
# - Add User-Agent for identification
```

**View Modified Request:**
```bash
# Check audit log to see parameter modifications
curl http://localhost:8000/api/v1/audit/recent | jq '.[] | select(.tool_name=="WebFetch")'
```

### Scenario 4: Time-Based Restrictions

```python
# demo-scenario-4.py
"""Demonstrate time-based access control"""

from datetime import datetime

current_hour = datetime.now().hour
print(f"Current hour: {current_hour}")

# This will be DENIED if run after 6 PM or before 8 AM
print("Attempting code execution...")
# Claude Code tool: Bash("python script.py")

# Read operations always allowed
print("Reading files (always allowed)...")
# Claude Code tool: Read("README.md")
```

## Monitoring and Debugging

### 1. Real-Time Monitoring Dashboard

```bash
# Terminal 4: Start monitoring dashboard
cd /path/to/superego-mcp
python docs/demo/monitor.py

# Opens browser with real-time view of:
# - Tool call requests
# - Security decisions
# - AI evaluation results
# - Performance metrics
```

### 2. Debug Mode

Enable detailed logging for troubleshooting:

```bash
# In ~/.claude/hooks/config.yaml
hooks:
  - name: "superego-security-check"
    debug: true
    log_level: "DEBUG"
```

### 3. Test Specific Rules

```bash
# Test rule matching without executing tools
claude hooks dry-run "Bash" '{"command": "rm -rf /"}'

# Output:
# Rule matched: block-rm-rf
# Action: DENY
# Reason: Destructive command blocked for safety
```

## Demo Metrics

After running the demo scenarios, view aggregated metrics:

```bash
# Get security metrics
curl http://localhost:8000/api/v1/metrics

# Example output:
{
  "total_requests": 25,
  "decisions": {
    "ALLOW": 15,
    "DENY": 5,
    "SAMPLE": 4,
    "MODIFY": 1
  },
  "average_latency_ms": 23,
  "ai_evaluations": {
    "total": 4,
    "approved": 2,
    "denied": 2
  },
  "top_blocked_tools": [
    {"tool": "Bash", "count": 3},
    {"tool": "Write", "count": 2}
  ]
}
```

## Advanced Demo: Multi-Agent Scenario

```python
# demo-multi-agent.py
"""Demonstrate different security policies for different agents"""

# Configure agent-specific rules
agent_rules = {
  "developer-agent": {
    "allowed_tools": ["*"],
    "restricted_paths": ["/etc", "/usr/bin"]
  },
  "analyst-agent": {
    "allowed_tools": ["Read", "Grep", "LS"],
    "restricted_paths": ["*"]
  },
  "admin-agent": {
    "allowed_tools": ["*"],
    "restricted_paths": [],
    "require_mfa": true
  }
}

# Simulate different agents
for agent_id, permissions in agent_rules.items():
    print(f"\n--- Testing as {agent_id} ---")
    # Set agent context
    os.environ["CLAUDE_AGENT_ID"] = agent_id
    
    # Try various operations
    # Each will be evaluated based on agent-specific rules
```

## Troubleshooting Common Issues

### Issue 1: Hooks Not Intercepting

```bash
# Verify hook is catching tool patterns
claude hooks debug --pattern "Bash"

# Check hook script syntax
node -c ~/.claude/hooks/superego-check.js
```

### Issue 2: Superego Connection Failed

```bash
# Test direct connection
curl -v http://localhost:8000/health

# Check firewall rules
sudo lsof -i :8000
```

### Issue 3: AI Evaluation Timeout

```yaml
# Increase timeout in rules
sampling_config:
  timeout_ms: 10000  # 10 seconds
  model: "gpt-4"
  temperature: 0.3
```

## Performance Testing

```bash
# Run performance benchmark
python docs/demo/benchmark.py

# Results show:
# - Average latency per tool call
# - Hook overhead
# - AI evaluation time
# - Rule matching performance
```

## Demo Cleanup

```bash
# Disable hooks after demo
claude hooks disable superego-security-check
claude hooks disable superego-audit-log

# Stop Superego server
# Press Ctrl+C in Terminal 1

# Clean up demo files
rm -f demo-scenario-*.py
rm -f unsafe_code.py safe_code.py
```

## Key Takeaways

1. **Defense in Depth**: Multiple layers of security checks
2. **Flexible Rules**: From simple patterns to AI evaluation
3. **Real-Time Updates**: Hot reload for instant policy changes
4. **Comprehensive Audit**: Every decision is logged
5. **Performance**: Minimal overhead (~20-50ms per tool call)

## Next Steps

1. Customize rules for your specific use case
2. Integrate with your security infrastructure
3. Set up alerts for suspicious activity
4. Export audit logs to SIEM systems
5. Create agent-specific security policies