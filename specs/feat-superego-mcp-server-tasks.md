# Task Breakdown: Superego MCP Server
Generated: 2025-08-11
Source: specs/feat-superego-mcp-server.md

## Overview

This task breakdown decomposes the Superego MCP Server specification into actionable implementation tasks. The system is an intelligent tool request interception and evaluation system that acts as a security and governance layer for AI agents, using rule-based categorization combined with AI-powered sampling decisions.

**Target**: Day 1 prototype (8 hours) with modern Python tooling (uv, ruff, hatchling, justfile).

## Phase 1: Foundation (Morning - 4 hours)

### Task 1.1: Project Setup and Structure
**Description**: Initialize Python project with modern tooling and dependencies
**Size**: Small
**Priority**: High
**Dependencies**: None
**Can run parallel with**: None (foundation task)

**Technical Requirements**:
- Python 3.11+ with uv package manager
- Modern Python tooling: ruff, hatchling, mypy
- Project structure following domain-driven architecture
- Justfile for task automation

**Dependencies from spec**:
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

**Directory Structure**:
```
superego-mcp/
├── pyproject.toml
├── justfile
├── src/superego_mcp/
│   ├── __init__.py
│   ├── domain/          # Domain models and business logic
│   ├── infrastructure/   # External services and adapters  
│   ├── presentation/    # MCP server endpoints
│   └── main.py
├── config/
│   ├── rules.yaml
│   └── server.yaml
├── tests/
└── demo/               # FastAgent demo client
```

**Implementation Steps**:
1. Initialize project: `uv init superego-mcp`
2. Create pyproject.toml with dependencies
3. Setup justfile with common tasks (dev, test, lint, demo)
4. Create directory structure
5. Initialize git repository
6. Setup basic README.md

**Acceptance Criteria**:
- [ ] Project initializes with `uv install`
- [ ] All dependencies resolve correctly
- [ ] Directory structure matches domain architecture
- [ ] Justfile provides dev, test, lint tasks
- [ ] Basic imports work (from superego_mcp import domain)
- [ ] Tests: `uv run pytest` executes (even if no tests yet)

### Task 1.2: Domain Models Implementation  
**Description**: Implement Pydantic 2.0 domain models with validation and sanitization
**Size**: Medium
**Priority**: High
**Dependencies**: Task 1.1 (Project Setup)
**Can run parallel with**: None (core models needed by other tasks)

**Technical Requirements**:
- Pydantic 2.0 BaseModel classes
- Input validation and sanitization
- Immutable security rules
- Error handling domain models
- Type safety and field validation

**Domain Models from spec**:
```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal, Optional, Dict, Any
from enum import Enum
import uuid

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

**Error Handling Models**:
```python
from enum import Enum

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
```

**Implementation Steps**:
1. Create src/superego_mcp/domain/models.py
2. Implement all domain models with Pydantic 2.0 syntax
3. Add parameter sanitization methods
4. Create error handling classes
5. Add comprehensive type hints
6. Implement model validation tests

**Acceptance Criteria**:
- [ ] All models instantiate correctly with valid data
- [ ] Parameter sanitization prevents injection attacks
- [ ] SecurityRule model is immutable (frozen=True)
- [ ] Field validation works (tool_name regex, priority range)
- [ ] Error classes provide structured error information
- [ ] Tests: Model validation, sanitization, error handling

### Task 1.3: Security Policy Engine
**Description**: Implement rule-based evaluation with priority system and file storage
**Size**: Large
**Priority**: High  
**Dependencies**: Task 1.2 (Domain Models)
**Can run parallel with**: Task 1.4 (Prompt Builder) after models complete

**Technical Requirements**:
- Priority-based rule matching inspired by CCO-MCP patterns
- File-based rule storage with YAML format
- Rule evaluation with context matching
- Performance targets: < 10ms for 90% of requests

**Rule Matching Implementation**:
```python
from typing import List, Optional
import yaml
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
                if tool_pattern != request.tool_name:
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
                if request.parameters[key] != expected:
                    return False
                    
        # Path-based matching  
        if 'cwd_pattern' in conditions:
            import re
            pattern = conditions['cwd_pattern']
            if not re.match(pattern, request.cwd):
                return False
                
        return True
