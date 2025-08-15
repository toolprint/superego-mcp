#!/usr/bin/env python3
"""
Claude Code Audit Hook for Superego MCP Integration

This hook logs completed MCP tool executions for security audit purposes.

Usage: Called automatically by Claude Code when PostToolUse hook triggers
Input: JSON data via stdin containing tool execution results
Output: Always exits with code 0 (logging only, doesn't block execution)
"""

import json
import sys
import time
import requests
from typing import Dict, Any
import logging

# Configuration
SUPEREGO_URL = "http://localhost:8000"
AUDIT_ENDPOINT = f"{SUPEREGO_URL}/webhook/tool-audit"
TIMEOUT_SECONDS = 5
DEBUG = True

# Setup logging
if DEBUG:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/tmp/superego_audit.log'),
            logging.StreamHandler(sys.stderr)
        ]
    )
logger = logging.getLogger('superego_audit')


def parse_hook_input() -> Dict[str, Any]:
    """Parse JSON input from Claude Code hook system."""
    try:
        input_data = sys.stdin.read()
        logger.debug(f"Raw audit input: {input_data}")
        
        hook_data = json.loads(input_data)
        logger.debug(f"Parsed audit data: {json.dumps(hook_data, indent=2)}")
        
        return hook_data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse audit input JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error parsing audit input: {e}")
        return {}


def extract_execution_info(hook_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract tool execution information from hook data."""
    try:
        event_data = hook_data.get('event', {})
        tool_call = event_data.get('toolCall', {})
        result = event_data.get('result', {})
        
        execution_info = {
            'tool_name': tool_call.get('name', 'unknown'),
            'parameters': tool_call.get('parameters', {}),
            'result': result,
            'success': not bool(result.get('error')),
            'session_id': hook_data.get('sessionId', ''),
            'timestamp': time.time(),
            'source': 'claude_code_audit'
        }
        
        # Add execution time if available
        if 'executionTime' in event_data:
            execution_info['execution_time_ms'] = event_data['executionTime']
            
        logger.debug(f"Extracted execution info: {json.dumps(execution_info, indent=2)}")
        return execution_info
        
    except Exception as e:
        logger.error(f"Failed to extract execution info: {e}")
        return {
            'tool_name': 'unknown',
            'parameters': {},
            'result': {'error': f'Extraction error: {e}'},
            'success': False,
            'session_id': '',
            'timestamp': time.time(),
            'source': 'claude_code_audit'
        }


def send_audit_log(execution_info: Dict[str, Any]) -> None:
    """Send tool execution log to Superego MCP for audit."""
    try:
        payload = {
            'tool_name': execution_info['tool_name'],
            'parameters': execution_info['parameters'],
            'result': execution_info['result'],
            'success': execution_info['success'],
            'metadata': {
                'session_id': execution_info.get('session_id', ''),
                'timestamp': execution_info['timestamp'],
                'source': execution_info['source'],
                'execution_time_ms': execution_info.get('execution_time_ms')
            }
        }
        
        logger.debug(f"Sending audit log: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            AUDIT_ENDPOINT,
            json=payload,
            timeout=TIMEOUT_SECONDS,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Claude-Code-Audit-Hook/1.0'
            }
        )
        
        if response.status_code == 200:
            logger.info("Audit log sent successfully")
        else:
            logger.warning(f"Audit service responded with {response.status_code}: {response.text}")
            
    except requests.exceptions.Timeout:
        logger.warning("Audit log timeout - continuing anyway")
    except requests.exceptions.ConnectionError:
        logger.warning("Cannot connect to audit service - continuing anyway")
    except Exception as e:
        logger.warning(f"Error sending audit log: {e}")


def main():
    """Main audit hook execution function."""
    logger.info("=== Superego Audit Hook Started ===")
    
    try:
        # Parse input from Claude Code
        hook_data = parse_hook_input()
        
        if not hook_data:
            logger.warning("No valid hook data received")
            sys.exit(0)
        
        # Extract execution information
        execution_info = extract_execution_info(hook_data)
        
        # Send audit log (best effort)
        send_audit_log(execution_info)
        
        logger.info("Audit hook completed successfully")
        
    except Exception as e:
        logger.error(f"Error in audit hook: {e}")
    
    # Always exit successfully - audit is best-effort and shouldn't block anything
    sys.exit(0)


if __name__ == "__main__":
    main()