#!/usr/bin/env python3
"""
Claude Code Security Hook for Superego MCP Integration.

This hook uses the proper Pydantic V2 models and domain integration service
to provide seamless, type-safe integration between Claude Code hooks and
the Superego security evaluation system.

Features:
- Full schema validation using Pydantic V2 models
- Direct domain integration without webhook dependencies
- Comprehensive error handling with fail-closed security
- Structured logging and audit trails
- Support for all Claude Code hook event types

Usage: Called automatically by Claude Code when hook events trigger
Input: JSON data via stdin containing hook event information
Output: Exit code 0 (continue) or 1 (stop) with structured JSON response
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from superego_mcp.domain.claude_code_models import (
    HookEventName,
    PermissionDecision,
    validate_hook_input,
)
from superego_mcp.domain.hook_integration import HookIntegrationService
from superego_mcp.domain.models import SuperegoError, ErrorCode
from superego_mcp.domain.services import InterceptionService
from superego_mcp.domain.repositories import FileRuleRepository


class SuperegoSecurityHook:
    """Enhanced security hook with proper domain integration."""
    
    def __init__(self, config_path: Optional[Path] = None, debug: bool = True):
        """Initialize the security hook."""
        self.debug = debug
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize hook integration service
        self.integration_service = HookIntegrationService()
        
        # Initialize Superego services
        self.interception_service = self._initialize_interception_service(config_path)
        
        self.logger.info("Superego Security Hook initialized")
    
    def setup_logging(self):
        """Set up logging configuration."""
        log_level = logging.DEBUG if self.debug else logging.INFO
        
        # Configure logging with both file and stderr output
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/tmp/superego_hook.log'),
                logging.StreamHandler(sys.stderr)
            ]
        )
    
    def _initialize_interception_service(self, config_path: Optional[Path]) -> InterceptionService:
        """Initialize the Superego interception service."""
        try:
            # Default config path if not provided
            if not config_path:
                hook_dir = Path(__file__).parent
                config_path = hook_dir.parent / "config" / "superego" / "rules.yaml"
            
            if not config_path.exists():
                self.logger.warning(f"Rules file not found at {config_path}, using default rules")
                # Create minimal default rules
                config_path = self._create_default_rules()
            
            return InterceptionService.from_rules_file(config_path)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize interception service: {e}")
            # Return a service with minimal rule engine for safety
            from superego_mcp.domain.services import RuleEngine
            rule_repo = FileRuleRepository()
            rule_engine = RuleEngine(rule_repo)
            return InterceptionService.from_rule_engine(rule_engine)
    
    def _create_default_rules(self) -> Path:
        """Create minimal default rules for safety."""
        default_rules = {
            "rules": [
                {
                    "id": "system-file-protection",
                    "priority": 900,
                    "conditions": {
                        "parameter_contains": "/etc/"
                    },
                    "action": "deny",
                    "reason": "System file access blocked"
                },
                {
                    "id": "dangerous-commands",
                    "priority": 800,
                    "conditions": {
                        "tool_name": "Bash",
                        "parameter_contains": "rm -rf"
                    },
                    "action": "deny",
                    "reason": "Dangerous command blocked"
                }
            ]
        }
        
        import yaml
        default_path = Path("/tmp/superego_default_rules.yaml")
        with open(default_path, 'w') as f:
            yaml.safe_dump(default_rules, f)
        
        self.logger.info(f"Created default rules at {default_path}")
        return default_path
    
    def read_hook_input(self) -> Dict[str, Any]:
        """Read and parse hook input from stdin."""
        try:
            # Read all input from stdin
            input_data = sys.stdin.read().strip()
            
            if not input_data:
                raise ValueError("No input data received")
            
            self.logger.debug(f"Raw hook input: {input_data}")
            
            # Parse JSON
            hook_data = json.loads(input_data)
            self.logger.debug(f"Parsed hook data: {json.dumps(hook_data, indent=2)}")
            
            return hook_data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse hook input JSON: {e}")
            raise SuperegoError(
                code=ErrorCode.PARAMETER_VALIDATION_FAILED,
                message=f"Invalid JSON input: {e}",
                user_message="Hook input is not valid JSON"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error reading input: {e}")
            raise SuperegoError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to read hook input: {e}",
                user_message="Unable to process hook input"
            )
    
    async def process_hook_event(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Process a hook event and return the appropriate response."""
        try:
            # Parse and validate hook input
            hook_input = self.integration_service.parse_hook_input(raw_input)
            self.logger.info(f"Processing {hook_input.hook_event_name} event")
            
            # Check if this event needs security evaluation
            if not self.integration_service.should_evaluate_request(hook_input):
                self.logger.info("Event does not require security evaluation, allowing")
                return self._create_success_response(hook_input.hook_event_name)
            
            # Convert to tool request
            tool_request = self.integration_service.convert_to_tool_request(hook_input)
            if not tool_request:
                self.logger.info("No tool request generated, allowing")
                return self._create_success_response(hook_input.hook_event_name)
            
            self.logger.info(f"Evaluating tool request: {tool_request.tool_name}")
            
            # Evaluate with Superego
            decision = await self.interception_service.evaluate_request(tool_request)
            
            self.logger.info(
                f"Security decision: {decision.action} - {decision.reason} "
                f"(confidence: {decision.confidence:.1%})"
            )
            
            # Convert decision to hook output
            hook_output = self.integration_service.convert_decision_to_hook_output(
                decision, hook_input.hook_event_name
            )
            
            # Create response for Claude Code
            response = self._create_hook_response(hook_output, decision)
            
            return response
            
        except SuperegoError as e:
            self.logger.error(f"Superego error: {e.message}")
            return self._create_error_response(e, raw_input)
        except Exception as e:
            self.logger.error(f"Unexpected error processing hook event: {e}")
            error = SuperegoError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Hook processing failed: {e}",
                user_message="Security evaluation failed"
            )
            return self._create_error_response(error, raw_input)
    
    def _create_hook_response(self, hook_output, decision) -> Dict[str, Any]:
        """Create the hook response in Claude Code format."""
        response = {
            "continue": hook_output.continue_,
            "timestamp": time.time(),
            "source": "superego_security_hook"
        }
        
        # Add event-specific fields
        if hasattr(hook_output, 'permission'):
            response["permission"] = hook_output.permission.value
        
        if hasattr(hook_output, 'message') and hook_output.message:
            response["message"] = hook_output.message
        
        if hook_output.stop_reason:
            response["stop_reason"] = hook_output.stop_reason.value
        
        if hasattr(hook_output, 'suppress_output'):
            response["suppress_output"] = hook_output.suppress_output
        
        # Add security metadata
        response["security"] = {
            "action": decision.action,
            "confidence": decision.confidence,
            "rule_id": decision.rule_id,
            "processing_time_ms": decision.processing_time_ms
        }
        
        return response
    
    def _create_success_response(self, event_type: HookEventName) -> Dict[str, Any]:
        """Create a success response for events that don't need evaluation."""
        return {
            "continue": True,
            "permission": PermissionDecision.ALLOW.value,
            "message": "No security evaluation required",
            "timestamp": time.time(),
            "source": "superego_security_hook",
            "security": {
                "action": "allow",
                "confidence": 1.0,
                "rule_id": None,
                "processing_time_ms": 0
            }
        }
    
    def _create_error_response(
        self, 
        error: SuperegoError, 
        raw_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an error response with fail-closed security."""
        event_type = raw_input.get("hook_event_name", "unknown")
        
        return {
            "continue": False,
            "permission": PermissionDecision.DENY.value,
            "message": error.user_message,
            "stop_reason": "error",
            "suppress_output": True,
            "timestamp": time.time(),
            "source": "superego_security_hook",
            "error": {
                "code": error.code.value,
                "message": error.message,
                "event_type": event_type
            }
        }
    
    def output_response(self, response: Dict[str, Any]):
        """Output the response in the format expected by Claude Code."""
        try:
            # Output structured JSON response to stdout
            json_response = json.dumps(response, indent=2)
            print(json_response, file=sys.stdout)
            
            # Also log the response for debugging
            self.logger.debug(f"Hook response: {json_response}")
            
            # Exit with appropriate code
            exit_code = 0 if response.get("continue", False) else 1
            
            # Log final decision
            action_msg = "ALLOW" if exit_code == 0 else "DENY"
            message = response.get("message", "No message")
            self.logger.info(f"Final decision: {action_msg} - {message}")
            
            sys.exit(exit_code)
            
        except Exception as e:
            self.logger.error(f"Failed to output response: {e}")
            # Fail closed - output minimal error response and exit with error code
            error_response = {
                "continue": False,
                "message": "Critical error in security hook",
                "timestamp": time.time()
            }
            print(json.dumps(error_response), file=sys.stdout)
            sys.exit(1)


async def main():
    """Main entry point for the security hook."""
    hook = SuperegoSecurityHook()
    
    try:
        hook.logger.info("=== Superego Security Hook Started ===")
        
        # Read hook input
        raw_input = hook.read_hook_input()
        
        # Process the hook event
        response = await hook.process_hook_event(raw_input)
        
        # Output response and exit
        hook.output_response(response)
        
    except KeyboardInterrupt:
        hook.logger.info("Hook interrupted by user")
        hook.output_response({
            "continue": False,
            "message": "Hook interrupted",
            "timestamp": time.time()
        })
    except Exception as e:
        hook.logger.error(f"Unhandled error in security hook: {e}")
        hook.output_response({
            "continue": False,
            "message": f"Critical hook error: {e}",
            "timestamp": time.time()
        })


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())