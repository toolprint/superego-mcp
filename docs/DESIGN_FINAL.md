# Superego MCP Server - Final Design Document

**Version:** 2.0 (Rapid Prototype Focus)  
**Date:** 2025-08-11  
**Status:** Ready for Implementation

## Executive Summary

This document presents the refined design for the Superego MCP Server, incorporating critical architectural improvements while maintaining focus on rapid prototype implementation. The design addresses five key recommendations from the architectural review:

1. **Circuit Breaker for AI Sampling** - Prevents cascade failures from AI service outages
2. **Parameter Sanitization** - Validates inputs before AI prompt construction  
3. **Domain Layer Design** - Separates business logic from infrastructure
4. **Error Handling Strategy** - Defines error propagation and user feedback
5. **Health Checks** - Enables monitoring and SLA metrics

The design prioritizes **Day 1 functionality** with a security-first approach, using modern Python tooling and patterns that enable future library extraction.

**Important**: This design includes FastAgent as a demo client (not a server component) to test MCP sampling functionality, since Claude Code does not yet support sampling. The FastAgent demo allows testing of the AI-powered security evaluation features during development.

## Core Architecture

### Domain-Driven Design

The architecture now features a proper domain layer that isolates business logic from infrastructure concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────┐   │
│  │ STDIO         │  │ HTTP/SSE        │  │ MCP Resources│   │
│  │ Transport     │  │ Transport       │  │ Endpoints    │   │
│  └───────────────┘  └─────────────────┘  └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                      Domain Layer                            │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────┐   │
│  │ SecurityPolicy│  │ DecisionEngine  │  │ AuditService │   │
│  │ (Rules)       │  │ (AI Sampling)   │  │ (Logging)    │   │
│  └───────────────┘  └─────────────────┘  └──────────────┘   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │               Domain Models (Pydantic 2.0)            │   │
│  │  ToolRequest | Decision | Rule | AuditEntry | Config │   │
│  └───────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                       │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────┐   │
│  │ ConfigLoader  │  │ PromptTemplates │  │ StorageAdapter│  │
│  │ (File Watch)  │  │ (BAML/Jinja2)   │  │ (Pluggable)  │   │
│  └───────────────┘  └─────────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Domain Models

All domain objects use Pydantic 2.0 for validation and serialization:

```python
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Literal, Optional, Dict, Any
from enum import Enum

class ToolAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    SAMPLE = "sample"

class ToolRequest(BaseModel):
    """Domain model for tool execution requests"""
    tool_name: str = Field(..., pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    parameters: Dict[str, Any]
    session_id: str
    agent_id: str
    cwd: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('parameters')
    def sanitize_parameters(cls, v):
        """Prevent parameter injection attacks"""
        # Deep sanitization logic here
        return v

class SecurityRule(BaseModel):
    """Domain model for security rules"""
    id: str
    priority: int = Field(..., ge=0, le=999)
    conditions: Dict[str, Any]
    action: ToolAction
    reason: Optional[str] = None
    sampling_guidance: Optional[str] = None
    
    class Config:
        frozen = True  # Immutable rules

class Decision(BaseModel):
    """Domain model for security decisions"""
    action: Literal["allow", "deny"]
    reason: str
    rule_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: int
    
class AuditEntry(BaseModel):
    """Domain model for audit trail entries"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request: ToolRequest
    decision: Decision
    rule_matches: list[str]
    ttl: Optional[datetime] = None
```

## Critical Component Implementations

### 1. Circuit Breaker for AI Sampling

Implements timeout and fallback mechanisms to prevent cascade failures:

