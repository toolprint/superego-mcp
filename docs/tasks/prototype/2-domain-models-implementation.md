---
schema: 1
id: 2
title: Domain Models Implementation
status: done
created: "2025-08-11T05:24:42.500Z"
updated: "2025-08-11T06:28:46.500Z"
tags:
  - phase1
  - foundation
  - high-priority
  - medium
dependencies:
  - 1
---
## Description
Implement Pydantic 2.0 domain models with validation, sanitization, and error handling classes

## Details
Implement Pydantic 2.0 domain models with validation and sanitization for Superego MCP Server.

Technical Requirements:
- Pydantic 2.0 BaseModel classes
- Input validation and sanitization
- Immutable security rules
- Error handling domain models
- Type safety and field validation

Domain Models Implementation:
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

Error Handling Models:
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

Implementation Steps:
1. Create src/superego_mcp/domain/models.py
2. Implement all domain models with Pydantic 2.0 syntax
3. Add parameter sanitization methods
4. Create error handling classes
5. Add comprehensive type hints
6. Implement model validation tests
EOF < /dev/null

## Validation
- [ ] All models instantiate correctly with valid data
- [ ] Parameter sanitization prevents injection attacks
- [ ] SecurityRule model is immutable (frozen=True)
- [ ] Field validation works (tool_name regex, priority range)
- [ ] Error classes provide structured error information
- [ ] Tests: Model validation, sanitization, error handling

Test scenarios:
1. Create ToolRequest with valid data - should succeed
2. Try ToolRequest with invalid tool_name - should fail validation
3. Test parameter sanitization with malicious input
4. Verify SecurityRule cannot be modified after creation
5. Test priority field validation (0-999 range)
6. Verify error handling with SuperegoError instances