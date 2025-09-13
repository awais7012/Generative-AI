from pymongo import MongoClient
from app.config.settings import settings
from app.db.mongodb import connection
from pydantic import BaseModel, EmailStr
from datetime import datetime
import redis
import json

# Redis client
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

class User(BaseModel):
    user_id: str
    username: str
    email: EmailStr
    tokensUsed: int
    isGuest: bool = True
    isPaidUser: bool = False
    created_at: datetime = datetime.utcnow()

class Chat(BaseModel):
    chat_id: str
    user_id: str
    title: str
    chatTokensUsed: int 
    # chatContext removed - now in Redis
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
            {"$inc": {"chatTokensUsed": tokens_used}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"❌ Chat token update error: {e}")
        return False