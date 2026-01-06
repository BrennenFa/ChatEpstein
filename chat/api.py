from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uvicorn
import os
from .chatbot import setup_rag_chain
from langchain_community.callbacks import get_openai_callback
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Epstein Documents RAG API",
    description="Query Jeffrey Epstein-related documents with citations",
    version="1.0.0"
)

# implement rate limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
allowed_origins = os.getenv("FRONTEND_URL")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User query")
    session_id: str = Field(default="default", description="Session ID for conversation history")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What do you know about Les Wexner?",
                "session_id": "user-123"
            }
        }


class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI-generated answer with citations")
    citations: Dict[str, str] = Field(default_factory=dict, description="Map of citation keys to S3 URLs")
    tokens_used: int = Field(..., description="Total tokens consumed")
    prompt_tokens: int = Field(..., description="Input tokens")
    completion_tokens: int = Field(..., description="Output tokens")
    session_id: str = Field(..., description="Session ID used")

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "**Findings:**\nLes Wexner is a retail legend...",
                "citations": {
                    "DOJ-OGR-00024943, Page 1.0": "https://s3.amazonaws.com/..."
                },
                "tokens_used": 2500,
                "prompt_tokens": 2000,
                "completion_tokens": 500,
                "session_id": "user-123"
            }
        }


class HealthResponse(BaseModel):
    status: str
    message: str


rag_chain = None
citations_metadata = None

@app.on_event("startup")
async def startup_event():
    """Initialize the RAG chain when the API starts"""
    global rag_chain, citations_metadata
    rag_chain, citations_metadata = setup_rag_chain()


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="Epstein Documents RAG API is running"
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check"""
    if rag_chain is None:
        raise HTTPException(status_code=503, detail="RAG chain not initialized")

    return HealthResponse(
        status="healthy",
        message="All systems operational"
    )


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("300/hour")
@limiter.limit("10/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """
    Query the Epstein documents with conversational context.

    - **message**: Your question about the documents
    - **session_id**: Optional session ID to maintain conversation history
    """
    # Verify API key
    expected_key = os.getenv("BACKEND_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="Server configuration error")
    if x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    if rag_chain is None:
        raise HTTPException(status_code=503, detail="RAG chain not initialized")

    try:
        # Track token usage
        with get_openai_callback() as cb:
            answer = rag_chain.invoke(
                {"input": chat_request.message},
                config={"configurable": {"session_id": chat_request.session_id}}
            )

            # Get citations that were populated during chain execution
            current_citations = dict(citations_metadata)

            return ChatResponse(
                answer=answer,
                citations=current_citations,
                tokens_used=cb.total_tokens,
                prompt_tokens=cb.prompt_tokens,
                completion_tokens=cb.completion_tokens,
                session_id=chat_request.session_id
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")




if __name__ == "__main__":
    # Run with: python api.py
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
