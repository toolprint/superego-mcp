---
schema: 1
id: 3
title: Security Policy Engine
status: done
created: "2025-08-11T05:26:40.747Z"
updated: "2025-08-11T06:39:50.240Z"
tags:
  - phase1
  - foundation
  - high-priority
  - large
dependencies:
  - 2
---
## Description
Implement rule-based evaluation with priority system, file storage, and performance targets under 10ms

## Details
Implement rule-based security evaluation with priority system and file storage for Superego MCP Server.

Technical Requirements:
- Priority-based rule matching inspired by CCO-MCP patterns
- File-based rule storage with YAML format
- Rule evaluation with context matching
- Performance targets: < 10ms for 90% of requests

Security Policy Engine Implementation:
```python
from typing import List, Optional
import yaml
import time
from pathlib import Path

class SecurityPolicyEngine:
    """Rule-based security evaluation with priority matching"""
    
    def __init__(self, rules_file: Path):
        self.rules_file = rules_file
        self.rules: List[SecurityRule] = []
        self.load_rules()
        
    def load_rules(self) -> None:
        """Load and parse security rules from YAML file"""
        if not self.rules_file.exists():
            raise SuperegoError(
                ErrorCode.INVALID_CONFIGURATION,
                f"Rules file not found: {self.rules_file}",
                "Security rules configuration is missing"
            )
            
        with open(self.rules_file, 'r') as f:
            rules_data = yaml.safe_load(f)
            
        self.rules = []
        for rule_data in rules_data.get('rules', []):
            rule = SecurityRule(**rule_data)
            self.rules.append(rule)
            
        # Sort by priority (lower number = higher priority)
        self.rules.sort(key=lambda r: r.priority)
        
    async def evaluate(self, request: ToolRequest) -> Decision:
        """Evaluate tool request against security rules"""
        start_time = time.perf_counter()
        
        try:
            # Find first matching rule (highest priority)
            matching_rule = self._find_matching_rule(request)
            
            if not matching_rule:
                # Default allow if no rules match
                return Decision(
                    action="allow",
                    reason="No security rules matched",
                    confidence=0.5,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000)
                )
                
            if matching_rule.action == ToolAction.SAMPLE:
                # Delegate to AI sampling engine
                return await self._handle_sampling(request, matching_rule, start_time)
                
            return Decision(
                action=matching_rule.action.value,
                reason=matching_rule.reason or f"Rule {matching_rule.id} matched",
                rule_id=matching_rule.id,
                confidence=1.0,  # Rule-based decisions are certain
                processing_time_ms=int((time.perf_counter() - start_time) * 1000)
            )
            
        except Exception as e:
            return self._handle_error(e, request, start_time)
            
    def _find_matching_rule(self, request: ToolRequest) -> Optional[SecurityRule]:
        """Find highest priority rule matching the request"""
        for rule in self.rules:  # Already sorted by priority
            if self._rule_matches(rule, request):
                return rule
        return None
        
    def _rule_matches(self, rule: SecurityRule, request: ToolRequest) -> bool:
        """Check if rule conditions match the request"""
        conditions = rule.conditions
        
        # Tool name matching
        if 'tool_name' in conditions:
            tool_pattern = conditions['tool_name']
            if isinstance(tool_pattern, str):
                if tool_pattern \!= request.tool_name:
                    return False
            elif isinstance(tool_pattern, list):
                if request.tool_name not in tool_pattern:
                    return False
                    
        # Parameter matching
        if 'parameters' in conditions:
            param_conditions = conditions['parameters']
            for key, expected in param_conditions.items():
                if key not in request.parameters:
                    return False
                if request.parameters[key] \!= expected:
                    return False
                    
        # Path-based matching  
        if 'cwd_pattern' in conditions:
            import re
            pattern = conditions['cwd_pattern']
            if not re.match(pattern, request.cwd):
                return False
                
        return True
        
    async def _handle_sampling(self, request: ToolRequest, rule: SecurityRule, start_time: float) -> Decision:
        """Handle sampling action (placeholder for Day 1)"""
        # For Day 1 prototype, return allow with note about sampling
        return Decision(
            action="allow",
            reason=f"Rule {rule.id} requires sampling - allowing for Day 1 prototype",
            rule_id=rule.id,
            confidence=0.7,
            processing_time_ms=int((time.perf_counter() - start_time) * 1000)
        )
        
    def _handle_error(self, error: Exception, request: ToolRequest, start_time: float) -> Decision:
        """Handle rule evaluation errors"""
        return Decision(
            action="deny",
            reason="Rule evaluation failed - failing closed for security",
            confidence=0.8,
            processing_time_ms=int((time.perf_counter() - start_time) * 1000)
        )
```

Sample Rules Configuration:
```yaml
# config/rules.yaml
rules:
  - id: "deny_dangerous_commands"
    priority: 1
    conditions:
      tool_name: ["rm", "sudo", "chmod", "dd"]
    action: "deny"
    reason: "Dangerous system command blocked"
    
  - id: "sample_file_operations" 
    priority: 10
    conditions:
      tool_name: ["edit", "write", "delete"]
    action: "sample"
    reason: "File operation requires AI evaluation"
    sampling_guidance: "Evaluate if this file operation is safe based on the file path and content"
    
  - id: "allow_safe_commands"
    priority: 99
    conditions:
      tool_name: ["read", "ls", "grep", "find"]
    action: "allow"
    reason: "Safe read-only command"
```

Implementation Steps:
1. Create src/superego_mcp/domain/security_policy.py
2. Implement SecurityPolicyEngine with rule loading
3. Add rule matching logic with priority handling
4. Create sample rules.yaml configuration
5. Add performance monitoring (< 10ms target)
6. Implement error handling for rule evaluation failures
EOF < /dev/null

## Validation
- [ ] Rules load correctly from YAML file
- [ ] Priority-based matching works (lower number = higher priority)
- [ ] Rule conditions match tool names, parameters, paths
- [ ] Performance meets < 10ms target for rule evaluation
- [ ] Error handling for missing/invalid rule files
- [ ] Tests: Rule loading, matching logic, priority ordering

Test scenarios:
1. Load valid rules.yaml - should succeed and sort by priority
2. Test rule matching with various tool names and conditions
3. Verify priority ordering (priority 1 matches before priority 10)
4. Test parameter matching conditions
5. Test regex pattern matching for cwd_pattern
6. Measure rule evaluation performance (< 10ms)
7. Test error handling with missing/malformed rule files