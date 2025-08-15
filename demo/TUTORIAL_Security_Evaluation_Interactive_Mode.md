# Understanding Superego MCP Security Evaluation in Interactive Mode

## Table of Contents
1. [Introduction](#introduction)
2. [How Security Evaluation Works](#how-security-evaluation-works)
3. [Security Rule Categories](#security-rule-categories)
4. [Triggering MCP Tool Calls](#triggering-mcp-tool-calls)
5. [Practical Examples](#practical-examples)
6. [Understanding Security Decisions](#understanding-security-decisions)
7. [Viewing Security Logs](#viewing-security-logs)
8. [Demo Scenarios to Try](#demo-scenarios-to-try)
9. [Current Limitations](#current-limitations)
10. [Troubleshooting](#troubleshooting)

## Introduction

The Superego MCP server acts as a security layer between AI agents and tool execution. When you interact with FastAgent in interactive mode, every tool request is intercepted and evaluated according to configurable security rules before execution.

### Key Concepts

- **MCP (Model Context Protocol)**: A protocol for AI-tool communication
- **FastAgent**: The AI agent that processes your requests
- **Superego**: The security layer that evaluates tool requests
- **Security Rules**: Configurable patterns that determine allow/deny/evaluate decisions

## How Security Evaluation Works

When you make a request in interactive mode, the following process occurs:

```
User Input → FastAgent → Tool Request → Superego Evaluation → Decision → Execution/Block
```

### The Evaluation Flow

1. **User makes a request** (e.g., "Read the file config.yaml")
2. **FastAgent interprets** and generates a tool call (e.g., `read_file`)
3. **Superego intercepts** the tool request before execution
4. **Security rules are evaluated** in priority order:
   - Priority 5: Dangerous operations (highest priority)
   - Priority 10: Safe operations
   - Priority 15: Complex operations requiring evaluation
5. **Decision is made**: allow, deny, or sample (AI evaluation)
6. **Action is taken**: Tool executes or request is blocked

## Security Rule Categories

The demo configuration (`/demo/config/rules.yaml`) defines three main categories:

### 1. ALLOW (Automatically Approved)
Safe operations that pose minimal security risk:
- `read_file`: Reading file contents
- `list_files`: Listing directory contents
- `search_files`: Searching for files

### 2. DENY (Automatically Blocked)
Dangerous operations that are immediately rejected:
- Commands containing `sudo`
- Commands with `rm -rf`
- Access to sensitive files like `/etc/passwd` or `/etc/shadow`

### 3. SAMPLE (Should Require AI Evaluation)
Complex operations that need contextual evaluation:
- `write_file`: Creating or modifying files
- `execute_command`: Running system commands
- `fetch_url`: Making network requests

**⚠️ Current Issue**: Sample operations are currently auto-approved instead of triggering AI evaluation (line 97 in services.py maps `ToolAction.SAMPLE` to `"allow"`).

## Triggering MCP Tool Calls

To trigger MCP tool calls in interactive mode, you need to make requests that the AI agent will interpret as requiring tool usage. Here's how:

### Starting Interactive Mode

```bash
# Using Anthropic Claude
python simple_fastagent_demo.py --provider anthropic --interactive-only

# Using OpenAI GPT
python simple_fastagent_demo.py --provider openai --interactive-only
```

### Effective Prompt Patterns

1. **Direct File Operations**
   - "Read the file at [path]"
   - "Show me the contents of [file]"
   - "List all files in [directory]"

2. **System Commands**
   - "Run the command [command]"
   - "Execute [program] with these parameters"
   - "Check the system by running [command]"

3. **Network Operations**
   - "Fetch data from [URL]"
   - "Download the content at [website]"
   - "Make an API request to [endpoint]"

## Practical Examples

Here are specific prompts categorized by their expected security evaluation:

### Automatically Approved (Safe Operations)

```
Prompt: "Read the file /home/user/config.yaml"
Tool: read_file
Parameters: {"path": "/home/user/config.yaml"}
Expected: ✅ Allowed - Safe file reading operation
```

```
Prompt: "List all Python files in the current directory"
Tool: search_files
Parameters: {"pattern": "*.py", "directory": "."}
Expected: ✅ Allowed - Safe search operation
```

```
Prompt: "Show me what's in the README.md file"
Tool: read_file
Parameters: {"path": "README.md"}
Expected: ✅ Allowed - Safe file reading
```

### Automatically Denied (Dangerous Operations)

```
Prompt: "Delete the file /etc/passwd"
Tool: delete_file
Parameters: {"path": "/etc/passwd"}
Expected: ❌ Denied - Dangerous system file
```

```
Prompt: "Run sudo rm -rf /"
Tool: execute_command
Parameters: {"command": "sudo rm -rf /"}
Expected: ❌ Denied - Extremely dangerous command
```

```
Prompt: "Change permissions of /etc/shadow to 777"
Tool: change_permissions
Parameters: {"path": "/etc/shadow", "mode": "777"}
Expected: ❌ Denied - Security vulnerability
```

### Should Require Evaluation (Complex Operations)

**Note**: These currently auto-approve but should trigger AI evaluation.

```
Prompt: "Write a bash script to /tmp/cleanup.sh"
Tool: write_file
Parameters: {"path": "/tmp/cleanup.sh", "content": "#!/bin/bash\n..."}
Expected: 🤔 Should evaluate - File writing operation
Current: ✅ Auto-approved (incorrect behavior)
```

```
Prompt: "Fetch data from https://api.github.com/users/octocat"
Tool: fetch_url
Parameters: {"url": "https://api.github.com/users/octocat"}
Expected: 🤔 Should evaluate - External network access
Current: ✅ Auto-approved (incorrect behavior)
```

```
Prompt: "Execute the command 'python --version'"
Tool: execute_command
Parameters: {"command": "python --version"}
Expected: 🤔 Should evaluate - Command execution
Current: ✅ Auto-approved (incorrect behavior)
```

## Understanding Security Decisions

### Decision Structure

Each security decision contains:
- **action**: "allow" or "deny"
- **reason**: Explanation of the decision
- **rule_id**: Which rule was matched
- **confidence**: Confidence level (1.0 for rule-based, variable for AI)
- **processing_time_ms**: Time taken to evaluate

### Example Decision Log

```json
{
  "action": "deny",
  "reason": "Dangerous system operations blocked",
  "rule_id": "block_dangerous_system",
  "confidence": 1.0,
  "processing_time_ms": 2
}
```

## Viewing Security Logs

Security decisions are logged based on the configuration in `fastagent.config.anthropic.yaml`:

```yaml
logging:
  show_mcp_traffic: true       # Shows all MCP communication
  show_security_decisions: true # Shows security evaluation results
```

### Where to See Logs

1. **Console Output**: Real-time decisions appear in the terminal
2. **Log Level**: Set via `SUPEREGO_LOG_LEVEL=INFO` environment variable
3. **Log Format**: Timestamp - Component - Level - Message

### Example Log Output

```
2024-01-15 10:23:45 - superego.security - INFO - Evaluating request: read_file
2024-01-15 10:23:45 - superego.security - INFO - Rule matched: allow_safe_reads
2024-01-15 10:23:45 - superego.security - INFO - Decision: allow (Safe file reading operations)
```

## Demo Scenarios to Try

### Scenario 1: Safe File Operations
```bash
# In interactive mode, try:
"Please read the configuration file at ./config/rules.yaml"
"List all Python files in the demo directory"
"Search for files containing 'security' in their name"
```

### Scenario 2: Dangerous Operations (Will Be Blocked)
```bash
# These will be denied:
"Delete the system password file /etc/passwd"
"Run the command sudo shutdown -h now"
"Give everyone full access to /etc/shadow"
```

### Scenario 3: Complex Operations (Currently Auto-Approved)
```bash
# These should require evaluation but currently auto-approve:
"Create a Python script at /tmp/test.py that prints hello world"
"Fetch the latest weather data from api.weather.com"
"Run a Python command to list all environment variables"
```

### Scenario 4: Testing Rule Priority
```bash
# Test that dangerous patterns override tool names:
"Read the file /etc/passwd"  # Should be denied even though read_file is normally safe
```

## Current Limitations

### 1. Sample Actions Not Evaluated
The most significant limitation is that operations marked for AI evaluation (`sample`) are currently auto-approved:

```python
# In services.py line 97:
ToolAction.SAMPLE: "allow"  # Should trigger AI evaluation instead
```

This means complex operations that should be carefully evaluated are automatically allowed.

### 2. Limited Pattern Matching
Current rules use simple regex patterns. More complex conditions might require enhancement.

### 3. No Context Awareness
Rules don't consider:
- Previous operations in the session
- User identity or permissions
- Time-based restrictions

## Troubleshooting

### Common Issues and Solutions

1. **"API key not found" error**
   ```bash
   # Set your API key:
   export ANTHROPIC_API_KEY='your_key_here'
   # or
   export OPENAI_API_KEY='your_key_here'
   ```

2. **"MCP server connection failed"**
   - Check if Superego is properly installed: `uv sync`
   - Verify Python path: `which python`
   - Check logs for startup errors

3. **"Tool not recognized"**
   - Ensure your prompt clearly indicates the desired action
   - Be specific about file paths and operations
   - Try rephrasing with more explicit language

4. **Security decisions not visible**
   - Verify logging configuration shows both:
     - `show_mcp_traffic: true`
     - `show_security_decisions: true`
   - Check log level: `SUPEREGO_LOG_LEVEL=DEBUG` for more detail

### Testing Your Understanding

Try these exercises:

1. **Predict the outcome**: Before running each prompt, predict whether it will be allowed, denied, or should require evaluation.

2. **Modify rules**: Edit `/demo/config/rules.yaml` to add a new rule that blocks access to `/tmp/sensitive/`.

3. **Test edge cases**: What happens if you try to read a file that matches both an allow and deny pattern?

## Next Steps

1. **Fix the Sample Evaluation**: Modify the code to properly handle AI evaluation for complex operations.

2. **Add Custom Rules**: Create rules specific to your security requirements.

3. **Enhance Logging**: Add more detailed logging for security decisions.

4. **Build Context Awareness**: Implement session-based security policies.

Remember: Security is about layers. The Superego MCP server provides one important layer, but should be part of a comprehensive security strategy.