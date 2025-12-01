# System Flow Diagram (Mermaid)

## Complete System Flow

```mermaid
graph TD
    A[User Query<br/>POST /api/v1/query] --> B[FastAPI Route Handler]
    B --> C[Extract Client IP]
    C --> D[Generate session_id<br/>from IP hash]
    D --> E[Orchestrator.process_query_async]
    
    E --> F[Get Conversation Context<br/>session_id → ConversationContext]
    F --> G[Detect Multi-Agent Need<br/>LCEL chain with multi_agent_prompt]
    
    G --> H{Multi-Agent?}
    H -->|No| I[Route Single Agent<br/>LCEL chain with routing_prompt]
    H -->|Yes| J{Sequential or Parallel?}
    
    J -->|Parallel| K[Process Multiple Agents<br/>in Parallel]
    J -->|Sequential| L[Process Multiple Agents<br/>Sequentially with Context]
    
    I --> M[Get Agent Instance<br/>create_agent]
    K --> M
    L --> M
    
    M --> N[BaseAgent.process_query]
    N --> O[AgentExecutor.run<br/>initialize_agent]
    
    O --> P[Agent uses RAG tool]
    P --> Q[RAG Tool Execution<br/>tech_rag_search]
    
    Q --> S[Load Vector Store<br/>Chroma]
    S --> T[Similarity Search<br/>with_score]
    T --> U[Convert Distance to Similarity<br/>Filter by min_similarity]
    U --> V[Format Context String]
    V --> W[Return to Agent]
    
    W --> X[Agent generates response<br/>using LLM with context]
    R --> X
    
    X --> Y[Extract Sources<br/>_retrieve_context]
    Y --> Z[Return AgentResponse<br/>content + sources]
    
    Z --> AA[Orchestrator bundles responses]
    AA --> AB[Update Conversation Context]
    AB --> AC[Return OrchestratorResponse]
    
    AC --> AD[FastAPI formats response]
    AD --> AE[Return JSON to User]
    
    style A fill:#e1f5ff
    style E fill:#fff4e1
    style N fill:#e8f5e9
    style Q fill:#f3e5f5
    style S fill:#fce4ec
    style AE fill:#e1f5ff
```

## Component Interaction Diagram

```mermaid
graph LR
    subgraph "API Layer"
        A[FastAPI Route]
        B[Session Management]
    end
    
    subgraph "Orchestration Layer"
        C[Orchestrator]
        D[LCEL Routing Chain]
        E[Multi-Agent Detection]
        F[Context Manager]
    end
    
    subgraph "Agent Layer"
        G[BaseAgent]
        H[initialize_agent]
        I[AgentExecutor]
    end
    
    subgraph "Tool Layer"
        J[RAG Tool]
        K[tech_rag_search]
        L[finance_rag_search]
        M[hr_rag_search]
        N[legal_rag_search]
        O[general_rag_search]
    end
    
    subgraph "Vector Store Layer"
        P[Chroma Vector Store]
        Q[tech_handbook]
        R[finance_handbook]
        S[hr_handbook]
        T[legal_handbook]
        U[general_handbook]
    end
    
    A --> B
    B --> C
    C --> D
    C --> E
    C --> F
    C --> G
    G --> H
    H --> I
    I --> J
    J --> K
    J --> L
    J --> M
    J --> N
    J --> O
    K --> P
    L --> P
    M --> P
    N --> P
    O --> P
    P --> Q
    P --> R
    P --> S
    P --> T
    P --> U
```

## Data Flow Sequence

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI Route
    participant Orch as Orchestrator
    participant Agent as BaseAgent
    participant Tool as RAG Tool
    participant VS as Vector Store
    participant LLM as OpenAI LLM
    
    User->>API: POST /api/v1/query
    API->>API: Generate session_id from IP
    API->>Orch: process_query_async(query, session_id)
    
    Orch->>Orch: Get conversation context
    Orch->>LLM: LCEL chain (multi-agent detection)
    LLM-->>Orch: {agents: ["tech"], requires_multi: false}
    
    Orch->>LLM: LCEL chain (routing)
    LLM-->>Orch: "tech"
    
    Orch->>Agent: process_query(query, history)
    Agent->>Agent: Format conversation history
    Agent->>Agent: agent_executor.run(query)
    
    Agent->>Tool: tech_rag_search(query)
    Tool->>VS: Load vector store
    Tool->>VS: similarity_search_with_score(query, k=8)
    VS-->>Tool: [(doc, distance), ...]
    Tool->>Tool: Convert distance to similarity
    Tool->>Tool: Filter by min_similarity
    Tool->>Tool: Deduplicate
    Tool-->>Agent: Formatted context string
    
    Agent->>LLM: Generate response with context
    LLM-->>Agent: Response text
    
    Agent->>VS: _retrieve_context() for sources
    VS-->>Agent: Source documents with metadata
    Agent-->>Orch: AgentResponse(content, sources)
    
    Orch->>Orch: Bundle responses
    Orch->>Orch: Update conversation context
    Orch-->>API: OrchestratorResponse
    
    API->>API: Format QueryResponse
    API-->>User: JSON Response
```

## Key Decision Points

```mermaid
flowchart TD
    Start[Query Received] --> CheckMulti{Multi-Agent<br/>Detection}
    
    CheckMulti -->|Single Agent| RouteSingle[Route to Single Agent]
    CheckMulti -->|Multiple Agents| CheckSeq{Sequential<br/>or Parallel?}
    
    CheckSeq -->|Sequential| SeqProcess[Process with Context Handoff]
    CheckSeq -->|Parallel| ParProcess[Process Independently]
    
    RouteSingle --> GetAgent[Get Agent Instance]
    SeqProcess --> GetAgent
    ParProcess --> GetAgent
    
    GetAgent --> AgentProcess[Agent.process_query]
    AgentProcess --> UseTool{Use RAG Tool?}
    
    UseTool -->|Yes| ToolExec[Execute RAG Tool]
    
    ToolExec --> VectorSearch[Vector Store Search]
    VectorSearch --> Filter[Filter by Similarity]
    Filter --> Format[Format Context]
    Format --> LLMGen[LLM Generates Response]
    LLMGen --> ExtractSources[Extract Sources]
    ExtractSources --> Bundle[Bundle Responses]
    Bundle --> Return[Return to User]
    
    style CheckMulti fill:#fff4e1
    style CheckSeq fill:#fff4e1
    style UseTool fill:#e8f5e9
    style VectorSearch fill:#f3e5f5
```

## Technology Stack Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE                            │
│              HTTP POST Request                               │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────▼────────┐            ┌────────▼────────┐
│   FastAPI      │            │   Langfuse       │
│   (Web Server) │            │   (Observability)│
└───────┬────────┘            └─────────────────┘
        │
┌───────▼──────────────────────────────────────┐
│           ORCHESTRATOR                         │
│  • LCEL Chain (Routing)                       │
│  • LCEL Chain (Multi-Agent Detection)         │
│  • Context Management                         │
└───────┬───────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────┐
│           BASE AGENT                           │
│  • initialize_agent (LangChain)               │
│  • AgentExecutor                               │
└───────┬───────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────┐
│           RAG TOOLS                            │
│  • Tool (LangChain)                           │
│  • Vector Store Access                        │
└───────┬───────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────┐
│           VECTOR STORE                         │
│  • Chroma                                     │
│  • OpenAI Embeddings                         │
│  • Cosine Similarity                         │
└──────────────────────────────────────────────┘
```

