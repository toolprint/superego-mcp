# Superego MCP - Detailed Data Flow Diagrams

## Table of Contents

1. [CLI Hook Integration Flow](#cli-hook-integration-flow)
2. [MCP Server Startup Flow](#mcp-server-startup-flow)
3. [Security Policy Evaluation Flow](#security-policy-evaluation-flow)
4. [Inference Provider Selection Flow](#inference-provider-selection-flow)
5. [Error Handling and Recovery Flow](#error-handling-and-recovery-flow)
6. [Configuration Hot Reload Flow](#configuration-hot-reload-flow)
7. [Audit Logging Flow](#audit-logging-flow)

## CLI Hook Integration Flow

### Complete CLI Evaluation Lifecycle

```mermaid
stateDiagram-v2
    [*] --> ClaudeCodeTrigger: User executes tool
    
    ClaudeCodeTrigger --> HookCheck: Check PreToolUse hooks
    
    HookCheck --> HookMatch: Matcher matches tool
    HookCheck --> ExecuteTool: No matching hook
    
    HookMatch --> InvokeSuperego: Execute superego advise
    
    InvokeSuperego --> ReadStdin: Read JSON from stdin
    
    ReadStdin --> ParseInput: Parse hook input
    
    ParseInput --> ValidateInput: Validate required fields
    
    ValidateInput --> CreateRequest: Create ToolRequest
    ValidateInput --> ErrorExit1: Invalid input
    
    CreateRequest --> MockEvaluation: Use MockInferenceProvider
    
    MockEvaluation --> CheckRules: Apply mock rules
    
    CheckRules --> Allow: Safe operation
    CheckRules --> Deny: Dangerous operation
    CheckRules --> Ask: Uncertain operation
    
    Allow --> FormatResponse: Create allow response
    Deny --> FormatResponse: Create deny response
    Ask --> FormatResponse: Create ask response
    
    FormatResponse --> OutputJSON: Write to stdout
    
    OutputJSON --> ExitCode0: Success
    
    ExitCode0 --> ClaudeDecision: Claude processes response
    
    ClaudeDecision --> ExecuteTool: Permission granted
    ClaudeDecision --> BlockTool: Permission denied
    ClaudeDecision --> AskUser: Request user input
    
    ErrorExit1 --> ClaudeError: Non-blocking error
    
    ExecuteTool --> [*]
    BlockTool --> [*]
    AskUser --> [*]
    ClaudeError --> [*]
```

### Hook Input/Output Format

```mermaid
flowchart LR
    subgraph "Claude Code Hook Input"
        INPUT["{<br/>
        'session_id': 'abc123',<br/>
        'transcript_path': '/path/to/transcript',<br/>
        'cwd': '/current/directory',<br/>
        'hook_event_name': 'PreToolUse',<br/>
        'tool_name': 'Bash',<br/>
        'tool_input': {<br/>
            'command': 'rm -rf /'<br/>
        }<br/>
        }"]
    end
    
    subgraph "Superego Processing"
        PROC[CLI Evaluator<br/>MockInferenceProvider]
    end
    
    subgraph "Hook Output"
        OUTPUT["{<br/>
        'hook_specific_output': {<br/>
            'hook_event_name': 'PreToolUse',<br/>
            'permission_decision': 'deny',<br/>
            'permission_decision_reason': 'Dangerous command detected'<br/>
        },<br/>
        'decision': 'block',<br/>
        'reason': 'Dangerous command detected'<br/>
        }"]
    end
    
    INPUT --> PROC
    PROC --> OUTPUT
```

## MCP Server Startup Flow

### Initialization Sequence

```mermaid
sequenceDiagram
    participant Main as main.py
    participant CM as ConfigManager
    participant EH as ErrorHandler
    participant AL as AuditLogger
    participant HM as HealthMonitor
    participant ASM as AIServiceManager
    participant ISM as InferenceStrategyManager
    participant SPE as SecurityPolicyEngine
    participant CW as ConfigWatcher
    participant MTS as MultiTransportServer
    
    Main->>Main: async_main()
    
    %% Configuration Loading
    Main->>CM: load_config()
    CM->>CM: Read config.yaml
    CM->>CM: Apply env overrides
    CM-->>Main: ServerConfig
    
    %% Core Components
    Main->>EH: new ErrorHandler()
    Main->>AL: new AuditLogger()
    Main->>HM: new HealthMonitor()
    
    %% AI Components (conditional)
    alt AI Sampling Enabled
        Main->>Main: Create CircuitBreaker
        Main->>ASM: new AIServiceManager(config, circuit_breaker)
        Main->>Main: Create SecurePromptBuilder
    end
    
    %% Inference System
    alt Has Inference Config
        Main->>ISM: new InferenceStrategyManager(config, dependencies)
        ISM->>ISM: Initialize providers
        ISM->>ISM: CLI providers
        ISM->>ISM: API providers
        ISM->>ISM: MCP sampling provider
    end
    
    %% Security Policy
    Main->>SPE: new SecurityPolicyEngine(deps)
    SPE->>SPE: Load rules.yaml
    SPE->>SPE: Initialize pattern engine
    
    %% Config Watcher
    Main->>CW: new ConfigWatcher(rules_file, reload_callback)
    
    %% Health Monitoring
    Main->>HM: register_component("security_policy", SPE)
    Main->>HM: register_component("audit_logger", AL)
    Main->>HM: register_component("config_watcher", CW)
    
    %% Multi-Transport Server
    Main->>MTS: new MultiTransportServer(deps)
    MTS->>MTS: Setup core MCP tools
    MTS->>MTS: Setup resources
    
    %% Start Services
    Main->>CW: start()
    Main->>MTS: start()
    
    %% Run until shutdown
    Main->>Main: Wait for shutdown signal
```

### Component Dependencies

```mermaid
graph TD
    subgraph "Configuration Layer"
        CFG[ServerConfig]
        RULES[rules.yaml]
    end
    
    subgraph "Infrastructure Services"
        EH[ErrorHandler]
        AL[AuditLogger]
        HM[HealthMonitor]
        CB[CircuitBreaker]
    end
    
    subgraph "AI/Inference Layer"
        ASM[AIServiceManager]
        PB[PromptBuilder]
        ISM[InferenceStrategyManager]
    end
    
    subgraph "Domain Layer"
        SPE[SecurityPolicyEngine]
        PE[PatternEngine]
    end
    
    subgraph "Presentation Layer"
        MTS[MultiTransportServer]
        HTTP[HTTP Transport]
        WS[WebSocket Transport]
        STDIO[STDIO Transport]
    end
    
    CFG --> ASM
    CFG --> ISM
    CFG --> MTS
    
    RULES --> SPE
    
    CB --> ASM
    ASM --> ISM
    PB --> ISM
    
    ISM --> SPE
    ASM --> SPE
    PB --> SPE
    
    SPE --> PE
    
    EH --> MTS
    AL --> MTS
    HM --> MTS
    SPE --> MTS
    
    MTS --> HTTP
    MTS --> WS
    MTS --> STDIO
    
    style SPE fill:#ffebee
    style ISM fill:#e3f2fd
    style MTS fill:#e8f5e9
```

## Security Policy Evaluation Flow

### Complete Evaluation Process

```mermaid
flowchart TD
    START[Tool Request]
    
    START --> VALIDATE[Validate Request]
    
    VALIDATE --> SANITIZE[Sanitize Parameters]
    
    SANITIZE --> LOADRULES{Rules Loaded?}
    
    LOADRULES -->|No| RELOAD[Reload Rules]
    LOADRULES -->|Yes| MATCHRULES[Match Rules by Priority]
    
    RELOAD --> MATCHRULES
    
    MATCHRULES --> LOOP{For Each Rule}
    
    LOOP --> CHECK[Check Conditions]
    
    CHECK --> PATTERN[Pattern Matching]
    
    PATTERN --> TOOLNAME{Tool Name<br/>Match?}
    PATTERN --> PARAMS{Parameters<br/>Match?}
    PATTERN --> CWD{CWD Pattern<br/>Match?}
    PATTERN --> TIME{Time Range<br/>Match?}
    
    TOOLNAME -->|All Match| MATCH[Rule Matches]
    PARAMS -->|All Match| MATCH
    CWD -->|All Match| MATCH
    TIME -->|All Match| MATCH
    
    TOOLNAME -->|Any Fail| NEXT[Next Rule]
    PARAMS -->|Any Fail| NEXT
    CWD -->|Any Fail| NEXT
    TIME -->|Any Fail| NEXT
    
    MATCH --> ACTION{Rule Action?}
    
    ACTION -->|Allow| ALLOW[Create Allow Decision]
    ACTION -->|Deny| DENY[Create Deny Decision]
    ACTION -->|Sample| SAMPLE[AI Evaluation Required]
    
    NEXT --> LOOP
    
    SAMPLE --> INFMGR{Inference<br/>Manager?}
    
    INFMGR -->|Available| NEWINF[Use Inference Manager]
    INFMGR -->|Not Available| LEGACY[Use Legacy AI Service]
    
    NEWINF --> PROVIDER[Select Provider]
    LEGACY --> AISVC[AIServiceManager]
    
    PROVIDER --> EVAL[Evaluate with AI]
    AISVC --> EVAL
    
    EVAL --> AIDECISION[AI Decision]
    
    AIDECISION --> FINAL[Final Decision]
    ALLOW --> FINAL
    DENY --> FINAL
    
    LOOP -->|No More Rules| DEFAULT[Default Deny]
    DEFAULT --> FINAL
    
    style SAMPLE fill:#e3f2fd
    style ALLOW fill:#c8e6c9
    style DENY fill:#ffcdd2
```

### Pattern Engine Detail

```mermaid
flowchart LR
    subgraph "Pattern Types"
        INPUT[Input Value]
    end
    
    subgraph "Pattern Processing"
        TYPE{Pattern Type?}
        
        STRING[String Matcher<br/>Exact/Contains]
        REGEX[Regex Matcher<br/>Compiled Pattern]
        GLOB[Glob Matcher<br/>Wildcard Match]
        JSON[JSONPath Matcher<br/>Path Expression]
    end
    
    subgraph "Caching Layer"
        CACHE{In Cache?}
        STORE[Store Result]
        GET[Get Result]
    end
    
    subgraph "Result"
        MATCH[Match Result]
    end
    
    INPUT --> TYPE
    
    TYPE -->|string| STRING
    TYPE -->|regex| REGEX
    TYPE -->|glob| GLOB
    TYPE -->|jsonpath| JSON
    
    STRING --> CACHE
    REGEX --> CACHE
    GLOB --> CACHE
    JSON --> CACHE
    
    CACHE -->|Yes| GET
    CACHE -->|No| STORE
    
    GET --> MATCH
    STORE --> MATCH
    
    style CACHE fill:#e8f5e9
```

## Inference Provider Selection Flow

### Provider Strategy

```mermaid
stateDiagram-v2
    [*] --> RequestReceived: Inference Request
    
    RequestReceived --> CheckSpecific: Check if provider specified
    
    CheckSpecific --> UseSpecific: Provider specified
    CheckSpecific --> UsePreference: No provider specified
    
    UseSpecific --> GetProvider: Get specific provider
    UsePreference --> IterateProviders: Use preference list
    
    IterateProviders --> CheckAvailable: Check next provider
    
    CheckAvailable --> ProviderExists: Provider exists?
    CheckAvailable --> NoMoreProviders: No more providers
    
    ProviderExists --> CheckHealth: Run health check
    
    CheckHealth --> Healthy: Provider healthy
    CheckHealth --> Unhealthy: Provider unhealthy
    
    Healthy --> UseProvider: Select provider
    Unhealthy --> IterateProviders: Try next
    
    GetProvider --> UseProvider
    
    UseProvider --> ExecuteEval: Execute evaluation
    
    ExecuteEval --> Success: Evaluation successful
    ExecuteEval --> Failure: Evaluation failed
    
    Success --> ReturnDecision: Return decision
    Failure --> HandleError: Handle error
    
    NoMoreProviders --> DefaultDecision: Use default deny
    
    HandleError --> ReturnDecision
    DefaultDecision --> ReturnDecision
    
    ReturnDecision --> [*]
```

### Provider Types and Capabilities

```mermaid
graph TB
    subgraph "Mock Provider"
        MOCK[MockInferenceProvider]
        MOCKRULES[Hardcoded Rules<br/>- rm -rf<br/>- sudo<br/>- eval]
    end
    
    subgraph "CLI Providers"
        CLAUDE[Claude CLI Provider]
        CLAUDECMD[claude command<br/>JSON I/O]
    end
    
    subgraph "API Providers"
        FUTURE[Future API Providers<br/>OpenAI, Gemini, etc]
    end
    
    subgraph "MCP Sampling"
        MCPS[MCPSamplingProvider]
        LEGACY[Wraps AIServiceManager]
        SAMPLING[User approval flow]
    end
    
    MOCK --> MOCKRULES
    CLAUDE --> CLAUDECMD
    MCPS --> LEGACY
    MCPS --> SAMPLING
    
    style MOCK fill:#e8f5e9
    style CLAUDE fill:#e3f2fd
    style MCPS fill:#fff3e0
```

## Error Handling and Recovery Flow

### Error Propagation

```mermaid
flowchart TD
    subgraph "Error Sources"
        DOMAIN[Domain Errors<br/>SuperegoError]
        INFRA[Infrastructure Errors<br/>Network, Timeout]
        PRES[Presentation Errors<br/>Transport specific]
    end
    
    subgraph "Error Handler"
        EH[ErrorHandler]
        CLASSIFY[Classify Error]
        TRANSFORM[Transform Error]
        LOG[Log Error]
    end
    
    subgraph "Recovery Strategies"
        RETRY[Retry Logic]
        CB[Circuit Breaker]
        FALLBACK[Fallback Decision]
    end
    
    subgraph "User Response"
        SAFE[Safe Error Message]
        DECISION[Fallback Decision]
    end
    
    DOMAIN --> EH
    INFRA --> EH
    PRES --> EH
    
    EH --> CLASSIFY
    CLASSIFY --> TRANSFORM
    TRANSFORM --> LOG
    
    CLASSIFY --> RETRY
    CLASSIFY --> CB
    CLASSIFY --> FALLBACK
    
    RETRY --> SAFE
    CB --> SAFE
    FALLBACK --> DECISION
    
    SAFE --> USER[User]
    DECISION --> USER
    
    style EH fill:#ffebee
    style FALLBACK fill:#fff3e0
```

### Circuit Breaker States

```mermaid
stateDiagram-v2
    [*] --> Closed: Initial State
    
    Closed --> Open: Failure threshold reached
    Closed --> Closed: Success
    Closed --> Closed: Failure < threshold
    
    Open --> HalfOpen: Recovery timeout
    Open --> Open: Request rejected
    
    HalfOpen --> Closed: Success
    HalfOpen --> Open: Failure
    
    note right of Closed: Normal operation<br/>All requests pass through
    
    note right of Open: Circuit broken<br/>Fast fail all requests
    
    note right of HalfOpen: Testing recovery<br/>Limited requests allowed
```

## Configuration Hot Reload Flow

### File Watcher Mechanism

```mermaid
sequenceDiagram
    participant FS as File System
    participant CW as ConfigWatcher
    participant WD as Watchdog
    participant SPE as SecurityPolicyEngine
    participant Cache as Pattern Cache
    
    CW->>WD: Start watching rules.yaml
    
    loop File Monitoring
        FS->>WD: File change event
        WD->>CW: on_modified()
        
        CW->>CW: Debounce check
        
        alt Debounce period passed
            CW->>SPE: reload_rules()
            
            SPE->>FS: Read rules.yaml
            SPE->>SPE: Parse YAML
            SPE->>SPE: Validate rules
            
            alt Validation Success
                SPE->>SPE: Update rules list
                SPE->>Cache: Clear pattern cache
                SPE->>CW: Reload complete
                CW->>CW: Log success
            else Validation Failure
                SPE->>CW: Reload failed
                CW->>CW: Log error
                SPE->>SPE: Keep old rules
            end
        else Within debounce
            CW->>CW: Skip reload
        end
    end
```

### Configuration Cascade

```mermaid
flowchart TD
    subgraph "Configuration Sources"
        YAML[config.yaml]
        ENV[Environment Variables]
        CLI[CLI Arguments]
    end
    
    subgraph "Loading Priority"
        DEFAULT[Default Values]
        FILE[File Values]
        ENVOVER[Env Overrides]
        CLIOVER[CLI Overrides]
    end
    
    subgraph "Configuration Objects"
        SERVER[ServerConfig]
        AI[AISamplingConfig]
        INF[InferenceConfig]
        TRANS[TransportConfig]
    end
    
    DEFAULT --> FILE
    FILE --> ENVOVER
    ENVOVER --> CLIOVER
    
    YAML --> FILE
    ENV --> ENVOVER
    CLI --> CLIOVER
    
    CLIOVER --> SERVER
    CLIOVER --> AI
    CLIOVER --> INF
    CLIOVER --> TRANS
    
    style CLIOVER fill:#e8f5e9
```

## Audit Logging Flow

### Audit Entry Creation

```mermaid
flowchart LR
    subgraph "Request Processing"
        REQ[Tool Request]
        DEC[Decision]
        RULES[Matched Rules]
    end
    
    subgraph "Audit Logger"
        CREATE[Create Entry]
        ENRICH[Enrich Metadata]
        STORE[Store Entry]
    end
    
    subgraph "Audit Entry"
        ENTRY["
        {
            id: uuid,
            timestamp: datetime,
            request: ToolRequest,
            decision: Decision,
            rule_matches: [rule_ids],
            ttl: datetime
        }
        "]
    end
    
    subgraph "Storage"
        MEM[In-Memory Store]
        FUTURE[Future: Persistent Store]
    end
    
    REQ --> CREATE
    DEC --> CREATE
    RULES --> CREATE
    
    CREATE --> ENRICH
    ENRICH --> ENTRY
    ENTRY --> STORE
    
    STORE --> MEM
    STORE -.-> FUTURE
    
    style ENTRY fill:#e8f5e9
    style FUTURE fill:#f5f5f5,stroke-dasharray: 5 5
```

### Audit Query Flow

```mermaid
sequenceDiagram
    participant Client
    participant MCP as MCP Server
    participant AL as AuditLogger
    participant Store as Storage
    
    Client->>MCP: get_recent_audit_entries()
    MCP->>AL: get_recent_entries(limit=10)
    
    AL->>Store: Query entries
    Store->>Store: Filter by timestamp
    Store->>Store: Sort by timestamp DESC
    Store->>Store: Limit results
    Store-->>AL: Entry list
    
    AL->>AL: Sanitize sensitive data
    AL->>AL: Format for display
    
    AL-->>MCP: Formatted entries
    MCP-->>Client: JSON response
```

## Summary

These data flow diagrams illustrate the complex interactions within the Superego MCP system. Key observations:

1. **Dual Mode Operation**: The system elegantly handles both CLI evaluation (lightweight) and full MCP server modes
2. **Layered Error Handling**: Errors are transformed and handled appropriately at each layer
3. **Flexible Provider System**: The inference architecture supports multiple provider types with fallback strategies
4. **Hot Reload Capability**: Configuration changes can be applied without server restart
5. **Comprehensive Audit Trail**: All security decisions are logged for compliance and debugging

The architecture demonstrates good separation of concerns but would benefit from dependency injection to reduce coupling and improve testability.