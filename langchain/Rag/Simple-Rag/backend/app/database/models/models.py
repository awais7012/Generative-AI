# app/models/models.py
from pymongo import MongoClient
from app.config.settings import settings
from app.db.mongodb import connection
from pydantic import BaseModel, EmailStr
from datetime import datetime
import redis
import json
import uuid

# Redis client
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

class User(BaseModel):
    user_id: str
    username: str
    email: EmailStr
    tokensUsed: int = 0
    isGuest: bool = True
    guestTokenLimit: int = 3000
    isPaidUser: bool = False
    created_at: datetime = datetime.utcnow()

class Chat(BaseModel):
    chat_id: str
    user_id: str
    title: str
    chatTokensUsed: int = 0
    chatTokenLimit: int = 30000
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

class Document(BaseModel):
    doc_id: str
    user_id: str
    filename: str
    file_path: str
    chunks_count: int
    uploaded_at: datetime = datetime.utcnow()

# REDIS CHAT CONTEXT FUNCTIONS
def get_chat_context(user_id: str, chat_id: str, limit: int = 10) -> str:
    """Get recent chat history from Redis"""
    try:
        chat_key = f"chat:{user_id}:{chat_id}"
        messages = redis_client.lrange(chat_key, -limit, -1)
        
        if not messages:
            return ""
        
        context = ""
        for msg in messages:
            msg_data = json.loads(msg)
            role = msg_data.get("role", "user")
            content = msg_data.get("content", "")
            context += f"{role}: {content}\n"
        
        return context.strip()
    except Exception as e:
        print(f"❌ Redis get error: {e}")
        return ""

def update_chat_context(user_id: str, chat_id: str, role: str, content: str):
    """Add new message to Redis chat context"""
    try:
        chat_key = f"chat:{user_id}:{chat_id}"
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add to Redis list
        redis_client.lpush(chat_key, json.dumps(message))
        
        # Keep only last 50 messages
        redis_client.ltrim(chat_key, 0, 49)
        
        # Set TTL
        redis_client.expire(chat_key, settings.redis_ttl)
        
        return True
    except Exception as e:
        print(f"❌ Redis update error: {e}")
        return False

# TOKEN TRACKING FUNCTIONS
def update_user_tokens(user_id: str, tokens_used: int):
    """Update user token usage in MongoDB"""
    try:
        db = connection()
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
        db = connection()
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

# USER MANAGEMENT FUNCTIONS
def create_user(user_id: str, username: str = "", email: str = "", is_guest: bool = True):
    """Create a new user in the database"""
    try:
        db = connection()
        
        # Generate defaults for guest users
        if is_guest and not username:
            username = f"Guest_{user_id[-8:]}"
        if is_guest and not email:
            email = f"{user_id}@guest.local"
        
        user_doc = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "tokensUsed": 0,
            "isGuest": is_guest,
            "guestTokenLimit": 3000,
            "isPaidUser": False,
            "created_at": datetime.utcnow()
        }
        
        result = db.users.insert_one(user_doc)
        return result.inserted_id is not None
    except Exception as e:
        print(f"❌ User creation error: {e}")
        return False

def get_user_by_id(user_id: str):
    """Get user by user_id"""
    try:
        db = connection()
        return db.users.find_one({"user_id": user_id})
    except Exception as e:
        print(f"❌ User fetch error: {e}")
        return None

def create_chat(user_id: str, chat_id: str = None, title: str = "New Chat"):
    """Create a new chat for a user"""
    try:
        if not chat_id:
            chat_id = f"chat_{uuid.uuid4().hex[:12]}"
        
        db = connection()
        chat_doc = {
            "user_id": user_id,
            "chat_id": chat_id,
            "title": title,
            "chatTokensUsed": 0,
            "chatTokenLimit": 30000,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = db.chats.insert_one(chat_doc)
        if result.inserted_id:
            return chat_doc
        return None
    except Exception as e:
        print(f"❌ Chat creation error: {e}")
        return None

def get_user_chats(user_id: str, limit: int = 50):
    """Get all chats for a user"""
    try:
        db = connection()
        return list(db.chats.find(
            {"user_id": user_id}
        ).sort("updated_at", -1).limit(limit))
    except Exception as e:
        print(f"❌ Chat fetch error: {e}")
        return []

def check_user_limits(user: dict) -> dict:
    """Check if user has exceeded limits"""
    result = {
        "user_limit_exceeded": False,
        "user_message": "",
        "tokens_remaining": 0
    }
    
    current_tokens = user.get("tokensUsed", 0)
    
    if user.get("isGuest", True):
        token_limit = user.get("guestTokenLimit", 3000)
        if current_tokens >= token_limit:
            result["user_limit_exceeded"] = True
            result["user_message"] = "Guest token limit exceeded. Please sign up to continue!"
        else:
            result["tokens_remaining"] = token_limit - current_tokens
    elif not user.get("isPaidUser", False):
        token_limit = 10000  # Free registered user limit
        if current_tokens >= token_limit:
            result["user_limit_exceeded"] = True
            result["user_message"] = "Free user token limit exceeded. Please upgrade to continue!"
        else:
            result["tokens_remaining"] = token_limit - current_tokens
    else:
        result["tokens_remaining"] = float('inf')  # Unlimited for paid users
    
    return result

def check_chat_limits(chat: dict) -> dict:
    """Check if chat has exceeded limits"""
    result = {
        "chat_limit_exceeded": False,
        "chat_message": "",
        "chat_tokens_remaining": 0
    }
    
    current_tokens = chat.get("chatTokensUsed", 0)
    token_limit = chat.get("chatTokenLimit", 30000)
    
    if current_tokens >= token_limit:
        result["chat_limit_exceeded"] = True
        result["chat_message"] = "This conversation has reached its limit. Please start a new chat or upgrade your plan."
    else:
        result["chat_tokens_remaining"] = token_limit - current_tokens
    
    return result