```

**Sample Rules Configuration**:
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

**Implementation Steps**:
1. Create src/superego_mcp/domain/security_policy.py
2. Implement SecurityPolicyEngine with rule loading
3. Add rule matching logic with priority handling
4. Create sample rules.yaml configuration
5. Add performance monitoring (< 10ms target)
6. Implement error handling for rule evaluation failures

**Acceptance Criteria**:
- [ ] Rules load correctly from YAML file
- [ ] Priority-based matching works (lower number = higher priority)
- [ ] Rule conditions match tool names, parameters, paths
- [ ] Performance meets < 10ms target for rule evaluation
- [ ] Error handling for missing/invalid rule files
- [ ] Tests: Rule loading, matching logic, priority ordering

### Task 1.4: Secure Prompt Builder
**Description**: Implement Jinja2-based prompt construction with input sanitization
**Size**: Medium
**Priority**: High
**Dependencies**: Task 1.2 (Domain Models)
**Can run parallel with**: Task 1.3 (Security Policy) after models complete

**Technical Requirements**:
- Jinja2 templates with auto-escaping enabled
- Comprehensive input sanitization
- Prompt injection protection
- Template validation and security

**Secure Prompt Implementation**:
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

**Implementation Steps**:
1. Create src/superego_mcp/infrastructure/prompt_builder.py
2. Implement SecurePromptBuilder with Jinja2 integration
3. Add comprehensive input sanitization methods
4. Create evaluation prompt template
5. Add validation for template security
6. Implement prompt injection protection tests

**Acceptance Criteria**:
- [ ] Jinja2 templates render with auto-escaping enabled
- [ ] Input sanitization prevents injection attacks
- [ ] Tool names validated against regex whitelist
- [ ] Parameter values recursively sanitized with length limits
- [ ] Path sanitization removes directory traversal patterns
- [ ] Control characters stripped from all inputs
- [ ] Tests: Injection attempts, sanitization edge cases, template security

## Phase 1: Core Infrastructure (Afternoon - 4 hours)

### Task 1.5: Circuit Breaker Implementation
**Description**: Implement async circuit breaker for AI service resilience  
**Size**: Medium
**Priority**: High
**Dependencies**: Task 1.2 (Domain Models)
**Can run parallel with**: Task 1.6 (Error Handling)

**Technical Requirements**:
- Circuit breaker states: closed, open, half-open
- Configurable failure threshold and recovery timeout
- Async timeout handling with proper exception management
- Fallback decision logic for service failures

**Circuit Breaker Implementation**:
```python
from typing import Literal, Optional, Callable, Any
import asyncio
import time
import logging

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass

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
        self.logger = logging.getLogger(__name__)
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
                self.logger.info("Circuit breaker entering half-open state")
            else:
                raise CircuitBreakerOpenError("AI service unavailable - circuit breaker open")
                
        try:
            async with asyncio.timeout(self.timeout_seconds):
                result = await func(*args, **kwargs)
                self._on_success()
                return result
                
        except asyncio.TimeoutError:
            self.logger.error(f"AI service call timed out after {self.timeout_seconds}s")
            self._on_failure()
            raise CircuitBreakerOpenError("AI service timeout")
            
        except Exception as e:
            self.logger.error(f"AI service call failed: {e}")
            self._on_failure()
            raise
            
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
        
    def _on_success(self) -> None:
        """Handle successful operation"""
        if self.state in ["half_open", "open"]:
            self.logger.info("Circuit breaker reset to closed state")
            
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None
        
    def _on_failure(self) -> None:
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open" 
            self.logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )
        elif self.state == "half_open":
            self.state = "open"
            self.logger.warning("Circuit breaker returned to open state")
            
    def get_state(self) -> dict:
        """Get current circuit breaker state for monitoring"""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }
