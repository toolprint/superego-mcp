#!/usr/bin/env python3
"""
Base demo class for Superego MCP demonstrations.

This module provides a standardized base class that all demos should inherit from,
ensuring consistent ToolRequest generation using the Claude Code hook test harness.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the project source directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from superego_mcp.domain.claude_code_models import (
    HookEventName,
    PreToolUseInput,
    PostToolUseInput,
    ToolInputData,
    ToolResponseData,
)
from superego_mcp.domain.hook_integration import HookIntegrationService
from superego_mcp.domain.models import Decision, ToolAction, ToolRequest
from superego_mcp.domain.security_policy import SecurityPolicyEngine
from superego_mcp.infrastructure.inference import (
    CLIProvider,
    CLIProviderConfig,
    InferenceConfig,
    InferenceStrategyManager,
)
from superego_mcp.infrastructure.prompt_builder import SecurePromptBuilder


class BaseDemo(ABC):
    """
    Base class for all Superego MCP demonstrations.
    
    This class provides:
    - Standard initialization and configuration
    - Hook-based ToolRequest generation using HookIntegrationService
    - Consistent error handling and logging
    - Common display utilities
    """
    
    def __init__(self, 
                 demo_name: str,
                 log_level: str = "INFO",
                 rules_file: Optional[str] = None,
                 session_id: Optional[str] = None,
                 ai_provider: str = "mock",
                 claude_model: Optional[str] = None,
                 api_key_env: str = "ANTHROPIC_API_KEY"):
        """
        Initialize the base demo.
        
        Args:
            demo_name: Name of the demo for logging
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            rules_file: Path to security rules file
            session_id: Optional session ID (auto-generated if not provided)
            ai_provider: AI provider type ("mock", "claude_cli", "api")
            claude_model: Claude model to use (for real providers)
            api_key_env: Environment variable name for API key
        """
        self.demo_name = demo_name
        self.log_level = log_level
        self.session_id = session_id or f"demo-{int(datetime.now().timestamp())}"
        self.cwd = str(Path.cwd())
        self.ai_provider = ai_provider
        self.claude_model = claude_model or "claude-sonnet-4-20250514"
        self.api_key_env = api_key_env
        
        # Set up logging
        self._setup_logging()
        self.logger = logging.getLogger(f"demo.{demo_name}")
        
        # Initialize services
        self.hook_integration = HookIntegrationService()
        
        # Track timing and provider info
        self.provider_info = None
        self.timing_info = []
        
        self.security_engine = self._initialize_security_engine(rules_file)
        
        # Demo state
        self.transcript_path = f"/tmp/{self.demo_name}_{self.session_id}.json"
        self.results: List[Dict[str, Any]] = []
        
        self.logger.info(f"Initialized {demo_name} demo")
        self.logger.info(f"Session ID: {self.session_id}")
        self.logger.info(f"Working directory: {self.cwd}")
        self.logger.info(f"AI Provider: {self.ai_provider}")
        if self.provider_info:
            self.logger.info(f"Provider Details: {self.provider_info}")
    
    def _setup_logging(self):
        """Configure logging for the demo."""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Remove existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Configure new handlers
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(f'/tmp/{self.demo_name}.log')
            ]
        )
    
    
    def _initialize_security_engine(self, rules_file: Optional[str]) -> SecurityPolicyEngine:
        """
        Initialize the security engine with rules and AI provider.
        
        Args:
            rules_file: Path to rules file (uses default if not provided)
            
        Returns:
            Configured SecurityPolicyEngine instance
        """
        if not rules_file:
            # Use default demo rules
            rules_file = str(Path(__file__).parent / "config" / "rules.yaml")
        
        # Initialize based on provider type
        if self.ai_provider == "mock":
            return self._create_mock_engine(rules_file)
        elif self.ai_provider == "claude_cli":
            return self._create_cli_engine(rules_file)
        elif self.ai_provider == "api":
            return self._create_api_engine(rules_file)
        else:
            self.logger.warning(f"Unknown AI provider: {self.ai_provider}, falling back to mock")
            return self._create_mock_engine(rules_file)
    
    def _create_mock_engine(self, rules_file: str) -> SecurityPolicyEngine:
        """Create security engine with mock AI service."""
        mock_ai_service = self._create_mock_ai_service()
        mock_prompt_builder = self._create_mock_prompt_builder()
        
        try:
            engine = SecurityPolicyEngine(
                rules_file=Path(rules_file),
                ai_service_manager=mock_ai_service,
                prompt_builder=mock_prompt_builder
            )
            self.provider_info = {"type": "mock", "provider": "demo_mock", "model": "mock-gpt-3.5"}
            self.logger.info(f"Loaded security rules from: {rules_file} (Mock AI)")
            return engine
        except Exception as e:
            self.logger.warning(f"Failed to load rules from {rules_file}: {e}")
            default_rules = Path(__file__).parent / "config" / "rules.yaml"
            return SecurityPolicyEngine(
                rules_file=default_rules,
                ai_service_manager=mock_ai_service,
                prompt_builder=mock_prompt_builder
            )
    
    def _create_cli_engine(self, rules_file: str) -> SecurityPolicyEngine:
        """Create security engine with Claude CLI provider."""
        try:
            # Test if Claude CLI is working (either with API key or OAuth)
            try:
                import subprocess
                # Use --version for a quick test instead of a full prompt
                result = subprocess.run(
                    ["claude", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode != 0:
                    self.logger.warning("Claude CLI version check failed, falling back to mock")
                    self.logger.debug(f"CLI error: {result.stderr}")
                    return self._create_mock_engine(rules_file)
                
                self.logger.info(f"Claude CLI available: {result.stdout.strip()}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                self.logger.warning(f"Claude CLI not available: {e}, falling back to mock")
                return self._create_mock_engine(rules_file)
            
            # Create CLI provider configuration
            cli_config = CLIProviderConfig(
                name="claude_cli_demo",
                enabled=True,
                type="claude",
                command="claude",
                model=self.claude_model,
                api_key_env_var=self.api_key_env,  # Optional - CLI can use OAuth
                timeout_seconds=30  # Reasonable timeout for real API calls
            )
            
            # Create inference configuration
            inference_config = InferenceConfig(
                timeout_seconds=30,
                provider_preference=["claude_cli_demo"],
                cli_providers=[cli_config],
                api_providers=[]
            )
            
            # Create dependencies
            prompt_builder = SecurePromptBuilder()
            dependencies = {
                "prompt_builder": prompt_builder,
                "ai_service_manager": None  # Not needed for CLI provider
            }
            
            # Create inference manager
            inference_manager = InferenceStrategyManager(inference_config, dependencies)
            
            # Create security engine with inference manager
            engine = SecurityPolicyEngine(
                rules_file=Path(rules_file),
                prompt_builder=prompt_builder,
                inference_manager=inference_manager
            )
            
            self.provider_info = {
                "type": "claude_cli", 
                "provider": "claude", 
                "model": self.claude_model,
                "command": "claude"
            }
            self.logger.info(f"Loaded security rules from: {rules_file} (Claude CLI)")
            return engine
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Claude CLI provider: {e}")
            self.logger.info("Falling back to mock provider")
            return self._create_mock_engine(rules_file)
    
    def _create_api_engine(self, rules_file: str) -> SecurityPolicyEngine:
        """Create security engine with direct API provider (placeholder)."""
        self.logger.warning("Direct API provider not yet implemented, falling back to mock")
        return self._create_mock_engine(rules_file)
    
    def _create_mock_ai_service(self):
        """Create a mock AI service for demo purposes that simulates SAMPLE decisions."""
        class MockAIService:
            def __init__(self, parent_demo):
                self.parent_demo = parent_demo
                
            async def evaluate_with_ai(self, prompt: str, cache_key: str):
                """Mock AI evaluation that returns sample decisions based on tool type."""
                # Import here to avoid circular dependencies
                from dataclasses import dataclass
                
                # Add small delay to simulate processing time for mock
                start_time = time.time()
                await asyncio.sleep(0.1)  # Small delay to show it's "processing"
                end_time = time.time()
                
                # Record timing for mock calls
                self.parent_demo.timing_info.append({
                    "provider": "mock",
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_ms": int((end_time - start_time) * 1000)
                })
                
                @dataclass
                class MockAIDecision:
                    decision: str
                    reasoning: str
                    confidence: float
                    provider: str = "demo_mock"
                    model: str = "mock-gpt-3.5"
                    risk_factors: List[str] = None
                
                    def __post_init__(self):
                        if self.risk_factors is None:
                            self.risk_factors = []
                
                # Simple logic: allow most operations but deny clearly dangerous ones
                if any(danger in prompt.lower() for danger in ['rm -rf', '/etc/passwd', 'sudo', 'malicious']):
                    return MockAIDecision(
                        decision="deny",
                        reasoning="AI evaluation detected high-risk operation that should be blocked",
                        confidence=0.9,
                        risk_factors=["destructive_command", "system_modification"]
                    )
                else:
                    return MockAIDecision(
                        decision="allow",
                        reasoning="AI evaluation determined this operation is safe to proceed",
                        confidence=0.8,
                        risk_factors=["requires_monitoring"]
                    )
            
            def get_health_status(self):
                return {"status": "healthy", "provider": "demo_mock"}
        
        return MockAIService(self)
    
    def _create_mock_prompt_builder(self):
        """Create a mock prompt builder for demo purposes."""
        class MockPromptBuilder:
            def build_evaluation_prompt(self, request, rule):
                """Build a simple evaluation prompt."""
                return f"Evaluate security for tool: {request.tool_name} with parameters: {request.parameters}"
        
        return MockPromptBuilder()
    
    @staticmethod
    def add_common_arguments(parser: argparse.ArgumentParser):
        """Add common command-line arguments for demos."""
        parser.add_argument(
            "--ai-provider",
            choices=["mock", "claude_cli", "api"],
            default="mock",
            help="AI provider to use for sampling decisions (default: mock)"
        )
        parser.add_argument(
            "--claude-model",
            default="claude-sonnet-4-20250514",
            help="Claude model to use for real providers (default: claude-sonnet-4-20250514)"
        )
        parser.add_argument(
            "--api-key-env",
            default="ANTHROPIC_API_KEY",
            help="Environment variable name for API key (default: ANTHROPIC_API_KEY)"
        )
        parser.add_argument(
            "--rules-file",
            help="Path to custom security rules file"
        )
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Logging level (default: INFO)"
        )
        parser.add_argument(
            "--show-timing",
            action="store_true",
            help="Show timing information for AI calls"
        )
    
    def create_hook_input(self,
                         tool_name: str,
                         tool_parameters: Dict[str, Any],
                         event_type: HookEventName = HookEventName.PRE_TOOL_USE) -> Dict[str, Any]:
        """
        Create a hook input for testing.
        
        Args:
            tool_name: Name of the tool being called
            tool_parameters: Parameters for the tool
            event_type: Type of hook event
            
        Returns:
            Raw hook input dictionary
        """
        hook_input = {
            "session_id": self.session_id,
            "transcript_path": self.transcript_path,
            "cwd": self.cwd,
            "hook_event_name": event_type.value,
            "tool_name": tool_name,
            "tool_input": tool_parameters
        }
        
        # Add tool response for PostToolUse events
        if event_type == HookEventName.POST_TOOL_USE:
            hook_input["tool_response"] = {
                "success": True,
                "output": "Simulated tool output"
            }
        
        return hook_input
    
    async def _process_tool_request_async(self,
                           tool_name: str,
                           parameters: Dict[str, Any],
                           description: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a tool request through the security engine.
        
        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            description: Optional description of the operation
            
        Returns:
            Result dictionary with decision and details
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Processing: {description or tool_name}")
        self.logger.info(f"{'='*60}")
        
        try:
            # Create hook input
            hook_input_raw = self.create_hook_input(tool_name, parameters)
            
            # Parse and validate
            hook_input = self.hook_integration.parse_hook_input(hook_input_raw)
            self.logger.debug(f"Parsed hook input: {hook_input.hook_event_name}")
            
            # Convert to tool request
            tool_request = self.hook_integration.convert_to_tool_request(hook_input)
            if not tool_request:
                self.logger.warning("No tool request generated from hook input")
                return self._create_error_result("No tool request generated", hook_input_raw)
            
            self.logger.info(f"Tool: {tool_request.tool_name}")
            self.logger.info(f"Parameters: {json.dumps(tool_request.parameters, indent=2)}")
            
            # Evaluate with security engine
            decision = await self.security_engine.evaluate(tool_request)
            
            # Convert to hook output
            hook_output = self.hook_integration.convert_decision_to_hook_output(
                decision, hook_input.hook_event_name
            )
            
            # Create result
            result = {
                "description": description or f"{tool_name} operation",
                "tool_name": tool_name,
                "parameters": parameters,
                "decision": decision.model_dump(),
                "hook_output": hook_output.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Display result
            self._display_result(result)
            
            # Store result
            self.results.append(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            error_result = self._create_error_result(str(e), {
                "tool_name": tool_name,
                "parameters": parameters
            })
            self.results.append(error_result)
            return error_result
    
    def process_tool_request_sync(self,
                                 tool_name: str,
                                 parameters: Dict[str, Any],
                                 description: Optional[str] = None) -> Dict[str, Any]:
        """
        Synchronous wrapper for process_tool_request.
        
        This method provides backward compatibility for synchronous demo code
        by running the async method in an event loop.
        """
        try:
            # Get or create event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we need to handle this differently
                # For now, we'll use asyncio.create_task which should work in most cases
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self._process_tool_request_async(tool_name, parameters, description))
                    )
                    return future.result()
            else:
                # Run in the existing loop
                return loop.run_until_complete(
                    self._process_tool_request_async(tool_name, parameters, description)
                )
        except Exception as e:
            self.logger.error(f"Error in sync wrapper: {e}")
            return self._create_error_result(str(e), {
                "tool_name": tool_name,
                "parameters": parameters,
                "description": description
            })
    
    # For backward compatibility, make the original method name point to the sync version
    def process_tool_request(self,
                           tool_name: str,
                           parameters: Dict[str, Any],
                           description: Optional[str] = None) -> Dict[str, Any]:
        """Backward compatibility method - calls the sync wrapper."""
        return self.process_tool_request_sync(tool_name, parameters, description)
    
    def _create_error_result(self, error_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a standardized error result."""
        return {
            "description": context.get("description", "Error"),
            "tool_name": context.get("tool_name", "unknown"),
            "parameters": context.get("parameters", {}),
            "error": error_message,
            "decision": {
                "action": ToolAction.DENY,
                "reason": f"Error: {error_message}",
                "confidence": 1.0
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _display_result(self, result: Dict[str, Any]):
        """Display a result in a consistent format."""
        decision = result.get("decision", {})
        action = decision.get("action", "ERROR")
        reason = decision.get("reason", "Unknown")
        confidence = decision.get("confidence", 0.0)
        
        # Color codes for terminal
        colors = {
            ToolAction.ALLOW: "\033[92m",    # Green
            ToolAction.DENY: "\033[91m",     # Red
            ToolAction.SAMPLE: "\033[93m",   # Yellow
            "ERROR": "\033[91m"              # Red
        }
        reset_color = "\033[0m"
        
        color = colors.get(action, reset_color)
        
        print(f"\n{color}Decision: {action}{reset_color}")
        print(f"Reason: {reason}")
        print(f"Confidence: {confidence:.1%}")
        
        if "rule_id" in decision and decision["rule_id"]:
            print(f"Rule: {decision['rule_id']}")
        
        if "error" in result:
            print(f"\n❌ Error: {result['error']}")
    
    def run_batch_scenarios(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run a batch of scenarios and return aggregated results.
        
        Args:
            scenarios: List of scenario dictionaries with tool_name, parameters, description
            
        Returns:
            Summary of all results
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Running {len(scenarios)} scenarios for {self.demo_name}")
        self.logger.info(f"{'='*70}")
        
        for scenario in scenarios:
            self.process_tool_request(
                tool_name=scenario["tool_name"],
                parameters=scenario["parameters"],
                description=scenario.get("description")
            )
        
        return self.get_summary()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all processed requests."""
        summary = {
            "demo_name": self.demo_name,
            "session_id": self.session_id,
            "ai_provider": self.ai_provider,
            "provider_info": self.provider_info,
            "total_requests": len(self.results),
            "by_action": {
                ToolAction.ALLOW: 0,
                ToolAction.DENY: 0,
                ToolAction.SAMPLE: 0
            },
            "errors": 0,
            "timing": {
                "total_ai_calls": len(self.timing_info),
                "total_ai_time_ms": sum(t.get("duration_ms", 0) for t in self.timing_info),
                "avg_ai_time_ms": 0 if not self.timing_info else 
                    sum(t.get("duration_ms", 0) for t in self.timing_info) / len(self.timing_info),
                "ai_calls": self.timing_info
            },
            "results": self.results
        }
        
        for result in self.results:
            if "error" in result:
                summary["errors"] += 1
            else:
                decision = result["decision"]
                action = decision["action"]
                
                # Check if this operation went through AI evaluation (sampling)
                if decision.get("ai_provider"):
                    # This was a sampled operation that went through AI evaluation
                    summary["by_action"][ToolAction.SAMPLE] += 1
                else:
                    # This was a direct rule-based decision
                    summary["by_action"][action] += 1
        
        return summary
    
    def display_summary(self):
        """Display a summary of all results."""
        summary = self.get_summary()
        
        print(f"\n{'='*70}")
        print(f"Summary for {self.demo_name}")
        print(f"{'='*70}")
        print(f"AI Provider: {summary['ai_provider']}")
        if summary['provider_info']:
            provider_info = summary['provider_info']
            if provider_info['type'] == 'mock':
                print(f"Provider Type: {provider_info['type']} (simulated responses)")
            elif provider_info['type'] == 'claude_cli':
                print(f"Provider Type: {provider_info['type']} (real Claude API via CLI)")
                print(f"Model: {provider_info['model']}")
                print(f"Command: {provider_info['command']}")
        
        print(f"\nResults:")
        print(f"Total requests: {summary['total_requests']}")
        print(f"Allowed: {summary['by_action'][ToolAction.ALLOW]}")
        print(f"Denied: {summary['by_action'][ToolAction.DENY]}")
        print(f"Sampled: {summary['by_action'][ToolAction.SAMPLE]}")
        print(f"Errors: {summary['errors']}")
        
        # Show timing information if available
        timing = summary['timing']
        if timing['total_ai_calls'] > 0:
            print(f"\nAI Call Performance:")
            print(f"Total AI calls: {timing['total_ai_calls']}")
            print(f"Total AI time: {timing['total_ai_time_ms']}ms")
            print(f"Average AI time: {timing['avg_ai_time_ms']:.1f}ms per call")
            
            if summary['ai_provider'] == 'mock':
                print("(Note: Mock provider includes artificial delay for demonstration)")
            elif summary['ai_provider'] == 'claude_cli':
                print("(Note: Real API calls - timing includes network latency)")
        else:
            print(f"\nNo AI calls made (all decisions were rule-based)")
    
    def save_results(self, output_file: Optional[str] = None):
        """Save results to a JSON file."""
        if not output_file:
            output_file = f"/tmp/{self.demo_name}_{self.session_id}_results.json"
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.get_summary(), f, indent=2, default=str)
        
        self.logger.info(f"Results saved to: {output_path}")
    
    @abstractmethod
    def run(self):
        """
        Run the demo. This method must be implemented by subclasses.
        """
        pass
    
    def cleanup(self):
        """Clean up demo resources."""
        # Override in subclasses if needed
        pass