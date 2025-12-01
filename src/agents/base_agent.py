"""Base agent class for specialist agents."""

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langfuse import observe
from langfuse.langchain import CallbackHandler

# Load environment variables
load_dotenv()

from config import LLM_MODEL, MIN_SIMILARITY
from indexing.embeddings import load_vector_store
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
    ):
        """
        Initialize the agent.
        
        Args:
            name: Agent name (e.g., "finance", "hr")
            handbook_name: Name of the handbook/vector store
            description: Agent description
            llm_model: LLM model to use. Defaults to config LLM_MODEL.
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
        
        # Load vector store (lazy loading - will be loaded on first use)
        self._vector_store = None
        
        # Create agent prompt
        self._create_agent_prompt()
    
    def _initialize_llm(self):
        """Initialize the LLM with Langfuse instrumentation."""
        self.llm = initialize_llm(
            model=self.llm_model,
            langfuse_handler=self.langfuse_handler
        )
    
    def _load_vector_store(self):
        """Lazy load the vector store."""
        if self._vector_store is None:
            self._vector_store = load_vector_store(self.handbook_name)
        return self._vector_store
    
    def _create_agent_prompt(self):
        """Create the agent-specific prompt template."""
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are a {self.name.upper()} specialist agent for JupiterIQ, a SaaS company.

Your role: {self.description}

You have access to the {self.handbook_name} knowledge base. Use the retrieved context to provide accurate, helpful answers.

Guidelines:
1. Answer based on the provided context from the knowledge base
2. If the context doesn't contain enough information, say so clearly
3. Be concise but thorough
4. Maintain a professional, helpful tone
5. If the query is outside your domain, acknowledge it and suggest routing to another agent

Context from knowledge base:
{{context}}

Previous conversation context (if any):
{{conversation_history}}

User query: {{query}}

Provide a helpful, accurate response based on the context above:"""),
            ("human", "{query}"),
        ])
    
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
            # Retrieve relevant context (filtered by min_similarity)
            context_docs = self._retrieve_context(query, k=k, min_similarity=min_similarity)
            
            if not context_docs:
                return AgentResponse(
                    content=f"I couldn't find relevant information in the {self.handbook_name} knowledge base to answer your query. Please try rephrasing or contact support for assistance.",
                    agent_name=self.name,
                    sources=[],
                    metadata={"error": "no_context_found"},
                )
            
            # Format context for prompt
            context_text = "\n\n".join([
                f"[Source {i+1}]\n{doc['content']}"
                for i, doc in enumerate(context_docs)
            ])
            
            # Format conversation history
            history_text = ""
            if conversation_history:
                history_text = "\n".join([
                    f"{msg['role'].title()}: {msg['content']}"
                    for msg in conversation_history[-5:]  # Last 5 messages
                ])
            
            # Create RAG chain
            chain = (
                {
                    "context": lambda x: context_text,
                    "conversation_history": lambda x: history_text,
                    "query": RunnablePassthrough(),
                }
                | self.prompt
                | self.llm
                | StrOutputParser()
            )
            
            # Generate response
            response_content = chain.invoke(
                query,
                config={"callbacks": [self.langfuse_handler]}
            )
            
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

