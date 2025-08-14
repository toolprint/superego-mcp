# Superego MCP Demo Guide

Welcome to the Superego MCP Demo Suite! This guide provides comprehensive instructions for running and understanding all available demonstrations.

## Overview

The Superego MCP demo suite has been completely standardized to use a hook-based test harness, eliminating external dependencies and providing consistent behavior across all demos. All demos now inherit from a common base class and use the Claude Code hook simulation for security evaluation.

## Quick Start

### Prerequisites

- Python 3.8+
- Superego MCP source code
- No external API keys required!
- No Claude Code installation required!

### Running Your First Demo

1. **Start with the Demo Dashboard** (Recommended):
   ```bash
   cd demo
   python demo_dashboard.py
   ```
   This provides an interactive menu to explore all available demos.

2. **Or run a specific demo directly**:
   ```bash
   python simple_fastagent_demo.py
   ```

## Demo Architecture

All demos now follow a standardized architecture:

```
demo/
├── base_demo.py           # Base class all demos inherit from
├── demo_utils.py          # Shared utilities and helpers
├── demo_dashboard.py      # Central navigation hub
├── interactive_hook_demo.py   # Advanced interactive demo
├── scenario_runner.py     # Batch execution with metrics
└── [other demos]          # All using the same framework
```

### Key Components

1. **BaseDemo Class** (`base_demo.py`)
   - Provides standardized initialization
   - Hook-based ToolRequest generation
   - Consistent error handling and logging
   - Common display utilities

2. **Demo Utilities** (`demo_utils.py`)
   - Tool request generation helpers
   - Response formatting utilities
   - CLI argument parsing
   - Configuration loading

3. **Hook Integration**
   - Uses `HookIntegrationService` from the domain layer
   - Simulates Claude Code hook events
   - No external dependencies required

## Available Demos

### Basic Demos

#### 1. Simple FastAgent Demo
**Script**: `simple_fastagent_demo.py`  
**Difficulty**: Beginner  
**Time**: 5 minutes

A streamlined demo with essential scenarios:
- Quick demo mode (3 scenarios)
- Full demo (all scenarios)
- Custom scenario selection

```bash
python simple_fastagent_demo.py
```

#### 2. Claude Code Demo
**Script**: `claude_code_demo.py`  
**Difficulty**: Beginner  
**Time**: 5-10 minutes

Interactive demo showcasing Claude Code patterns:
- Pre-defined security scenarios
- Interactive request builder
- Real-time feedback

```bash
python claude_code_demo.py --interactive
```

### Intermediate Demos

#### 3. FastAgent Demo
**Script**: `fastagent_demo.py`  
**Difficulty**: Intermediate  
**Time**: 10-15 minutes

Comprehensive FastAgent integration patterns:
- Category-based scenarios (File, Shell, Network, etc.)
- Risk assessment mode
- Interactive category selection

```bash
python fastagent_demo.py --log-level DEBUG
```

#### 4. Security Scenarios Demo
**Script**: `security_scenarios.py`  
**Difficulty**: Intermediate  
**Time**: 15-20 minutes

Extensive security evaluation scenarios:
- 40+ scenarios across risk levels
- Risk matrix analysis
- Scenario browser with search

```bash
python security_scenarios.py --rules config/rules.yaml
```

### Advanced Demos

#### 5. Interactive Hook Demo
**Script**: `interactive_hook_demo.py`  
**Difficulty**: Advanced  
**Time**: Variable

Menu-driven testing with real-time feedback:
- Scenario templates
- Custom request builder
- Session statistics
- Multiple export formats

```bash
python interactive_hook_demo.py
```

#### 6. Scenario Runner
**Script**: `scenario_runner.py`  
**Difficulty**: Advanced  
**Time**: 20-30 minutes

Batch execution with detailed metrics:
- Performance tracking
- Filtered scenario runs
- HTML/CSV/JSON export
- Custom scenario files

```bash
# Run all scenarios
python scenario_runner.py

# Run from custom file
python scenario_runner.py --scenarios my_scenarios.json --output results.html
```

### Utility Demos

#### 7. Hook Simulator
**Script**: `hook_simulator.py`  
**Difficulty**: Advanced  
**Time**: Variable

Low-level hook simulation for testing:
- Direct hook testing
- Custom hook inputs
- Batch simulation mode

```bash
python hook_simulator.py --mode batch --output /tmp/results.json
```

## Common Command-Line Options

All demos support these standard options:

```bash
--log-level {DEBUG,INFO,WARNING,ERROR}  # Set logging verbosity
--rules PATH                            # Custom security rules file
--output PATH                          # Output file for results
--session-id ID                        # Custom session identifier
--interactive                          # Run in interactive mode
--scenarios PATH                       # Load scenarios from file
```

## Demo Patterns and Best Practices

### Creating Custom Scenarios

All demos accept scenarios in this format:

```json
{
  "tool_name": "Read",
  "parameters": {
    "file_path": "/path/to/file"
  },
  "description": "Read configuration file"
}
```

### Understanding Security Decisions

The demos evaluate three types of decisions:
- **ALLOW**: Operation is safe to proceed
- **DENY**: Operation blocked for security reasons
- **SAMPLE**: Requires human review/approval

### Session Management

All demos:
- Generate unique session IDs
- Track request history
- Provide summary statistics
- Support result export

## Extending the Demos

### Creating a New Demo

1. Create a new Python file in the `demo/` directory
2. Import and extend `BaseDemo`:

```python
from base_demo import BaseDemo

class MyCustomDemo(BaseDemo):
    def __init__(self, **kwargs):
        super().__init__(demo_name="my_custom", **kwargs)
    
    def run(self):
        # Your demo logic here
        self.process_tool_request("Read", {"file_path": "test.txt"})
```

3. Use the provided utilities for consistent behavior
4. Add your demo to `demo_dashboard.py` for easy discovery

### Adding Custom Scenarios

Create a JSON file with your scenarios:

```json
[
  {
    "tool_name": "Bash",
    "parameters": {
      "command": "echo 'Hello'",
      "description": "Test echo"
    },
    "description": "Safe echo command",
    "expected_action": "allow"
  }
]
```

Then run with any demo that supports scenario files:
```bash
python scenario_runner.py --scenarios my_scenarios.json
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure you're in the `demo/` directory
   - The demos automatically add the source path

2. **No Results**
   - Check the log level: `--log-level DEBUG`
   - Verify rules file exists if specified

3. **Permission Errors**
   - Demos use `/tmp` for output by default
   - Specify `--output` for custom location

### Getting Help

1. Run any demo with `-h` or `--help`
2. Use the Demo Dashboard's help option
3. Check individual demo source for examples

## Best Practices

1. **Start Simple**: Begin with `simple_fastagent_demo.py`
2. **Explore Interactively**: Use `interactive_hook_demo.py`
3. **Test Thoroughly**: Run `security_scenarios.py` for comprehensive testing
4. **Analyze Performance**: Use `scenario_runner.py` for metrics
5. **Export Results**: Save session data for later analysis

## Summary

The Superego MCP demo suite provides:
- Zero external dependencies
- Consistent hook-based evaluation
- Multiple difficulty levels
- Comprehensive security scenarios
- Detailed metrics and reporting
- Easy extensibility

All demos work standalone and demonstrate different aspects of the Superego MCP security evaluation system. Start with the Demo Dashboard for the best experience!