```python
from asyncio import timeout as async_timeout
from typing import Optional
import asyncio

class CircuitBreaker:
    """Circuit breaker pattern for external service calls"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        timeout_seconds: int = 10
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state: Literal["closed", "open", "half_open"] = "closed"
        
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
                
        try:
            async with async_timeout(self.timeout_seconds):
                result = await func(*args, **kwargs)
                self._on_success()
                return result
        except Exception as e:
            self._on_failure()
            raise
            
    def _on_success(self):
        """Reset circuit breaker on successful call"""
        self.failure_count = 0
        self.state = "closed"
        
    def _on_failure(self):
        """Track failures and open circuit if threshold exceeded"""
        self.failure_count += 1
        self.last_failure_time = asyncio.get_event_loop().time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to retry"""
        return (
            self.last_failure_time and
            asyncio.get_event_loop().time() - self.last_failure_time >= self.recovery_timeout
        )

class AIDecisionEngine:
    """AI-powered decision engine with circuit breaker protection"""
    
    def __init__(self, prompt_builder: 'SecurePromptBuilder'):
        self.prompt_builder = prompt_builder
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            timeout_seconds=10
        )
        
    async def evaluate(self, request: ToolRequest, rule: SecurityRule) -> Decision:
        """Evaluate request using AI with fallback on failure"""
        try:
            return await self.circuit_breaker.call(
                self._evaluate_with_ai, request, rule
            )
        except (CircuitBreakerOpenError, asyncio.TimeoutError) as e:
            # Fallback to conservative decision
            return Decision(
                action="deny",
                reason=f"AI evaluation unavailable: {str(e)}. Denying by default.",
                confidence=0.5,
                processing_time_ms=0
            )
            
    async def _evaluate_with_ai(
        self, 
        request: ToolRequest, 
        rule: SecurityRule
    ) -> Decision:
        """Actual AI evaluation logic"""
        prompt = self.prompt_builder.build_evaluation_prompt(request, rule)
        
        # Use your preferred LLM client here
        response = await llm_client.sample(
            prompt,
            temperature=0.1,
            max_tokens=500
        )
        
        return self._parse_ai_response(response, rule.id)
```

### 2. Secure Prompt Templating

Using BAML-inspired patterns for secure prompt construction:

```python
from jinja2 import Environment, select_autoescape, Template
from typing import Dict, Any
import re

class SecurePromptBuilder:
    """Secure prompt construction with input sanitization"""
    
    def __init__(self):
        # Configure Jinja2 with auto-escaping
        self.env = Environment(
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Load prompt templates
        self.templates = {
            'evaluation': self._load_template('evaluation_prompt.j2'),
            'context': self._load_template('context_prompt.j2')
        }
        
    def build_evaluation_prompt(
        self, 
        request: ToolRequest, 
        rule: SecurityRule
    ) -> str:
        """Build secure evaluation prompt"""
        # Sanitize all inputs
        sanitized_data = {
            'tool_name': self._sanitize_tool_name(request.tool_name),
            'parameters': self._sanitize_parameters(request.parameters),
            'cwd': self._sanitize_path(request.cwd),
            'agent_id': self._sanitize_identifier(request.agent_id),
            'guidance': self._sanitize_text(rule.sampling_guidance or "")
        }
        
        # Render template with sanitized data
        return self.templates['evaluation'].render(**sanitized_data)
        
    def _sanitize_tool_name(self, tool_name: str) -> str:
        """Validate tool name against whitelist"""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', tool_name):
            raise ValueError(f"Invalid tool name: {tool_name}")
        return tool_name
        
    def _sanitize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Deep sanitization of parameter dictionary"""
        sanitized = {}
        for key, value in params.items():
            if not isinstance(key, str) or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                continue  # Skip invalid keys
                
            if isinstance(value, str):
                # Remove potential prompt injection patterns
                sanitized[key] = re.sub(r'[<>{}]', '', value)[:1000]  # Limit length
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_parameters(value)  # Recursive
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_parameters({'_': item})['_'] 
                                 for item in value[:100]]  # Limit array size
        return sanitized
        
    def _sanitize_path(self, path: str) -> str:
        """Sanitize file paths"""
        # Remove any potential path traversal attempts
        return re.sub(r'\.\.[/\\]', '', path)
        
    def _sanitize_identifier(self, identifier: str) -> str:
        """Sanitize identifiers"""
        return re.sub(r'[^a-zA-Z0-9_-]', '', identifier)[:100]
        
    def _sanitize_text(self, text: str) -> str:
        """Sanitize free-form text"""
        # Remove control characters and limit length
        return ''.join(c for c in text if c.isprintable())[:500]
```

Example prompt template (`evaluation_prompt.j2`):

