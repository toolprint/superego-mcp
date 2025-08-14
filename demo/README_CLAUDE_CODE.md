# Superego MCP - Claude Code Demo

Welcome to the Superego MCP demo optimized for Claude Code's CLI inference capabilities!

## 🚀 Quick Start (2 minutes)

```bash
# 1. Navigate to demo directory
cd superego-mcp/demo

# 2. Run the quick start script
./quick_start_cli.sh

# 3. Follow the interactive prompts
```

That's it! The script will check all prerequisites and start everything for you.

## 📋 Manual Setup

If you prefer to set things up manually:

### Prerequisites

1. **Claude CLI** installed and in PATH
   ```bash
   claude --version
   ```

2. **ANTHROPIC_API_KEY** environment variable set
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

3. **Python 3.10+** installed
   ```bash
   python --version
   ```

### Starting the Demo

1. **Start the server**:
   ```bash
   python -m superego_mcp.main --config demo/claude-code-demo.yaml
   ```

2. **Run the demo** (in another terminal):
   ```bash
   python claude_code_demo.py
   ```

## 🎯 What This Demo Shows

The demo showcases how Superego MCP uses Claude CLI to make intelligent security decisions:

- **File Operations**: Safe vs. dangerous file access
- **System Commands**: Allowed vs. blocked commands
- **Network Requests**: Trusted vs. suspicious URLs
- **Code Execution**: Safe vs. malicious code

## 📚 Documentation

- **[Setup Guide](CLAUDE_CODE_SETUP.md)** - Detailed setup instructions
- **[CLI Scenarios](CLI_INFERENCE_SCENARIOS.md)** - Example security evaluations
- **[Troubleshooting](TROUBLESHOOTING_CLI.md)** - Common issues and solutions

## 🔧 Configuration

The demo uses two main configuration files:

1. **claude-code-demo.yaml** - Server configuration with CLI inference
2. **config/rules-cli-demo.yaml** - Security rules with CLI evaluation

Key features:
- CLI-only inference (no MCP sampling)
- Optimized prompts for fast responses
- Educational rule examples
- Comprehensive logging

## 💡 Demo Modes

The demo supports two modes:

### Demo Mode
Runs through pre-defined scenarios showing various security evaluations:
```bash
python claude_code_demo.py
# Select "demo" when prompted
```

### Interactive Mode
Test your own tool requests:
```bash
python claude_code_demo.py
# Select "interactive" when prompted
```

Example requests:
```
Tool name: read_file
Parameters: {"path": "/etc/passwd"}

Tool name: execute_command
Parameters: {"command": "git clone https://github.com/user/repo"}

Tool name: write_file
Parameters: {"path": "/tmp/test.txt", "content": "Hello world"}
```

## 🔍 Verification

Check your setup at any time:
```bash
python setup_verification_cli.py
```

This verifies:
- Claude CLI installation
- API key configuration
- Server connectivity
- Inference functionality

## 🛠️ Troubleshooting Quick Tips

1. **"Claude CLI not found"**
   - Install: `brew install claude` (macOS)
   - Add to PATH: `export PATH="$PATH:/path/to/claude"`

2. **"API key not set"**
   - Set: `export ANTHROPIC_API_KEY="sk-ant-..."`
   - Add to `~/.bashrc` for persistence

3. **"Server not responding"**
   - Check if running: `curl http://localhost:8000/health`
   - Check logs: `tail -f demo/logs/server.log`

4. **"Timeout errors"**
   - Increase timeout in `claude-code-demo.yaml`
   - Check network connection

## 📊 Understanding Results

Each security evaluation shows:

- **Decision**: Allow or Deny
- **Confidence**: How certain the evaluation is (0.0-1.0)
- **Reasoning**: Why the decision was made
- **Risk Factors**: Identified security concerns
- **Rule**: Which security rule was applied
- **Provider**: Confirms "claude_cli" was used

## 🎓 Learning More

This demo is designed to be educational. Explore the configuration files and modify rules to see how different scenarios are evaluated.

Key files to explore:
- `claude-code-demo.yaml` - See how CLI inference is configured
- `config/rules-cli-demo.yaml` - Learn about security rule patterns
- `claude_code_demo.py` - Understand the demo implementation

## 🤝 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/superego-mcp/issues)
- **Documentation**: [Full Documentation](../README.md)
- **Community**: [Discord Server](https://discord.gg/your-server)

Happy exploring! The goal is to show how AI can make intelligent security decisions to protect your development environment while enabling productive work.