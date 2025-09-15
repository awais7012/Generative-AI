# backend/main.py - Working version without Clerk for testing
from fastapi import FastAPI, Depends, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import json
from datetime import datetime

# For now, let's use simplified imports to avoid Clerk issues
# from app.middleware.auth import get_clerk_identity, determine_user_identity
# from app.middleware.token import (
#     get_db, create_or_get_user, create_or_get_chat,
#     check_user_token_limits, check_chat_token_limits,
#     extract_chat_id_from_body, calculate_remaining_tokens,
#     update_user_tokens, update_chat_tokens
# )

# Simplified mock implementations for testing
class MockDB:
    def __init__(self):
        self.users_data = {}
        self.chats_data = {}
        
    @property
    def users(self):
        return self
        
    @property  
    def chats(self):
        return self
    
    def find_one(self, query):
        if "user_id" in query and "chat_id" not in query:
            return self.users_data.get(query["user_id"])
        elif "user_id" in query and "chat_id" in query:
            key = f"{query['user_id']}:{query['chat_id']}"
            return self.chats_data.get(key)
        return None
    
    def insert_one(self, doc):
        if "chat_id" in doc:
            key = f"{doc['user_id']}:{doc['chat_id']}"
            self.chats_data[key] = doc
        else:
            self.users_data[doc["user_id"]] = doc
        return type('Result', (), {'inserted_id': True})()
    
    def update_one(self, query, update):
        # Mock update logic
        if "$inc" in update:
            if "user_id" in query and "chat_id" not in query:
                user = self.users_data.get(query["user_id"])
                if user:
                    for field, value in update["$inc"].items():
                        user[field] = user.get(field, 0) + value
            elif "user_id" in query and "chat_id" in query:
                key = f"{query['user_id']}:{query['chat_id']}"
                chat = self.chats_data.get(key)
                if chat:
                    for field, value in update["$inc"].items():
                        chat[field] = chat.get(field, 0) + value
        return type('Result', (), {'modified_count': 1})()

# Global mock database
mock_db = MockDB()

def get_db():
    return mock_db

def get_user_identity(request: Request) -> tuple:
    """Extract user identity from request headers"""
    guest_id = request.headers.get("X-Guest-ID")
    if not guest_id:
        guest_id = f"guest_{uuid.uuid4().hex[:12]}"
    
    return (
        guest_id,           # user_id
        True,              # is_guest
        f"{guest_id}@guest.local",  # email
        f"Guest_{guest_id[-8:]}",   # username
        guest_id           # guest_id_for_header
    )

def create_or_get_user(db, user_id: str, username: str, email: str, is_guest: bool) -> dict:
    """Get existing user or create new user"""
    user = db.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "tokensUsed": 0,
            "isGuest": is_guest,
            "guestTokenLimit": 3000,
            "isPaidUser": False,
            "created_at": datetime.utcnow()
        }
        db.insert_one(user)
    return user

def create_or_get_chat(db, user_id: str, chat_id: str) -> dict:
    """Get existing chat or create new chat"""
    chat = db.find_one({"user_id": user_id, "chat_id": chat_id})
    if not chat:
        chat = {
            "user_id": user_id,
            "chat_id": chat_id,
            "title": "New Chat",
            "chatTokensUsed": 0,
            "chatTokenLimit": 30000,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        db.insert_one(chat)
    return chat

def check_user_token_limits(user: dict):
    """Check user token limits"""
    current_tokens = user.get("tokensUsed", 0)
    if user.get("isGuest", True):
        token_limit = user.get("guestTokenLimit", 3000)
        if current_tokens >= token_limit:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Guest token limit exceeded",
                    "message": "You've used all your free tokens. Please sign up to continue!",
                    "tokens_used": current_tokens,
                    "token_limit": token_limit,
                    "requires_login": True
                }
            )

def check_chat_token_limits(chat: dict):
    """Check chat token limits"""
    chat_tokens = chat.get("chatTokensUsed", 0)
    chat_limit = chat.get("chatTokenLimit", 30000)
    if chat_tokens >= chat_limit:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Chat token limit exceeded",
                "message": "This conversation has reached its limit. Please start a new chat.",
                "chat_tokens_used": chat_tokens,
                "chat_token_limit": chat_limit,
                "requires_new_chat": True
            }
        )

async def extract_chat_id_from_body(request: Request) -> str:
    """Extract chat_id from request body"""
    try:
        body = await request.body()
        if body:
            request_data = json.loads(body.decode())
            chat_id = request_data.get("chat_id")
            if chat_id:
                return chat_id
    except Exception as e:
        print(f"Error parsing request body: {e}")
    
    raise HTTPException(status_code=400, detail="Missing chat_id in request body")