```

**Implementation Steps**:
1. Create src/superego_mcp/infrastructure/circuit_breaker.py
2. Implement CircuitBreaker with async timeout handling
3. Add state management (closed/open/half-open)
4. Create fallback decision logic integration
5. Add monitoring and logging capabilities
6. Implement comprehensive state transition tests

**Acceptance Criteria**:
- [ ] Circuit breaker opens after configured failure threshold
- [ ] Half-open state attempts recovery after timeout
- [ ] Async timeout handling works correctly with proper exceptions
- [ ] State transitions logged appropriately  
- [ ] Monitoring provides current state and failure metrics
- [ ] Tests: State transitions, timeout handling, recovery behavior

### Task 1.6: Error Handling & Logging
**Description**: Implement centralized error handling with structured audit logging
**Size**: Medium  
**Priority**: High
**Dependencies**: Task 1.2 (Domain Models), Task 1.5 (Circuit Breaker)
**Can run parallel with**: Task 1.7 (FastMCP Integration)

**Technical Requirements**:
- Structured error responses with user-friendly messages  
- Audit trail logging with structured data
- Health check endpoints with component status
- Fail-closed for security errors, fail-open for availability issues

**Error Handler Implementation**:
```python
import logging
import structlog
import time
from typing import Dict, Any, List

class ErrorHandler:
    """Centralized error handling with structured logging"""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        
    def handle_error(self, error: Exception, request: ToolRequest) -> Decision:
        """Convert exceptions to security decisions"""
        start_time = time.perf_counter()
        processing_time = int((time.perf_counter() - start_time) * 1000)
        
        if isinstance(error, SuperegoError):
            return self._handle_superego_error(error, request, processing_time)
        elif isinstance(error, CircuitBreakerOpenError):
            return self._handle_circuit_breaker_error(error, request, processing_time)
        else:
            return self._handle_unexpected_error(error, request, processing_time)
            
    def _handle_superego_error(
        self, 
        error: SuperegoError, 
        request: ToolRequest,
        processing_time: int
    ) -> Decision:
        """Handle known SuperegoError instances"""
        
        # Log structured error information
        self.logger.error(
            "Superego error occurred",
            error_code=error.code.value,
            error_message=error.message,
            user_message=error.user_message,
            context=error.context,
            tool_name=request.tool_name,
            session_id=request.session_id,
            agent_id=request.agent_id
        )
        
        if error.code == ErrorCode.AI_SERVICE_UNAVAILABLE:
            # Fail open for AI service issues - allow with low confidence
            return Decision(
                action="allow",
                reason=error.user_message,
                confidence=0.3,
                processing_time_ms=processing_time
            )
        else:
            # Fail closed for security errors - deny with high confidence  
            return Decision(
                action="deny",
                reason=error.user_message,
                confidence=0.8,
                processing_time_ms=processing_time
            )
            
    def _handle_circuit_breaker_error(
        self,
        error: CircuitBreakerOpenError, 
        request: ToolRequest,
        processing_time: int
    ) -> Decision:
        """Handle circuit breaker failures"""
        
        self.logger.warning(
            "Circuit breaker prevented AI service call",
            tool_name=request.tool_name,
            session_id=request.session_id,
            error_message=str(error)
        )
        
        # Fail open for circuit breaker - allow with very low confidence
        return Decision(
            action="allow",
            reason="AI evaluation unavailable - allowing with caution",
            confidence=0.2,
            processing_time_ms=processing_time
        )
        
    def _handle_unexpected_error(
        self,
        error: Exception,
        request: ToolRequest, 
        processing_time: int
    ) -> Decision:
        """Handle unexpected exceptions"""
        
        self.logger.error(
            "Unexpected error during request processing",
            error_type=type(error).__name__,
            error_message=str(error),
            tool_name=request.tool_name,
            session_id=request.session_id,
            exc_info=True  # Include full traceback
        )
        
        # Fail closed for unexpected errors - security first
        return Decision(
            action="deny",
            reason="Internal security evaluation error", 
            confidence=0.9,
            processing_time_ms=processing_time
        )

