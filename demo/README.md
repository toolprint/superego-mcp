# Superego MCP Demo Suite

This directory contains a comprehensive suite of demonstrations showcasing the Superego MCP security evaluation system using a standardized hook-based test harness.

## 🚀 Quick Start

### No External Dependencies Required!
- ✅ No API keys needed
- ✅ No Claude Code installation required
- ✅ Works completely standalone
- ✅ Consistent behavior across all demos

### Start Here:
```bash
cd demo
python demo_dashboard.py
```

The Demo Dashboard provides an interactive menu to explore all available demos with descriptions and guided navigation.

### Optional Provider Configuration

While the demos work standalone, you can also configure API providers:

**Anthropic Claude (Recommended)**
```bash
export ANTHROPIC_API_KEY="your_anthropic_key"
```

**OpenAI GPT**
```bash
export OPENAI_API_KEY="your_openai_key"
# Or use the secrets file method
cp fastagent.secrets.yaml.example fastagent.secrets.yaml
# Edit fastagent.secrets.yaml with your API key
```

### Run Modes
- **Interactive Selection**: Default mode with menu options
- **Scenarios Only**: Run automated tests with `--scenarios-only`
- **Interactive Only**: Start chat mode directly with `--interactive-only`

## 📁 Demo Architecture

All demos follow a standardized architecture using the hook-based test harness:

```
demo/
├── base_demo.py              # Base class all demos inherit from
├── demo_utils.py             # Shared utilities and helpers
├── demo_dashboard.py         # Central navigation hub
│
├── claude_code_demo.py       # Claude Code patterns demo
├── fastagent_demo.py         # FastAgent integration patterns
├── simple_fastagent_demo.py  # Simplified FastAgent demo
├── security_scenarios.py     # Comprehensive security scenarios
├── interactive_hook_demo.py  # Advanced interactive demo
├── scenario_runner.py        # Batch execution with metrics
├── hook_simulator.py         # Low-level hook testing
│
└── config/                   # Configuration files
    ├── rules.yaml           # Default security rules
    └── rules-cli-demo.yaml  # CLI demo rules
```

## 🎯 Available Demos

### Basic Demos (Beginner-Friendly)

#### 1. **Simple FastAgent Demo** (`simple_fastagent_demo.py`)
- **Time**: 5 minutes
- **Features**: Quick demo mode, essential scenarios, simple interface
```bash
python simple_fastagent_demo.py
```

#### 2. **Claude Code Demo** (`claude_code_demo.py`)
- **Time**: 5-10 minutes
- **Features**: Interactive request builder, pre-defined scenarios, real-time feedback
```bash
python claude_code_demo.py --interactive
```

### Intermediate Demos

#### 3. **FastAgent Demo** (`fastagent_demo.py`)
- **Time**: 10-15 minutes
- **Features**: Category-based scenarios, risk assessment, comprehensive patterns
```bash
python fastagent_demo.py
```

#### 4. **Security Scenarios Demo** (`security_scenarios.py`)
- **Time**: 15-20 minutes
- **Features**: 40+ scenarios, risk matrix analysis, scenario browser
```bash
python security_scenarios.py
```

### Advanced Demos

#### 5. **Interactive Hook Demo** (`interactive_hook_demo.py`)
- **Time**: Variable
- **Features**: Menu-driven interface, scenario templates, session statistics
```bash
python interactive_hook_demo.py
```

#### 6. **Scenario Runner** (`scenario_runner.py`)
- **Time**: 20-30 minutes
- **Features**: Batch execution, performance metrics, multiple export formats
```bash
python scenario_runner.py --output results.html
```

## 🛠️ Common Options

All demos support these standard command-line options:

```bash
--log-level {DEBUG,INFO,WARNING,ERROR}  # Logging verbosity
--rules PATH                            # Custom security rules
--output PATH                          # Output file for results
--session-id ID                        # Custom session ID
--interactive                          # Interactive mode
--scenarios PATH                       # Load scenarios from file
```

## 📊 Security Evaluation Categories

The demos evaluate operations across four security levels:

### 🟢 Safe Operations
- File reads in user directories
- Directory listings
- Safe shell commands
- Public API requests

### 🔴 Dangerous Operations  
- System file modifications
- Destructive commands
- Credential access
- Malicious scripts

### 🟡 Complex Operations
- Package installations
- API key searches
- Network requests
- Archive extractions

### ⚠️ Suspicious Operations
- Remote code execution
- Path traversal attempts
- Data exfiltration
- Privilege escalation

## 🔧 Extending the Demos

### Creating a Custom Demo

1. Create a new file extending `BaseDemo`:

```python
from base_demo import BaseDemo
from demo_utils import Colors, create_demo_header

class MyDemo(BaseDemo):
    def __init__(self, **kwargs):
        super().__init__(demo_name="my_demo", **kwargs)
    
    def run(self):
        print(create_demo_header("My Custom Demo"))
        
        # Process a tool request
        self.process_tool_request(
            tool_name="Read",
            parameters={"file_path": "test.txt"},
            description="Test file read"
        )
        
        # Show summary
        self.display_summary()
```

2. Add to Demo Dashboard for easy discovery

### Custom Scenarios

Create a JSON file with scenarios:

```json
[
  {
    "tool_name": "Bash",
    "parameters": {
      "command": "echo 'Hello World'",
      "description": "Test echo"
    },
    "description": "Safe echo command",
    "expected_action": "allow"
  }
]
```

Run with:
```bash
python scenario_runner.py --scenarios my_scenarios.json
```

## 📈 Key Features

### Hook-Based Test Harness
- Simulates Claude Code hook events
- No external dependencies
- Consistent behavior
- Full tool coverage

### Standardized Framework
- Common base class
- Shared utilities
- Consistent CLI options
- Unified error handling

### Comprehensive Coverage
- 100+ test scenarios
- All Claude Code tools
- Multiple risk levels
- Edge cases included

### Rich Feedback
- Real-time decisions
- Detailed explanations
- Performance metrics
- Export capabilities

## 🐛 Troubleshooting

### Import Errors
```bash
# Ensure you're in the demo directory
cd demo
python <demo_name>.py
```

### No Output
```bash
# Increase log level
python <demo_name>.py --log-level DEBUG
```

### Custom Rules Not Working
```bash
# Verify rules file path
python <demo_name>.py --rules ./config/rules.yaml
```

## 📚 Additional Resources

### Documentation
- **Comprehensive Guide**: This README provides complete documentation
- **Security Rules**: Check `config/rules.yaml` for detailed rule configurations

### Exploring the Demos
- **Beginner Path**: Start with Simple FastAgent Demo
- **Advanced Exploration**: Dive into Interactive Hook Demo
- **Comprehensive Testing**: Use Security Scenarios Demo

### Need More Help?
- Explore individual demo scripts for specific use cases
- Use `--help` flag with any demo for detailed options
- Check `demo_dashboard.py` for an interactive navigation hub

## 🎓 Learning Path

1. **Start**: Demo Dashboard → Simple FastAgent Demo
2. **Explore**: Interactive Hook Demo → Custom scenarios
3. **Test**: Security Scenarios → Risk assessment
4. **Analyze**: Scenario Runner → Performance metrics
5. **Extend**: Create custom demos → Share with team

## 🤝 Contributing

When adding new demos:
1. Extend `BaseDemo` for consistency
2. Use `demo_utils` for common tasks
3. Add to Demo Dashboard
4. Update documentation
5. Test with various scenarios

## 📄 License

See the main project LICENSE file for details.