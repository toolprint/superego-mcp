# Superego MCP Server - Implementation Specification

**Status:** Ready for Implementation  
**Authors:** AI Engineer Agent  
**Date:** 2025-08-11  
**Version:** 1.0

## Overview

This specification defines the implementation of Superego MCP Server, an intelligent tool request interception and evaluation system that acts as a security and governance layer for AI agents. The server uses rule-based categorization combined with AI-powered sampling decisions to determine whether tool requests should be allowed or denied.

## Background/Problem Statement

AI agents can execute potentially dangerous operations through tool calls without adequate oversight. Current solutions lack:

- **Dynamic rule-based evaluation** of tool requests based on configurable policies
- **AI-powered decision making** for complex scenarios requiring contextual judgment
- **Real-time configuration updates** without service restart
- **Comprehensive audit trails** for compliance and forensic analysis
- **Integration with Claude Code PreToolUse hooks** for seamless workflow protection

## Goals

- ✅ **Day 1 Prototype**: Implement a functional security evaluation server in 8 hours
- ✅ **Rule-Based Protection**: Priority-based rule matching inspired by CCO-MCP patterns
- ✅ **AI-Powered Decisions**: Sampling-based evaluation for complex security scenarios
- ✅ **Circuit Breaker Resilience**: Graceful degradation when AI services are unavailable
- ✅ **Security-First Design**: Input sanitization and prompt injection protection
- ✅ **Modern Python Tooling**: uv, ruff, hatchling, justfile for development workflow
- ✅ **Demo Client**: FastAgent client to test sampling before Claude Code supports it

## Non-Goals

- ❌ **Authentication/Authorization**: Single user, single tenant for prototype
- ❌ **Distributed Scaling**: Single-node deployment initially
- ❌ **Advanced FastAgent Integration**: Complex workflow patterns deferred to Phase 2
- ❌ **Web Dashboard**: GUI interface for future enhancement
- ❌ **Database Backends**: File-based storage for simplicity

## Technical Dependencies

### Core Dependencies
```toml
[project]
name = "superego-mcp"
version = "0.1.0"
description = "Intelligent tool request interception for AI agents"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0.0",           # MCP server framework with sampling support
    "pydantic>=2.0.0",          # Data validation and domain models
    "pyyaml>=6.0",              # Configuration file parsing
    "watchfiles>=0.20.0",       # File system monitoring for hot-reload
    "jinja2>=3.1.0",            # Secure prompt templating
    "httpx>=0.25.0",            # HTTP client for AI services
    "structlog>=23.0.0",        # Structured logging
    "psutil>=5.9.0",            # System metrics for health checks
]

[project.optional-dependencies]
demo = [
    "fast-agent-mcp>=0.1.0",    # Demo client for sampling testing
]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]
```

### External Services
- **LLM Provider**: Claude, OpenAI, or compatible API for AI sampling decisions
- **File System**: YAML configuration files with hot-reload capability

## Detailed Design

### Domain-Driven Architecture

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
│  │ (File Watch)  │  │ (Jinja2)        │  │ (In-Memory)  │   │
│  └───────────────┘  └─────────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Domain Models (Pydantic 2.0)

```python
from pydantic import BaseModel, Field, field_validator
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
    
    @field_validator('parameters')
    @classmethod
    def sanitize_parameters(cls, v):
        """Prevent parameter injection attacks"""
        return cls._deep_sanitize(v)

class SecurityRule(BaseModel):
    """Domain model for security rules"""
    id: str
    priority: int = Field(..., ge=0, le=999)
    conditions: Dict[str, Any]
    action: ToolAction
    reason: Optional[str] = None
    sampling_guidance: Optional[str] = None
    
    model_config = {"frozen": True}  # Immutable rules

class Decision(BaseModel):
    """Domain model for security decisions"""
    action: Literal["allow", "deny"]
    reason: str
    rule_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    processing_time_ms: int

class AuditEntry(BaseModel):
    """Domain model for audit trail entries"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request: ToolRequest
    decision: Decision
    rule_matches: list[str]
    ttl: Optional[datetime] = None
```

