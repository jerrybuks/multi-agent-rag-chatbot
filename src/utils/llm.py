"""Utility functions for LLM initialization."""

import os
from typing import Optional, List

from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler


def initialize_llm(
    model: str,
    langfuse_handler: Optional[CallbackHandler] = None,
    temperature: float = 0.0,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> ChatOpenAI:
    """
    Initialize a ChatOpenAI LLM instance with Langfuse instrumentation.
    
    Supports both OpenAI and OpenRouter (via OPENAI_API_BASE).
    
    Args:
        model: LLM model name (e.g., "gpt-4o-mini")
        langfuse_handler: Optional Langfuse callback handler. If None, creates a new one.
        temperature: Temperature for the LLM (default: 0.0)
        api_key: Optional API key. If None, reads from OPENAI_API_KEY env var.
        base_url: Optional base URL. If None, reads from OPENAI_API_BASE env var.
    
    Returns:
        Initialized ChatOpenAI instance.
    
    Raises:
        ValueError: If OPENAI_API_KEY is not found.
    """
    # Get API key
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not found. Set it as an environment variable or pass api_key parameter."
        )
    
    # Get base URL (for OpenRouter support)
    if base_url is None:
        base_url = os.getenv("OPENAI_API_BASE")
    
    # Initialize Langfuse handler if not provided
    # CallbackHandler reads from environment variables automatically
    if langfuse_handler is None:
        langfuse_handler = CallbackHandler()
    
    # Initialize LLM
    if base_url:
        # Using OpenRouter or custom OpenAI-compatible endpoint
        llm = ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
            callbacks=[langfuse_handler],
            temperature=temperature,
        )
    else:
        # Using standard OpenAI API
        llm = ChatOpenAI(
            model=model,
            callbacks=[langfuse_handler],
            temperature=temperature,
        )
    
    return llm

