#!/usr/bin/env python3
"""
Setup Verification Script for Superego MCP Demo

This script verifies that all prerequisites are properly configured
before running the FastAgent demo.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class SetupVerifier:
    """Verifies demo setup and prerequisites."""

    def __init__(self):
        """Initialize the setup verifier."""
        self.demo_dir = Path(__file__).parent
        self.project_root = self.demo_dir.parent
        self.issues: List[str] = []
        self.warnings: List[str] = []

    def check_python_environment(self) -> bool:
        """Check Python environment and dependencies."""
        print("🐍 Checking Python Environment")
        print("-" * 40)
        
        success = True
        
        # Check Python version
        python_version = sys.version_info
        if python_version >= (3, 9):
            print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        else:
            print(f"❌ Python {python_version.major}.{python_version.minor}.{python_version.micro} (requires 3.9+)")
            self.issues.append("Python 3.9+ required")
            success = False
        
        # Check uv
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"✅ UV: {result.stdout.strip()}")
            else:
                print("❌ UV not available")
                self.issues.append("UV package manager not installed")
                success = False
        except Exception:
            print("❌ UV not available")
            self.issues.append("UV package manager not installed")
            success = False
        
        return success

    def check_fastagent(self) -> bool:
        """Check FastAgent availability."""
        print("\n🚀 Checking FastAgent")
        print("-" * 40)
        
        try:
            result = subprocess.run(
                ["uv", "run", "--extra", "demo", "fast-agent", "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=self.project_root
            )
            if result.returncode == 0:
                print(f"✅ FastAgent: {result.stdout.strip()}")
                return True
            else:
                print("❌ FastAgent not available")
                print(f"   Error: {result.stderr.strip()}")
                self.issues.append("FastAgent not installed - run 'uv sync --extra demo'")
                return False
        except subprocess.TimeoutExpired:
            print("❌ FastAgent check timed out")
            self.issues.append("FastAgent installation issue - check dependencies")
            return False
        except Exception as e:
            print(f"❌ Error checking FastAgent: {e}")
            self.issues.append("Cannot verify FastAgent installation")
            return False

    def check_mcp_server(self) -> bool:
        """Check MCP server functionality."""
        print("\n🛡️  Checking Superego MCP Server")
        print("-" * 40)
        
        try:
            # Test basic server initialization
            init_request = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"setup-test","version":"1.0"},"capabilities":{}}}'
            
            result = subprocess.run(
                ["uv", "run", "python", "-m", "superego_mcp.stdio_main"],
                input=init_request + '\n',
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.project_root
            )
            
            if result.returncode == 0 and "result" in result.stdout:
                print("✅ MCP server initializes correctly")
                print("✅ MCP protocol handshake working")
                return True
            else:
                print("❌ MCP server initialization failed")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()[:200]}")
                self.issues.append("MCP server not working properly")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ MCP server startup timed out")
            self.issues.append("MCP server takes too long to start")
            return False
        except Exception as e:
            print(f"❌ Error testing MCP server: {e}")
            self.issues.append("Cannot test MCP server functionality")
            return False

    def check_api_keys(self) -> Tuple[bool, str]:
        """Check API key configuration."""
        print("\n🔑 Checking API Keys")
        print("-" * 40)
        
        # Check environment variables
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        if anthropic_key:
            # Validate key format (should start with sk-)
            if anthropic_key.startswith("sk-"):
                print("✅ Anthropic API key found in environment (valid format)")
                return True, "Anthropic"
            else:
                print("⚠️  Anthropic API key found but format looks incorrect")
                self.warnings.append("Anthropic API key format may be incorrect")
        
        if openai_key:
            # Validate key format (should start with sk-)
            if openai_key.startswith("sk-"):
                print("✅ OpenAI API key found in environment (valid format)")
                return True, "OpenAI"
            else:
                print("⚠️  OpenAI API key found but format looks incorrect")
                self.warnings.append("OpenAI API key format may be incorrect")
        
        # Check secrets file
        secrets_file = self.demo_dir / "fastagent.secrets.yaml"
        if secrets_file.exists():
            try:
                import yaml
                with open(secrets_file, 'r') as f:
                    secrets = yaml.safe_load(f)
                
                anthropic_configured = secrets.get("anthropic", {}).get("api_key")
                openai_configured = secrets.get("openai", {}).get("api_key")
                
                if anthropic_configured and anthropic_configured != "your_anthropic_api_key_here":
                    if anthropic_configured.startswith("sk-"):
                        print("✅ Anthropic API key found in secrets file (valid format)")
                        return True, "Anthropic"
                    else:
                        print("⚠️  Anthropic API key in secrets file has incorrect format")
                        self.warnings.append("Anthropic API key format may be incorrect")
                        
                elif openai_configured and openai_configured != "your_openai_api_key_here":
                    if openai_configured.startswith("sk-"):
                        print("✅ OpenAI API key found in secrets file (valid format)")
                        return True, "OpenAI"
                    else:
                        print("⚠️  OpenAI API key in secrets file has incorrect format")
                        self.warnings.append("OpenAI API key format may be incorrect")
                else:
                    print("❌ Secrets file exists but contains placeholder keys")
                    
            except Exception as e:
                print(f"⚠️  Error reading secrets file: {e}")
                self.warnings.append("Cannot read secrets file properly")
        
        print("❌ No valid API keys found")
        self.issues.append("API key required - set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        return False, ""

    def check_config_files(self) -> bool:
        """Check configuration files."""
        print("\n📄 Checking Configuration Files")
        print("-" * 40)
        
        success = True
        
        # Check provider-specific config files
        anthropic_config = self.demo_dir / "fastagent.config.anthropic.yaml"
        openai_config = self.demo_dir / "fastagent.config.openai.yaml"
        
        anthropic_exists = anthropic_config.exists()
        openai_exists = openai_config.exists()
        
        if anthropic_exists:
            print("✅ Anthropic config file exists")
        else:
            print("❌ Anthropic config file missing")
            self.issues.append("fastagent.config.anthropic.yaml not found")
            success = False
            
        if openai_exists:
            print("✅ OpenAI config file exists")
        else:
            print("❌ OpenAI config file missing")
            self.issues.append("fastagent.config.openai.yaml not found")
            success = False
        
        # Check at least one valid config file
        for config_file, provider in [(anthropic_config, "Anthropic"), (openai_config, "OpenAI")]:
            if config_file.exists():
                try:
                    import yaml
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                        
                    # Check if MCP server is configured
                    if "mcp" in config and "servers" in config["mcp"] and "superego" in config["mcp"]["servers"]:
                        print(f"✅ {provider} - Superego MCP server configured")
                    else:
                        print(f"❌ {provider} - Superego MCP server not configured")
                        self.issues.append(f"{provider} MCP server configuration missing")
                        success = False
                        
                except Exception as e:
                    print(f"❌ Error reading {provider} config file: {e}")
                    self.issues.append(f"Cannot read {provider} FastAgent configuration")
                    success = False
        
        # Check legacy config file (optional)
        legacy_config = self.demo_dir / "fastagent.config.yaml"
        if legacy_config.exists():
            print("⚠️  Legacy config file found (fastagent.config.yaml)")
            self.warnings.append("Legacy config file detected - provider-specific configs are now used")
        
        # Check rules file
        rules_file = self.demo_dir / "config" / "rules.yaml"
        if rules_file.exists():
            print("✅ Security rules file exists")
        else:
            print("⚠️  Security rules file missing (will use defaults)")
            self.warnings.append("Custom security rules not configured")
        
        # Check secrets example file
        secrets_example = self.demo_dir / "fastagent.secrets.yaml.example"
        if secrets_example.exists():
            print("✅ Secrets example file available")
        else:
            print("⚠️  Secrets example file missing")
            self.warnings.append("No secrets template available")
        
        return success

    def show_setup_summary(self, api_key_status: Tuple[bool, str]):
        """Show setup summary and next steps."""
        print("\n" + "=" * 60)
        print("🏆 SETUP VERIFICATION SUMMARY")
        print("=" * 60)
        
        if not self.issues:
            print("🎉 All checks passed! You're ready to run the demo.")
            if api_key_status[0]:
                print(f"🔑 Using {api_key_status[1]} for AI interactions")
            print("\n▶️  Run the demo with:")
            print("   uv run --extra demo python simple_fastagent_demo.py")
        else:
            print("❌ Issues found that must be resolved:")
            for i, issue in enumerate(self.issues, 1):
                print(f"   {i}. {issue}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
        
        print("\n📚 Documentation:")
        print("   • API Keys: https://console.anthropic.com/account/keys")
        print("   • FastAgent: https://fast-agent.ai/")
        print("   • UV Package Manager: https://docs.astral.sh/uv/")

    def run_verification(self) -> bool:
        """Run all verification checks."""
        print("🔍 Superego MCP Demo Setup Verification")
        print("=" * 60)
        print(f"📁 Demo directory: {self.demo_dir}")
        print(f"📁 Project root: {self.project_root}")
        print()
        
        # Run all checks
        python_ok = self.check_python_environment()
        fastagent_ok = self.check_fastagent()
        mcp_ok = self.check_mcp_server()
        api_key_ok, provider = self.check_api_keys()
        config_ok = self.check_config_files()
        
        # Show summary
        self.show_setup_summary((api_key_ok, provider))
        
        # Return overall status
        return python_ok and fastagent_ok and mcp_ok and api_key_ok and config_ok


def main():
    """Main entry point."""
    verifier = SetupVerifier()
    success = verifier.run_verification()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()