### Core Component Implementations

#### 1. Circuit Breaker for AI Sampling

```python
from typing import Literal, Optional
import asyncio

class CircuitBreaker:
    """Prevents cascade failures from AI service outages"""
    
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
                raise CircuitBreakerOpenError("AI service unavailable")
                
        try:
            async with asyncio.timeout(self.timeout_seconds):
                result = await func(*args, **kwargs)
                self._on_success()
                return result
        except Exception as e:
            self._on_failure()
            raise
```

#### 2. Secure Prompt Builder

```python
from jinja2 import Environment, select_autoescape
import re

class SecurePromptBuilder:
    """Secure prompt construction with input sanitization"""
    
    def __init__(self):
        self.env = Environment(
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
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
            'guidance': self._sanitize_text(rule.sampling_guidance or "")
        }
        
        template = self.env.from_string(EVALUATION_TEMPLATE)
        return template.render(**sanitized_data)
        
    def _sanitize_tool_name(self, tool_name: str) -> str:
        """Validate tool name against whitelist"""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', tool_name):
            raise ValueError(f"Invalid tool name: {tool_name}")
        return tool_name
```

#### 3. Error Handling Strategy

```python
from enum import Enum
import logging

class ErrorCode(str, Enum):
    RULE_EVALUATION_FAILED = "RULE_EVAL_001"
    AI_SERVICE_UNAVAILABLE = "AI_SVC_001"
    INVALID_CONFIGURATION = "CONFIG_001"
    PARAMETER_VALIDATION_FAILED = "PARAM_001"
    INTERNAL_ERROR = "INTERNAL_001"

class SuperegoError(Exception):
    """Base exception with user-friendly messages"""
    
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
    """Centralized error handling with structured logging"""
    
    def handle_error(self, error: Exception, request: ToolRequest) -> Decision:
        """Convert exceptions to security decisions"""
        if isinstance(error, SuperegoError):
            if error.code == ErrorCode.AI_SERVICE_UNAVAILABLE:
                # Fail open for AI service issues
                return Decision(
                    action="allow",
                    reason=error.user_message,
                    confidence=0.3,
                    processing_time_ms=0
                )
            else:
                # Fail closed for security errors
                return Decision(
                    action="deny", 
                    reason=error.user_message,
                    confidence=0.8,
                    processing_time_ms=0
                )
```

#### 4. Health Monitoring

```python
from typing import Dict, Literal
import psutil

class HealthStatus(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: Dict[str, 'ComponentHealth']
    metrics: Dict[str, float]

class HealthMonitor:
    """System health monitoring with component checks"""
    
    async def check_health(self) -> HealthStatus:
        """Comprehensive health check"""
        component_health = {}
        
        # Check each component
        for name, component in self.components.items():
            if hasattr(component, 'health_check'):
                try:
                    result = await component.health_check()
                    component_health[name] = ComponentHealth(
                        status=result.get('status', 'healthy'),
                        message=result.get('message')
                    )
                except Exception as e:
                    component_health[name] = ComponentHealth(
                        status="unhealthy",
                        message=str(e)
                    )
                    
        # Collect system metrics
        metrics = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'requests_per_second': self._get_request_rate(),
            'average_response_time_ms': self._get_avg_response_time()
        }
        
        return HealthStatus(
            status=self._determine_overall_status(component_health),
            components=component_health,
            metrics=metrics
        )
```

### Registry Pattern for Future Library Extraction

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable

class Registry(ABC):
    """Abstract base for modular registries"""
    
    @abstractmethod
    def register(self, key: str, value: Any) -> None: ...
        
    @abstractmethod  
    def get(self, key: str) -> Any: ...
        
    @abstractmethod
    def list_keys(self) -> list[str]: ...

