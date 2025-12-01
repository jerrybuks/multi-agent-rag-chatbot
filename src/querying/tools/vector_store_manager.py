"""Vector store manager for preloading and caching vector stores."""

from typing import Dict, Optional, Union, List
from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS

from indexing.embeddings import load_vector_store


class VectorStoreManager:
    """Manages preloaded vector stores for all handbooks."""
    
    def __init__(self, handbook_names: List[str]):
        """
        Initialize and preload all vector stores.
        
        Args:
            handbook_names: List of handbook names to preload
        """
        self._stores: Dict[str, Union[Chroma, FAISS]] = {}
        self._preload_stores(handbook_names)
    
    def _preload_stores(self, handbook_names: List[str]):
        """Preload all vector stores."""
        print("=" * 60)
        print("Preloading vector stores...")
        print("=" * 60)
        
        for handbook_name in handbook_names:
            try:
                print(f"Loading vector store for {handbook_name}...")
                store = load_vector_store(handbook_name)
                self._stores[handbook_name] = store
                print(f"✓ Loaded {handbook_name}")
            except Exception as e:
                print(f"✗ Error loading {handbook_name}: {e}")
                # Continue loading other stores even if one fails
        
        print(f"\n✓ Preloaded {len(self._stores)}/{len(handbook_names)} vector stores")
        print("=" * 60)
    
    def get_store(self, handbook_name: str) -> Optional[Union[Chroma, FAISS]]:
        """
        Get a preloaded vector store.
        
        Args:
            handbook_name: Name of the handbook
            
        Returns:
            Vector store if found, None otherwise
        """
        return self._stores.get(handbook_name)
    
    def has_store(self, handbook_name: str) -> bool:
        """Check if a vector store is loaded."""
        return handbook_name in self._stores
    
    def list_loaded_stores(self) -> List[str]:
        """List all loaded vector store names."""
        return list(self._stores.keys())