class AuditLogger:
    """Structured audit logging for security decisions"""
    
    def __init__(self):
        self.logger = structlog.get_logger("audit")
        self.entries: List[AuditEntry] = []  # In-memory for Day 1
        
    async def log_decision(
        self, 
        request: ToolRequest, 
        decision: Decision,
        rule_matches: List[str] = None
    ) -> None:
        """Log security decision to audit trail"""
        
        entry = AuditEntry(
            request=request,
            decision=decision,
            rule_matches=rule_matches or []
        )
        
        # Add to in-memory storage
        self.entries.append(entry)
        
        # Structured logging
        await self.logger.ainfo(
            "Security decision logged",
            audit_id=entry.id,
            tool_name=request.tool_name,
            action=decision.action,
            reason=decision.reason,
            confidence=decision.confidence,
            processing_time_ms=decision.processing_time_ms,
            rule_id=decision.rule_id,
            rule_matches=rule_matches,
            session_id=request.session_id,
            agent_id=request.agent_id,
            cwd=request.cwd,
            timestamp=entry.timestamp.isoformat()
        )
        
    def get_recent_entries(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent audit entries for monitoring"""
        return sorted(self.entries, key=lambda e: e.timestamp, reverse=True)[:limit]
        
    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics for monitoring"""
        if not self.entries:
            return {"total": 0}
            
        total = len(self.entries)
        allowed = sum(1 for e in self.entries if e.decision.action == "allow")
        denied = total - allowed
        
        avg_processing_time = sum(e.decision.processing_time_ms for e in self.entries) / total
        
        return {
            "total": total,
            "allowed": allowed, 
            "denied": denied,
            "allow_rate": allowed / total,
            "avg_processing_time_ms": avg_processing_time
        }
```

**Health Monitoring Implementation**:
```python
from typing import Dict, Literal
import psutil
from datetime import datetime

class ComponentHealth(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    message: Optional[str] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)

class HealthStatus(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]  
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: Dict[str, ComponentHealth]
    metrics: Dict[str, float]

class HealthMonitor:
    """System health monitoring with component checks"""
    
    def __init__(self):
        self.components = {}
        
    def register_component(self, name: str, component: Any) -> None:
        """Register component for health monitoring"""
        self.components[name] = component
        
    async def check_health(self) -> HealthStatus:
        """Comprehensive health check"""
        component_health = {}
        
        # Check each registered component
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
            else:
                # Default healthy for components without health checks
                component_health[name] = ComponentHealth(status="healthy")
                
        # Collect system metrics
        metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage_percent': psutil.disk_usage('/').percent
        }
        
        # Determine overall status
        overall_status = self._determine_overall_status(component_health)
        
        return HealthStatus(
            status=overall_status,
            components=component_health,
            metrics=metrics
        )
        
    def _determine_overall_status(
        self, 
        component_health: Dict[str, ComponentHealth]
    ) -> Literal["healthy", "degraded", "unhealthy"]:
        """Determine overall health from component statuses"""
        
        if not component_health:
            return "healthy"
            
        statuses = [comp.status for comp in component_health.values()]
        
        if any(status == "unhealthy" for status in statuses):
            return "unhealthy"
        elif any(status == "degraded" for status in statuses):
            return "degraded"
        else:
            return "healthy"
```

**Implementation Steps**:
1. Create src/superego_mcp/infrastructure/error_handler.py
2. Implement ErrorHandler with structured decision logic
3. Create AuditLogger with in-memory storage for Day 1
4. Add HealthMonitor with component registration
5. Setup structured logging configuration
6. Implement error handling and audit tests

**Acceptance Criteria**:
- [ ] SuperegoError instances handled with appropriate fail-open/fail-closed logic
- [ ] Circuit breaker errors result in fail-open decisions
- [ ] Unexpected errors result in fail-closed decisions
- [ ] Audit entries logged with structured data
- [ ] Health monitoring provides component status and system metrics
- [ ] Tests: Error handling decisions, audit logging, health checks

### Task 1.7: FastMCP Server Integration
**Description**: Implement MCP server with FastMCP 2.0 framework and STDIO transport
**Size**: Large
**Priority**: High  
**Dependencies**: Task 1.1 (Project Setup), Task 1.2 (Domain Models), Task 1.6 (Error Handling)
**Can run parallel with**: Task 1.8 (FastAgent Demo) after core functionality complete

**Technical Requirements**:
- FastMCP 2.0 server with tool and resource endpoints
- STDIO transport for Claude Code integration
- Request processing pipeline with security evaluation
- MCP resource endpoints for configuration exposure

**FastMCP Server Implementation**:
```python
from fastmcp import FastMCP, Context
import asyncio
import yaml
import json
from typing import Dict, Any

