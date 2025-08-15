# Configuration Directory Structure

This directory contains organized configuration files for the Superego MCP demo system.

## Directory Structure

```
config/
├── claude-code/          # Claude Code specific configurations
│   └── claude-hooks-config.json    # Hook configuration for Claude Code
├── fastagent/           # FastAgent framework configurations  
│   ├── fastagent.config.anthropic.yaml  # Anthropic API config
│   ├── fastagent.config.openai.yaml     # OpenAI API config
│   └── fastagent.secrets.yaml.example   # Secrets template
└── superego/            # Superego MCP security configurations
    ├── claude-code-demo.yaml       # Main demo server config
    ├── rules.yaml                  # Standard security rules
    └── rules-cli-demo.yaml         # CLI demo specific rules
```

## Configuration Files

### Claude Code Configurations (`claude-code/`)

- **claude-hooks-config.json**: Defines PreToolUse and PostToolUse hooks that intercept MCP tool calls for security evaluation

### FastAgent Configurations (`fastagent/`)

- **fastagent.config.anthropic.yaml**: Configuration for using Anthropic Claude models with FastAgent
- **fastagent.config.openai.yaml**: Configuration for using OpenAI models with FastAgent  
- **fastagent.secrets.yaml.example**: Template for API keys and secrets (copy to `fastagent.secrets.yaml`)

### Superego Configurations (`superego/`)

- **claude-code-demo.yaml**: Main configuration for running the Superego MCP server in demo mode
- **rules.yaml**: Standard set of security rules for tool evaluation
- **rules-cli-demo.yaml**: Extended rules specifically designed for CLI inference demonstrations

## Backward Compatibility

Symlinks are maintained at the demo root level for backward compatibility:
- `claude-code-demo.yaml` → `config/superego/claude-code-demo.yaml`
- `fastagent.config.*.yaml` → `config/fastagent/fastagent.config.*.yaml`

## Usage

### Starting the Superego MCP Server
```bash
python -m superego_mcp.main --config config/superego/claude-code-demo.yaml
```

### Setting up Claude Code Hooks
```bash
./setup_claude_hooks.sh
```

### Running FastAgent Demos
```bash
# With Anthropic
python fastagent_demo.py --config config/fastagent/fastagent.config.anthropic.yaml

# With OpenAI  
python fastagent_demo.py --config config/fastagent/fastagent.config.openai.yaml
```

## Security Rules

The security rules in the `superego/` directory define how tool calls are evaluated:

- **rules.yaml**: Basic security patterns (file access, system commands, etc.)
- **rules-cli-demo.yaml**: Comprehensive rule set demonstrating CLI-based inference capabilities

Rules are evaluated in priority order (lower numbers = higher priority), with the first matching rule determining the action.