"""Configuration settings for the application."""

from pathlib import Path

# Directory paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
HANDBOOKS_DIR = DATA_DIR / "handbooks"
OUTPUT_DIR = DATA_DIR
JSONL_DIR = DATA_DIR / "jsonl"

# Chunking configuration
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100  # 10% of CHUNK_SIZE

# Embedding model configuration
OPENAI_MODEL = "text-embedding-ada-002"

# LLM configuration for routing
LLM_MODEL = "gpt-4o-mini"  # Model for orchestrator routing decisions

# Vector store configuration
VECTOR_STORE_TYPE = "chroma"  # Options: "chroma" or "faiss"
VECTOR_STORE_PATH = DATA_DIR / "vectorstore"

# RAG retrieval configuration
MIN_SIMILARITY = 0.75  # Minimum similarity threshold for retrieved context (0.0 to 1.0)

# Markdown header levels to split on
HEADERS_TO_SPLIT_ON = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

# Text splitter separators (in order of preference)
TEXT_SPLITTER_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
