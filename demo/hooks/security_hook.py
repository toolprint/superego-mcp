#!/usr/bin/env python3
"""
Claude Code Security Hook for Superego MCP Integration

This hook intercepts MCP tool calls before execution and sends them
to the Superego MCP server for security evaluation.

Usage: Called automatically by Claude Code when PreToolUse hook triggers
Input: JSON data via stdin containing tool call information
Output: Exit code 0 (allow) or 1 (deny) with optional message
"""

import json
import sys
import time
import requests
from typing import Dict, Any, Optional
import logging

# Configuration
SUPEREGO_URL = "http://localhost:8000"
WEBHOOK_ENDPOINT = f"{SUPEREGO_URL}/webhook/tool-intercept"
TIMEOUT_SECONDS = 10
DEBUG = True

# Setup logging
if DEBUG:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/tmp/superego_hook.log'),
            logging.StreamHandler(sys.stderr)
        ]
    )
logger = logging.getLogger('superego_hook')


def parse_hook_input() -> Dict[str, Any]:
    """Parse JSON input from Claude Code hook system."""
    try:
        # Read all input from stdin
        input_data = sys.stdin.read()
        logger.debug(f"Raw hook input: {input_data}")
        
        # Parse JSON
        hook_data = json.loads(input_data)
        logger.debug(f"Parsed hook data: {json.dumps(hook_data, indent=2)}")
        
        return hook_data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse hook input JSON: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error parsing input: {e}")
        sys.exit(1)


def extract_tool_info(hook_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant tool call information from hook data."""
    try:
        # Hook data structure from Claude Code
        event_data = hook_data.get('event', {})
        tool_call = event_data.get('toolCall', {})
        
        # Extract tool information
        tool_info = {
            'tool_name': tool_call.get('name', 'unknown'),
            'parameters': tool_call.get('parameters', {}),
            'session_id': hook_data.get('sessionId', ''),
            'timestamp': time.time(),
            'source': 'claude_code_hook'
        }
        
        # Add context if available
        if 'context' in event_data:
            tool_info['context'] = event_data['context']
            
        logger.debug(f"Extracted tool info: {json.dumps(tool_info, indent=2)}")
        return tool_info
        
    except Exception as e:
        logger.error(f"Failed to extract tool info: {e}")
        return {
            'tool_name': 'unknown',
            'parameters': {},
            'session_id': '',
            'timestamp': time.time(),
            'source': 'claude_code_hook',
            'extraction_error': str(e)
        }


def send_security_request(tool_info: Dict[str, Any]) -> Dict[str, Any]:
    """Send tool call to Superego MCP for security evaluation."""
    try:
        # Prepare request payload
        payload = {
            'tool_name': tool_info['tool_name'],
            'parameters': tool_info['parameters'],
            'metadata': {
                'session_id': tool_info.get('session_id', ''),
                'timestamp': tool_info['timestamp'],
                'source': tool_info['source']
            }
        }
        
        logger.debug(f"Sending security request: {json.dumps(payload, indent=2)}")
        
        # Send HTTP request to Superego MCP
        response = requests.post(
            WEBHOOK_ENDPOINT,
            json=payload,
            timeout=TIMEOUT_SECONDS,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Claude-Code-Security-Hook/1.0'
            }
        )
        
        logger.debug(f"Security response status: {response.status_code}")
        logger.debug(f"Security response body: {response.text}")
        
        # Parse response
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Security evaluation result: {result}")
            return result
        else:
            logger.error(f"Security service error: {response.status_code} - {response.text}")
            return {
                'decision': 'deny',
                'reason': f'Security service unavailable (HTTP {response.status_code})',
                'confidence': 0.5,
                'error': True
            }
            
    except requests.exceptions.Timeout:
        logger.error("Security evaluation timeout")
        return {
            'decision': 'deny',
            'reason': 'Security evaluation timeout - denying for safety',
            'confidence': 0.5,
            'error': True
        }
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to security service")
        return {
            'decision': 'deny',
            'reason': 'Security service unavailable - denying for safety',
            'confidence': 0.5,
            'error': True
        }
    except Exception as e:
        logger.error(f"Unexpected error in security request: {e}")
        return {
            'decision': 'deny',
            'reason': f'Security evaluation error: {str(e)}',
            'confidence': 0.5,
            'error': True
        }


def handle_security_decision(decision_data: Dict[str, Any]) -> None:
    """Handle the security decision and exit appropriately."""
    decision = decision_data.get('decision', 'deny').lower()
    reason = decision_data.get('reason', 'No reason provided')
    confidence = decision_data.get('confidence', 0.0)
    
    if decision == 'allow':
        logger.info(f"ALLOW: {reason} (confidence: {confidence:.2f})")
        print(f"Security check passed: {reason}", file=sys.stderr)
        sys.exit(0)  # Exit code 0 = allow
    else:
        logger.warning(f"DENY: {reason} (confidence: {confidence:.2f})")
        print(f"Security check failed: {reason}", file=sys.stderr)
        sys.exit(1)  # Exit code 1 = deny


def main():
    """Main hook execution function."""
    logger.info("=== Superego Security Hook Started ===")
    
    try:
        # Parse input from Claude Code
        hook_data = parse_hook_input()
        
        # Extract tool call information
        tool_info = extract_tool_info(hook_data)
        
        # Special handling for certain tool types
        tool_name = tool_info.get('tool_name', '')
        
        # Skip security check for certain safe operations
        if tool_name in ['mcp__debug__ping', 'mcp__health__check']:
            logger.info(f"Skipping security check for safe tool: {tool_name}")
            sys.exit(0)
        
        # Send to Superego MCP for evaluation
        decision_data = send_security_request(tool_info)
        
        # Handle the decision
        handle_security_decision(decision_data)
        
    except KeyboardInterrupt:
        logger.info("Hook interrupted by user")
        sys.exit(1)
    except SystemExit:
        raise  # Re-raise sys.exit() calls
    except Exception as e:
        logger.error(f"Unhandled error in security hook: {e}")
        print(f"Security hook error: {e}", file=sys.stderr)
        sys.exit(1)  # Fail closed on unexpected errors


if __name__ == "__main__":
    main()