---
schema: 1
id: 4
title: Secure Prompt Builder
status: done
created: "2025-08-11T05:30:52.478Z"
updated: "2025-08-11T06:47:30.304Z"
tags:
  - phase1
  - foundation
  - high-priority
  - medium
dependencies:
  - 2
---
## Description
Implement Jinja2-based prompt construction with comprehensive input sanitization and injection protection

## Details
Implement Jinja2-based prompt construction with input sanitization for Superego MCP Server.

Technical Requirements:
- Jinja2 templates with auto-escaping enabled
- Comprehensive input sanitization
- Prompt injection protection
- Template validation and security

Secure Prompt Builder Implementation:
```python
from jinja2 import Environment, select_autoescape
import re
import html

class SecurePromptBuilder:
    """Secure prompt construction with input sanitization"""
    
    def __init__(self):
        self.env = Environment(
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Load evaluation prompt template
        self.evaluation_template = self.env.from_string(EVALUATION_TEMPLATE)
        
    def build_evaluation_prompt(
        self, 
        request: ToolRequest, 
        rule: SecurityRule
    ) -> str:
        """Build secure evaluation prompt with sanitized inputs"""
        sanitized_data = {
            'tool_name': self._sanitize_tool_name(request.tool_name),
            'parameters': self._sanitize_parameters(request.parameters),
            'cwd': self._sanitize_path(request.cwd),
            'agent_id': self._sanitize_identifier(request.agent_id),
            'session_id': self._sanitize_identifier(request.session_id),
            'guidance': self._sanitize_text(rule.sampling_guidance or ""),
            'rule_id': rule.id,
            'timestamp': request.timestamp.isoformat()
        }
        
        return self.evaluation_template.render(**sanitized_data)
        
    def _sanitize_tool_name(self, tool_name: str) -> str:
        """Validate tool name against whitelist pattern"""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', tool_name):
            raise ValueError(f"Invalid tool name: {tool_name}")
        return tool_name
        
    def _sanitize_parameters(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Sanitize parameter values recursively"""
        sanitized = {}
        for key, value in params.items():
            # Sanitize key
            clean_key = re.sub(r'[^\w\-_]', '', str(key))[:100]
            
            # Sanitize value based on type
            if isinstance(value, dict):
                clean_value = str(self._sanitize_parameters(value))[:1000]
            elif isinstance(value, list):
                clean_value = str([self._sanitize_text(str(v)) for v in value])[:1000]  
            else:
                clean_value = self._sanitize_text(str(value))
                
            sanitized[clean_key] = clean_value
            
        return sanitized
        
    def _sanitize_path(self, path: str) -> str:
        """Sanitize file system paths"""
        # Remove directory traversal attempts
        clean_path = re.sub(r'\.\./?', '', str(path))
        
        # Remove control characters
        clean_path = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean_path)
        
        # Limit length
        return clean_path[:500]
        
    def _sanitize_identifier(self, identifier: str) -> str:
        """Sanitize session/agent identifiers"""
        # Keep only alphanumeric, hyphens, underscores
        clean_id = re.sub(r'[^\w\-]', '', str(identifier))
        return clean_id[:50]
        
    def _sanitize_text(self, text: str) -> str:
        """General text sanitization"""
        # HTML escape
        clean_text = html.escape(str(text))
        
        # Remove control characters
        clean_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean_text)
        
        # Limit length to prevent DoS
        return clean_text[:2000]

# Evaluation prompt template
EVALUATION_TEMPLATE = """
You are a security evaluation system analyzing tool execution requests.

REQUEST DETAILS:
- Tool: {{ tool_name }}
- Parameters: {{ parameters }}
- Working Directory: {{ cwd }}
- Agent: {{ agent_id }}
- Session: {{ session_id }}
- Timestamp: {{ timestamp }}

RULE CONTEXT:
- Rule ID: {{ rule_id }}
- Guidance: {{ guidance }}

INSTRUCTIONS:
Evaluate if this tool request should be ALLOWED or DENIED based on:
1. Security implications of the tool and parameters
2. Potential for system damage or data exposure  
3. Context provided in the rule guidance
4. Working directory and file access patterns

Respond with EXACTLY this format:
DECISION: [ALLOW|DENY]
REASON: [Brief explanation in one sentence]
CONFIDENCE: [0.0-1.0 numeric confidence score]

Your evaluation:
"""
```

Implementation Steps:
1. Create src/superego_mcp/infrastructure/prompt_builder.py
2. Implement SecurePromptBuilder with Jinja2 integration
3. Add comprehensive input sanitization methods
4. Create evaluation prompt template
5. Add validation for template security
6. Implement prompt injection protection tests
EOF < /dev/null

## Validation
- [ ] Jinja2 templates render with auto-escaping enabled
- [ ] Input sanitization prevents injection attacks
- [ ] Tool names validated against regex whitelist
- [ ] Parameter values recursively sanitized with length limits
- [ ] Path sanitization removes directory traversal patterns
- [ ] Control characters stripped from all inputs
- [ ] Tests: Injection attempts, sanitization edge cases, template security

Test scenarios:
1. Build prompt with clean data - should render correctly
2. Test tool name validation with invalid names - should raise ValueError
3. Test parameter sanitization with injection attempts
4. Verify path sanitization removes "../" patterns
5. Test identifier sanitization keeps only safe characters
6. Test length limits prevent DoS via oversized inputs
7. Verify HTML escaping works correctly in templates