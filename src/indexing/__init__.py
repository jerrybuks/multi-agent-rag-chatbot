"""Indexing package for processing handbooks and generating vector stores."""

from .parsing import load_handbooks, load_single_handbook
from .chunking import chunk_markdown_intelligently, chunk_with_recursive_splitter
from .embeddings import (
    generate_embeddings,
    load_vector_store,
    generate_embedding_for_text,
)

__all__ = [
    # Parsing
    "load_handbooks",
    "load_single_handbook",
    # Chunking
    "chunk_markdown_intelligently",
    "chunk_with_recursive_splitter",
    # Embeddings
    "generate_embeddings",
    "load_vector_store",
    "generate_embedding_for_text",
]
