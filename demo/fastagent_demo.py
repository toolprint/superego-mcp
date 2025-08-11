"""FastAgent Demo for Superego MCP Security Evaluation.

This module provides a comprehensive demo of FastAgent integration with the Superego MCP server,
showcasing security evaluation capabilities for AI tool requests.
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    # Import FastAgent components - graceful fallback if not available
    from fast_agent_mcp import AgentConfig, FastAgent, MCPConfig
except ImportError:
    print("⚠️  FastAgent not available. Please install with: uv sync --extra demo")
    sys.exit(1)


@dataclass
class DemoScenario:
    """Demo scenario configuration."""
    name: str
    description: str
    tool_name: str
    parameters: dict[str, Any]
    expected_action: str
    explanation: str


class SuperegoFastAgentDemo:
    """FastAgent demo showcasing Superego MCP security evaluation."""

    def __init__(self, config_path: Path | None = None):
        """Initialize the demo.
        
        Args:
            config_path: Path to FastAgent configuration file
        """
        self.config_path = config_path or Path(__file__).parent / "fastagent.config.yaml"
        self.agent: FastAgent | None = None
        self.scenarios: list[DemoScenario] = []
        self._load_config()
        self._setup_scenarios()

    def _load_config(self) -> None:
        """Load FastAgent configuration."""
        try:
            with open(self.config_path) as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ Configuration file not found: {self.config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Invalid YAML configuration: {e}")
            sys.exit(1)

    def _setup_scenarios(self) -> None:
        """Setup demo scenarios from configuration."""
        demo_config = self.config.get('demo', {})

        # Safe operations scenarios
        safe_ops = demo_config.get('scenarios', {}).get('safe_operations', [])
        for category in safe_ops:
            for example in category.get('examples', []):
                self.scenarios.append(DemoScenario(
                    name=f"Safe: {category['name']}",
                    description=category['description'],
                    tool_name=example['tool'],
                    parameters=example['params'],
                    expected_action="allow",
                    explanation="This operation is considered safe and should be allowed."
                ))

        # Dangerous operations scenarios
        dangerous_ops = demo_config.get('scenarios', {}).get('dangerous_operations', [])
        for category in dangerous_ops:
            for example in category.get('examples', []):
                self.scenarios.append(DemoScenario(
                    name=f"Dangerous: {category['name']}",
                    description=category['description'],
                    tool_name=example['tool'],
                    parameters=example['params'],
                    expected_action="block",
                    explanation="This operation is dangerous and should be blocked."
                ))

        # Complex operations scenarios
        complex_ops = demo_config.get('scenarios', {}).get('complex_operations', [])
        for category in complex_ops:
            for example in category.get('examples', []):
                self.scenarios.append(DemoScenario(
                    name=f"Complex: {category['name']}",
                    description=category['description'],
                    tool_name=example['tool'],
                    parameters=example['params'],
                    expected_action="sample",
                    explanation="This operation requires evaluation and may need approval."
                ))

    async def initialize_agent(self) -> None:
        """Initialize the FastAgent with Superego MCP configuration."""
        print("🤖 Initializing FastAgent with Superego MCP server...")

        try:
            # Create MCP configuration
            mcp_config = MCPConfig(
                servers=self.config['mcp']['servers'],
                sampling=self.config['mcp']['sampling']
            )

            # Create agent configuration
            agent_config = AgentConfig(
                name=self.config['agent']['name'],
                description=self.config['agent']['description'],
                system_prompt=self.config['agent']['system_prompt'],
                mcp_config=mcp_config
            )

            # Initialize FastAgent
            self.agent = FastAgent(agent_config)
            await self.agent.initialize()

            print("✅ FastAgent initialized successfully!")

        except Exception as e:
            print(f"❌ Failed to initialize FastAgent: {e}")
            raise

    async def run_interactive_demo(self) -> None:
        """Run interactive demo mode."""
        print("\n🎯 Interactive Demo Mode")
        print("=" * 50)
        print("You can interact with the agent and see how Superego evaluates tool requests.")
        print("Type 'help' for commands, 'scenarios' to see predefined scenarios, 'quit' to exit.")
        print()

        while True:
            try:
                user_input = input("\n👤 You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break

                if user_input.lower() == 'help':
                    self._show_help()
                    continue

                if user_input.lower() == 'scenarios':
                    await self._show_scenarios()
                    continue

                if user_input.lower().startswith('run scenario '):
                    scenario_num = user_input.split()[-1]
                    await self._run_scenario_by_number(scenario_num)
                    continue

                # Send user input to agent
                print("\n🤖 Agent: Processing your request...")
                response = await self.agent.process(user_input)
                print(f"🤖 Agent: {response}")

            except KeyboardInterrupt:
                print("\n\n👋 Demo interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    async def run_automated_scenarios(self) -> None:
        """Run all predefined scenarios automatically."""
        print("\n🎯 Automated Security Scenarios")
        print("=" * 50)

        for i, scenario in enumerate(self.scenarios, 1):
            print(f"\n📋 Scenario {i}: {scenario.name}")
            print(f"   Description: {scenario.description}")
            print(f"   Tool: {scenario.tool_name}")
            print(f"   Parameters: {json.dumps(scenario.parameters, indent=4)}")
            print(f"   Expected: {scenario.expected_action.upper()}")
            print(f"   Explanation: {scenario.explanation}")

            try:
                # Create a natural language request for the scenario
                request = self._scenario_to_natural_language(scenario)
                print(f"   Request: {request}")

                # Process through agent
                print("   🔄 Processing...")
                response = await self.agent.process(request)

                print(f"   📊 Result: {response}")

                # Brief pause between scenarios
                await asyncio.sleep(1)

            except Exception as e:
                print(f"   ❌ Error: {e}")

        print("\n✅ All scenarios completed!")

    def _scenario_to_natural_language(self, scenario: DemoScenario) -> str:
        """Convert scenario to natural language request."""
        tool_name = scenario.tool_name
        params = scenario.parameters

        if tool_name == "read_file":
            return f"Please read the file at {params.get('path')}"
        elif tool_name == "write_file":
            return f"Please write content to {params.get('path')}"
        elif tool_name == "delete_file":
            return f"Please delete the file {params.get('path')}"
        elif tool_name == "execute_command":
            return f"Please run this command: {params.get('command')}"
        elif tool_name == "search_files":
            return f"Please search for files matching {params.get('pattern')} in {params.get('directory')}"
        elif tool_name == "fetch_url":
            return f"Please fetch data from {params.get('url')}"
        elif tool_name == "change_permissions":
            return f"Please change permissions of {params.get('path')} to {params.get('mode')}"
        else:
            return f"Please use the {tool_name} tool with parameters: {json.dumps(params)}"

    def _show_help(self) -> None:
        """Show help information."""
        print("""