# Initialize FastMCP server
mcp = FastMCP("Superego MCP Server")

# Global components (will be injected)
security_policy: SecurityPolicyEngine = None
audit_logger: AuditLogger = None  
error_handler: ErrorHandler = None

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
    
    try:
        # Create domain model from request
        request = ToolRequest(
            tool_name=tool_name,
            parameters=parameters,
            session_id=session_id,
            agent_id=agent_id,
            cwd=cwd
        )
        
        # Apply security policy evaluation  
        decision = await security_policy.evaluate(request)
        
        # Extract rule matches for audit trail
        rule_matches = []
        if decision.rule_id:
            rule_matches.append(decision.rule_id)
            
        # Log decision to audit trail
        await audit_logger.log_decision(request, decision, rule_matches)
        
        # Return MCP-compatible response
        return {
            "action": decision.action,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "processing_time_ms": decision.processing_time_ms,
            "rule_id": decision.rule_id
        }
        
    except Exception as e:
        # Handle errors with centralized error handler
        fallback_decision = error_handler.handle_error(e, request)
        
        # Still log the fallback decision
        await audit_logger.log_decision(request, fallback_decision, [])
        
        return {
            "action": fallback_decision.action,
            "reason": fallback_decision.reason,
            "confidence": fallback_decision.confidence,
            "processing_time_ms": fallback_decision.processing_time_ms,
            "error": True
        }

@mcp.resource("config://rules")
async def get_current_rules() -> str:
    """Expose current security rules as MCP resource"""
    try:
        # Read current rules from file
        rules_data = {
            'rules': [rule.model_dump() for rule in security_policy.rules],
            'total_rules': len(security_policy.rules),
            'last_updated': security_policy.rules_file.stat().st_mtime
        }
        return yaml.dump(rules_data, default_flow_style=False)
        
    except Exception as e:
        return f"Error loading rules: {str(e)}"

@mcp.resource("audit://recent")
async def get_recent_audit_entries() -> str:
    """Expose recent audit entries for monitoring"""
    try:
        entries = audit_logger.get_recent_entries(limit=50)
        audit_data = {
            'entries': [entry.model_dump() for entry in entries],
            'stats': audit_logger.get_stats()
        }
        return json.dumps(audit_data, indent=2, default=str)
        
    except Exception as e:
        return f"Error loading audit entries: {str(e)}"

@mcp.resource("health://status")
async def get_health_status() -> str:
    """Expose system health status"""
    try:
        # Health check will be injected from main
        health_status = await health_monitor.check_health()
        return json.dumps(health_status.model_dump(), indent=2, default=str)
        
    except Exception as e:
        return f"Error checking health: {str(e)}"

# Server startup and dependency injection
async def create_server(
    security_policy_engine: SecurityPolicyEngine,
    audit_log: AuditLogger,
    err_handler: ErrorHandler,
    health_mon: HealthMonitor
) -> FastMCP:
    """Create and configure MCP server with dependencies"""
    
    # Inject dependencies into global scope (for Day 1 simplicity)
    global security_policy, audit_logger, error_handler, health_monitor
    security_policy = security_policy_engine
    audit_logger = audit_log
    error_handler = err_handler
    health_monitor = health_mon
    
    return mcp

# Entry point for STDIO transport
def run_stdio_server():
    """Run MCP server with STDIO transport for Claude Code"""
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_stdio_server()
```

**Main Application Bootstrap**:
```python
# src/superego_mcp/main.py
import asyncio
import logging
from pathlib import Path

