# Superego MCP Server - Design Document

## Executive Summary

Superego MCP is an advanced Model Context Protocol (MCP) server that provides intelligent tool request interception and evaluation. It acts as a security and governance layer for AI agents, using rule-based categorization combined with AI-powered sampling decisions to determine whether tool requests should be allowed or denied.

## Problem Statement

AI agents can execute potentially dangerous operations through tool calls. Current solutions lack:
- Dynamic rule-based evaluation of tool requests
- AI-powered decision making for complex scenarios
- Real-time configuration updates without service restart
- Comprehensive audit trails
- Integration with Claude Code PreToolUse hooks

## Solution Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Superego MCP Server                     │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────┐   │
│  │ Transport     │  │ Rule Engine     │  │ Decision     │   │
│  │ Layer         │  │ (Priority-based)│  │ Engine       │   │
│  │ - STDIO       │  │ - File Storage  │  │ (AI Sampling)│   │
│  │ - HTTP/SSE    │  │ - Hot Reload    │  │              │   │
│  └───────────────┘  └─────────────────┘  └──────────────┘   │
│                                                             │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────┐   │
│  │ Config        │  │ Audit Logger    │  │ Resource     │   │
│  │ Manager       │  │ (Pluggable)     │  │ Endpoints    │   │
│  │ - File Watch  │  │ - TTL Support   │  │ - Dynamic    │   │
│  │ - Validation  │  │ - In-Memory     │  │ - Config     │   │
│  └───────────────┘  └─────────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Component Design

### 1. Transport Layer

**Supported Transports:**
- **STDIO**: Direct integration with Claude Code hooks via stdin/stdout
- **HTTP**: RESTful API for remote access and integration
- **Server-Sent Events (SSE)**: Real-time streaming for monitoring dashboards

**Implementation Framework:**
- FastMCP 2.0 provides unified transport abstraction
- Automatic protocol negotiation and capability detection
- Type-safe message serialization/deserialization

### 2. Rule Engine

**Architecture Pattern:** Priority-based rule matching inspired by CCO-MCP

```yaml
# Example Rule Configuration
rules:
  - id: "block-dangerous-commands"
    priority: 1  # Lower = higher precedence
    conditions:
      tool_name: ["rm", "sudo", "dd"]
      parameters:
        path: "**/.*"  # Block operations on hidden files
    action: "DENY"
    reason: "Dangerous system operation blocked"
    
  - id: "sample-file-operations"
    priority: 10
    conditions:
      tool_name: ["edit", "write", "delete"]
      agent_id: "*"
    action: "SAMPLE"
    sampling_guidance: "Evaluate if file modification is safe and necessary"
    
  - id: "allow-read-operations"
    priority: 99
    conditions:
      tool_name: ["read", "list", "grep", "glob"]
    action: "ALLOW"
    reason: "Read operations are generally safe"
```

**Key Features:**
- **Priority System**: Lower numbers = higher precedence, enabling rule hierarchies
- **Pattern Matching**: Glob patterns for tool names, parameters, and agent IDs
- **Flexible Actions**: ALLOW, DENY, or SAMPLE (delegate to AI)
- **Context Awareness**: Access to session state, working directory, agent context

### 3. Decision Engine

**AI-Powered Sampling:**
```python
async def evaluate_with_ai(request: ToolRequest, context: dict) -> Decision:
    """
    Use LLM sampling for nuanced decision making
    """
    prompt = f"""
    Evaluate this tool request for security and appropriateness:
    
    Tool: {request.tool_name}
    Parameters: {request.parameters}
    Context: Working in {context['cwd']}, Agent: {context['agent_id']}
    Session: {context['session_info']}
    
    Consider:
    - Potential security risks
    - Business policy compliance
    - User intent and context
    - Least-privilege principles
    
    Respond with: ALLOW/DENY and detailed reasoning.
    """
    
    response = await sampling_client.sample(
        prompt, 
        system="You are a security decision engine. Be conservative with destructive operations."
    )
    
    return Decision.parse_llm_response(response)
```

**Decision Flow:**
1. Rule engine evaluates request
2. If rule action is SAMPLE, invoke AI decision engine
3. AI considers context, security implications, and business rules
4. Returns structured decision with reasoning
5. Decision and reasoning logged to audit trail

### 4. Configuration Management

**Dynamic Configuration:**
- **Hot Reload**: File system watching with zero-downtime updates
- **Validation**: Schema validation before applying configuration changes
- **Rollback**: Automatic rollback on invalid configurations
- **Notifications**: MCP notifications to clients on configuration changes

```python
class ConfigManager:
    async def on_config_change(self, file_path: str):
        """Handle configuration file changes"""
        try:
            new_config = self.load_and_validate(file_path)
            old_config = self.current_config
            
            # Apply new configuration
            self.rule_engine.update_rules(new_config.rules)
            self.current_config = new_config
            
            # Notify MCP clients
            await self.mcp_server.notify_resource_changed("config://rules")
            
            self.audit_logger.log_config_change(old_config, new_config)
            
        except ValidationError as e:
            self.logger.error(f"Invalid configuration: {e}")
            # Keep current configuration, log error
```

