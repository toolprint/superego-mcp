# Superego MCP Demo

This demo showcases the integration between FastAgent and the Superego MCP server for AI tool security evaluation.

## Quick Start

1. **Run Setup Verification**
   ```bash
   python setup_verification.py
   ```

2. **Configure API Key** (choose one option)
   
   **Option A: Environment Variable (Recommended)**
   ```bash
   export ANTHROPIC_API_KEY="your_anthropic_key"
   # OR
   export OPENAI_API_KEY="your_openai_key"
   ```
   
   **Option B: Secrets File**
   ```bash
   cp fastagent.secrets.yaml.example fastagent.secrets.yaml
   # Edit fastagent.secrets.yaml and add your API key
   ```

3. **Run the Demo**
   ```bash
   # Using Anthropic Claude (default)
   uv run --extra demo python simple_fastagent_demo.py --provider anthropic
   
   # Using OpenAI GPT
   uv run --extra demo python simple_fastagent_demo.py --provider openai
   
   # Advanced options:
   # Run only scenarios (no interactive mode)
   uv run --extra demo python simple_fastagent_demo.py --provider anthropic --scenarios-only
   
   # Run only interactive mode (no scenarios)
   uv run --extra demo python simple_fastagent_demo.py --provider openai --interactive-only
   ```

## Getting API Keys

- **Anthropic (Claude)**: https://console.anthropic.com/account/keys
- **OpenAI (GPT)**: https://platform.openai.com/api-keys

## Demo Scenarios

The demo tests these security scenarios:

### 🟢 Safe Operations (Should be Allowed)
- Reading configuration files
- Listing directory contents
- Searching for files

### 🔴 Dangerous Operations (Should be Blocked)
- System file deletion (`rm -rf /`)
- Password file access (`/etc/passwd`)
- Sudo commands

### 🟡 Complex Operations (Should Require Evaluation)
- Writing script files
- Network requests
- Command execution

## Troubleshooting

### "Connection closed" Error
- **Cause**: Usually an API key issue
- **Solution**: Run `python setup_verification.py` to diagnose

### "FastAgent not available" Error
- **Cause**: Missing dependencies
- **Solution**: Run `uv sync --extra demo`

### "No valid API keys found" Error
- **Cause**: API key not configured
- **Solution**: Follow the API key setup steps above

## Demo Options

### Provider Selection
Choose between two AI providers:

- **Anthropic Claude**: `--provider anthropic` (default)
  - Uses Claude models (Sonnet, Haiku, Opus)
  - Configuration: `fastagent.config.anthropic.yaml`
  
- **OpenAI GPT**: `--provider openai`  
  - Uses GPT models (GPT-4o, GPT-4-turbo, GPT-3.5)
  - Configuration: `fastagent.config.openai.yaml`

### Run Modes
- **Interactive Selection**: Default mode with menu options
- **Scenarios Only**: `--scenarios-only` - Run automated tests only
- **Interactive Only**: `--interactive-only` - Start chat mode directly

## Files

- `simple_fastagent_demo.py` - Main demo script with provider support
- `setup_verification.py` - Setup verification and diagnostics
- `fastagent.config.anthropic.yaml` - Anthropic Claude configuration
- `fastagent.config.openai.yaml` - OpenAI GPT configuration
- `fastagent.config.yaml` - Legacy config (deprecated)
- `fastagent.secrets.yaml.example` - API key template for both providers
- `config/rules.yaml` - Security rules configuration

## How It Works

1. **FastAgent** starts and connects to the Superego MCP server
2. **User prompts** are processed by FastAgent's AI agent
3. **Tool requests** are intercepted by the Superego MCP server
4. **Security evaluation** determines if requests are allowed/denied/evaluated
5. **Results** are returned to the user with security decisions

The integration demonstrates how AI agents can be secured with rule-based and AI-based security evaluation.