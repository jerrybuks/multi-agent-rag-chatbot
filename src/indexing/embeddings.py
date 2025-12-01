"""Initialize embeddings and vector stores (Chroma/Faiss) for document chunks."""

import os
from pathlib import Path
from typing import List, Union

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS

# Load environment variables from .env file
load_dotenv()

from config import (
    OPENAI_MODEL,
    VECTOR_STORE_TYPE,
    VECTOR_STORE_PATH,
)


def _initialize_embeddings_model():
    """
    Initialize OpenAI embeddings model.
    Supports both OpenAI and OpenRouter (via OPENAI_API_BASE).
    
    Returns:
        Initialized OpenAIEmbeddings model.
    
    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not found. Set it as an environment variable."
        )
    
    # Check for OpenRouter base URL
    base_url = os.getenv("OPENAI_API_BASE")
    
    # Initialize embeddings model
    if base_url:
        # Using OpenRouter or custom OpenAI-compatible endpoint
        print(f"Using OpenAI-compatible API at {base_url}")
        embeddings_model = OpenAIEmbeddings(
            model=OPENAI_MODEL,
            openai_api_key=api_key,
            openai_api_base=base_url,
        )
    else:
        # Using standard OpenAI API
        print("Using OpenAI API")
        embeddings_model = OpenAIEmbeddings(model=OPENAI_MODEL)
    
    return embeddings_model


def generate_embeddings(
    chunks,
    handbook_name: str,
    vector_store_type: str = None,
    base_persist_directory: Path = None,
) -> Union[Chroma, FAISS]:
    """
    Generate embeddings and create vector store for document chunks.
    Encapsulates all embedding and vector store creation logic.
    
    Args:
        chunks: List of Document chunks to embed and store.
        handbook_name: Name of the handbook (used for directory/collection naming).
        vector_store_type: Type of vector store ("chroma" or "faiss"). Defaults to config.
        base_persist_directory: Base directory for vector stores. Defaults to config.
    
    Returns:
        Initialized vector store with chunks and embeddings.
    
    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    # Initialize embeddings model (supports OpenAI and OpenRouter)
    embeddings_model = _initialize_embeddings_model()
    
    # Create vector store
    if vector_store_type is None:
        vector_store_type = VECTOR_STORE_TYPE
    
    if base_persist_directory is None:
        base_persist_directory = VECTOR_STORE_PATH
    
    # Create handbook-specific directory
    persist_directory = base_persist_directory / handbook_name
    persist_directory.mkdir(parents=True, exist_ok=True)
    
    collection_name = handbook_name  # Use handbook name as collection name
    
    print(f"Generating embeddings and creating {vector_store_type.upper()} vector store for {handbook_name} with {len(chunks)} chunks...")
    
    if vector_store_type.lower() == "chroma":
        # Delete existing collection if it exists to avoid duplicates
        # Chroma.from_documents() appends to existing collections, causing duplicates
        import chromadb
        client = chromadb.PersistentClient(path=str(persist_directory))
        try:
            client.delete_collection(name=collection_name)
            print(f"Deleted existing collection '{collection_name}' to avoid duplicates")
        except Exception:
            # Collection doesn't exist, which is fine
            pass
        
        # Generate IDs matching JSONL format for consistency
        ids = [
            f"{chunk.metadata.get('handbook', handbook_name)}_{i}"
            for i, chunk in enumerate(chunks)
        ]
        
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings_model,
            persist_directory=str(persist_directory),
            collection_name=collection_name,
            ids=ids,  # Use consistent IDs matching JSONL format
            collection_metadata={"hnsw:space": "cosine"},
        )
        print(f"Chroma vector store created and persisted to {persist_directory}")
        
    elif vector_store_type.lower() == "faiss":
        vector_store = FAISS.from_documents(
            documents=chunks,
            embedding=embeddings_model,
        )
        # Save FAISS index
        faiss_path = persist_directory / "faiss_index"
        vector_store.save_local(str(faiss_path))
        print(f"FAISS vector store created and saved to {faiss_path}")
        
    else:
        raise ValueError(f"Unknown vector store type: {vector_store_type}. Use 'chroma' or 'faiss'")
    
    return vector_store


def load_vector_store(
    handbook_name: str,
    vector_store_type: str = None,
    base_persist_directory: Path = None,
) -> Union[Chroma, FAISS]:
    """
    Load an existing vector store for a specific handbook.
    
    Args:
        handbook_name: Name of the handbook.
        vector_store_type: Type of vector store ("chroma" or "faiss"). Defaults to config.
        base_persist_directory: Base directory for vector stores. Defaults to config.
    
    Returns:
        Loaded vector store.
    
    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    # Initialize embeddings model (supports OpenAI and OpenRouter)
    embeddings_model = _initialize_embeddings_model()
    
    if vector_store_type is None:
        vector_store_type = VECTOR_STORE_TYPE
    
    if base_persist_directory is None:
        base_persist_directory = VECTOR_STORE_PATH
    
    # Handbook-specific directory
    persist_directory = base_persist_directory / handbook_name
    collection_name = handbook_name
    
    if vector_store_type.lower() == "chroma":
        vector_store = Chroma(
            persist_directory=str(persist_directory),
            embedding_function=embeddings_model,
            collection_name=collection_name,
            # collection_metadata={"hnsw:space": "cosine"}, # Use cosine similarity
        )
        print(f"Loaded Chroma vector store from {persist_directory}")
        
    elif vector_store_type.lower() == "faiss":
        faiss_path = persist_directory / "faiss_index"
        vector_store = FAISS.load_local(
            str(faiss_path),
            embeddings_model,
            allow_dangerous_deserialization=True,
        )
        print(f"Loaded FAISS vector store from {faiss_path}")
        
    else:
        raise ValueError(f"Unknown vector store type: {vector_store_type}. Use 'chroma' or 'faiss'")
    
    return vector_store


def generate_embedding_for_text(text: str) -> List[float]:
    """
    Generate a single embedding for a text string (for queries).
    
    Args:
        text: Text to embed.
    
    Returns:
        Embedding vector.
    
    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    # Initialize embeddings model (supports OpenAI and OpenRouter)
    embeddings_model = _initialize_embeddings_model()
    
    return embeddings_model.embed_query(text)
