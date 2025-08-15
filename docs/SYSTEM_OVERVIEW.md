# Superego MCP - Complete System Overview

## Executive Summary

Superego MCP is a sophisticated security-focused Model Context Protocol (MCP) server that provides intelligent tool request interception for AI agents. This document provides a complete overview of the system architecture, component interactions, and operational flows.

## System Architecture Overview

```mermaid
graph TB
    subgraph "External Integrations"
        CC[Claude Code<br/>AI Assistant]
        AI[AI Services<br/>Claude/OpenAI/Gemini]
        FS[File System<br/>Config & Rules]
        USER[End User]
    end
    
    subgraph "Superego MCP System"
        subgraph "Entry Points"
            CLI[CLI Interface<br/>'superego' command]
            HOOKS[Hooks Manager<br/>Claude Code Integration]
        end
        
        subgraph "Operating Modes"
            ADVISE[Advise Mode<br/>CLI Evaluation]
            SERVER[Server Mode<br/>Full MCP]
        end
        
        subgraph "Core Engine"
            SPE[Security Policy Engine]
            INF[Inference System]
            PE[Pattern Engine]
        end
        
        subgraph "Infrastructure"
            CONFIG[Configuration<br/>Manager]
            AUDIT[Audit Logger]
            HEALTH[Health Monitor]
            CB[Circuit Breaker]
        end
        
        subgraph "Transports"
            STDIO[STDIO Transport]
            HTTP[HTTP/SSE/WS]
        end
    end
    
    USER --> CLI
    CC --> HOOKS
    CC --> STDIO
    AI --> INF
    FS --> CONFIG
    
    CLI --> ADVISE
    CLI --> SERVER
    CLI --> HOOKS
    
    ADVISE --> SPE
    SERVER --> SPE
    
    SPE --> PE
    SPE --> INF
    SPE --> AUDIT
    
    INF --> CB
    CONFIG --> SPE
    HEALTH --> SERVER
    
    SERVER --> STDIO
    SERVER --> HTTP
    
    style SPE fill:#ffebee
    style INF fill:#e3f2fd
    style ADVISE fill:#e8f5e9
    style SERVER fill:#fff3e0
```

## Component Interaction Map

```mermaid
flowchart TB
    subgraph "User Interaction Layer"
        DEV[Developer]
        CLAUDE[Claude Code]
        ADMIN[Administrator]
    end
    
    subgraph "Interface Layer"
        subgraph "CLI Commands"
            ADV[superego advise]
            MCP[superego mcp]
            HOOK[superego hooks]
        end
        
        subgraph "Protocols"
            JSON[JSON-RPC]
            REST[REST API]
            WS[WebSocket]
        end
    end
    
    subgraph "Application Layer"
        subgraph "Evaluation Engine"
            EVAL[Security Evaluator]
            RULES[Rule Matcher]
            AI_EVAL[AI Evaluator]
        end
        
        subgraph "Management"
            RULE_MGMT[Rule Management]
            CONFIG_MGMT[Config Management]
            HOOK_MGMT[Hook Management]
        end
    end
    
    subgraph "Service Layer"
        subgraph "Core Services"
            POLICY[Policy Service]
            INFERENCE[Inference Service]
            PATTERN[Pattern Service]
        end
        
        subgraph "Support Services"
            AUDIT_SVC[Audit Service]
            HEALTH_SVC[Health Service]
            CACHE[Cache Service]
        end
    end
    
    subgraph "Infrastructure Layer"
        subgraph "External"
            AI_PROVIDER[AI Providers]
            FILE_SYS[File System]
            LOGS[Log Storage]
        end
        
        subgraph "Internal"
            ERROR[Error Handler]
            CIRCUIT[Circuit Breaker]
            WATCHER[Config Watcher]
        end
    end
    
    DEV --> ADV
    CLAUDE --> ADV
    ADMIN --> MCP
    ADMIN --> HOOK
    
    ADV --> JSON
    MCP --> REST
    MCP --> WS
    
    JSON --> EVAL
    REST --> RULE_MGMT
    WS --> EVAL
    
    EVAL --> POLICY
    RULE_MGMT --> CONFIG_MGMT
    HOOK_MGMT --> FILE_SYS
    
    POLICY --> INFERENCE
    POLICY --> PATTERN
    INFERENCE --> AI_PROVIDER
    
    POLICY --> AUDIT_SVC
    EVAL --> CACHE
    
    INFERENCE --> CIRCUIT
    CONFIG_MGMT --> WATCHER
    
    style POLICY fill:#ffebee
    style INFERENCE fill:#e3f2fd
    style EVAL fill:#e8f5e9
```