```jinja2
Evaluate the following tool request for security and policy compliance:

TOOL INFORMATION:
- Name: {{ tool_name }}
- Parameters: {{ parameters | tojson(indent=2) }}

EXECUTION CONTEXT:
- Working Directory: {{ cwd }}
- Agent ID: {{ agent_id }}

EVALUATION GUIDANCE:
{{ guidance }}

INSTRUCTIONS:
1. Consider potential security risks
2. Evaluate against principle of least privilege
3. Check for policy violations
4. Assess business impact

Respond with a JSON object containing:
{
  "decision": "allow" or "deny",
  "reason": "Clear explanation of the decision",
  "risk_factors": ["list", "of", "identified", "risks"],
  "confidence": 0.0 to 1.0
}
```

### 3. Error Handling Strategy

Comprehensive error handling with user-friendly feedback:

```python
from typing import Optional, Dict, Any
from enum import Enum
import logging

class ErrorCode(str, Enum):
    """Standardized error codes"""
    RULE_EVALUATION_FAILED = "RULE_EVAL_001"
    AI_SERVICE_UNAVAILABLE = "AI_SVC_001"
    INVALID_CONFIGURATION = "CONFIG_001"
    PARAMETER_VALIDATION_FAILED = "PARAM_001"
    INTERNAL_ERROR = "INTERNAL_001"

class SuperegoError(Exception):
    """Base exception for all Superego errors"""
    
    def __init__(
        self, 
        code: ErrorCode, 
        message: str, 
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.user_message = user_message
        self.context = context or {}
        super().__init__(message)

class ErrorHandler:
    """Centralized error handling with logging and user feedback"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
    def handle_error(self, error: Exception, request: ToolRequest) -> Decision:
        """Convert exceptions to decisions with appropriate feedback"""
        
        if isinstance(error, SuperegoError):
            self.logger.error(
                f"Superego error: {error.code}",
                extra={
                    'error_code': error.code,
                    'message': error.message,
                    'context': error.context,
                    'request': request.dict()
                }
            )
            
            # Determine action based on error type
            if error.code in [ErrorCode.AI_SERVICE_UNAVAILABLE]:
                # Allow on AI service failure (fail open)
                return Decision(
                    action="allow",
                    reason=error.user_message,
                    confidence=0.3,
                    processing_time_ms=0
                )
            else:
                # Deny on other errors (fail closed)
                return Decision(
                    action="deny",
                    reason=error.user_message,
                    confidence=0.8,
                    processing_time_ms=0
                )
        else:
            # Unexpected error - log and deny
            self.logger.exception(
                "Unexpected error in request processing",
                extra={'request': request.dict()}
            )
            
            return Decision(
                action="deny",
                reason="An internal error occurred. Request denied for safety.",
                confidence=0.9,
                processing_time_ms=0
            )
```

### 4. Health Checks and Monitoring

Comprehensive health check system for all components:

```python
from typing import Dict, Literal
from datetime import datetime
import psutil
import asyncio

class HealthStatus(BaseModel):
    """Health check response model"""
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: Dict[str, 'ComponentHealth']
    metrics: Dict[str, float]

class ComponentHealth(BaseModel):
    """Individual component health"""
    status: Literal["healthy", "degraded", "unhealthy"]
    message: Optional[str] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)

class HealthMonitor:
    """System health monitoring"""
    
    def __init__(self, components: Dict[str, Any]):
        self.components = components
        self.metrics = {}
        
    async def check_health(self) -> HealthStatus:
        """Perform comprehensive health check"""
        component_health = {}
        
        # Check each component
        checks = []
        for name, component in self.components.items():
            if hasattr(component, 'health_check'):
                checks.append(self._check_component(name, component))
                
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        for name, result in zip(self.components.keys(), results):
            if isinstance(result, Exception):
                component_health[name] = ComponentHealth(
                    status="unhealthy",
                    message=str(result)
                )
            else:
                component_health[name] = result
                
        # Collect system metrics
        self.metrics = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'requests_per_second': self._get_request_rate(),
            'average_response_time_ms': self._get_avg_response_time()
        }
        
        # Determine overall status
        statuses = [h.status for h in component_health.values()]
        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"
            
        return HealthStatus(
            status=overall_status,
            components=component_health,
            metrics=self.metrics
        )
        
    async def _check_component(self, name: str, component: Any) -> ComponentHealth:
        """Check individual component health"""
        try:
            result = await component.health_check()
            return ComponentHealth(
                status=result.get('status', 'healthy'),
                message=result.get('message')
            )
        except Exception as e:
            return ComponentHealth(
                status="unhealthy",
                message=str(e)
            )
```

