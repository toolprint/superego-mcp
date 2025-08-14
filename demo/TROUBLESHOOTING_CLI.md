# Troubleshooting Guide for CLI Inference

This guide helps you diagnose and fix common issues when using Claude Code's CLI inference with Superego MCP.

## Table of Contents

1. [Diagnostic Checklist](#diagnostic-checklist)
2. [Common Issues and Solutions](#common-issues-and-solutions)
3. [Performance Optimization](#performance-optimization)
4. [Debug Mode and Logging](#debug-mode-and-logging)
5. [CLI Response Debugging](#cli-response-debugging)
6. [Fallback Configuration](#fallback-configuration)
7. [Advanced Troubleshooting](#advanced-troubleshooting)

## Diagnostic Checklist

Run through this checklist first to identify common problems:

```bash
# 1. Check Claude CLI is installed
which claude || echo "❌ Claude CLI not found in PATH"

# 2. Verify CLI version
claude --version || echo "❌ Cannot get Claude version"

# 3. Test API key
echo $ANTHROPIC_API_KEY | grep -q "sk-ant" && echo "✅ API key set" || echo "❌ API key not set"

# 4. Test basic CLI functionality
claude -p non-interactive "Say OK" 2>&1 | grep -q "OK" && echo "✅ CLI works" || echo "❌ CLI test failed"

# 5. Test JSON mode
claude -p non-interactive --format json "Return {\"status\": \"ok\"}" 2>&1 | jq . && echo "✅ JSON mode works" || echo "❌ JSON mode failed"

# 6. Check server is running
curl -s http://localhost:8000/health | jq . || echo "❌ Server not responding"

# 7. Test inference endpoint
curl -s -X POST http://localhost:8000/test-inference | jq . || echo "❌ Inference test failed"
```

## Common Issues and Solutions

### Issue 1: "Claude CLI not found"

**Error Messages:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'claude'
Error: claude_cli provider failed: Command 'claude' not found
```

**Root Causes:**
- Claude CLI not installed
- Claude not in system PATH
- Different installation location

**Solutions:**

1. **Install Claude CLI:**
   ```bash
   # macOS
   brew install claude
   
   # Linux
   curl -fsSL https://claude.ai/install.sh | sh
   
   # Manual download
   wget https://github.com/anthropics/claude-cli/releases/latest/download/claude-linux-amd64
   chmod +x claude-linux-amd64
   sudo mv claude-linux-amd64 /usr/local/bin/claude
   ```

2. **Add to PATH:**
   ```bash
   # Find where claude is installed
   find / -name claude 2>/dev/null
   
   # Add to PATH (replace with actual path)
   export PATH="$PATH:/opt/claude/bin"
   
   # Make permanent
   echo 'export PATH="$PATH:/opt/claude/bin"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Use absolute path in config:**
   ```yaml
   cli_providers:
     - name: "claude_cli"
       command: "/usr/local/bin/claude"  # Use full path
   ```

### Issue 2: "API Key Issues"

**Error Messages:**
```
Error: Missing API key. Set ANTHROPIC_API_KEY environment variable
Authentication failed: Invalid API key
Rate limit exceeded for API key
```

**Solutions:**

1. **Set API key correctly:**
   ```bash
   # Set for current session
   export ANTHROPIC_API_KEY="sk-ant-api03-..."
   
   # Verify it's set
   echo $ANTHROPIC_API_KEY
   
   # Add to shell profile for persistence
   echo 'export ANTHROPIC_API_KEY="sk-ant-api03-..."' >> ~/.bashrc
   source ~/.bashrc
   ```

2. **Check API key validity:**
   ```bash
   # Test API key directly
   curl -H "x-api-key: $ANTHROPIC_API_KEY" \
        -H "anthropic-version: 2023-06-01" \
        -H "content-type: application/json" \
        -X POST https://api.anthropic.com/v1/messages \
        -d '{"model": "claude-3-sonnet-20240229", 
             "max_tokens": 10,
             "messages": [{"role": "user", "content": "Hi"}]}'
   ```

3. **Use different environment variable:**
   ```yaml
   cli_providers:
     - name: "claude_cli"
       api_key_env_var: "MY_CLAUDE_KEY"  # Custom env var
   ```

### Issue 3: "Timeout Errors"

**Error Messages:**
```
TimeoutError: CLI inference timed out after 15 seconds
Error: Request timeout waiting for Claude response
Inference request exceeded timeout_seconds
```

**Solutions:**

1. **Increase timeout values:**
   ```yaml
   inference:
     timeout_seconds: 30  # Increase global timeout
     
     cli_providers:
       - name: "claude_cli"
         timeout_seconds: 25  # Provider-specific timeout
   ```

2. **Optimize prompts for faster responses:**
   ```yaml
   system_prompt: |
     You are a security evaluator. Be concise.
     Respond with JSON only, no explanations outside JSON.
     
     Format: {"decision": "allow/deny", "confidence": 0-1, "reasoning": "brief", "risk_factors": []}
   ```

3. **Check network latency:**
   ```bash
   # Time a simple request
   time claude -p non-interactive "Say hi"
   
   # If > 5 seconds, you have network issues
   ```

### Issue 4: "JSON Parsing Errors"

**Error Messages:**
```
JSONDecodeError: Expecting property name enclosed in double quotes
Failed to parse CLI response as JSON
Invalid JSON in Claude response: ...
```

**Common Causes:**
- Claude returning explanation text before/after JSON
- Malformed JSON structure
- Non-JSON responses

**Solutions:**

1. **Improve system prompt:**
   ```yaml
   system_prompt: |
     CRITICAL: Respond with valid JSON only. No text before or after the JSON.
     
     Example response:
     {"decision": "allow", "confidence": 0.9, "reasoning": "Safe operation", "risk_factors": []}
     
     DO NOT include any explanation outside the JSON structure.
   ```

2. **Enable JSON extraction:**
   ```yaml
   cli_providers:
     - name: "claude_cli"
       parse_json: true
       json_extraction_pattern: '^\s*\{[\s\S]*\}\s*$'
       # Extracts JSON even if there's whitespace
   ```

3. **Add response validation:**
   ```python
   # In your configuration or code
   def validate_claude_response(response_text):
       # Try to extract JSON from response
       import re
       json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
       if json_match:
           return json.loads(json_match.group())
       raise ValueError("No valid JSON found in response")
   ```

### Issue 5: "Inconsistent Responses"

**Symptoms:**
- Same request gets different decisions
- Confidence scores vary widely
- Reasoning doesn't match decision

**Solutions:**

1. **Set temperature to 0:**
   ```yaml
   cli_providers:
     - name: "claude_cli"
       args: ["-p", "non-interactive", "--format", "json", "--temperature", "0"]
   ```

2. **Add explicit decision criteria:**
   ```yaml
   system_prompt: |
     Decision criteria (in order):
     1. If path contains /etc, /sys, /root -> DENY
     2. If tool is read_file and path is in project -> ALLOW
     3. If tool modifies files outside project -> DENY
     4. Otherwise -> Evaluate based on risk
   ```

3. **Enable response caching:**
   ```yaml
   performance:
     caching:
       response_cache_ttl: 600  # Cache for 10 minutes
   ```

## Performance Optimization

### Reducing Latency

1. **Batch similar requests:**
   ```yaml
   # Instead of individual evaluations
   inference:
     batch_inference: true
     batch_timeout_ms: 100
   ```

2. **Pre-warm the CLI:**
   ```bash
   # Add to startup script
   claude -p non-interactive "Ready" > /dev/null 2>&1
   ```

3. **Use connection pooling:**
   ```yaml
   performance:
     connection_pooling:
       max_connections: 10
       keepalive_timeout: 60
   ```

### Memory Usage

1. **Limit prompt size:**
   ```yaml
   cli_providers:
     - name: "claude_cli"
       max_prompt_length: 1000  # Truncate long prompts
   ```

2. **Enable response streaming:**
   ```yaml
   cli_providers:
     - name: "claude_cli"
       stream_response: false  # Disable for lower memory
   ```

## Debug Mode and Logging

### Enable Verbose Logging

1. **Server-level debugging:**
   ```bash
   # Start server with debug logging
   python -m superego_mcp.main --config claude-code-demo.yaml --log-level DEBUG
   ```

2. **Configuration-based debugging:**
   ```yaml
   # In claude-code-demo.yaml
   log_level: "DEBUG"
   demo:
     verbose_inference_logs: true
     log_cli_commands: true
     log_cli_responses: true
   ```

3. **Trace specific requests:**
   ```bash
   # Enable request tracing
   export SUPEREGO_TRACE=true
   export SUPEREGO_TRACE_FILE=/tmp/superego_trace.log
   ```

### Analyzing Debug Logs

Look for these key patterns:

```bash
# Check CLI command construction
grep "Executing CLI command" /tmp/superego.log

# View actual CLI commands
grep "claude -p non-interactive" /tmp/superego.log

# Check response parsing
grep "CLI raw response" /tmp/superego.log

# Find parsing errors
grep -E "(JSONDecodeError|Failed to parse)" /tmp/superego.log
```

## CLI Response Debugging

### Test CLI Manually

Replicate what Superego does:

```bash
# 1. Create a test prompt file
cat > test_prompt.txt << 'EOF'
You are a security evaluator. Evaluate this request:
Tool: read_file
Path: /etc/passwd

Respond with JSON only:
{"decision": "allow/deny", "confidence": 0-1, "reasoning": "...", "risk_factors": []}
EOF

# 2. Test with Claude CLI
claude -p non-interactive --format json < test_prompt.txt

# 3. Test with exact arguments from config
claude -p non-interactive --format json --temperature 0 < test_prompt.txt
```

### Common Response Issues

1. **Extra text in response:**
   ```
   I'll evaluate this security request.
   
   {"decision": "deny", ...}
   
   This operation is risky because...
   ```
   
   **Fix:** Strengthen the "JSON only" instruction in prompt

2. **Incomplete JSON:**
   ```json
   {
     "decision": "allow",
     "confidence": 0.8,
     "reasoning": "This seems safe because
   ```
   
   **Fix:** Add max_tokens limit or timeout

3. **Wrong JSON structure:**
   ```json
   {
     "allow": true,  // Wrong key
     "score": 80,    // Wrong type
   }
   ```
   
   **Fix:** Provide exact example in system prompt

## Fallback Configuration

### Configure Fallback Behavior

1. **Default to deny on errors:**
   ```yaml
   inference:
     error_behavior: "deny"  # or "allow" or "fallback"
     
     fallback_rules:
       - tool_name: "read_file"
         default: "allow"
       - tool_name: "write_file"
         default: "deny"
   ```

2. **Add backup provider:**
   ```yaml
   inference:
     provider_preference:
       - "claude_cli"
       - "openai_cli"  # Fallback provider
     
     cli_providers:
       - name: "openai_cli"
         enabled: true
         command: "openai"
         # ... OpenAI configuration
   ```

3. **Circuit breaker pattern:**
   ```yaml
   inference:
     circuit_breaker:
       enabled: true
       failure_threshold: 3
       timeout_seconds: 60
       half_open_attempts: 1
   ```

## Advanced Troubleshooting

### System Resource Issues

1. **Check system resources:**
   ```bash
   # CPU usage
   top -n 1 | grep claude
   
   # Memory usage
   ps aux | grep superego
   
   # Open file descriptors
   lsof -p $(pgrep -f superego) | wc -l
   ```

2. **Resource limits:**
   ```bash
   # Increase limits if needed
   ulimit -n 4096  # File descriptors
   ulimit -u 2048  # Processes
   ```

### Network Diagnostics

1. **Test API connectivity:**
   ```bash
   # DNS resolution
   nslookup api.anthropic.com
   
   # Network path
   traceroute api.anthropic.com
   
   # SSL/TLS test
   openssl s_client -connect api.anthropic.com:443
   ```

2. **Proxy configuration:**
   ```bash
   # If behind proxy
   export HTTP_PROXY=http://proxy:8080
   export HTTPS_PROXY=http://proxy:8080
   export NO_PROXY=localhost,127.0.0.1
   ```

### Creating Diagnostic Report

Generate a complete diagnostic report:

```bash
#!/bin/bash
# save as diagnose.sh

echo "=== Superego MCP CLI Diagnostic Report ==="
echo "Date: $(date)"
echo

echo "=== Environment ==="
echo "OS: $(uname -a)"
echo "Python: $(python --version)"
echo "Claude CLI: $(claude --version 2>&1)"
echo "API Key Set: $([ -n "$ANTHROPIC_API_KEY" ] && echo "Yes" || echo "No")"
echo

echo "=== Claude CLI Test ==="
claude -p non-interactive "Return OK" 2>&1

echo -e "\n=== JSON Mode Test ==="
claude -p non-interactive --format json '{"test": "ok"}' 2>&1

echo -e "\n=== Server Status ==="
curl -s http://localhost:8000/health | jq . 2>&1

echo -e "\n=== Recent Errors ==="
grep -i error /tmp/superego*.log 2>/dev/null | tail -20

echo -e "\n=== System Resources ==="
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')"
echo "Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2}')"
```

Save and run:
```bash
chmod +x diagnose.sh
./diagnose.sh > diagnostic_report.txt
```

## Getting Help

If you're still experiencing issues:

1. **Check the logs** with debug mode enabled
2. **Run the diagnostic script** above
3. **Test CLI commands manually** to isolate the issue
4. **Review your configuration** for typos or invalid settings
5. **Check GitHub issues** for similar problems
6. **Join the community Discord** for real-time help

Remember: Most CLI inference issues are related to:
- PATH configuration (Claude not found)
- API key setup (authentication)
- Network connectivity (timeouts)
- Response format (JSON parsing)

Address these four areas first, and you'll resolve 90% of issues.