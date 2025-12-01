"""Base agent class for specialist agents using LangChain tools and agents."""

import os
from abc import ABC
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain.agents import initialize_agent, AgentType, AgentExecutor
from langfuse import observe
from langfuse.langchain import CallbackHandler

# Load environment variables
load_dotenv()

from typing import Optional, Union
from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS

from config import LLM_MODEL, MIN_SIMILARITY
from indexing.embeddings import load_vector_store
from querying.tools.rag_tool import get_rag_tools_for_agent
from utils.llm import initialize_llm


@dataclass
class AgentResponse:
    """Response from an agent."""
    content: str
    agent_name: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for specialist agents."""
    
    def __init__(
        self,
        name: str,
        handbook_name: str,
        description: str,
        llm_model: str = None,
        vector_store: Optional[Union[Chroma, FAISS]] = None,
    ):
        """
        Initialize the agent.
        
        Args:
            name: Agent name (e.g., "finance", "hr")
            handbook_name: Name of the handbook/vector store
            description: Agent description
            llm_model: LLM model to use. Defaults to config LLM_MODEL.
            vector_store: Preloaded vector store. If None, will load on demand (slower)
        """
        self.name = name
        self.handbook_name = handbook_name
        self.description = description
        self.llm_model = llm_model or LLM_MODEL
        
        # Initialize Langfuse callback handler
        # CallbackHandler reads from environment variables automatically
        self.langfuse_handler = CallbackHandler()
        
        # Initialize LLM
        self._initialize_llm()
        
        # Store preloaded vector store or None for lazy loading
        self._vector_store = vector_store
        
        # Get RAG tools for this agent (pass preloaded vector store)
        self.tools = get_rag_tools_for_agent(name, handbook_name, vector_store=vector_store)
        
        # Create agent using initialize_agent with tools
        self._create_agent_with_tools()
    
    def _initialize_llm(self):
        """Initialize the LLM with Langfuse instrumentation."""
        self.llm = initialize_llm(
            model=self.llm_model,
            langfuse_handler=self.langfuse_handler
        )
    
    def _create_agent_with_tools(self):
        """Create agent using initialize_agent with RAG tools."""
        system_message = f"""You are a {self.name.upper()} specialist agent for JupiterIQ, a SaaS company.

Your role: {self.description}

You have access to tools to search the {self.handbook_name} knowledge base. Always use the {self.name}_rag_search tool to search the knowledge base when answering questions.

Guidelines:
1. Always use the {self.name}_rag_search tool to search the knowledge base when answering questions
2. Answer based on the retrieved context from the tool
3. If the context doesn't contain enough information, say so clearly
4. Be concise but thorough
5. Maintain a professional, helpful tone
6. If the query is outside your domain, acknowledge it and suggest routing to another agent"""
        
        # Initialize agent with tools using LangChain's initialize_agent
        self.agent_executor = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=False,
            agent_kwargs={
                "system_message": system_message,
            },
            handle_parsing_errors=True,
        )
    
    def _load_vector_store(self):
        """Lazy load the vector store."""
        if self._vector_store is None:
            self._vector_store = load_vector_store(self.handbook_name)
        return self._vector_store
    
    def _retrieve_context(
        self, 
        query: str, 
        k: int = 4,
        min_similarity: float = MIN_SIMILARITY
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from the vector store.
        
        Chroma returns cosine distance (0 = identical, 2 = opposite).
        We convert to similarity: similarity = 1 - distance
        
        Args:
            query: User query
            k: Number of documents to retrieve
            min_similarity: Minimum similarity threshold (0.0 to 1.0). 
                          Defaults to config MIN_SIMILARITY.
            
        Returns:
            List of retrieved documents with metadata, filtered by min_similarity
        """
        
        vector_store = self._load_vector_store()
        
        # Retrieve relevant documents (Chroma returns cosine distance)
        docs = vector_store.similarity_search_with_score(query, k=k)
        
        # Format for context and convert distance to similarity
        context_docs = []
        for doc, distance in docs:
            # Convert cosine distance to similarity
            # For cosine: similarity = 1 - distance
            # Distance range: 0 (identical) to 2 (opposite)
            # Similarity range: 1 (identical) to -1 (opposite)
            similarity = 1.0 - float(distance)
            
            # Filter by minimum similarity threshold
            if similarity >= min_similarity:
                context_docs.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity": similarity,
                    "distance": float(distance),  # Keep distance for reference
                })
        
        return context_docs
    
    @observe(name="agent_process_query")
    def process_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        k: int = 4,
        min_similarity: float = MIN_SIMILARITY,
    ) -> AgentResponse:
        """
        Process a query and generate a response.
        
        Args:
            query: User query
            conversation_history: Previous conversation messages [{"role": "user/assistant", "content": "..."}]
            k: Number of documents to retrieve
            min_similarity: Minimum similarity threshold (0.0 to 1.0). Defaults to config MIN_SIMILARITY.
            
        Returns:
            AgentResponse with answer and sources
        """
        # Metadata is captured automatically by @observe decorator
        
        try:
            # Format conversation history if provided
            if conversation_history:
                history_context = "\n".join([
                    f"{msg['role'].title()}: {msg['content']}"
                    for msg in conversation_history[-5:]  # Last 5 messages
                ])
                full_query = f"Previous conversation:\n{history_context}\n\nCurrent question: {query}"
            else:
                full_query = query
            
            # Run agent with tools (agent will use RAG tool automatically)
            response_content = self.agent_executor.run(
                full_query,
                callbacks=[self.langfuse_handler]
            )
            
            # Extract sources by retrieving context separately for metadata
            # (The agent used the tool, but we need source details for response)
            context_docs = self._retrieve_context(query, k=k, min_similarity=min_similarity)
            
            # Extract sources
            sources = [
                {
                    "content": doc["content"],  # Full content, no truncation
                    "metadata": doc["metadata"],
                    "similarity": doc["similarity"],
                    "distance": doc.get("distance"),  # Keep for reference
                }
                for doc in context_docs
            ]
            
            # Metadata captured by @observe decorator
            
            return AgentResponse(
                content=response_content,
                agent_name=self.name,
                sources=sources,
                metadata={"success": True},
            )
            
        except Exception as e:
            # Error is automatically captured by @observe decorator
            return AgentResponse(
                content=f"I encountered an error while processing your query. Please try again or contact support if the issue persists.",
                agent_name=self.name,
                sources=[],
                metadata={"error": str(e), "error_type": type(e).__name__},
            )

