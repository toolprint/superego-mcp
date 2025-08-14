#!/usr/bin/env python3
"""
Setup Verification Script for Superego MCP with Claude CLI

This script verifies that all prerequisites are properly configured
for running the Claude Code demo with CLI inference.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx


class CLISetupVerifier:
    """Verifies Claude Code demo setup and prerequisites."""

    def __init__(self):
        """Initialize the setup verifier."""
        self.demo_dir = Path(__file__).parent
        self.project_root = self.demo_dir.parent
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.successes: List[str] = []

    def print_header(self, title: str):
        """Print a formatted section header."""
        print(f"\n{title}")
        print("-" * 50)

    def check_python_environment(self) -> bool:
        """Check Python environment and dependencies."""
        self.print_header("🐍 Python Environment")
        
        success = True
        
        # Check Python version
        python_version = sys.version_info
        if python_version >= (3, 10):
            self.successes.append(f"Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        else:
            self.issues.append(f"Python 3.10+ required (found {python_version.major}.{python_version.minor})")
            success = False
        
        # Check required packages
        required_packages = ["httpx", "rich", "superego_mcp"]
        for package in required_packages:
            try:
                __import__(package.replace("_", "-"))
                self.successes.append(f"Package '{package}' installed")
            except ImportError:
                self.issues.append(f"Package '{package}' not installed")
                success = False
        
        return success

    def check_claude_cli(self) -> bool:
        """Check Claude CLI installation and configuration."""
        self.print_header("🤖 Claude CLI")
        
        success = True
        
        # Check if claude command exists
        claude_path = shutil.which("claude")
        if claude_path:
            self.successes.append(f"Claude CLI found at: {claude_path}")
            
            # Check version
            try:
                result = subprocess.run(
                    ["claude", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.successes.append(f"Claude CLI version: {result.stdout.strip()}")
                else:
                    self.warnings.append("Could not determine Claude CLI version")
            except Exception as e:
                self.warnings.append(f"Error checking Claude version: {str(e)}")
            
            # Test basic functionality
            try:
                result = subprocess.run(
                    ["claude", "-p", "non-interactive", "Say OK"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and "OK" in result.stdout:
                    self.successes.append("Claude CLI basic test passed")
                else:
                    self.issues.append("Claude CLI test failed - check API key")
                    success = False
            except subprocess.TimeoutExpired:
                self.issues.append("Claude CLI test timed out - check network connection")
                success = False
            except Exception as e:
                self.issues.append(f"Claude CLI test error: {str(e)}")
                success = False
            
            # Test JSON mode
            try:
                result = subprocess.run(
                    ["claude", "-p", "non-interactive", "--format", "json", 
                     'Respond with JSON: {"status": "ok"}'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    try:
                        # Try to parse JSON from response
                        output = result.stdout.strip()
                        # Extract JSON from response (might have extra text)
                        import re
                        json_match = re.search(r'\{.*\}', output, re.DOTALL)
                        if json_match:
                            json.loads(json_match.group())
                            self.successes.append("Claude CLI JSON mode working")
                        else:
                            self.warnings.append("Claude CLI JSON mode returns non-JSON")
                    except json.JSONDecodeError:
                        self.warnings.append("Claude CLI JSON mode returns invalid JSON")
                else:
                    self.warnings.append("Claude CLI JSON mode test failed")
            except Exception as e:
                self.warnings.append(f"Claude CLI JSON mode error: {str(e)}")
        
        else:
            self.issues.append("Claude CLI not found in PATH")
            success = False
            print("\nTo install Claude CLI:")
            print("  macOS: brew install claude")
            print("  Linux: curl -fsSL https://claude.ai/install.sh | sh")
            print("  Or download from: https://claude.ai/cli")
        
        return success

    def check_api_key(self) -> bool:
        """Check if ANTHROPIC_API_KEY is set."""
        self.print_header("🔑 API Key Configuration")
        
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        
        if api_key:
            if api_key.startswith("sk-ant-"):
                self.successes.append("ANTHROPIC_API_KEY is set and formatted correctly")
                
                # Test API key validity
                try:
                    import httpx
                    response = httpx.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "claude-3-sonnet-20240229",
                            "max_tokens": 10,
                            "messages": [{"role": "user", "content": "Hi"}]
                        },
                        timeout=10
                    )
                    if response.status_code == 200:
                        self.successes.append("API key validated successfully")
                    elif response.status_code == 401:
                        self.issues.append("API key is invalid")
                        return False
                    elif response.status_code == 429:
                        self.warnings.append("API rate limit reached (key is valid)")
                    else:
                        self.warnings.append(f"API test returned status {response.status_code}")
                except Exception as e:
                    self.warnings.append(f"Could not validate API key: {str(e)}")
            else:
                self.warnings.append("API key doesn't match expected format (sk-ant-...)")
            return True
        else:
            self.issues.append("ANTHROPIC_API_KEY environment variable not set")
            print("\nTo set your API key:")
            print("  export ANTHROPIC_API_KEY='your-api-key-here'")
            print("  # Add to ~/.bashrc or ~/.zshrc for persistence")
            return False

    async def check_server_connection(self) -> bool:
        """Check if Superego server is running."""
        self.print_header("🌐 Server Connection")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/health", timeout=5)
                if response.status_code == 200:
                    health = response.json()
                    self.successes.append(f"Server is running (status: {health.get('status')})")
                    
                    # Check inference configuration
                    try:
                        response = await client.get("http://localhost:8000/inference/status")
                        if response.status_code == 200:
                            status = response.json()
                            providers = status.get("available_providers", [])
                            if "claude_cli" in providers:
                                self.successes.append("CLI inference provider is configured")
                            else:
                                self.warnings.append("CLI inference provider not found in configuration")
                    except:
                        self.warnings.append("Could not check inference configuration")
                    
                    return True
                else:
                    self.issues.append(f"Server returned status {response.status_code}")
                    return False
        except httpx.ConnectError:
            self.issues.append("Cannot connect to server at http://localhost:8000")
            print("\nTo start the server:")
            print("  cd", self.project_root)
            print("  python -m superego_mcp.main --config demo/claude-code-demo.yaml")
            return False
        except Exception as e:
            self.issues.append(f"Server connection error: {str(e)}")
            return False

    def check_configuration_files(self) -> bool:
        """Check if required configuration files exist."""
        self.print_header("📁 Configuration Files")
        
        success = True
        
        required_files = [
            ("claude-code-demo.yaml", self.demo_dir / "claude-code-demo.yaml"),
            ("rules-cli-demo.yaml", self.demo_dir / "config" / "rules-cli-demo.yaml"),
            ("claude_code_demo.py", self.demo_dir / "claude_code_demo.py")
        ]
        
        for name, path in required_files:
            if path.exists():
                self.successes.append(f"{name} exists")
            else:
                self.issues.append(f"{name} not found at {path}")
                success = False
        
        # Check if claude-code-demo.yaml has correct settings
        config_path = self.demo_dir / "claude-code-demo.yaml"
        if config_path.exists():
            try:
                import yaml
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                
                # Check inference configuration
                if config.get("inference", {}).get("cli_providers"):
                    cli_provider = config["inference"]["cli_providers"][0]
                    if cli_provider.get("enabled") and cli_provider.get("name") == "claude_cli":
                        self.successes.append("CLI inference is enabled in configuration")
                    else:
                        self.warnings.append("CLI inference may not be properly configured")
                
                # Check if MCP sampling is disabled
                if not config.get("ai_sampling", {}).get("enabled", True):
                    self.successes.append("MCP sampling is disabled (good for CLI demo)")
                else:
                    self.warnings.append("MCP sampling is enabled (consider disabling for CLI demo)")
                    
            except Exception as e:
                self.warnings.append(f"Could not parse configuration: {str(e)}")
        
        return success

    async def run_inference_test(self) -> bool:
        """Test actual inference functionality."""
        self.print_header("🧪 Inference Test")
        
        if not all([
            any("Server is running" in s for s in self.successes),
            any("Claude CLI" in s for s in self.successes),
            any("API key" in s for s in self.successes)
        ]):
            self.warnings.append("Skipping inference test (prerequisites not met)")
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                test_request = {
                    "tool_name": "read_file",
                    "parameters": {"path": "/tmp/test.txt"},
                    "agent_id": "setup-verifier",
                    "session_id": "test-session"
                }
                
                response = await client.post(
                    "http://localhost:8000/intercept",
                    json=test_request,
                    timeout=20
                )
                
                if response.status_code == 200:
                    result = response.json()
                    decision = result.get("decision")
                    provider = result.get("inference_provider")
                    
                    if decision in ["allow", "deny"]:
                        self.successes.append(f"Inference test passed (decision: {decision})")
                        if provider == "claude_cli":
                            self.successes.append("CLI inference provider confirmed working")
                        elif provider:
                            self.warnings.append(f"Using {provider} instead of claude_cli")
                    else:
                        self.warnings.append(f"Unexpected decision: {decision}")
                else:
                    self.warnings.append(f"Inference test returned status {response.status_code}")
                    
        except httpx.TimeoutError:
            self.warnings.append("Inference test timed out (may need to increase timeout)")
        except Exception as e:
            self.warnings.append(f"Inference test error: {str(e)}")
        
        return True

    def print_summary(self):
        """Print verification summary."""
        self.print_header("📊 Verification Summary")
        
        total_checks = len(self.successes) + len(self.warnings) + len(self.issues)
        
        if self.successes:
            print(f"\n✅ Passed ({len(self.successes)}/{total_checks}):")
            for success in self.successes:
                print(f"   • {success}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if self.issues:
            print(f"\n❌ Issues ({len(self.issues)}):")
            for issue in self.issues:
                print(f"   • {issue}")
        
        print("\n" + "=" * 50)
        
        if not self.issues:
            print("✨ All critical checks passed! You're ready to run the demo.")
            print("\nNext steps:")
            print("1. Start the server (if not running):")
            print("   python -m superego_mcp.main --config demo/claude-code-demo.yaml")
            print("\n2. Run the demo:")
            print("   python demo/claude_code_demo.py")
        else:
            print("❗ Please fix the issues above before running the demo.")
            print("\nFor detailed setup instructions, see:")
            print("   demo/CLAUDE_CODE_SETUP.md")

    async def verify_all(self):
        """Run all verification checks."""
        print("🔍 Superego MCP Claude Code Demo - Setup Verification")
        print("=" * 50)
        
        # Run checks
        self.check_python_environment()
        self.check_claude_cli()
        self.check_api_key()
        await self.check_server_connection()
        self.check_configuration_files()
        await self.run_inference_test()
        
        # Print summary
        self.print_summary()


async def main():
    """Main entry point."""
    verifier = CLISetupVerifier()
    await verifier.verify_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)