def update_user_tokens(user_id: str, tokens_used: int):
    """Update user tokens"""
    db = get_db()
    db.update_one({"user_id": user_id}, {"$inc": {"tokensUsed": tokens_used}})
    print(f"Updated user {user_id} tokens: +{tokens_used}")

def update_chat_tokens(user_id: str, chat_id: str, tokens_used: int):
    """Update chat tokens"""
    db = get_db()
    db.update_one(
        {"user_id": user_id, "chat_id": chat_id}, 
        {"$inc": {"chatTokensUsed": tokens_used}}
    )
    print(f"Updated chat {chat_id} tokens: +{tokens_used}")

def query_rag_system(user_id: str, chat_id: str, prompt: str):
    """Mock RAG system"""
    return {
        "answer": f"🤖 Mock response for: '{prompt}'\n\nUser: {user_id}\nChat: {chat_id}",
        "tokens_used": len(prompt.split()) * 3
    }

# FastAPI app
app = FastAPI(
    title="Multi-User RAG API", 
    version="1.0.0",
    description="RAG system with user authentication and token limits"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# Middleware
async def check_user_and_limits(request: Request, response: Response, db = Depends(get_db)):
    """Main middleware for user and token management"""
    
    # Get user identity
    user_id, is_guest, email, username, guest_id_for_header = get_user_identity(request)
    
    # Set guest ID in response header
    if guest_id_for_header:
        response.headers["X-Guest-ID"] = guest_id_for_header
    
    # Get or create user
    user = create_or_get_user(db, user_id, username, email, is_guest)
    
    # Check user token limits
    check_user_token_limits(user)
    
    # Extract chat_id from request body
    chat_id = await extract_chat_id_from_body(request)
    
    # Get or create chat
    chat = create_or_get_chat(db, user_id, chat_id)
    
    # Check chat token limits
    check_chat_token_limits(chat)
    
    # Store in request state
    request.state.user = user
    request.state.chat = chat
    request.state.is_guest = is_guest
    request.state.user_id = user_id
    request.state.chat_id = chat_id
    
    return True

# Routes
@app.get("/")
async def root():
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
    """Main RAG query endpoint"""
    user = request.state.user
    chat = request.state.chat
    
    # Process request
    result = query_rag_system(user["user_id"], chat["chat_id"], body.prompt)
    tokens_used = result["tokens_used"]
    
    # Update token counts
    update_user_tokens(user["user_id"], tokens_used)
    update_chat_tokens(user["user_id"], chat["chat_id"], tokens_used)
    
    return {
        "success": True,
        "answer": result["answer"],
        "tokens_used": tokens_used,
        "user_id": user["user_id"],
        "chat_id": chat["chat_id"],
        "is_guest": user["isGuest"],
        "user_tokens_remaining": user["guestTokenLimit"] - user["tokensUsed"] - tokens_used,
        "chat_tokens_remaining": chat["chatTokenLimit"] - chat["chatTokensUsed"] - tokens_used
    }

@app.get("/api/user/status")
async def get_user_status(
    request: Request,
    response: Response,
    limits_ok = Depends(check_user_and_limits)
):
    """Get user status"""
    user = request.state.user
    chat = request.state.chat
    
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "is_guest": user["isGuest"],
        "tokens_used": user["tokensUsed"],
        "token_limit": user["guestTokenLimit"],
        "chat_tokens_used": chat["chatTokensUsed"],
        "chat_token_limit": chat["chatTokenLimit"],
        "current_chat_id": chat["chat_id"]
    }

@app.post("/api/chat/new")
async def create_new_chat(
    request: Request,
    response: Response,
    body: ChatCreateRequest = ChatCreateRequest(),
    db = Depends(get_db)
):
    """Create new chat"""
    user_id, is_guest, email, username, guest_id_for_header = get_user_identity(request)
    
    if guest_id_for_header:
        response.headers["X-Guest-ID"] = guest_id_for_header
    
    # Ensure user exists
    create_or_get_user(db, user_id, username, email, is_guest)
    
    # Create new chat
    chat_id = f"chat_{uuid.uuid4().hex[:12]}"
    new_chat = {
        "user_id": user_id,
        "chat_id": chat_id,
        "title": body.title,
        "chatTokensUsed": 0,
        "chatTokenLimit": 30000,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    db.insert_one(new_chat)
    
    return {
        "success": True,
        "chat_id": chat_id,
        "title": body.title,
        "user_id": user_id,
        "is_guest": is_guest
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)