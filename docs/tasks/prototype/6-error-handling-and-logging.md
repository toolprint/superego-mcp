---
schema: 1
id: 6
title: Error Handling & Logging
status: done
created: "2025-08-11T05:45:49.384Z"
updated: "2025-08-11T06:58:32.012Z"
tags:
  - phase1
  - infrastructure
  - high-priority
  - medium
dependencies:
  - 2
  - 5
---
## Description
Implement centralized error handling with structured audit logging and health monitoring

## Details
Implement centralized error handling with structured audit logging for Superego MCP Server.

Technical Requirements:
- Structured error responses with user-friendly messages  
- Audit trail logging with structured data
- Health check endpoints with component status
- Fail-closed for security errors, fail-open for availability issues

Error Handler Implementation:
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

Health Monitoring Implementation:
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

Implementation Steps:
1. Create src/superego_mcp/infrastructure/error_handler.py
2. Implement ErrorHandler with structured decision logic
3. Create AuditLogger with in-memory storage for Day 1
4. Add HealthMonitor with component registration
5. Setup structured logging configuration
6. Implement error handling and audit tests
EOF < /dev/null

## Validation
- [ ] SuperegoError instances handled with appropriate fail-open/fail-closed logic
- [ ] Circuit breaker errors result in fail-open decisions
- [ ] Unexpected errors result in fail-closed decisions
- [ ] Audit entries logged with structured data
- [ ] Health monitoring provides component status and system metrics
- [ ] Tests: Error handling decisions, audit logging, health checks

Test scenarios:
1. Handle SuperegoError with AI_SERVICE_UNAVAILABLE - should fail open
2. Handle SuperegoError with CONFIG_001 - should fail closed
3. Handle CircuitBreakerOpenError - should fail open with low confidence
4. Handle unexpected Exception - should fail closed with high confidence
5. Audit logging captures all decision details
6. Health monitoring collects system metrics (CPU, memory, disk)
7. Component health checks integrate correctly