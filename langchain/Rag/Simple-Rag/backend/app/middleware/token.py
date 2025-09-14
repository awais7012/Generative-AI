# backend/app/middleware/token.py
import uuid
import json
from fastapi import HTTPException, Request, Depends, Response
from datetime import datetime
from typing import Optional

# Import your database connection (adjust path as needed)
# from app.db.mongodb import connection
# For now, I'll create a mock - replace with your actual import

# Mock database connection - REPLACE with your actual connection
class MockConnection:
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
        return type('', (), {'inserted_id': True})()
    
    def update_one(self, query, update):
        # Mock update logic
        return type('', (), {'modified_count': 1})()

def get_db():
    """Database dependency - replace with your actual db connection"""
    # return connection()  # Your actual connection
    return MockConnection()  # Mock for testing

def create_or_get_user(db, user_id: str, username: str, email: str, is_guest: bool) -> dict:
    """
    Get existing user or create new user in database
    """
    user = db.users.find_one({"user_id": user_id})
    
    if not user:
        # Create new user
        new_user = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "tokensUsed": 0,
            "isGuest": is_guest,
            "guestTokenLimit": 3000,
            "isPaidUser": False,
            "created_at": datetime.utcnow()
        }
        db.users.insert_one(new_user)
        user = new_user
    
    return user

def create_or_get_chat(db, user_id: str, chat_id: str) -> dict:
    """
    Get existing chat or create new chat record
    """
    chat = db.chats.find_one({"user_id": user_id, "chat_id": chat_id})
    
    if not chat:
        # Create new chat
        new_chat = {
            "user_id": user_id,
            "chat_id": chat_id,
            "title": "New Chat",
            "chatTokensUsed": 0,
            "chatTokenLimit": 30000,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        db.chats.insert_one(new_chat)
        chat = new_chat
    
    return chat

def check_user_token_limits(user: dict) -> None:
    """
    Check if user has exceeded their token limits
    Raises HTTPException if limits exceeded
    """
    current_tokens = user.get("tokensUsed", 0)
    
    if user.get("isGuest", True):
        # Guest user limits
        token_limit = user.get("guestTokenLimit", 3000)
        if current_tokens >= token_limit:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Guest token limit exceeded",
                    "message": "You've used all your free tokens. Please sign up to continue!",
                    "tokens_used": current_tokens,
                    "token_limit": token_limit,
                    "requires_login": True,
                    "action": "signup"
                }
            )
    elif not user.get("isPaidUser", False):
        # Free registered user limits
        token_limit = 10000  # Higher limit for registered users
        if current_tokens >= token_limit:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Free user token limit exceeded",
                    "message": "Please upgrade to continue using the service.",
                    "tokens_used": current_tokens,
                    "token_limit": token_limit,
                    "requires_upgrade": True,
                    "action": "upgrade"
                }
            )
    # Paid users have unlimited tokens

def check_chat_token_limits(chat: dict) -> None:
    """
    Check if chat has exceeded token limits
    Raises HTTPException if limits exceeded
    """
    chat_tokens_used = chat.get("chatTokensUsed", 0)
    chat_token_limit = chat.get("chatTokenLimit", 30000)
    
    if chat_tokens_used >= chat_token_limit:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Chat token limit exceeded",
                "message": "This conversation has reached its limit. Please start a new chat or upgrade your plan.",
                "chat_tokens_used": chat_tokens_used,
                "chat_token_limit": chat_token_limit,
                "requires_new_chat": True,
                "chat_id": chat["chat_id"],
                "action": "new_chat"
            }
        )

def get_chat_id_from_request(request: Request) -> str:
    """
    Extract chat_id from request body
    """
    # This will be called after request body is read
    # We'll handle this in the main middleware
    pass

async def extract_chat_id_from_body(request: Request) -> str:
    """
    Extract chat_id from request body JSON
    """
    try:
        body = await request.body()
        if body:
            request_data = json.loads(body.decode())
            chat_id = request_data.get("chat_id")
            if chat_id:
                return chat_id
    except Exception as e:
        print(f"Error parsing request body: {e}")
    
    raise HTTPException(
        status_code=400,
        detail={
            "error": "Missing chat_id",
            "message": "chat_id is required in request body"
        }
    )

def calculate_remaining_tokens(user: dict, chat: dict) -> dict:
    """
    Calculate remaining tokens for user and chat
    """
    user_remaining = None
    if user.get("isGuest", True):
        user_limit = user.get("guestTokenLimit", 3000)
        user_remaining = max(0, user_limit - user.get("tokensUsed", 0))
    elif not user.get("isPaidUser", False):
        user_limit = 10000  # Free user limit
        user_remaining = max(0, user_limit - user.get("tokensUsed", 0))
    
    chat_limit = chat.get("chatTokenLimit", 30000)
    chat_remaining = max(0, chat_limit - chat.get("chatTokensUsed", 0))
    
    return {
        "user_tokens_remaining": user_remaining,
        "chat_tokens_remaining": chat_remaining,
        "user_token_limit": user.get("guestTokenLimit", 3000) if user.get("isGuest") else (10000 if not user.get("isPaidUser") else None),
        "chat_token_limit": chat_limit
    }

# Token update functions (you already have these in your models)
def update_user_tokens(user_id: str, tokens_used: int):
    """Update user token usage in MongoDB"""
    try:
        db = get_db()
        result = db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"tokensUsed": tokens_used}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"❌ Token update error: {e}")
        return False

def update_chat_tokens(user_id: str, chat_id: str, tokens_used: int):
    """Update chat-specific token usage"""
    try:
        db = get_db()
        result = db.chats.update_one(
            {"user_id": user_id, "chat_id": chat_id},
            {
                "$inc": {"chatTokensUsed": tokens_used},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"❌ Chat token update error: {e}")
        return False