### 5. Registry Pattern for Future Library Extraction

Modular registry pattern for prompts, resources, and tools:

```python
from typing import Dict, Type, Callable, Any
from abc import ABC, abstractmethod

class Registry(ABC):
    """Abstract base for all registries"""
    
    @abstractmethod
    def register(self, key: str, value: Any) -> None:
        pass
        
    @abstractmethod
    def get(self, key: str) -> Any:
        pass
        
    @abstractmethod
    def list_keys(self) -> list[str]:
        pass

class PromptRegistry(Registry):
    """Registry for prompt templates"""
    
    def __init__(self):
        self._prompts: Dict[str, Template] = {}
        
    def register(self, key: str, template: Template) -> None:
        """Register a prompt template"""
        self._prompts[key] = template
        
    def get(self, key: str) -> Template:
        """Get a prompt template"""
        if key not in self._prompts:
            raise KeyError(f"Prompt '{key}' not found")
        return self._prompts[key]
        
    def list_keys(self) -> list[str]:
        """List all registered prompts"""
        return list(self._prompts.keys())

class ToolRegistry(Registry):
    """Registry for MCP tools"""
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        
    def register(self, key: str, handler: Callable) -> None:
        """Register a tool handler"""
        self._tools[key] = handler
        
    def get(self, key: str) -> Callable:
        """Get a tool handler"""
        if key not in self._tools:
            raise KeyError(f"Tool '{key}' not found")
        return self._tools[key]
        
    def list_keys(self) -> list[str]:
        """List all registered tools"""
        return list(self._tools.keys())

class ResourceRegistry(Registry):
    """Registry for MCP resources"""
    
    def __init__(self):
        self._resources: Dict[str, Callable] = {}
        
    def register(self, key: str, handler: Callable) -> None:
        """Register a resource handler"""
        self._resources[key] = handler
        
    def get(self, key: str) -> Callable:
        """Get a resource handler"""
        if key not in self._resources:
            raise KeyError(f"Resource '{key}' not found")
        return self._resources[key]
        
    def list_keys(self) -> list[str]:
        """List all registered resources"""
        return list(self._resources.keys())

# Global registry instances
prompt_registry = PromptRegistry()
tool_registry = ToolRegistry()
resource_registry = ResourceRegistry()
```

## Technology Stack

### Core Dependencies

```toml
[project]
name = "superego-mcp"
version = "0.1.0"
description = "Intelligent tool request interception for AI agents"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "watchfiles>=0.20.0",
    "jinja2>=3.1.0",
    "httpx>=0.25.0",
    "structlog>=23.0.0",
    "psutil>=5.9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 88
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
```

### Task Automation with Justfile

```justfile
# Justfile for task automation

# Default recipe
default:
    @just --list

# Install dependencies with uv
install:
    uv pip install -e ".[dev]"

# Run tests
test:
    pytest tests/ -v --cov=superego_mcp

# Lint code
lint:
    ruff check .
    mypy superego_mcp/

# Format code
format:
    ruff format .

# Run development server
dev:
    python -m superego_mcp.server --config config/dev.yaml --transport stdio

# Launch FastAgent demo client
demo:
    # Launch FastAgent configured to connect to Superego MCP server
    # This demonstrates sampling functionality before Claude Code supports it
    python -m fastagent.demo --mcp-server superego --config config/demo_client.yaml

# Build package
build:
    hatchling build

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info
    find . -type d -name __pycache__ -exec rm -rf {} +
```

## FastAgent Demo Client

### Purpose and Implementation

**FastAgent serves as a working demo client for testing the Superego MCP server's sampling capabilities.** Since Claude Code does not yet support MCP sampling features, FastAgent provides a way to demonstrate and test the security evaluation functionality during development.

#### Key Points:

1. **Demo Client Only**: FastAgent is NOT a component of the Superego server itself. It's an external client used solely for testing and demonstration purposes.

2. **Sampling Support**: FastAgent supports the MCP sampling protocol, allowing you to test the AI-powered security evaluation features before Claude Code adds this capability.

3. **Simple Launch**: The demo client can be launched directly from the justfile with a single command, making it easy to test your Superego server implementation.