class PromptRegistry(Registry):
    """Registry for secure prompt templates"""
    
    def __init__(self):
        self._prompts: Dict[str, Template] = {}
        
    def register(self, key: str, template: Template) -> None:
        self._prompts[key] = template
        
    def get(self, key: str) -> Template:
        if key not in self._prompts:
            raise KeyError(f"Prompt '{key}' not found")
        return self._prompts[key]

# Global registry instances for future extraction
prompt_registry = PromptRegistry()
tool_registry = ToolRegistry() 
resource_registry = ResourceRegistry()
```

### FastMCP Integration

```python
from fastmcp import FastMCP, Context

mcp = FastMCP("Superego MCP Server")

@mcp.tool
async def evaluate_tool_request(
    tool_name: str,
    parameters: dict,
    session_id: str,
    agent_id: str,
    cwd: str,
    ctx: Context
) -> dict:
    """Evaluate tool request for security compliance"""
    
    request = ToolRequest(
        tool_name=tool_name,
        parameters=parameters,
        session_id=session_id,
        agent_id=agent_id,
        cwd=cwd
    )
    
    # Apply security policy evaluation
    decision = await security_policy.evaluate(request)
    
    # Log for audit trail
    await audit_service.log_decision(request, decision)
    
    return {
        "action": decision.action,
        "reason": decision.reason,
        "confidence": decision.confidence
    }

@mcp.resource("config://rules")
async def get_current_rules() -> str:
    """Expose current security rules as MCP resource"""
    return yaml.dump(config_manager.get_rules())

@mcp.resource("audit://recent")
async def get_recent_audit_entries() -> str:
    """Expose recent audit entries for monitoring"""
    entries = audit_logger.get_recent_entries(limit=100)
    return json.dumps([entry.model_dump() for entry in entries])
```

## User Experience

### 1. Installation and Setup

```bash
# Install with uv
uv add superego-mcp

# Setup project structure  
just setup

# Configure rules
vim config/rules.yaml

# Start server
just dev
```

### 2. Claude Code Integration

```bash
# Add to Claude Code hooks configuration
echo "PreToolUse: superego-mcp --transport stdio --config config/superego.yaml" >> ~/.claude/hooks.yaml
```

### 3. Demo Client Testing

```bash
# Launch FastAgent demo client to test sampling
just demo

# Test dangerous command (should be denied)
> rm -rf /

# Test file operation (should trigger AI sampling)  
> edit important-file.txt

# Test safe operation (should be allowed)
> ls -la
```

## FastAgent Demo Client

### Purpose

**FastAgent serves as a working demo client for testing the Superego MCP server's sampling capabilities.** Since Claude Code does not yet support MCP sampling features, FastAgent provides a way to demonstrate and test the security evaluation functionality during development.

### Critical Implementation Requirements

> ⚠️ **CRITICAL**: The implementation agent MUST read the latest FastAgent documentation on GitHub to understand how to properly set up FastAgent with sampling configuration and annotations. This includes:
> - Understanding the MCP sampling request/response protocol
> - Configuring FastAgent to connect to the Superego MCP server  
> - Setting up proper agent definitions with server references
> - Implementing demo scenarios that showcase security evaluation

### FastAgent Configuration

```yaml
# fastagent.config.yaml
mcp:
  servers:
    superego:
      transport: "http"
      url: "http://localhost:8080/mcp"
      sampling:
        model: "claude-3-sonnet"
```

```python
# demo_agent.py
import fast_agent as fast

@fast.agent(
    name="security_demo",
    instruction="You are a demo agent for testing security evaluation",
    servers=["superego"]
)
async def main():
    async with fast.run() as agent:
        await agent.interactive()
```

### Demo Scenarios

The FastAgent demo should demonstrate:

1. **Allowed Operations**: Safe tool requests (`read`, `ls`, `grep`)  
2. **Denied Operations**: Dangerous commands (`rm`, `sudo`, `chmod`)
3. **Sampled Operations**: Complex requests requiring AI evaluation (`edit`, `write`)
4. **Circuit Breaker**: Behavior when AI service is unavailable

## Testing Strategy

### Unit Tests

```python
# Test rule matching logic
def test_priority_rule_matching():
    """Validates priority-based rule evaluation"""
    rules = [
        SecurityRule(id="high", priority=1, action=ToolAction.DENY),
        SecurityRule(id="low", priority=99, action=ToolAction.ALLOW)
    ]
    assert rule_engine.match(request).rule_id == "high"

