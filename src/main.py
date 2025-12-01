"""FastAPI application setup for the multi-agent RAG chatbot."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path

# Add src to path if not already there
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from agents import Orchestrator
from querying import setup_query_routes


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Initialize FastAPI app
    app = FastAPI(
        title="JupiterIQ Multi-Agent RAG Chatbot",
        description="Multi-agent RAG chatbot for handling customer inquiries across departments",
        version="0.1.0",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize orchestrator (singleton)
    orchestrator = Orchestrator()
    
    # Setup query routes
    query_router = setup_query_routes(orchestrator)
    app.include_router(query_router)
    
    # Root endpoint
    @app.get("/")
    def read_root():
        """Root endpoint with API information."""
        return {
            "name": "JupiterIQ Multi-Agent RAG Chatbot",
            "version": "0.1.0",
            "status": "operational",
            "endpoints": {
                "root": {
                    "GET /": "This endpoint - API information",
                    "GET /health": "Health check endpoint",
                },
                "query": {
                    "POST /api/v1/query": "Process a user query through the orchestrator",
                    "GET /api/v1/agents": "List all available specialist agents",
                    "GET /api/v1/sessions/{session_id}/history": "Get conversation history for a session",
                    "DELETE /api/v1/sessions/{session_id}": "Clear conversation history for a session",
                },
                "docs": {
                    "GET /docs": "Interactive API documentation (Swagger UI)",
                    "GET /redoc": "Alternative API documentation (ReDoc)",
                },
            },
        }
    
    # Health check endpoint
    @app.get("/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "ok"}
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
