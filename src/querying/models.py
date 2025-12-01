"""Pydantic models for query endpoints."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from config import MIN_SIMILARITY


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str = Field(
        ...,
        description="User's question or query",
        example="How do I update my payment method for my subscription?"
    )
    min_similarity: Optional[float] = Field(
        default=MIN_SIMILARITY,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold (0.0 to 1.0) for retrieved context. Defaults to config value.",
        example=0.78
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How do I update my payment method for my subscription?",
                "min_similarity": 0.78
            }
        }


class SourceResponse(BaseModel):
    """Source information from agent."""
    content: str
    metadata: Dict[str, Any]
    similarity: float
    distance: Optional[float] = None


class AgentResponseModel(BaseModel):
    """Agent response model."""
    content: str
    agent_name: str
    sources: List[SourceResponse]
    metadata: Dict[str, Any]


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    content: str = Field(..., description="The answer to the user's query")
    agents_used: List[str] = Field(..., description="List of agents that processed the query")
    routing_mode: str = Field(..., description="How the query was processed (single, multi_parallel, multi_sequential)")
    sources: List[SourceResponse] = Field(default_factory=list, description="Sources used to generate the response")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the processing")
    session_id: str = Field(..., description="Session ID for this conversation")
    quality_score: Optional[float] = Field(None, ge=1.0, le=10.0, description="Automatic quality score (1-10) from Langfuse evaluator")
    quality_reasoning: Optional[str] = Field(None, description="Reasoning for the quality score")