from .domain.models import *
from .domain.security_policy import SecurityPolicyEngine  
from .infrastructure.error_handler import ErrorHandler, AuditLogger, HealthMonitor
from .infrastructure.circuit_breaker import CircuitBreaker
from .presentation.mcp_server import create_server, run_stdio_server

async def main():
    """Main application bootstrap"""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize configuration paths
    config_dir = Path("config")
    rules_file = config_dir / "rules.yaml"
    
    # Create components
    security_policy = SecurityPolicyEngine(rules_file)
    error_handler = ErrorHandler()
    audit_logger = AuditLogger()
    health_monitor = HealthMonitor()
    
    # Register components for health monitoring
    health_monitor.register_component("security_policy", security_policy)
    health_monitor.register_component("audit_logger", audit_logger)
    
    # Create and run MCP server
    server = await create_server(
        security_policy, 
        audit_logger, 
        error_handler,
        health_monitor
    )
    
    # Run with STDIO transport
    print("Starting Superego MCP Server with STDIO transport...")
    run_stdio_server()

if __name__ == "__main__":
    asyncio.run(main())
```

**Implementation Steps**:
1. Create src/superego_mcp/presentation/mcp_server.py  
2. Implement FastMCP tool and resource endpoints
3. Add request processing pipeline with error handling
4. Create main.py with component bootstrapping
5. Add STDIO transport configuration
6. Implement server integration tests

**Acceptance Criteria**:
- [ ] FastMCP server starts successfully with STDIO transport
- [ ] evaluate_tool_request tool processes requests correctly
- [ ] Resource endpoints expose rules, audit data, health status
- [ ] Error handling integrates with centralized ErrorHandler
- [ ] Component dependency injection works correctly
- [ ] Tests: Tool invocation, resource access, error scenarios

### Task 1.8: FastAgent Demo Setup
**Description**: Configure FastAgent demo client to test sampling functionality  
**Size**: Medium
**Priority**: Medium
**Dependencies**: Task 1.7 (FastMCP Server)
**Can run parallel with**: None (requires working MCP server)

**Technical Requirements**:
- FastAgent client configured to connect to Superego MCP server
- Demo scenarios showcasing security evaluation
- Test cases for allowed, denied, and sampled operations
- Integration testing with actual sampling calls

**⚠️ CRITICAL**: The implementation team MUST read the latest FastAgent documentation on GitHub to understand:
- MCP sampling request/response protocol  
- FastAgent configuration with server references
- Agent definitions and interactive mode setup
- Proper demo scenario implementation

**FastAgent Configuration**:
```yaml
# demo/fastagent.config.yaml  
mcp:
  servers:
    superego:
      transport: "stdio"  
      command: "uv"
      args: ["run", "python", "-m", "superego_mcp.main"]
      cwd: "../"
      sampling:
        enabled: true
        model: "claude-3-sonnet"
        timeout: 30
```

**Demo Agent Implementation**:
```python
# demo/security_demo_agent.py
import fast_agent as fast
import asyncio

@fast.agent(
    name="security_demo",
    instruction="""You are a security demo agent testing the Superego MCP server.
    
Your job is to demonstrate security evaluation by attempting various tool operations:
1. Safe operations that should be allowed
2. Dangerous operations that should be denied  
3. Complex operations that require AI sampling evaluation

Always explain what you're testing and what result you expect.""",
    servers=["superego"]
)
async def main():
    """Demo agent showcasing security evaluation"""
    
    print("🛡️ Superego Security Demo Agent")
    print("This agent will test various tool operations through the security layer.")
    print("Watch how different requests are allowed, denied, or sampled.\n")
    
    async with fast.run() as agent:
        # Run interactive mode for manual testing
        await agent.interactive()

if __name__ == "__main__":
    asyncio.run(main())
```

**Automated Demo Scenarios**:
```python
# demo/automated_demo.py
import fast_agent as fast
import asyncio
from typing import List, Tuple