🎯 Available Commands:
  help              - Show this help
  scenarios         - List all predefined scenarios  
  run scenario N    - Run scenario number N
  quit/exit/q       - Exit demo
  
💡 Natural Language:
  You can also ask the agent to perform tasks naturally, e.g.:
  - "Read the file /etc/passwd"
  - "List all Python files in the project"
  - "Delete the temporary file"
  
🔒 Security Notes:
  All tool requests are evaluated by Superego MCP for security compliance.
  You'll see real-time security decisions and explanations.
        """)

    async def _show_scenarios(self) -> None:
        """Show all available scenarios."""
        print("\n📋 Available Scenarios:")
        for i, scenario in enumerate(self.scenarios, 1):
            print(f"  {i:2d}. {scenario.name}")
            print(f"      {scenario.description}")
            print(f"      Expected: {scenario.expected_action.upper()}")

    async def _run_scenario_by_number(self, scenario_num: str) -> None:
        """Run a specific scenario by number."""
        try:
            num = int(scenario_num)
            if 1 <= num <= len(self.scenarios):
                scenario = self.scenarios[num - 1]
                print(f"\n🎯 Running Scenario {num}: {scenario.name}")

                request = self._scenario_to_natural_language(scenario)
                print(f"Request: {request}")

                response = await self.agent.process(request)
                print(f"Response: {response}")
            else:
                print(f"❌ Invalid scenario number. Choose 1-{len(self.scenarios)}")
        except ValueError:
            print("❌ Please provide a valid scenario number")

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.agent:
            await self.agent.cleanup()
        print("🧹 Cleanup completed")


async def main():
    """Main demo entry point."""
    print("🛡️  Superego MCP + FastAgent Security Demo")
    print("=" * 50)

    # Check if we're in the right directory
    current_dir = Path.cwd()
    config_path = current_dir / "demo" / "fastagent.config.yaml"

    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        print("Please run this from the superego-mcp root directory")
        return

    demo = SuperegoFastAgentDemo(config_path)

    try:
        # Initialize the agent
        await demo.initialize_agent()

        # Show demo options
        print("\n🎯 Demo Options:")
        print("1. Interactive mode - Chat with the security-aware agent")
        print("2. Automated scenarios - Run all predefined security tests")
        print("3. Both - Run scenarios first, then interactive mode")

        choice = input("\nChoose an option (1-3): ").strip()

        if choice == "1":
            await demo.run_interactive_demo()
        elif choice == "2":
            await demo.run_automated_scenarios()
        elif choice == "3":
            await demo.run_automated_scenarios()
            input("\nPress Enter to continue to interactive mode...")
            await demo.run_interactive_demo()
        else:
            print("❌ Invalid choice. Exiting.")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
