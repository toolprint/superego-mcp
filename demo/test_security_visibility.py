#!/usr/bin/env python3
"""Test script to verify security decision visibility."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from superego_mcp.domain.models import ToolRequest
from superego_mcp.infrastructure.security_formatter import SecurityDecisionFormatter
from superego_mcp.domain.security_policy import SecurityPolicyEngine


async def test_security_visibility():
    """Test that security decisions are visible with colored output."""
    
    print("🧪 Testing Security Decision Visibility")
    print("=" * 50)
    
    # Create a formatter
    formatter = SecurityDecisionFormatter()
    
    # Test scenarios from rules.yaml
    test_cases = [
        {
            "name": "Safe File Reading (should be ALLOWED)",
            "request": ToolRequest(
                tool_name="read_file",
                parameters={"path": "/home/user/config.yaml"},
                agent_id="test-agent",
                session_id="test-session",
                cwd="/tmp"
            )
        },
        {
            "name": "Dangerous Command (should be DENIED)",
            "request": ToolRequest(
                tool_name="execute_command",
                parameters={"command": "sudo rm -rf /"},
                agent_id="test-agent", 
                session_id="test-session",
                cwd="/tmp"
            )
        },
        {
            "name": "Complex Operation (should be SAMPLE)",
            "request": ToolRequest(
                tool_name="write_file",
                parameters={"path": "/tmp/script.sh", "content": "#!/bin/bash\necho 'hello'"},
                agent_id="test-agent",
                session_id="test-session", 
                cwd="/tmp"
            )
        }
    ]
    
    # Set up security policy engine
    rules_file = Path(__file__).parent / "config" / "rules.yaml"
    if not rules_file.exists():
        print(f"❌ Rules file not found: {rules_file}")
        return
    
    try:
        security_engine = SecurityPolicyEngine(rules_file)
        
        print(f"✅ Loaded security rules from: {rules_file}")
        print(f"📋 Found {len(security_engine.rules)} security rules")
        print()
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"📋 Test Case {i}: {test_case['name']}")
            print("-" * 40)
            
            # Evaluate the request
            decision = await security_engine.evaluate(test_case["request"])
            
            # Display the decision using our formatter
            formatter.display_decision(test_case["request"], decision)
            
            print()
        
        print("✅ All test cases completed!")
        print()
        print("🎯 What you should see:")
        print("   • Green ✅ for ALLOWED operations")
        print("   • Red ❌ for DENIED operations") 
        print("   • Yellow 🤖 for SAMPLE operations")
        print("   • Rule IDs, confidence scores, and reasons")
        print()
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_security_visibility())