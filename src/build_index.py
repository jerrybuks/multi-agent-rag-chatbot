"""
Build vector index from handbook markdown files.

This script orchestrates the indexing pipeline for each handbook:
1. Load and parse each handbook
2. Create RAG chunks for each handbook
3. Save chunks to JSONL file for each handbook
4. Generate embeddings and create vector store for each handbook
"""

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from indexing import (
    load_handbooks,
    chunk_markdown_intelligently,
    generate_embeddings,
)
from utils import save_chunks_to_jsonl
from config import JSONL_DIR


def main():
    """Main function to build the index."""
    print("=" * 60)
    print("Building Vector Index from Handbooks")
    print("=" * 60)
    
    # Step 1: Load and parse all handbooks
    print(f"\n{'='*60}")
    print("Step 1: Loading and parsing handbooks...")
    print(f"{'='*60}")
    handbooks = load_handbooks()
    
    if not handbooks:
        print("No handbooks found in data directory!")
        return
    
    # Process each handbook independently
    total_chunks = 0
    
    for handbook_name, content in handbooks.items():
        print(f"\n{'='*60}")
        print(f"Processing: {handbook_name}")
        print(f"{'='*60}")
        
        # Step 2: Create RAG chunks for this handbook
        print(f"Step 2: Creating chunks for {handbook_name}...")
        chunks = chunk_markdown_intelligently(content, handbook_name)
        total_chunks += len(chunks)
        
        # Step 3: Save chunks to JSONL file
        print(f"Step 3: Saving chunks to JSONL for {handbook_name}...")
        # Ensure jsonl directory exists
        JSONL_DIR.mkdir(parents=True, exist_ok=True)
        chunks_file = JSONL_DIR / f"{handbook_name}_chunks.jsonl"
        save_chunks_to_jsonl(chunks, chunks_file)
        print(f"✓ Saved {len(chunks)} chunks to {chunks_file}")
        
        # Step 4: Generate embeddings and create vector store
        print(f"Step 4: Generating embeddings and creating vector store for {handbook_name}...")
        try:
            vector_store = generate_embeddings(
                chunks=chunks,
                handbook_name=handbook_name,
            )
            print(f"✓ Vector store created for {handbook_name}")
        except ValueError as e:
            print(f"Error: {e}")
            return
    
    # Summary
    print(f"\n{'='*60}")
    print("Index building complete!")
    print(f"{'='*60}")
    print(f"Total handbooks processed: {len(handbooks)}")
    print(f"Total chunks created: {total_chunks}")
    print(f"\nFiles created:")
    for handbook_name in handbooks.keys():
        print(f"  - jsonl/{handbook_name}_chunks.jsonl")
        print(f"  - vectorstore/{handbook_name}/ (vector store directory)")


if __name__ == "__main__":
    main()
