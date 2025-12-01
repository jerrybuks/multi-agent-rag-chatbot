"""API routes for query endpoints."""

import hashlib
from fastapi import APIRouter, HTTPException, Request

from querying.agents import Orchestrator, OrchestratorResponse
from .models import QueryRequest, QueryResponse, SourceResponse

# Create router
router = APIRouter(prefix="/api/v1", tags=["query"])


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    Handles proxies and forwarded headers.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address as string
    """
    # Check for forwarded IP (common in production with proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = forwarded_for.split(",")[0].strip()
        return ip
    
    # Check for real IP header (some proxies use this)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client IP
    if request.client:
        return request.client.host
    
    # Last resort fallback
    return "unknown"


def generate_session_id_from_ip(ip: str) -> str:
    """
    Generate a session ID from IP address using hashing.
    This ensures privacy while maintaining session isolation per IP.
    
    Args:
        ip: Client IP address
        
    Returns:
        Hashed session ID
    """
    # Use SHA256 hash for privacy (one-way, can't reverse to get IP)
    # Add a salt-like prefix to make it more unique
    hash_input = f"session_{ip}".encode('utf-8')
    session_hash = hashlib.sha256(hash_input).hexdigest()[:16]  # Use first 16 chars
    return f"ip_{session_hash}"


def setup_query_routes(orchestrator: Orchestrator):
    """
    Setup query routes with orchestrator instance.
    
    Args:
        orchestrator: Orchestrator instance to use for processing queries
    """
    
    @router.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest, http_request: Request):
        """
        Process a user query through the orchestrator.
        
        Session ID is automatically generated from the client's IP address
        to maintain conversation continuity per user.
        
        The orchestrator will:
        1. Analyze the query to determine which agent(s) should handle it
        2. Route to single agent or multiple agents (parallel/sequential)
        3. Bundle responses into a coherent answer
        4. Maintain conversation context for the session
        """
        try:
            # Generate session ID from client IP address
            client_ip = get_client_ip(http_request)
            session_id = generate_session_id_from_ip(client_ip)
            
            # Process query through orchestrator
            response: OrchestratorResponse = await orchestrator.process_query_async(
                query=request.query,
                session_id=session_id,
                min_similarity=request.min_similarity,
            )
            
            # Extract all sources from agent responses
            all_sources = []
            for agent_response in response.responses:
                for source in agent_response.sources:
                    all_sources.append(
                        SourceResponse(
                            content=source.get("content", ""),
                            metadata=source.get("metadata", {}),
                            similarity=source.get("similarity", 0.0),
                            distance=source.get("distance"),
                        )
                    )
            
            # Build response
            return QueryResponse(
                content=response.content,
                agents_used=response.agents_used,
                routing_mode=response.routing_mode.value,
                sources=all_sources,
                metadata={
                    **response.metadata,
                    "routing_mode": response.routing_mode.value,
                },
                session_id=session_id,  # Use auto-generated session_id
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error processing query: {str(e)}"
            )
    
    @router.get("/agents")
    def list_agents():
        """List all available agents."""
        agents = orchestrator.list_available_agents()
        return {
            "agents": [
                {
                    "name": config.name,
                    "description": config.description,
                    "handbook_name": config.handbook_name,
                }
                for config in agents.values()
            ]
        }
    
    @router.get("/sessions/{session_id}/history")
    def get_conversation_history(session_id: str):
        """Get conversation history for a session."""
        context = orchestrator.get_conversation_context(session_id)
        
        if not context:
            raise HTTPException(
                status_code=404,
                detail=f"No conversation history found for session: {session_id}"
            )
        
        return {
            "session_id": session_id,
            "messages": context.messages,
            "agent_history": context.agent_history,
            "last_agent": context.last_agent,
            "message_count": len(context.messages),
        }
    
    @router.delete("/sessions/{session_id}")
    def clear_session(session_id: str):
        """Clear conversation history for a session."""
        orchestrator.clear_conversation_context(session_id)
        return {"message": f"Session {session_id} cleared successfully"}
    
    return router

