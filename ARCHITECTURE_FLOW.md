# System Architecture Flow Diagram

## Quick Overview

```
User Query
    ↓
[API Route] → Generate session_id from IP
    ↓
[Orchestrator] → LCEL Routing Chain → Determine Agent(s)
    ↓
[BaseAgent] → initialize_agent → Uses RAG Tool
    ↓
[RAG Tool] → Vector Store → Similarity Search
    ↓
[Agent] → LLM generates response
    ↓
[Orchestrator] → Bundle & return
    ↓
[API] → JSON Response
```

## Complete Flow: User Query → Response

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER MAKES QUERY                                  │
│                    POST /api/v1/query                                       │
│                    { "query": "what are browser requirements?" }            │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Route Handler                                     │
│                    src/querying/routes.py                                    │
│                                                                               │
│  1. Extract client IP from request                                           │
│  2. Generate session_id from IP (hashed)                                     │
│     → session_id = "ip_a1b2c3d4e5f6g7h8"                                   │
│  3. Parse QueryRequest (query, min_similarity)                               │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                                         │
│                    src/agents/orchestrator.py                                │
│                    Orchestrator.process_query_async()                        │
│                                                                               │
│  Step 1: Get/Create Conversation Context                                     │
│    → ConversationContext(session_id)                                        │
│    → Stores message history, agent history                                  │
│                                                                               │
│  Step 2: Detect Multi-Agent Need                                             │
│    → _detect_multi_agent(query)                                             │
│    → Uses LCEL chain with multi_agent_prompt                                  │
│    → Returns: {                                                              │
│         "requires_multiple_agents": false,                                   │
│         "agents": ["tech"],                                                  │
│         "requires_sequential": false                                         │
│       }                                                                       │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────┴─────────┐
                    │                   │
          ┌─────────▼─────────┐  ┌──────▼──────────────┐
          │  SINGLE AGENT     │  │  MULTI-AGENT       │
          │  PROCESSING       │  │  PROCESSING        │
          └─────────┬─────────┘  └──────┬─────────────┘
                    │                   │
                    │                   ├───► PARALLEL (independent queries)
                    │                   │     → Multiple agents process simultaneously
                    │                   │
                    │                   └───► SEQUENTIAL (dependent queries)
                    │                         → Agents process one-by-one with context handoff
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ROUTE TO SPECIALIST AGENT                                 │
│                    _route_single_agent(query)                                │
│                                                                               │
│  Uses LCEL chain with routing_prompt                                           │
│  → Analyzes query                                                           │
│  → Returns agent name: "tech"                                               │
│                                                                               │
│  Get Agent Instance:                                                         │
│    → _get_agent_instance("tech")                                            │
│    → Creates TechAgent if not exists                                         │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SPECIALIST AGENT                                          │
│                    src/agents/base_agent.py                                  │
│                    TechAgent.process_query()                                 │
│                                                                               │
│  Agent Structure:                                                             │
│    ├── agent_executor (initialize_agent with tools)                          │
│    └── tools = [tech_rag_search Tool]                                        │
│                                                                               │
│  Process Flow:                                                                │
│    1. Format conversation history                                            │
│    2. Run agent_executor.run(query)                                          │
│       └── Agent decides to use tech_rag_search tool                          │
│    3. Extract sources for response metadata                                  │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RAG TOOL EXECUTION                                        │
│                    src/agents/tools.py                                       │
│                    tech_rag_search.run(query)                                │
│                                                                               │
│  1. Load Vector Store                                                         │
│     → load_vector_store("tech_handbook")                                    │
│     → Chroma vector store from data/vectorstore/tech_handbook/              │
│                                                                               │
│  2. Similarity Search                                                        │
│     → vector_store.similarity_search_with_score(query, k=8)                 │
│     → Returns: [(doc, distance), ...]                                        │
│                                                                               │
│  3. Convert Distance to Similarity                                           │
│     → similarity = 1.0 - distance                                             │
│     → Filter by min_similarity (default 0.75)                                │
│     → Deduplicate by content                                                 │
│                                                                               │
│  4. Format Context                                                            │
│     → Returns formatted string with retrieved chunks                         │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AGENT GENERATES RESPONSE                                   │
│                    AgentExecutor (initialize_agent)                          │
│                                                                               │
│  Agent receives context from tool and generates answer:                      │
│    → Uses LLM with system prompt                                             │
│    → Incorporates retrieved context                                          │
│    → Generates final response                                                │
│                                                                               │
│  Extract Sources:                                                            │
│    → _retrieve_context() called again for source metadata                     │
│    → Builds sources list with similarity scores                              │
│                                                                               │
│  Return AgentResponse:                                                        │
│    {                                                                          │
│      "content": "The browser requirements are...",                            │
│      "agent_name": "tech",                                                   │
│      "sources": [...],                                                        │
│      "metadata": {"success": true, "method": "initialize_agent"}             │
│    }                                                                          │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR BUNDLES RESPONSE                             │
│                    _bundle_responses()                                       │
│                                                                               │
│  For Single Agent:                                                           │
│    → Returns response.content directly                                       │
│                                                                               │
│  For Multi-Agent:                                                             │
│    → Combines responses from all agents                                       │
│    → Formats: "[AGENT_NAME]\n{content}\n\n[AGENT_NAME]\n{content}"         │
│                                                                               │
│  Update Conversation Context:                                                │
│    → context.add_message("assistant", bundled_content)                       │
│    → context.agent_history.append(agent_name)                                │
│                                                                               │
│  Return OrchestratorResponse:                                                 │
│    {                                                                          │
│      "content": "The browser requirements...",                               │
│      "agents_used": ["tech"],                                                │
│      "routing_mode": "single",                                               │
│      "responses": [AgentResponse],                                           │
│      "metadata": {...}                                                       │
│    }                                                                          │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    API RESPONSE FORMATTING                                   │
│                    src/querying/routes.py                                    │
│                                                                               │
│  1. Extract all sources from agent responses                                 │
│  2. Build QueryResponse:                                                     │
│     {                                                                         │
│       "content": "...",                                                       │
│       "agents_used": ["tech"],                                              │
│       "routing_mode": "single",                                              │
│       "sources": [SourceResponse, ...],                                      │
│       "metadata": {...},                                                     │
│       "session_id": "ip_a1b2c3d4e5f6g7h8"                                    │
│     }                                                                         │
│                                                                               │
│  3. Return JSON response to user                                             │
└────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   USER RECEIVES     │
                    │   RESPONSE          │
                    └─────────────────────┘