### 5. Audit Trail

**Comprehensive Logging:**
- **Request Details**: Tool name, parameters, context, timestamps
- **Decision Records**: Allow/deny decisions with full reasoning
- **Configuration Changes**: Rule updates, system modifications
- **Performance Metrics**: Response times, sampling frequency

**Storage Strategy:**
```python
class AuditEntry:
    timestamp: datetime
    session_id: str
    tool_name: str
    parameters: dict
    decision: Decision
    reasoning: str
    response_time_ms: int
    rule_matches: list[RuleMatch]
    ttl: Optional[datetime]  # Auto-expiration
```

**Pluggable Backend:**
- **In-Memory**: Fast access, development/testing
- **File-Based**: Simple persistence, single-node deployments  
- **Database**: Future support for PostgreSQL, MongoDB
- **Cloud Storage**: Future support for S3, GCS

### 6. Claude Code Integration

**PreToolUse Hook Schema Compliance:**
```python
# Claude Code Event Schema
class PreToolUseEvent:
    tool_name: str
    tool_input: dict
    session_id: str
    cwd: str
    timestamp: str
    
# Superego Response Schema  
class HookResponse:
    action: Literal["allow", "block"]
    feedback: Optional[str]  # Shown to user on block
```

**Integration Flow:**
1. Claude Code invokes PreToolUse hook
2. Superego receives tool request via STDIO
3. Rule engine + decision engine evaluate request
4. Response sent back to Claude Code
5. Claude Code proceeds or blocks based on response

### 7. Resource Endpoints

**Dynamic MCP Resources:**
```python
@mcp.resource("config://rules")
async def get_current_rules():
    """Expose current rule configuration as MCP resource"""
    return Resource(
        uri="config://rules",
        name="Active Security Rules",
        mimeType="application/yaml",
        text=yaml.dump(config_manager.get_rules())
    )

@mcp.resource("audit://recent")  
async def get_recent_audit_entries():
    """Expose recent audit entries for monitoring"""
    entries = audit_logger.get_recent_entries(limit=100)
    return Resource(
        uri="audit://recent", 
        name="Recent Security Decisions",
        mimeType="application/json",
        text=json.dumps([entry.to_dict() for entry in entries])
    )
```

### 8. FastAgent Integration

**Advanced Workflow Patterns:**

```python
# Evaluator-Optimizer for rule refinement
@fast.evaluator_optimizer(
    name="security_rule_optimizer",
    generator="rule_generator_agent", 
    evaluator="security_auditor_agent",
    min_rating="GOOD",
    max_refinements=3
)
async def optimize_security_rules(
    current_rules: list[SecurityRule],
    incident_reports: list[IncidentReport]
) -> list[SecurityRule]:
    """Iteratively improve security rules based on incidents"""
    pass

# Router for complex decision scenarios
@fast.router(
    name="decision_complexity_router",
    agents=["simple_rule_matcher", "ml_risk_analyzer", "human_escalation"]
)  
async def route_complex_decision(request: ToolRequest) -> str:
    """Route to appropriate decision agent based on complexity"""
    if request.is_high_risk():
        return "human_escalation"
    elif request.requires_context_analysis():
        return "ml_risk_analyzer" 
    else:
        return "simple_rule_matcher"
```

## Technology Stack

### Core Dependencies
- **FastMCP 2.0**: MCP server framework with sampling support
- **FastAgent**: Multi-agent workflow orchestration
- **PyYAML**: Configuration file parsing
- **Watchfiles**: File system monitoring for hot-reload
- **Pydantic**: Data validation and serialization
- **Python 3.11+**: Modern Python features and performance

### Optional Dependencies
- **uvloop**: High-performance event loop (Unix systems)
- **orjson**: Fast JSON serialization
- **Rich**: Enhanced logging and debugging output
- **Typer**: CLI interface for administration

## Security Considerations

### Input Validation
- All configuration files validated against strict schemas
- Tool parameters sanitized before evaluation
- Path traversal protection for file operations

### Access Control  
- Rule-based permissions for different agent types
- Session isolation and context boundaries
- Audit trail integrity protection

### Performance & DoS Protection
- Rate limiting for sampling requests
- Circuit breakers for external AI services
- Resource limits for rule evaluation complexity
- TTL-based cleanup of audit entries

## Deployment Architecture

### Single-Node Development
```
┌─────────────────┐    STDIO    ┌──────────────────┐
│   Claude Code   │◄────────────┤ Superego MCP     │
│                 │             │ - YAML Config    │
│                 │             │ - File Storage   │
│                 │             │ - In-Memory Audit│
└─────────────────┘             └──────────────────┘
```

