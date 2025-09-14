# backend/main.py
from fastapi import FastAPI, Depends, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import json
from datetime import datetime

# Import from your middleware modules
from app.middleware.auth import get_clerk_identity, determine_user_identity
from app.middleware.token import (
    get_db, 
    create_or_get_user, 
    create_or_get_chat,
    check_user_token_limits,
    check_chat_token_limits,
    extract_chat_id_from_body,
    calculate_remaining_tokens,
    update_user_tokens,
    update_chat_tokens
)

# Mock RAG pipeline for testing - replace with your actual imports
def query_rag_system(user_id: str, chat_id: str, prompt: str):
    """Mock RAG system - replace with your actual RAG pipeline"""
    return {
        "answer": f"🤖 Mock response for: '{prompt}' (User: {user_id}, Chat: {chat_id})",
        "tokens_used": len(prompt.split()) * 3  # Mock token calculation
    }

app = FastAPI(
    title="Multi-User RAG API", 
    version="1.0.0",
    description="RAG system with user authentication and token limits"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class RagRequest(BaseModel):
    prompt: str
    chat_id: str

class ChatCreateRequest(BaseModel):
    title: str = "New Chat"

# Main middleware dependency
async def check_user_and_limits(
    request: Request,
    response: Response,
    identity: dict = Depends(get_clerk_identity),
    db = Depends(get_db),
):
    """
    Comprehensive middleware that handles:
    1. User authentication (Clerk + Guest)
    2. User creation/retrieval  
    3. Token limit checking
    4. Chat creation/retrieval
    5. Chat limit checking
    """
    
    # Step 1: Determine user identity
    user_id, is_guest, email, username, guest_id_for_header = determine_user_identity(request, identity)
    
    # Step 2: Set guest ID in response header if needed
    if guest_id_for_header:
        response.headers["X-Guest-ID"] = guest_id_for_header
    
    # Step 3: Get or create user in database
    user = create_or_get_user(db, user_id, username, email, is_guest)
    
    # Step 4: Check user token limits
    check_user_token_limits(user)
    
    # Step 5: Extract chat_id from request body
    chat_id = await extract_chat_id_from_body(request)
    
    # Step 6: Get or create chat record
    chat = create_or_get_chat(db, user_id, chat_id)
    
    # Step 7: Check chat token limits
    check_chat_token_limits(chat)
    
    # Step 8: Store everything in request state for downstream handlers
    request.state.user = user
    request.state.chat = chat
    request.state.is_guest = is_guest
    request.state.user_id = user_id
    request.state.chat_id = chat_id
    
    return True

# Routes
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "🚀 Multi-User RAG API is running!",
        "status": "healthy",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.post("/api/rag/query")
async def rag_query(
    request: Request,
    response: Response,
    body: RagRequest,
    limits_ok = Depends(check_user_and_limits)
):
    """
    Main RAG query endpoint with comprehensive protection
    """
    # Get data from request state (set by middleware)
    user = request.state.user
    chat = request.state.chat
    is_guest = request.state.is_guest
    user_id = request.state.user_id
    chat_id = request.state.chat_id
    
    try:
        # Call RAG pipeline
        result = query_rag_system(user_id=user_id, chat_id=chat_id, prompt=body.prompt)
        tokens_used = result.get("tokens_used", 0)
        
        # Update token usage in database
        update_user_tokens(user_id, tokens_used)
        update_chat_tokens(user_id, chat_id, tokens_used)
        
        # Calculate remaining tokens
        remaining_tokens = calculate_remaining_tokens(user, chat)
        
        # Prepare response
        response_data = {
            "success": True,
            "answer": result["answer"],
            "tokens_used": tokens_used,
            "user_id": user_id,
            "chat_id": chat_id,
            "is_guest": is_guest,
            **remaining_tokens
        }
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Processing failed",
                "message": f"Error processing request: {str(e)}"
            }
        )

@app.get("/api/user/status")
async def get_user_status(
    request: Request,
    response: Response,
    limits_ok = Depends(check_user_and_limits)
):
    """Get current user status and token usage"""
    user = request.state.user
    chat = request.state.chat
    is_guest = request.state.is_guest
    
    remaining_tokens = calculate_remaining_tokens(user, chat)
    
    return {
        "user_id": user["user_id"],
        "username": user.get("username", ""),
        "email": user.get("email", ""),
        "is_guest": is_guest,
        "is_paid_user": user.get("isPaidUser", False),
        "tokens_used": user.get("tokensUsed", 0),
        "chat_tokens_used": chat.get("chatTokensUsed", 0),
        **remaining_tokens,
        "current_chat_id": chat["chat_id"]
    }

@app.post("/api/chat/new")
async def create_new_chat(
    request: Request,
    response: Response,
    body: ChatCreateRequest = ChatCreateRequest(),
    identity: dict = Depends(get_clerk_identity),
    db = Depends(get_db)
):
    """Create a new chat for the user"""
    
    # Determine user identity
    user_id, is_guest, email, username, guest_id_for_header = determine_user_identity(request, identity)
    
    # Set guest ID in response header if needed
    if guest_id_for_header:
        response.headers["X-Guest-ID"] = guest_id_for_header
    
    # Ensure user exists in database
    user = create_or_get_user(db, user_id, username, email, is_guest)
    
    # Generate new chat ID
    chat_id = f"chat_{uuid.uuid4().hex[:12]}"
    
    # Create chat record
    new_chat = {
        "user_id": user_id,
        "chat_id": chat_id,
        "title": body.title,
        "chatTokensUsed": 0,
        "chatTokenLimit": 30000,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    db.chats.insert_one(new_chat)
    
    return {
        "success": True,
        "chat_id": chat_id,
        "title": body.title,
        "user_id": user_id,
        "is_guest": is_guest,
        "message": "New chat created successfully"
    }

@app.get("/api/user/chats")
async def get_user_chats(
    request: Request,
    response: Response,
    identity: dict = Depends(get_clerk_identity),
    db = Depends(get_db),
    limit: int = 20
):
    """Get all chats for current user"""
    
    # Determine user identity
    user_id, is_guest, email, username, guest_id_for_header = determine_user_identity(request, identity)
    
    # Set guest ID in response header if needed
    if guest_id_for_header:
        response.headers["X-Guest-ID"] = guest_id_for_header
    
    # Get user chats from database (you'll need to implement this query)
    # For now, return mock data
    return {
        "user_id": user_id,
        "chats": [
            {
                "chat_id": "chat_example123",
                "title": "Example Chat",
                "tokens_used": 150,
                "created_at": datetime.utcnow().isoformat()
            }
        ],
        "total": 1
    }

@app.delete("/api/chat/{chat_id}")
async def delete_chat(
    chat_id: str,
    request: Request,
    response: Response,
    identity: dict = Depends(get_clerk_identity),
    db = Depends(get_db)
):
    """Delete a specific chat"""
    
    # Determine user identity
    user_id, is_guest, email, username, guest_id_for_header = determine_user_identity(request, identity)
    
    # Set guest ID in response header if needed
    if guest_id_for_header:
        response.headers["X-Guest-ID"] = guest_id_for_header
    
    # Delete chat from database (implement this)
    # For now, return success
    return {
        "success": True,
        "message": f"Chat {chat_id} deleted successfully"
    }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom error handler for better error responses"""
    return {
        "success": False,
        "error": exc.detail if isinstance(exc.detail, dict) else {"message": exc.detail},
        "status_code": exc.status_code
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)