## Operational Flows

### 1. Tool Request Evaluation Flow

```mermaid
sequenceDiagram
    participant Agent as AI Agent
    participant Transport
    participant Server as MCP Server
    participant Policy as Security Policy
    participant Pattern as Pattern Engine
    participant Inference
    participant Audit
    
    Agent->>Transport: Tool Request
    Transport->>Server: Normalized Request
    
    Server->>Server: Validate & Sanitize
    Server->>Policy: evaluate(ToolRequest)
    
    Policy->>Pattern: Match Rules
    Pattern->>Pattern: Check Patterns
    Pattern-->>Policy: Matching Rules
    
    alt Direct Rule Match (Allow/Deny)
        Policy->>Policy: Apply Rule Action
        Policy-->>Server: Decision
    else Sample Action Required
        Policy->>Inference: Evaluate with AI
        Inference->>Inference: Select Provider
        Inference->>Inference: Build Prompt
        Inference-->>Policy: AI Decision
        Policy-->>Server: Decision
    end
    
    Server->>Audit: Log Decision
    Server-->>Transport: Response
    Transport-->>Agent: Decision Result
```

### 2. Configuration and Rule Management

```mermaid
flowchart LR
    subgraph "Configuration Sources"
        YAML[config.yaml]
        RULES[rules.yaml]
        ENV[Environment]
        CLI_ARGS[CLI Arguments]
    end
    
    subgraph "Configuration Processing"
        LOADER[Config Loader]
        VALIDATOR[Validator]
        MERGER[Config Merger]
        WATCHER[File Watcher]
    end
    
    subgraph "Runtime Configuration"
        ACTIVE[Active Config]
        CACHE[Config Cache]
        HOT_RELOAD[Hot Reload]
    end
    
    subgraph "Consumers"
        SERVICES[Services]
        TRANSPORTS[Transports]
        PROVIDERS[Providers]
    end
    
    YAML --> LOADER
    RULES --> LOADER
    ENV --> MERGER
    CLI_ARGS --> MERGER
    
    LOADER --> VALIDATOR
    VALIDATOR --> MERGER
    MERGER --> ACTIVE
    
    ACTIVE --> CACHE
    WATCHER --> HOT_RELOAD
    HOT_RELOAD --> ACTIVE
    
    CACHE --> SERVICES
    CACHE --> TRANSPORTS
    CACHE --> PROVIDERS
    
    style ACTIVE fill:#e8f5e9
    style HOT_RELOAD fill:#fff3e0
```

### 3. Multi-Mode Operation

```mermaid
stateDiagram-v2
    [*] --> CLIEntry: User runs 'superego'
    
    CLIEntry --> AdviseMode: superego advise
    CLIEntry --> ServerMode: superego mcp
    CLIEntry --> HooksMode: superego hooks
    
    state AdviseMode {
        [*] --> ReadInput: Read stdin
        ReadInput --> Evaluate: Mock evaluation
        Evaluate --> Output: Write stdout
        Output --> [*]: Exit
    }
    
    state ServerMode {
        [*] --> Initialize: Load config
        Initialize --> SelectTransport: Check transport
        
        SelectTransport --> StdioMode: stdio (default)
        SelectTransport --> HttpMode: http
        
        state StdioMode {
            [*] --> ListenStdio: Listen on stdin/stdout
            ListenStdio --> ProcessMCP: Handle MCP messages
        }
        
        state HttpMode {
            [*] --> StartHTTP: Start HTTP server
            StartHTTP --> ListenHTTP: Listen on port
            ListenHTTP --> ProcessREST: Handle REST/WS/SSE
        }
        
        ProcessMCP --> HandleRequest: Process request
        ProcessREST --> HandleRequest
        
        HandleRequest --> [*]: Until shutdown
    }
    
    state HooksMode {
        [*] --> ParseCommand: Parse hook command
        ParseCommand --> AddHook: hooks add
        ParseCommand --> ListHooks: hooks list
        ParseCommand --> RemoveHook: hooks remove
        
        AddHook --> UpdateSettings: Modify settings.json
        RemoveHook --> UpdateSettings
        ListHooks --> ShowHooks: Display hooks
        
        UpdateSettings --> [*]: Complete
        ShowHooks --> [*]: Complete
    }
```