### Production Multi-Transport
```
┌─────────────────┐    STDIO    ┌──────────────────┐
│   Claude Code   │◄────────────┤                  │
└─────────────────┘             │                  │
                                │  Superego MCP    │
┌─────────────────┐    HTTP     │                  │
│   Monitoring    │◄────────────┤  - DB Config     │
│   Dashboard     │             │  - Audit DB      │  
└─────────────────┘             │  - Health Check  │
                                └──────────────────┘
```

## Configuration Examples

### Basic Security Rules
```yaml
# config/rules.yaml
rules:
  # Block all dangerous system commands
  - id: "system-protection"
    priority: 1
    conditions:
      tool_name: ["rm", "sudo", "chmod", "chown", "dd", "mkfs"]
    action: "DENY"
    reason: "Dangerous system command blocked by security policy"

  # Require AI review for file modifications
  - id: "file-modification-review"  
    priority: 5
    conditions:
      tool_name: ["edit", "write", "multiedit"]
      parameters:
        file_path: "src/**/*.py"  # Only Python files
    action: "SAMPLE"
    sampling_guidance: "Review code changes for security vulnerabilities and best practices"

  # Allow safe read operations
  - id: "allow-read-operations"
    priority: 99
    conditions:
      tool_name: ["read", "glob", "grep", "ls"]
    action: "ALLOW"
    reason: "Read operations are safe"
```

### Server Configuration  
```yaml
# config/settings.yaml
server:
  name: "Superego MCP Server"
  version: "1.0.0"
  
transports:
  stdio:
    enabled: true
  http:
    enabled: true
    host: "0.0.0.0" 
    port: 8080
  sse:
    enabled: true
    port: 8081

audit:
  backend: "memory"  # memory, file, database
  ttl_hours: 24
  max_entries: 10000

sampling:
  timeout_seconds: 30
  model: "claude-3-sonnet"
  temperature: 0.1

rules:
  config_file: "config/rules.yaml"
  watch_for_changes: true
  validation_strict: true
```

## Installation and Usage

### Installation
```bash
pip install superego-mcp
```

### Basic Usage
```bash
# Run with STDIO (for Claude Code integration)
superego-mcp --transport stdio --config config/settings.yaml

# Run with HTTP transport
superego-mcp --transport http --port 8080 --config config/settings.yaml

# Run with both transports
superego-mcp --transport stdio,http --config config/settings.yaml
```

### Claude Code Integration
```bash
# Add to Claude Code hooks configuration
echo "PreToolUse: superego-mcp --transport stdio" >> ~/.claude/hooks.yaml
```

## Testing Strategy

### Unit Tests
- Rule matching logic with various conditions
- Decision engine with mocked AI responses  
- Configuration validation and error handling
- Audit trail storage and retrieval

### Integration Tests  
- End-to-end request processing
- Multiple transport support
- Configuration hot-reload functionality
- MCP protocol compliance

### Performance Tests
- Rule evaluation latency
- Concurrent request handling
- Memory usage with large audit trails
- Configuration reload impact

## Future Enhancements

### Phase 2 Features
- **Web Dashboard**: React-based monitoring and configuration UI
- **Database Backends**: PostgreSQL and MongoDB support
- **Machine Learning**: Anomaly detection for unusual tool usage patterns
- **Policy Templates**: Pre-built rule sets for common security scenarios

### Phase 3 Features  
- **Multi-Tenant Support**: Isolated configurations per organization
- **Distributed Deployment**: Horizontal scaling with shared state
- **Advanced Analytics**: Usage patterns, risk scoring, trend analysis
- **Integration APIs**: Webhooks, SIEM integration, compliance reporting

## Risk Assessment

### Technical Risks
- **AI Sampling Latency**: Mitigated by timeout controls and fallback rules
- **Configuration Errors**: Mitigated by strict validation and rollback mechanisms
- **Memory Leaks**: Mitigated by TTL-based cleanup and resource monitoring

### Security Risks  
- **Rule Bypass**: Mitigated by priority system and comprehensive logging
- **Configuration Tampering**: Mitigated by file permissions and audit trails
- **DoS Attacks**: Mitigated by rate limiting and circuit breakers

### Operational Risks
- **Service Downtime**: Mitigated by graceful fallback modes and health checks
- **Data Loss**: Mitigated by configurable audit persistence and backups
- **Performance Degradation**: Mitigated by performance monitoring and alerting

## Success Metrics

### Functional Metrics
- **Coverage**: % of tool requests properly categorized and evaluated
- **Accuracy**: % of AI decisions aligned with security policies  
- **Performance**: Average response time < 100ms for rule evaluation
- **Reliability**: 99.9% uptime with graceful degradation

### Security Metrics
- **Blocked Threats**: Number of dangerous operations prevented
- **False Positives**: % of legitimate requests incorrectly blocked
- **Audit Compliance**: 100% of security decisions logged and traceable
- **Configuration Drift**: Zero unauthorized configuration changes

This design provides a robust, scalable, and secure foundation for intelligent tool request evaluation while maintaining ease of use and deployment flexibility.