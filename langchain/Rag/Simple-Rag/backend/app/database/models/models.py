from pymongo import MongoClient
from app.config.settings import settings
from pymongo.errors import ConnectionFailure
from mongodb.py import connection
from pydantic import BaseModel, EmailStr
from datetime import datetime


class User(BaseModel):
    user_id : str
    username: str
    email: EmailStr
    tokensUsed:int
    isGuest: bool = True
    isPaidUser: bool = False
    created_at: datetime = datetime.utcnow()



class Chat(BaseModel):
    chat_id: str
    user_id: str
    title: str
    chatTokensUsed: int 
    chatContext : str 
    created_at: datetime = datetime.utcnow()


    