## Key Design Patterns

### 1. Layered Architecture

```mermaid
graph TD
    subgraph "Presentation Layer"
        P1[CLI Interface]
        P2[Transport Servers]
        P3[API Endpoints]
    end
    
    subgraph "Application Layer"
        A1[Use Cases]
        A2[Orchestration]
        A3[DTOs]
    end
    
    subgraph "Domain Layer"
        D1[Business Logic]
        D2[Domain Models]
        D3[Domain Services]
    end
    
    subgraph "Infrastructure Layer"
        I1[External Services]
        I2[Persistence]
        I3[Messaging]
    end
    
    P1 --> A1
    P2 --> A2
    P3 --> A3
    
    A1 --> D1
    A2 --> D2
    A3 --> D3
    
    D1 --> I1
    D2 --> I2
    D3 --> I3
    
    style D1 fill:#ffebee
    style D2 fill:#ffebee
    style D3 fill:#ffebee
```

### 2. Provider Strategy Pattern

```mermaid
classDiagram
    class InferenceProvider {
        <<interface>>
        +evaluate(request) Decision
        +health_check() Status
        +get_info() Info
    }
    
    class MockProvider {
        +evaluate(request) Decision
        -mock_rules: List
    }
    
    class CLIProvider {
        +evaluate(request) Decision
        -command: str
        -parse_response()
    }
    
    class MCPSamplingProvider {
        +evaluate(request) Decision
        -ai_service: AIService
        -request_approval()
    }
    
    class InferenceManager {
        -providers: Map
        +get_provider(name?) Provider
        +evaluate(request) Decision
    }
    
    InferenceProvider <|-- MockProvider
    InferenceProvider <|-- CLIProvider
    InferenceProvider <|-- MCPSamplingProvider
    InferenceManager o-- InferenceProvider
```

### 3. Circuit Breaker Pattern

```mermaid
stateDiagram-v2
    [*] --> Closed: Initial
    
    state Closed {
        [*] --> Monitoring: Track requests
        Monitoring --> Success: Request succeeds
        Monitoring --> Failure: Request fails
        Success --> Monitoring: Reset counter
        Failure --> CheckThreshold: Increment counter
        CheckThreshold --> Monitoring: Below threshold
        CheckThreshold --> Opening: Threshold reached
    }
    
    Opening --> Open: Trip breaker
    
    state Open {
        [*] --> FastFail: Reject requests
        FastFail --> WaitTimeout: Start timer
        WaitTimeout --> AttemptReset: Timeout elapsed
    }
    
    AttemptReset --> HalfOpen: Allow test request
    
    state HalfOpen {
        [*] --> TestRequest: Single request
        TestRequest --> Success2: Request succeeds
        TestRequest --> Failure2: Request fails
        Success2 --> Closing: Reset breaker
        Failure2 --> Opening2: Re-open breaker
    }
    
    Closing --> Closed: Resume normal
    Opening2 --> Open: Back to open
```

## Performance Characteristics

### Request Processing Pipeline

```mermaid
graph LR
    subgraph "Input Stage"
        REQ[Request<br/>~1ms]
        VAL[Validation<br/>~2ms]
        SAN[Sanitization<br/>~3ms]
    end
    
    subgraph "Evaluation Stage"
        CACHE{Cache Hit?}
        CACHED[Cached Result<br/>~1ms]
        PATTERN[Pattern Match<br/>~5ms]
        RULES[Rule Evaluation<br/>~10ms]
    end
    
    subgraph "AI Stage"
        AI_CHECK{AI Needed?}
        AI_EVAL[AI Evaluation<br/>~500-3000ms]
        MOCK[Mock Evaluation<br/>~5ms]
    end
    
    subgraph "Output Stage"
        DEC[Decision<br/>~1ms]
        AUDIT[Audit Log<br/>~2ms]
        RESP[Response<br/>~1ms]
    end
    
    REQ --> VAL --> SAN
    SAN --> CACHE
    
    CACHE -->|Yes| CACHED
    CACHE -->|No| PATTERN
    
    CACHED --> DEC
    PATTERN --> RULES
    
    RULES --> AI_CHECK
    AI_CHECK -->|Yes| AI_EVAL
    AI_CHECK -->|No| MOCK
    
    AI_EVAL --> DEC
    MOCK --> DEC
    
    DEC --> AUDIT --> RESP
    
    style CACHED fill:#c8e6c9
    style AI_EVAL fill:#ffeb3b
```