class SecurityDemoScenarios:
    """Automated demo scenarios for security evaluation testing"""
    
    def __init__(self):
        self.scenarios = [
            # Safe operations (should be allowed)
            ("read", {"file": "config.yaml"}, "ALLOW", "Safe read operation"),
            ("ls", {"path": "."}, "ALLOW", "Directory listing"),
            ("grep", {"pattern": "test", "file": "*.py"}, "ALLOW", "Text search"),
            
            # Dangerous operations (should be denied)
            ("rm", {"path": "/important/file"}, "DENY", "Dangerous deletion"),
            ("sudo", {"command": "apt update"}, "DENY", "Privileged command"),
            ("chmod", {"mode": "777", "file": "/etc/passwd"}, "DENY", "Permission change"),
            
            # Complex operations (should trigger sampling)
            ("edit", {"file": "production.config"}, "SAMPLE", "Production file edit"),
            ("write", {"file": "database.sql", "content": "DROP TABLE users;"}, "SAMPLE", "Database operation"),
            ("delete", {"file": "backup/important.zip"}, "SAMPLE", "Backup deletion"),
        ]
        
    async def run_all_scenarios(self):
        """Execute all demo scenarios"""
        print("🧪 Running Automated Security Demo Scenarios\n")
        
        results = []
        for tool_name, params, expected, description in self.scenarios:
            print(f"Testing: {description}")
            print(f"Tool: {tool_name}, Params: {params}")
            print(f"Expected: {expected}")
            
            try:
                # This would call the MCP server through FastAgent
                result = await self.call_security_evaluation(tool_name, params)
                
                print(f"Result: {result['action'].upper()}")
                print(f"Reason: {result['reason']}")
                print(f"Confidence: {result['confidence']}")
                
                # Check if result matches expectation
                success = self.check_expectation(result['action'], expected)
                results.append((description, success, result))
                
                print(f"✅ Match: {success}\n")
                
            except Exception as e:
                print(f"❌ Error: {e}\n")
                results.append((description, False, {"error": str(e)}))
                
        # Print summary
        self.print_summary(results)
        
    async def call_security_evaluation(self, tool_name: str, params: dict) -> dict:
        """Call security evaluation through FastAgent"""
        # This would be implemented using FastAgent's MCP integration
        # For Day 1, we'll simulate the call structure
        return {
            "action": "sample",  # Placeholder
            "reason": "Demo response",
            "confidence": 0.8
        }
        
    def check_expectation(self, actual: str, expected: str) -> bool:
        """Check if actual result matches expected outcome"""
        if expected == "SAMPLE":
            # For sampling, we expect either allow or deny after evaluation
            return actual.lower() in ["allow", "deny"]
        else:
            return actual.lower() == expected.lower()
            
    def print_summary(self, results: List[Tuple[str, bool, dict]]):
        """Print test summary"""
        total = len(results)
        passed = sum(1 for _, success, _ in results if success)
        
        print("\n📊 Demo Results Summary")
        print(f"Total scenarios: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success rate: {passed/total*100:.1f}%")

async def main():
    """Run automated demo scenarios"""
    demo = SecurityDemoScenarios()
    await demo.run_all_scenarios()

if __name__ == "__main__":
    asyncio.run(main())
```

**Demo Justfile Tasks**:
```make
# Add to justfile
demo:
    @echo "🚀 Starting FastAgent Security Demo"
    cd demo && uv run python security_demo_agent.py

demo-auto:
    @echo "🧪 Running Automated Security Scenarios" 
    cd demo && uv run python automated_demo.py

demo-setup:
    @echo "📦 Setting up FastAgent demo environment"
    uv add --optional-group demo fast-agent-mcp
    cd demo && uv run fast-agent init
