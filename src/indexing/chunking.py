"""Intelligent chunking of markdown documents."""

from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_core.documents import Document

from config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    HEADERS_TO_SPLIT_ON,
    TEXT_SPLITTER_SEPARATORS,
)


def chunk_markdown_intelligently(
    content: str,
    handbook_name: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[Document]:
    """
    Intelligently chunk markdown content using header-based splitting.
    Falls back to recursive character splitting if header splitting fails.
    
    Args:
        content: The markdown content to chunk.
        handbook_name: Name of the handbook (for metadata).
        chunk_size: Optional custom chunk size. Defaults to config value.
        chunk_overlap: Optional custom chunk overlap. Defaults to config value.
    
    Returns:
        List of Document chunks with metadata.
    """
    if chunk_size is None:
        chunk_size = CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = CHUNK_OVERLAP
    
    chunks = []
    
    # First, try markdown header-based splitting for better semantic chunks
    try:
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADERS_TO_SPLIT_ON,
            strip_headers=False
        )
        
        md_chunks = markdown_splitter.split_text(content)
        
        # Further split large chunks using recursive splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=TEXT_SPLITTER_SEPARATORS
        )
        
        for md_chunk in md_chunks:
            # Add handbook name to metadata
            md_chunk.metadata["handbook"] = handbook_name
            md_chunk.metadata["source"] = f"{handbook_name}.md"
            
            # If chunk is still too large, split it further
            if len(md_chunk.page_content) > chunk_size:
                sub_chunks = text_splitter.split_documents([md_chunk])
                chunks.extend(sub_chunks)
            else:
                chunks.append(md_chunk)
                
    except Exception as e:
        print(f"Warning: Header-based splitting failed for {handbook_name}: {e}")
        print("Falling back to recursive character splitting...")
        
        # Fallback to recursive character splitting
        chunks = chunk_with_recursive_splitter(
            content, handbook_name, chunk_size, chunk_overlap
        )
    
    print(f"Generated {len(chunks)} chunks for {handbook_name}")
    return chunks


def chunk_with_recursive_splitter(
    content: str,
    handbook_name: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[Document]:
    """
    Chunk content using recursive character text splitter.
    
    Args:
        content: The content to chunk.
        handbook_name: Name of the handbook (for metadata).
        chunk_size: Optional custom chunk size. Defaults to config value.
        chunk_overlap: Optional custom chunk overlap. Defaults to config value.
    
    Returns:
        List of Document chunks with metadata.
    """
    if chunk_size is None:
        chunk_size = CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = CHUNK_OVERLAP
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=TEXT_SPLITTER_SEPARATORS
    )
    
    doc = Document(
        page_content=content,
        metadata={"handbook": handbook_name, "source": f"{handbook_name}.md"}
    )
    
    return text_splitter.split_documents([doc])