### Scalability Considerations

```mermaid
graph TD
    subgraph "Current Architecture"
        SINGLE[Single Process]
        INMEM[In-Memory State]
        LOCAL[Local Config]
    end
    
    subgraph "Scaling Bottlenecks"
        B1[AI Provider Calls]
        B2[Pattern Matching]
        B3[Config Reload]
    end
    
    subgraph "Future Scaling Options"
        MULTI[Multi-Process]
        REDIS[Redis Cache]
        DIST[Distributed Config]
        QUEUE[Request Queue]
    end
    
    SINGLE --> B1
    INMEM --> B2
    LOCAL --> B3
    
    B1 --> QUEUE
    B2 --> REDIS
    B3 --> DIST
    
    QUEUE --> MULTI
    REDIS --> MULTI
    DIST --> MULTI
    
    style B1 fill:#ffcdd2
    style B2 fill:#ffcdd2
    style B3 fill:#ffcdd2
```

## Deployment Architecture

### Local Development Setup

```mermaid
graph TB
    subgraph "Developer Machine"
        subgraph "Superego MCP"
            SERVER[MCP Server<br/>Port 8000]
            CLI[CLI Tools]
        end
        
        subgraph "Claude Code"
            CC[Claude Code<br/>Extension]
            HOOKS[Hooks Config<br/>~/.claude/settings.json]
        end
        
        subgraph "Configuration"
            CONFIG[~/.toolprint/superego/config.yaml]
            RULES[config/rules.yaml]
        end
    end
    
    CC --> HOOKS
    HOOKS --> CLI
    CLI --> SERVER
    
    SERVER --> CONFIG
    SERVER --> RULES
    
    style SERVER fill:#e3f2fd
    style CLI fill:#e8f5e9
```

### Production Deployment Options

```mermaid
graph TB
    subgraph "Container Deployment"
        DOCKER[Docker Container]
        K8S[Kubernetes Pod]
    end
    
    subgraph "Process Management"
        SYSTEMD[systemd service]
        PM2[PM2 Process]
    end
    
    subgraph "Configuration Management"
        CONFIGMAP[K8s ConfigMap]
        VAULT[HashiCorp Vault]
        ENVFILE[Environment File]
    end
    
    subgraph "Monitoring"
        PROM[Prometheus Metrics]
        LOGS[Log Aggregation]
        HEALTH[Health Checks]
    end
    
    DOCKER --> K8S
    K8S --> CONFIGMAP
    
    SYSTEMD --> ENVFILE
    PM2 --> ENVFILE
    
    K8S --> HEALTH
    SYSTEMD --> HEALTH
    
    HEALTH --> PROM
    SERVER --> LOGS
    
    style K8S fill:#e3f2fd
    style SYSTEMD fill:#e8f5e9
```

## Summary

Superego MCP is a well-architected security system with:

### Strengths
- **Clear separation of concerns** between layers
- **Flexible provider system** for AI evaluation
- **Comprehensive security model** with defense in depth
- **Hot reload capability** for configuration changes
- **Multiple transport options** for different use cases
- **Extensive audit trail** for compliance

### Current Limitations
- **Global state management** makes testing difficult
- **Complex initialization** in main.py
- **Tight coupling** between some components
- **Limited horizontal scaling** options
- **In-memory storage** only

### Future Opportunities
- **Dependency injection** framework
- **Distributed deployment** support
- **Persistent storage** options
- **Enhanced monitoring** and metrics
- **Plugin architecture** for extensions
- **API gateway** integration

The architecture provides a solid foundation for a security-focused MCP server while maintaining flexibility for future enhancements and scaling requirements.