"""Parse and load handbook markdown files from the data directory."""

from pathlib import Path
from typing import Dict

from config import HANDBOOKS_DIR


def load_handbooks(data_dir: Path = None) -> Dict[str, str]:
    """
    Load all markdown handbook files from the handbooks directory.
    
    Args:
        data_dir: Optional custom data directory path. Defaults to config HANDBOOKS_DIR.
    
    Returns:
        Dictionary mapping handbook names (file stems) to their content.
    """
    if data_dir is None:
        data_dir = HANDBOOKS_DIR
    
    handbooks = {}
    handbook_files = list(data_dir.glob("*_handbook.md"))
    
    if not handbook_files:
        print(f"Warning: No handbook files found in {data_dir}")
        return handbooks
    
    for file_path in handbook_files:
        handbook_name = file_path.stem  # e.g., "hr_handbook"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            handbooks[handbook_name] = content
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            continue
    
    print(f"Loaded {len(handbooks)} handbooks: {list(handbooks.keys())}")
    return handbooks


def load_single_handbook(handbook_name: str, data_dir: Path = None) -> str:
    """
    Load a single handbook by name.
    
    Args:
        handbook_name: Name of the handbook (with or without .md extension)
        data_dir: Optional custom data directory path. Defaults to config HANDBOOKS_DIR.
    
    Returns:
        Content of the handbook file.
    
    Raises:
        FileNotFoundError: If the handbook file doesn't exist.
    """
    if data_dir is None:
        data_dir = HANDBOOKS_DIR
    
    # Remove .md extension if present
    if handbook_name.endswith(".md"):
        handbook_name = handbook_name[:-3]
    
    file_path = data_dir / f"{handbook_name}.md"
    
    if not file_path.exists():
        raise FileNotFoundError(f"Handbook not found: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

