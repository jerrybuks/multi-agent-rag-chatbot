"""File operations for saving and loading chunks to/from JSONL."""

import json
from pathlib import Path
from typing import List

from langchain_core.documents import Document


def save_chunks_to_jsonl(chunks: List[Document], output_file: Path):
    """
    Save document chunks to a JSONL file (without embeddings).
    
    Args:
        chunks: List of Document chunks to save.
        output_file: Path to output JSONL file.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            record = {
                "id": f"{chunk.metadata.get('handbook', 'unknown')}_{i}",
                "text": chunk.page_content,
                "metadata": chunk.metadata
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    print(f"Saved {len(chunks)} chunks to {output_file}")


def load_chunks_from_jsonl(input_file: Path) -> List[Document]:
    """
    Load chunks from a JSONL file.
    
    Args:
        input_file: Path to input JSONL file.
    
    Returns:
        List of Document chunks.
    """
    chunks = []
    
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            chunk = Document(
                page_content=record["text"],
                metadata=record.get("metadata", {})
            )
            chunks.append(chunk)
    
    return chunks

