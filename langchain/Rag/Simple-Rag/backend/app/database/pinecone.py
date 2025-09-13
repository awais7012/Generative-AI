from pinecone import Pinecone, PineconeException
from app.config.settings import settings
import os

try:
    # Initialize client (API key can also come from env var)
    pc = Pinecone(api_key=settings.pinecone_api_key, environment=settings.pinecone_environment)
    indexes = pc.list_indexes()
    print("✅ Connected to Pinecone! Indexes:", indexes)

except PineconeException as e:
    print("❌ Connection to Pinecone failed:", e)