```

## Component Details

### 1. **API Layer** (`src/querying/routes.py`)
- Receives HTTP POST request
- Generates session_id from IP address
- Calls orchestrator
- Formats response

### 2. **Orchestrator** (`src/agents/orchestrator.py`)
- **LCEL Routing Chain**: Uses LCEL chain to determine which agent(s) to use
- **Multi-Agent Detection**: Detects if query needs multiple agents using LCEL chain
- **Context Management**: Maintains conversation history per session
- **Response Bundling**: Combines multiple agent responses

### 3. **Specialist Agents** (`src/agents/base_agent.py`)
- **initialize_agent**: Uses LangChain's `initialize_agent` with tools
- **RAG Tools**: Each agent has a RAG search tool
- **Source Extraction**: Retrieves sources for response metadata

### 4. **RAG Tools** (`src/agents/tools.py`)
- **Tool Interface**: LangChain `Tool` for knowledge base search
- **Vector Store Access**: Loads Chroma vector store
- **Similarity Search**: Searches with filtering and deduplication
- **Context Formatting**: Formats retrieved chunks

### 5. **Vector Store** (`src/indexing/embeddings.py`)
- **Chroma**: Stores embeddings and documents
- **Per-Handbook**: Each handbook has its own vector store
- **Cosine Similarity**: Uses cosine distance for similarity search

## Data Flow

```
User Query
    ↓
[FastAPI Route] → Extract IP → Generate session_id
    ↓
[Orchestrator] → LCEL Chain (routing) → Determine agent(s)
    ↓
[BaseAgent] → initialize_agent → Agent decides to use tool
    ↓
[RAG Tool] → Vector Store → Similarity Search → Filter & Deduplicate
    ↓
[Agent] → LLM generates response from context
    ↓
[Orchestrator] → Bundle response → Update conversation context
    ↓
[FastAPI] → Format response → Return JSON
    ↓
User Response
```

## Key Technologies Used

- **LangChain Components**:
  - `initialize_agent` - Agent with tool usage
  - `LCEL` - LangChain Expression Language for prompt+model chains
  - `Tool` - Modular RAG functionality
  - `ChatPromptTemplate` - Structured prompts

- **Vector Store**: Chroma with cosine similarity
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: OpenAI GPT models (gpt-4o-mini for routing, configurable for agents)
- **Observability**: Langfuse for tracing and monitoring

## Session Management

```
Session ID (from IP) → ConversationContext
    ├── messages: [{"role": "user", "content": "..."}, ...]
    ├── agent_history: ["tech", "finance", ...]
    └── last_agent: "tech"
```

Each session maintains its own conversation history, allowing for context-aware responses across multiple queries.