4. **Configuration**: FastAgent will be configured to connect to the local Superego MCP server and demonstrate various tool requests that trigger different security rules.

### Critical Implementation Note

> ⚠️ **CRITICAL**: The implementation agent MUST read the latest FastAgent documentation on GitHub to understand how to properly set up FastAgent with sampling configuration and annotations. This includes:
> - Understanding the sampling request/response protocol
> - Configuring FastAgent to connect to the Superego MCP server
> - Setting up proper annotations for sampling support
> - Implementing the demo scenarios that showcase security evaluation

### Demo Scenarios

The FastAgent demo client should demonstrate:

1. **Allowed Operations**: Safe tool requests that pass security rules
2. **Denied Operations**: Dangerous commands that are automatically blocked
3. **Sampled Operations**: Requests that trigger AI evaluation for context-aware decisions
4. **Circuit Breaker**: What happens when the AI service is unavailable

## Implementation Prioritization

### Day 1 Prototype (8 hours)

**Morning (4 hours):**
1. Set up project structure with modern tooling (30 min)
2. Implement domain models with Pydantic 2.0 (1 hour)
3. Create basic SecurityPolicy with rule matching (1.5 hours)
4. Implement secure prompt builder with sanitization (1 hour)

**Afternoon (4 hours):**
1. Add circuit breaker for AI sampling (1 hour)
2. Implement error handling and logging (1 hour)
3. Create basic MCP server with STDIO transport (1 hour)
4. Add health checks and basic monitoring (30 min)
5. Testing and documentation (30 min)

**FastAgent Demo Setup:**
- After completing the core server, set up FastAgent as a demo client
- Configure it to connect to the Superego MCP server
- Create demo scenarios that showcase the security evaluation features
- Ensure the `just demo` command launches the client properly

### Day 2-3 Enhancements

- Add file-based configuration with hot reload
- Implement audit logging with TTL support
- Add HTTP/SSE transports
- Create MCP resource endpoints
- Enhance rule matching with glob patterns

### Future Iterations

- Extract registry pattern into separate library
- Add web dashboard for monitoring
- Implement distributed state management
- Add advanced AI workflow patterns (evaluator-optimizer, router patterns)

## Security Considerations

### Input Validation
- All inputs validated with Pydantic models
- Tool names restricted to alphanumeric patterns
- Parameters deep-sanitized before processing
- Path traversal protection on all file operations

### Prompt Security
- Template-based prompt construction
- Input sanitization before template rendering
- Length limits on all string inputs
- Control character filtering

### Error Handling
- No sensitive information in error messages
- Structured logging with context
- User-friendly feedback messages
- Fail-closed approach for security errors

## Configuration Example

```yaml
# config/superego.yaml
server:
  name: "Superego MCP Server"
  version: "1.0.0"

rules:
  - id: "block-dangerous"
    priority: 1
    conditions:
      tool_name: ["rm", "sudo", "chmod"]
    action: "deny"
    reason: "Dangerous system command"
    
  - id: "sample-writes"
    priority: 10
    conditions:
      tool_name: ["write", "edit"]
    action: "sample"
    sampling_guidance: "Evaluate if modification is safe and necessary"
    
  - id: "allow-reads"
    priority: 99
    conditions:
      tool_name: ["read", "ls", "grep"]
    action: "allow"

monitoring:
  health_check_interval: 30
  metrics_enabled: true
  
ai_sampling:
  timeout_seconds: 10
  fallback_action: "deny"
  circuit_breaker:
    failure_threshold: 3
    recovery_timeout: 30
```

## Conclusion

This refined design provides a solid foundation for the Superego MCP Server that can be implemented in a day while addressing critical security and reliability concerns. The architecture supports future enhancements through its modular design and registry pattern, while the focus on domain-driven design ensures clean separation of concerns.

The implementation prioritizes:
- **Security**: Input sanitization, secure prompt construction, fail-closed defaults
- **Reliability**: Circuit breakers, health checks, comprehensive error handling
- **Maintainability**: Clean architecture, domain models, modern Python tooling
- **Extensibility**: Registry pattern, pluggable components, clear interfaces

With this design, you can build a functional prototype quickly while maintaining a clear path for future enhancements and potential library extraction.