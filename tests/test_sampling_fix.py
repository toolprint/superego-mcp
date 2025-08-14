#!/usr/bin/env python3
"""
Simple test script to verify SAMPLE rules are working.

This script tests the sampling functionality without requiring
the full demo environment or external dependencies.
"""

import asyncio
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List

# Add the project source directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from superego_mcp.domain.models import ToolRequest, SecurityRule, Decision, ToolAction
    from superego_mcp.domain.security_policy import SecurityPolicyEngine
    from datetime import datetime, timezone
except ImportError as e:
    print(f"Import error: {e}")
    print("This test requires the security policy engine dependencies.")
    sys.exit(1)


@dataclass
class MockAIDecision:
    """Mock AI decision for testing."""
    decision: str
    reasoning: str
    confidence: float
    provider: str = "test_mock"
    model: str = "mock-model"
    risk_factors: List[str] = None

    def __post_init__(self):
        if self.risk_factors is None:
            self.risk_factors = []


class MockAIService:
    """Mock AI service for testing SAMPLE actions."""
    
    async def evaluate_with_ai(self, prompt: str, cache_key: str):
        """Mock AI evaluation."""
        print(f"  🤖 Mock AI evaluating: {prompt[:50]}...")
        
        # Simple logic based on prompt content
        if any(danger in prompt.lower() for danger in ['rm -rf', '/etc/passwd', 'sudo']):
            return MockAIDecision(
                decision="deny",
                reasoning="Mock AI detected dangerous operation",
                confidence=0.9,
                risk_factors=["destructive_command"]
            )
        else:
            return MockAIDecision(
                decision="allow", 
                reasoning="Mock AI determined operation is safe",
                confidence=0.8,
                risk_factors=["monitoring_required"]
            )
    
    def get_health_status(self):
        return {"status": "healthy", "provider": "test_mock"}


class MockPromptBuilder:
    """Mock prompt builder for testing."""
    
    def build_evaluation_prompt(self, request, rule):
        """Build evaluation prompt."""
        return f"Tool: {request.tool_name}, Params: {str(request.parameters)[:100]}"


async def test_sample_rules():
    """Test that SAMPLE rules work correctly."""
    print("🔍 Testing SAMPLE rule functionality...")
    
    # Use the demo rules file
    rules_file = Path(__file__).parent / "demo" / "config" / "rules.yaml"
    
    if not rules_file.exists():
        print(f"❌ Rules file not found: {rules_file}")
        return False
    
    # Create mock AI services
    mock_ai_service = MockAIService()
    mock_prompt_builder = MockPromptBuilder()
    
    # Initialize security engine with mock AI
    try:
        engine = SecurityPolicyEngine(
            rules_file=rules_file,
            ai_service_manager=mock_ai_service,
            prompt_builder=mock_prompt_builder
        )
        print(f"✅ Security engine initialized with {len(engine.rules)} rules")
    except Exception as e:
        print(f"❌ Failed to initialize security engine: {e}")
        return False
    
    # Test scenarios that should trigger SAMPLE rules
    test_scenarios = [
        {
            "name": "Write file (should be sampled)",
            "tool_name": "Write",
            "parameters": {"file_path": "/tmp/test.txt", "content": "Hello"},
            "expected_action": "sample"
        },
        {
            "name": "Execute safe command (should be sampled)",
            "tool_name": "Bash",
            "parameters": {"command": "echo hello", "description": "Test command"},
            "expected_action": "sample"
        },
        {
            "name": "Read safe file (should be allowed)",
            "tool_name": "Read",
            "parameters": {"file_path": "/home/user/test.txt"},
            "expected_action": "allow"
        },
        {
            "name": "Dangerous system command (should be denied)",
            "tool_name": "Bash",
            "parameters": {"command": "rm -rf /", "description": "Destroy system"},
            "expected_action": "deny"
        }
    ]
    
    results = {"total": 0, "allow": 0, "deny": 0, "sample": 0, "errors": 0}
    
    for scenario in test_scenarios:
        print(f"\n📋 Testing: {scenario['name']}")
        
        # Create tool request
        request = ToolRequest(
            tool_name=scenario["tool_name"],
            parameters=scenario["parameters"],
            session_id="test-session",
            agent_id="test-agent",
            cwd="/tmp",
            timestamp=datetime.now(timezone.utc)
        )
        
        try:
            # Evaluate with security engine
            decision = await engine.evaluate(request)
            
            print(f"  ➡️  Action: {decision.action}")
            print(f"  ➡️  Reason: {decision.reason}")
            print(f"  ➡️  Confidence: {decision.confidence:.1%}")
            
            if decision.rule_id:
                print(f"  ➡️  Rule: {decision.rule_id}")
            
            # Track results
            results["total"] += 1
            results[decision.action] += 1
            
            # Check if this was expected
            expected = scenario.get("expected_action")
            if expected and decision.action != expected:
                print(f"  ⚠️  Expected {expected}, got {decision.action}")
            else:
                print(f"  ✅ Result matches expectation")
                
        except Exception as e:
            print(f"  ❌ Error evaluating scenario: {e}")
            results["errors"] += 1
    
    # Print summary
    print(f"\n📊 Test Results Summary:")
    print(f"Total requests: {results['total']}")
    print(f"Allowed: {results['allow']}")
    print(f"Denied: {results['deny']}")  
    print(f"Sampled: {results['sample']}")
    print(f"Errors: {results['errors']}")
    
    # Check if sampling worked
    if results['sample'] > 0:
        print(f"\n✅ SUCCESS: SAMPLE rules are working! Got {results['sample']} sampled decisions.")
        return True
    else:
        print(f"\n❌ FAILURE: No SAMPLE actions occurred. Check rule configuration.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_sample_rules())
    sys.exit(0 if success else 1)