# Test parameter sanitization  
def test_parameter_sanitization():
    """Ensures prompt injection protection"""
    malicious_params = {"cmd": "rm -rf / && echo 'INJECTED'"}
    sanitized = prompt_builder._sanitize_parameters(malicious_params)
    assert "INJECTED" not in str(sanitized)

# Test circuit breaker
async def test_circuit_breaker_fallback():
    """Validates graceful degradation on AI service failure"""
    breaker = CircuitBreaker(failure_threshold=1)
    
    # Simulate failures
    with pytest.raises(Exception):
        await breaker.call(failing_ai_service)
        
    # Should fallback to deny decision
    decision = await decision_engine.evaluate(request, rule)
    assert decision.action == "deny"
    assert "AI evaluation unavailable" in decision.reason
```

### Integration Tests

```python
async def test_end_to_end_request_processing():
    """Tests complete request flow from transport to decision"""
    # Setup test server
    async with TestMCPServer() as server:
        # Send tool request
        response = await server.call_tool("evaluate_tool_request", {
            "tool_name": "rm",
            "parameters": {"path": "/important/file"},
            "session_id": "test-session",
            "agent_id": "test-agent", 
            "cwd": "/home/user"
        })
        
        # Verify security decision
        assert response["action"] == "deny"
        assert "Dangerous system command" in response["reason"]
```

### Performance Tests

```python
def test_rule_evaluation_latency():
    """Ensures rule matching completes under 10ms"""
    start_time = time.perf_counter()
    decision = rule_engine.evaluate(request)
    elapsed = time.perf_counter() - start_time
    
    assert elapsed < 0.01  # 10ms threshold
    assert decision.processing_time_ms < 10

async def test_concurrent_request_handling():
    """Validates handling of multiple simultaneous requests"""
    requests = [generate_test_request() for _ in range(100)]
    
    start_time = time.perf_counter()
    responses = await asyncio.gather(*[
        security_policy.evaluate(req) for req in requests
    ])
    elapsed = time.perf_counter() - start_time
    
    assert len(responses) == 100
    assert elapsed < 1.0  # Complete 100 requests in under 1 second
