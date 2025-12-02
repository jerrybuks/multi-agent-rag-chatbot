"""LangChain Tools for specialist agents."""

from typing import List, Dict, Any, Optional, Union
from langchain.agents import Tool
from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS
try:
    from langchain_core.pydantic_v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field

from config import MIN_SIMILARITY


class RAGToolInput(BaseModel):
    """Input schema for RAG tool."""
    query: str = Field(description="The user's question or query to search for in the knowledge base")


def create_rag_tool(
    handbook_name: str,
    agent_name: str,
    description: str,
    vector_store: Optional[Union[Chroma, FAISS]] = None,
) -> Tool:
    """
    Create a RAG (Retrieval Augmented Generation) tool for a specialist agent.
    
    Args:
        handbook_name: Name of the handbook/vector store
        agent_name: Name of the agent (e.g., "finance", "tech")
        description: Description of what this tool does
        vector_store: Preloaded vector store. If None, will load on demand (slower)
        
    Returns:
        LangChain Tool instance for RAG retrieval
    """
    
    # Store the vector store in closure
    _store = vector_store
    
    def _rag_search(query: str) -> str:
        """
        Search the knowledge base and return relevant context.
        
        Args:
            query: User query string
            
        Returns:
            Formatted context string with retrieved documents
        """
        # Use preloaded vector store if available, otherwise load on demand
        if _store is None:
            from indexing.embeddings import load_vector_store
            try:
                store = load_vector_store(handbook_name)
            except Exception as e:
                print(f"Error loading vector store for {handbook_name}: {e}")
                return f"No relevant information found in {handbook_name} knowledge base."
        else:
            store = _store
        
        # Check if store is valid
        if store is None:
            print(f"Vector store for {handbook_name} is None")
            return f"No relevant information found in {handbook_name} knowledge base."
        
        # Use default k and min_similarity (can be made configurable later)
        k = 4
        min_similarity = MIN_SIMILARITY
        
        # Retrieve documents
        try:
            docs = store.similarity_search_with_score(query, k=k * 2)
        except Exception as e:
            print(f"Error searching vector store for {handbook_name}: {e}")
            return f"No relevant information found in {handbook_name} knowledge base."
        
        # Convert distance to similarity and filter
        context_docs = []
        seen_content = set()
        
        for doc, distance in docs:
            similarity = 1.0 - float(distance)
            
            if similarity >= min_similarity:
                content_normalized = doc.page_content.strip()
                
                if content_normalized not in seen_content:
                    seen_content.add(content_normalized)
                    context_docs.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "similarity": similarity,
                    })
                    
                    if len(context_docs) >= k:
                        break
        
        if not context_docs:
            return f"No relevant information found in {handbook_name} knowledge base."
        
        # Format context
        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(
                f"[Source {i}] (Similarity: {doc['similarity']:.2f})\n{doc['content']}"
            )
        
        return "\n\n".join(context_parts)
    
    return Tool(
        name=f"{agent_name}_rag_search",
        func=_rag_search,
        description=description,
    )


def get_rag_tools_for_agent(
    agent_name: str, 
    handbook_name: str,
    vector_store: Optional[Union[Chroma, FAISS]] = None,
) -> List[Tool]:
    """
    Get RAG tools for a specific agent.
    
    Args:
        agent_name: Name of the agent
        handbook_name: Name of the handbook/vector store
        vector_store: Preloaded vector store. If None, will load on demand (slower)
        
    Returns:
        List of tools for the agent
    """
    descriptions = {
        "finance": f"Search the finance and billing knowledge base for information about payments, invoices, pricing, refunds, and financial matters.",
        "hr": f"Search the account management and user support knowledge base for information about accounts, users, subscriptions, and account settings.",
        "legal": f"Search the legal and compliance knowledge base for information about terms of service, privacy policies, compliance, and legal agreements.",
        "tech": f"Search the technical support and integration knowledge base for information about API documentation, integrations, troubleshooting, and technical implementation.",
        "general_knowledge": f"Search the general company knowledge base for general company information, product overview, and company policies.",
    }
    
    description = descriptions.get(agent_name, f"Search the {handbook_name} knowledge base.")
    
    return [
        create_rag_tool(
            handbook_name=handbook_name,
            agent_name=agent_name,
            description=description,
            vector_store=vector_store,
        )
    ]