```

**Implementation Steps**:
1. Create demo/ directory with FastAgent configuration
2. Read FastAgent documentation for proper MCP sampling setup
3. Implement security demo agent with interactive mode
4. Create automated demo scenarios for testing
5. Add justfile tasks for easy demo execution
6. Test end-to-end functionality with actual MCP server

**Acceptance Criteria**:
- [ ] FastAgent connects successfully to Superego MCP server
- [ ] Demo agent can invoke evaluate_tool_request through MCP sampling
- [ ] Safe operations return "allow" decisions
- [ ] Dangerous operations return "deny" decisions  
- [ ] Complex operations trigger AI sampling (if implemented)
- [ ] Automated scenarios demonstrate expected security behavior
- [ ] Tests: FastAgent connection, demo scenario execution, MCP integration

## Phase 2: Enhancement Tasks (Future)

### Task 2.1: Configuration Hot-Reload
**Description**: Implement file watching for configuration changes without restart
**Size**: Medium
**Priority**: Medium
**Dependencies**: Task 1.3 (Security Policy)
**Technical Requirements**: Use watchfiles for YAML monitoring, reload rules dynamically

### Task 2.2: HTTP/SSE Transport  
**Description**: Add HTTP transport with Server-Sent Events for web integration
**Size**: Large
**Priority**: Medium  
**Dependencies**: Task 1.7 (FastMCP Server)
**Technical Requirements**: FastMCP HTTP transport, SSE for real-time updates

### Task 2.3: AI Sampling Decision Engine
**Description**: Implement actual AI-powered sampling decisions with circuit breaker
**Size**: Large
**Priority**: Medium
**Dependencies**: Task 1.4 (Prompt Builder), Task 1.5 (Circuit Breaker)
**Technical Requirements**: LLM API integration, prompt-based evaluation, fallback logic

### Task 2.4: Advanced Rule Patterns
**Description**: Extend rule matching with regex patterns and complex conditions
**Size**: Medium
**Priority**: Low
**Dependencies**: Task 1.3 (Security Policy)
**Technical Requirements**: Regex matching, nested conditions, performance optimization

## Testing Strategy

### Unit Tests (Included in Each Task)
- Domain model validation and sanitization
- Rule matching logic with priority ordering
- Circuit breaker state transitions
- Error handling decision logic
- Prompt template security

### Integration Tests
- End-to-end request processing through MCP
- FastAgent demo client integration
- Configuration loading and validation
- Health monitoring and metrics collection

### Performance Tests  
- Rule evaluation latency (< 10ms target)
- Concurrent request handling
- Memory usage under load
- Circuit breaker performance impact

## Risk Assessment

### High Risk Items
1. **FastAgent Integration Complexity**: FastAgent documentation may be incomplete or outdated
   - Mitigation: Allocate extra time for FastAgent research and setup
   
2. **AI Service Dependencies**: Sampling decisions require external LLM API  
   - Mitigation: Circuit breaker provides fallback, Phase 1 focuses on rule-based decisions

3. **Performance Under Load**: Rule evaluation must meet < 10ms latency target
   - Mitigation: In-memory rule caching, performance testing early

### Medium Risk Items
1. **Configuration Management**: YAML parsing and validation complexity
   - Mitigation: Use pydantic for schema validation, comprehensive error handling
   
2. **Security Parameter Sanitization**: Complex injection attack prevention
   - Mitigation: Multi-layer sanitization, security-focused testing

## Execution Strategy

### Parallel Work Opportunities
- Task 1.3 (Security Policy) and Task 1.4 (Prompt Builder) after models complete
- Task 1.5 (Circuit Breaker) and Task 1.6 (Error Handling) can start together  
- Task 1.8 (FastAgent Demo) only after Task 1.7 (MCP Server) completes

### Critical Path
1. Task 1.1 (Project Setup) → Task 1.2 (Domain Models)
2. Task 1.2 → Task 1.3, 1.4, 1.5, 1.6 (can run in parallel)
3. Task 1.6 → Task 1.7 (MCP Server) → Task 1.8 (Demo)

### Day 1 Success Criteria
- Working MCP server with STDIO transport
- Rule-based security evaluation (allow/deny decisions)
- FastAgent demo client can connect and test operations
- Comprehensive error handling and audit logging
- Foundation ready for Phase 2 AI sampling integration