```

## Performance Considerations

### Latency Targets
- **Rule Evaluation**: < 10ms for 90% of requests
- **AI Sampling**: < 2 seconds with 10-second timeout
- **Audit Logging**: < 1ms (async background processing)

### Optimization Strategies
- **Rule Caching**: In-memory rule compilation for fast matching
- **Connection Pooling**: Reuse HTTP connections for AI service calls
- **Async Processing**: Non-blocking I/O for all operations
- **Circuit Breaking**: Prevent slow AI calls from blocking requests

### Resource Limits
- **Memory Usage**: < 100MB for rule storage and audit cache
- **CPU Usage**: < 5% baseline with burst capacity for AI calls  
- **File Descriptors**: Efficient file watching without resource leaks

## Security Considerations

### Input Validation
- **Tool Name Whitelist**: Regex validation `^[a-zA-Z_][a-zA-Z0-9_]*$`
- **Parameter Sanitization**: Deep sanitization with length limits
- **Path Traversal Protection**: Remove `../` patterns from paths
- **Control Character Filtering**: Strip non-printable characters

### Prompt Security  
- **Template-Based Construction**: Use Jinja2 with auto-escaping
- **Input Sanitization**: Clean all user inputs before template rendering
- **Length Limits**: Prevent DoS via oversized prompts
- **Injection Protection**: Escape special characters and control sequences

### Error Handling
- **No Information Leakage**: Generic error messages for security failures  
- **Structured Logging**: Detailed logs without sensitive data exposure
- **Fail-Closed Defaults**: Deny requests on security validation errors
- **Fail-Open Option**: Allow requests on AI service availability issues

## Documentation

### API Documentation
- **OpenAPI Spec**: Auto-generated from FastMCP annotations
- **MCP Protocol**: Tool and resource endpoint specifications
- **Configuration Schema**: YAML validation schema documentation

### User Guides  
- **Installation Guide**: Setup and configuration walkthrough
- **Rule Configuration**: Security policy creation examples
- **Integration Guide**: Claude Code hook setup instructions
- **Troubleshooting**: Common issues and solutions

### Developer Documentation
- **Architecture Overview**: System design and component interactions
- **Extension Guide**: Adding new rule types and storage backends
- **Testing Guide**: How to run and extend the test suite

## Implementation Phases

### Phase 1: Core Foundation (Day 1 - 8 hours)

**Morning (4 hours):**
1. **Project Setup** (30 min)
   - Initialize project with uv, ruff, hatchling
   - Create justfile for task automation
   - Setup basic directory structure

2. **Domain Models** (1 hour)  
   - Implement Pydantic 2.0 domain models
   - Add validation and sanitization logic
   - Create error handling classes

3. **Security Policy Engine** (1.5 hours)
   - Rule matching with priority system
   - File-based rule storage
   - Basic configuration loading

4. **Secure Prompt Builder** (1 hour)
   - Jinja2 template integration
   - Input sanitization implementation
   - Template validation

**Afternoon (4 hours):**
1. **Circuit Breaker Implementation** (1 hour)
   - Async timeout handling
   - State management (open/closed/half-open)
   - Fallback decision logic

2. **Error Handling & Logging** (1 hour)  
   - Structured error responses
   - Audit trail logging
   - Health check endpoints

3. **FastMCP Server Integration** (1 hour)
   - Tool and resource endpoint creation
   - STDIO transport configuration
   - Basic request processing

4. **FastAgent Demo Setup** (1 hour)
   - Configure demo client connection
   - Create test scenarios
   - Verify sampling functionality

### Phase 2: Enhancement (Days 2-3)
- Configuration hot-reload with file watching
- HTTP/SSE transport support  
- Advanced rule pattern matching
- Performance optimization

### Phase 3: Production Readiness (Future)
- Database storage backends
- Distributed state management
- Web dashboard interface
- Advanced analytics and reporting

## Open Questions

1. **AI Provider Selection**: Should we support multiple LLM providers simultaneously or stick to a primary provider with fallback?

2. **Rule Validation**: How strict should rule schema validation be? Should invalid rules block server startup or be ignored with warnings?

3. **Audit Retention**: What's the appropriate default TTL for audit entries? Should it be configurable per rule or globally?

4. **Performance Tuning**: Should we implement request queuing for AI sampling to prevent overwhelming the service?

5. **Configuration Migration**: How should we handle backward compatibility when rule schema evolves?

## References

### Design Documents
- [Original Design Document](docs/DESIGN.md)
- [Architectural Review](docs/DESIGN_REVIEW.md)  
- [Final Design Document](docs/DESIGN_FINAL.md)

### External Documentation
- [FastMCP 2.0 Documentation](https://github.com/jlowin/fastmcp) - Core MCP framework
- [FastAgent Documentation](https://github.com/evalstate/fast-agent) - Demo client framework  
- [Claude Code Hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) - Integration schemas
- [CCO-MCP](https://github.com/toolprint/cco-mcp) - Rule matching patterns
- [Model Context Protocol](https://modelcontextprotocol.io) - Protocol specification

### Technology References
- [Pydantic 2.0](https://docs.pydantic.dev/2.0/) - Data validation and serialization
- [Jinja2 Security](https://jinja.palletsprojects.com/en/3.1.x/api/#autoescaping) - Template security
- [Structured Logging](https://www.structlog.org/en/stable/) - Audit trail implementation
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html) - Resilience patterns

---

**Implementation Note**: This specification prioritizes rapid prototype development while maintaining security best practices. The modular design enables future enhancements without requiring architectural changes to the core system.