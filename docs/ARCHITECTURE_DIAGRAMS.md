# Superego MCP Architecture Documentation

**Version:** 1.0  
**Date:** 2025-08-15  
**Status:** Current Architecture Analysis

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [High-Level System Architecture](#high-level-system-architecture)
3. [Component Architecture](#component-architecture)
4. [Data Flow Diagrams](#data-flow-diagrams)
5. [Inference Provider Architecture](#inference-provider-architecture)
6. [Security Evaluation Flow](#security-evaluation-flow)
7. [Configuration and Dependency Management](#configuration-and-dependency-management)
8. [Current Architectural Issues](#current-architectural-issues)
9. [Recommendations](#recommendations)

## Executive Summary

Superego MCP is a security-focused Model Context Protocol (MCP) server that provides intelligent tool request interception for AI agents. The system operates in two primary modes:

1. **CLI Evaluation Mode** (`superego advise`) - A lightweight, standalone security evaluator for Claude Code hooks
2. **MCP Server Mode** (`superego mcp`) - A full-featured MCP server with rule management and advanced features

The architecture follows a layered approach with Domain, Infrastructure, and Presentation layers, but currently suffers from several architectural issues including global state management, complex initialization patterns, and tight coupling between components.

## High-Level System Architecture

```mermaid
graph TB
    subgraph "External Systems"
        CC[Claude Code]
        AI[AI Services<br/>Claude/OpenAI/Gemini]
        FS[File System<br/>Config & Rules]
    end
    
    subgraph "Superego MCP System"
        subgraph "Entry Points"
            CLI[CLI Interface<br/>superego]
            STDIO[STDIO Transport]
            HTTP[HTTP/SSE/WS Transport]
        end
        
        subgraph "Core Modes"
            EVAL[CLI Evaluation Mode<br/>advise command]
            MCP[MCP Server Mode<br/>mcp command]
        end
        
        subgraph "Core Services"
            SP[Security Policy Engine]
            INF[Inference System]
            AUDIT[Audit Logger]
        end
    end
    
    CC -->|Hook Request| CLI
    CC -->|MCP Protocol| STDIO
    AI -->|Inference| INF
    FS -->|Config/Rules| SP
    
    CLI --> EVAL
    CLI --> MCP
    
    EVAL --> SP
    MCP --> SP
    MCP --> HTTP
    MCP --> STDIO
    
    SP --> INF
    SP --> AUDIT
    
    style EVAL fill:#e1f5fe
    style MCP fill:#fff3e0
    style SP fill:#ffebee
```

## Component Architecture

### Layer Separation

```mermaid
graph TB
    subgraph "Presentation Layer"
        CLI[cli.py<br/>Unified CLI]
        CLIEVAL[cli_eval.py<br/>Standalone Evaluator]
        MCPS[mcp_server.py<br/>MCP Server]
        TS[transport_server.py<br/>Multi-Transport]
        HTTP[HTTP Transport]
        WS[WebSocket Transport]
        SSE[SSE Transport]
    end
    
    subgraph "Domain Layer"
        M[models.py<br/>Core Domain Models]
        CCM[claude_code_models.py<br/>Hook Models]
        PE[pattern_engine.py<br/>Pattern Matching]
        SPE[security_policy_engine.py<br/>Policy Evaluation]
        SVC[services.py<br/>Domain Services]
        REPO[repositories.py<br/>Domain Interfaces]
    end
    
    subgraph "Infrastructure Layer"
        INF[inference.py<br/>Provider System]
        AI[ai_service.py<br/>AI Integration]
        CFG[config.py<br/>Configuration]
        LOG[logging_config.py<br/>Logging]
        CB[circuit_breaker.py<br/>Resilience]
        PB[prompt_builder.py<br/>Prompt Construction]
    end
    
    CLI --> CLIEVAL
    CLI --> TS
    TS --> MCPS
    TS --> HTTP
    TS --> WS
    TS --> SSE
    
    CLIEVAL --> SPE
    MCPS --> SPE
    
    SPE --> M
    SPE --> PE
    SPE --> INF
    
    INF --> AI
    INF --> PB
    
    style CLI fill:#e8f5e9
    style SPE fill:#ffebee
    style INF fill:#e3f2fd
```

### Dependency Flow (Current State)

```mermaid
graph LR
    subgraph "Initialization Issues"
        MAIN[main.py<br/>Complex Init]
        GM[Global Managers]
        DI[Manual DI]
    end
    
    subgraph "Configuration"
        CM[ConfigManager]
        IC[InferenceConfig]
        SC[ServerConfig]
    end
    
    subgraph "Services"
        SPE[SecurityPolicyEngine]
        ISM[InferenceStrategyManager]
        ASM[AIServiceManager]
    end
    
    MAIN -->|Creates| CM
    MAIN -->|Creates| SPE
    MAIN -->|Creates| ISM
    MAIN -->|Creates| ASM
    
    CM -->|Loads| IC
    CM -->|Loads| SC
    
    SPE -->|Depends| ISM
    SPE -->|Depends| ASM
    ISM -->|Depends| ASM
    
    GM -->|Global State| SPE
    DI -->|Manual Wiring| Services
    
    style MAIN fill:#ffcdd2
    style GM fill:#ffcdd2
```

## Data Flow Diagrams

### CLI Evaluation Flow

```mermaid
sequenceDiagram
    participant User
    participant ClaudeCode
    participant CLI
    participant CLIEval
    participant MockProvider
    participant stdout
    
    User->>ClaudeCode: Execute tool command
    ClaudeCode->>CLI: PreToolUse hook (JSON via stdin)
    CLI->>CLIEval: evaluate_from_stdin()
    
    CLIEval->>CLIEval: Parse hook input
    CLIEval->>CLIEval: Create ToolRequest
    CLIEval->>MockProvider: evaluate(InferenceRequest)
    MockProvider->>MockProvider: Apply mock rules
    MockProvider-->>CLIEval: InferenceDecision
    
    CLIEval->>CLIEval: Convert to hook output format
    CLIEval->>stdout: JSON decision
    CLI-->>ClaudeCode: Hook response
    
    alt Decision: Allow
        ClaudeCode->>ClaudeCode: Execute tool
    else Decision: Deny/Ask
        ClaudeCode->>User: Show reason
    end
```

### MCP Server Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant Transport
    participant MCPServer
    participant SecurityPolicy
    participant InferenceManager
    participant Provider
    participant AuditLogger
    
    Client->>Transport: Tool request
    Transport->>MCPServer: evaluate_tool_request()
    MCPServer->>MCPServer: Create ToolRequest
    
    MCPServer->>SecurityPolicy: evaluate(ToolRequest)
    
    alt Rule Match Found
        SecurityPolicy->>SecurityPolicy: Apply rule action
        SecurityPolicy-->>MCPServer: Decision
    else Sample Action Required
        SecurityPolicy->>InferenceManager: get_provider()
        InferenceManager->>Provider: evaluate()
        
        alt Provider: MCP Sampling
            Provider->>Client: Request user approval
            Client-->>Provider: User decision
        else Provider: AI/CLI
            Provider->>Provider: AI evaluation
        end
        
        Provider-->>InferenceManager: InferenceDecision
        InferenceManager-->>SecurityPolicy: Decision
        SecurityPolicy-->>MCPServer: Decision
    end
    
    MCPServer->>AuditLogger: log_decision()
    MCPServer-->>Transport: Decision response
    Transport-->>Client: Response
```

### Configuration Loading Flow

```mermaid
flowchart LR
    subgraph "Configuration Sources"
        FS[File System<br/>config.yaml]
        ENV[Environment<br/>Variables]
        DEF[Default<br/>Values]
    end
    
    subgraph "ConfigManager"
        CM[ConfigManager]
        CW[ConfigWatcher]
        CACHE[Config Cache]
    end
    
    subgraph "Configuration Objects"
        SC[ServerConfig]
        IC[InferenceConfig]
        ASC[AISamplingConfig]
        TC[TransportConfig]
    end
    
    subgraph "Consumers"
        MAIN[main.py]
        SPE[SecurityPolicyEngine]
        ISM[InferenceStrategyManager]
    end
    
    FS --> CM
    ENV --> CM
    DEF --> CM
    
    CM --> CACHE
    CM --> CW
    
    CW -->|Watch| FS
    CW -->|Reload| SPE
    
    CACHE --> SC
    CACHE --> IC
    CACHE --> ASC
    CACHE --> TC
    
    SC --> MAIN
    IC --> ISM
    ASC --> SPE
    
    style CW fill:#fff3e0
    style CACHE fill:#e8f5e9
```

## Inference Provider Architecture

### Provider Hierarchy

```mermaid
classDiagram
    class InferenceProvider {
        <<abstract>>
        +evaluate(request) InferenceDecision
        +get_provider_info() ProviderInfo
        +health_check() HealthStatus
        +initialize()
        +cleanup()
    }
    
    class MockInferenceProvider {
        +evaluate(request) InferenceDecision
        -_apply_mock_rules()
    }
    
    class CLIProvider {
        -config: CLIProviderConfig
        +evaluate(request) InferenceDecision
        -_build_cli_command()
        -_parse_cli_response()
        -_validate_cli_availability()
    }
    
    class MCPSamplingProvider {
        -ai_service_manager: AIServiceManager
        -prompt_builder: SecurePromptBuilder
        +evaluate(request) InferenceDecision
        -_handle_mcp_sampling()
    }
    
    class InferenceStrategyManager {
        -providers: Dict[str, InferenceProvider]
        -config: InferenceConfig
        +get_provider(name?)
        +evaluate(request, provider?)
        -_initialize_providers()
    }
    
    InferenceProvider <|-- MockInferenceProvider
    InferenceProvider <|-- CLIProvider
    InferenceProvider <|-- MCPSamplingProvider
    InferenceStrategyManager o-- InferenceProvider
```

### Provider Selection Strategy

```mermaid
flowchart TD
    REQ[Inference Request]
    
    REQ --> CHECK{Provider<br/>Specified?}
    
    CHECK -->|Yes| SPECIFIC[Use Specific Provider]
    CHECK -->|No| PREF[Use Provider Preference List]
    
    PREF --> ITER[Iterate Providers]
    
    ITER --> AVAIL{Provider<br/>Available?}
    
    AVAIL -->|No| NEXT[Try Next Provider]
    AVAIL -->|Yes| HEALTH{Health<br/>Check OK?}
    
    HEALTH -->|No| NEXT
    HEALTH -->|Yes| USE[Use Provider]
    
    NEXT --> ITER
    
    USE --> EVAL[Evaluate Request]
    SPECIFIC --> EVAL
    
    EVAL --> RES[Return Decision]
    
    style CHECK fill:#fff3e0
    style HEALTH fill:#ffebee
```

## Security Evaluation Flow

### Rule Matching and Decision Flow

```mermaid
flowchart TD
    TR[Tool Request]
    
    TR --> PE[Pattern Engine]
    
    PE --> RULES{Match Rules<br/>by Priority}
    
    RULES --> R1[Rule 1<br/>Priority 0]
    RULES --> R2[Rule 2<br/>Priority 1]
    RULES --> RN[Rule N<br/>Priority N]
    
    R1 --> MATCH1{Conditions<br/>Match?}
    R2 --> MATCH2{Conditions<br/>Match?}
    RN --> MATCHN{Conditions<br/>Match?}
    
    MATCH1 -->|Yes| ACTION1{Action?}
    MATCH2 -->|Yes| ACTION2{Action?}
    MATCHN -->|Yes| ACTIONN{Action?}
    
    MATCH1 -->|No| NEXT1[Continue]
    MATCH2 -->|No| NEXT2[Continue]
    
    ACTION1 -->|Allow| ALLOW[Return Allow]
    ACTION1 -->|Deny| DENY[Return Deny]
    ACTION1 -->|Sample| SAMPLE[AI Evaluation]
    
    SAMPLE --> INF[Inference Manager]
    INF --> DECISION[Final Decision]
    
    style SAMPLE fill:#e3f2fd
    style ALLOW fill:#c8e6c9
    style DENY fill:#ffcdd2
```

### Pattern Matching Engine

```mermaid
flowchart LR
    subgraph "Pattern Types"
        STRING[String Pattern]
        REGEX[Regex Pattern]
        GLOB[Glob Pattern]
        JSON[JSONPath Pattern]
    end
    
    subgraph "Pattern Engine"
        CACHE[Pattern Cache<br/>LRU]
        MATCHER[Pattern Matcher]
        EVAL[Condition Evaluator]
    end
    
    subgraph "Complex Conditions"
        AND[AND Logic]
        OR[OR Logic]
        TIME[Time Range]
        PARAM[Parameter Match]
    end
    
    STRING --> MATCHER
    REGEX --> MATCHER
    GLOB --> MATCHER
    JSON --> MATCHER
    
    MATCHER --> CACHE
    CACHE --> EVAL
    
    EVAL --> AND
    EVAL --> OR
    EVAL --> TIME
    EVAL --> PARAM
    
    style CACHE fill:#e8f5e9
```

## Configuration and Dependency Management

### Current Issues - Global State

```mermaid
flowchart TD
    subgraph "Global State Problem"
        MCP[mcp_server.py]
        GLOBALS[Global Variables<br/>Lines 19-24]
        
        MCP --> GLOBALS
        
        GLOBALS --> G1[global security_policy]
        GLOBALS --> G2[global audit_logger]
        GLOBALS --> G3[global error_handler]
        GLOBALS --> G4[global health_monitor]
    end
    
    subgraph "Initialization Complexity"
        MAIN[main.py<br/>async_main()]
        INIT[Lines 35-209<br/>Complex Init]
        
        MAIN --> INIT
        
        INIT --> C1[Load Config]
        INIT --> C2[Create Components]
        INIT --> C3[Wire Dependencies]
        INIT --> C4[Start Services]
    end
    
    subgraph "Manual DI Pattern"
        DEP[dependencies dict]
        
        DEP --> D1[ai_service_manager]
        DEP --> D2[prompt_builder]
        
        D1 --> ISM[InferenceStrategyManager]
        D2 --> ISM
    end
    
    style GLOBALS fill:#ffcdd2
    style INIT fill:#ffcdd2
```

### Proposed DI Architecture

```mermaid
flowchart TB
    subgraph "Bootstrap Layer"
        CONT[DI Container]
        BOOT[Application Bootstrap]
        FACT[Service Factories]
    end
    
    subgraph "Service Registration"
        REG[Service Registry]
        LIFE[Lifecycle Management]
        SCOPE[Scoped Instances]
    end
    
    subgraph "Dependency Resolution"
        AUTO[Auto-wiring]
        LAZY[Lazy Loading]
        CYCLE[Cycle Detection]
    end
    
    BOOT --> CONT
    CONT --> REG
    CONT --> FACT
    
    REG --> LIFE
    REG --> SCOPE
    
    FACT --> AUTO
    AUTO --> LAZY
    AUTO --> CYCLE
    
    style CONT fill:#e8f5e9
    style AUTO fill:#e3f2fd
```

## Current Architectural Issues

### 1. Global State Management

The system currently uses global variables for dependency injection in the MCP server, making it difficult to test and creating tight coupling between components.

**Impact:**
- Testing requires mocking global state
- Multiple server instances not possible
- Difficult to reason about dependencies

### 2. Complex Initialization

The main.py file contains a 170+ line initialization function that mixes concerns:
- Configuration loading
- Component creation
- Dependency wiring
- Service startup

**Impact:**
- Hard to test individual components
- Difficult to modify initialization order
- Error handling is complex and scattered

### 3. Inference System Complexity

The inference system has evolved to support multiple providers but maintains backward compatibility through complex wrapper patterns:
- Legacy AIServiceManager wrapped by MCPSamplingProvider
- Duplicate configuration classes
- Complex provider initialization logic

**Impact:**
- Maintenance burden
- Potential for configuration drift
- Performance overhead from wrapper layers

### 4. Configuration Management

Configuration is scattered across multiple locations:
- CLIProviderConfig defined in multiple files
- Environment variable handling mixed with file loading
- No clear configuration validation layer

**Impact:**
- Configuration errors discovered at runtime
- Difficult to understand all configuration options
- Potential security issues from unvalidated input

### 5. Error Handling Patterns

Error handling is inconsistent across layers:
- Domain layer uses custom exceptions
- Infrastructure uses various error types
- Presentation layer has transport-specific errors

**Impact:**
- Difficult to handle errors consistently
- User-facing error messages may leak implementation details
- Error recovery strategies are ad-hoc

## Recommendations

### 1. Implement Proper Dependency Injection

Create a dedicated bootstrap package with a DI container:
```
src/superego_mcp/bootstrap/
├── container.py      # DI container implementation
├── factories.py      # Service factories
└── application.py    # Application bootstrap
```

### 2. Refactor Main Initialization

Break down the complex initialization into focused components:
- ConfigurationLoader: Handle all config loading
- ServiceBuilder: Create and wire services
- ApplicationRunner: Manage lifecycle

### 3. Simplify Inference Architecture

Create a clean provider abstraction without legacy wrappers:
- Define clear provider interface
- Implement providers directly
- Use factory pattern for provider creation

### 4. Consolidate Configuration

Create a single source of truth for configuration:
- Define all config models in one place
- Implement configuration validation
- Use configuration schemas

### 5. Standardize Error Handling

Implement a consistent error handling strategy:
- Define error hierarchy
- Create error transformation layer
- Implement user-friendly error messages

### 6. Performance Optimizations

Address performance bottlenecks:
- Implement proper caching strategies
- Use async I/O consistently
- Optimize pattern matching with better algorithms

### 7. Testing Infrastructure

Improve testability:
- Remove global state dependencies
- Create test fixtures for common scenarios
- Implement integration test harness

## Conclusion

Superego MCP demonstrates good architectural principles but has accumulated technical debt through rapid development. The primary issues revolve around dependency management, configuration handling, and the evolution of the inference system. By addressing these issues systematically, the codebase can become more maintainable, testable, and performant while maintaining its security-first focus.

The recommended refactoring plan prioritizes high-impact changes that will improve the developer experience and system reliability without requiring a complete rewrite. The modular architecture already in place provides a solid foundation for these improvements.