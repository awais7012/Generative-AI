from pymongo import MongoClient
from app.config.settings import settings
from pymongo.errors import ConnectionFailure


try:
    def connection():
        client = MongoClient(settings.mongodb_url)
        db = client[settings.mongodb_db_name]
        print("Connected to MongoDB successfully! ✅✅")
        return db

except ConnectionFailure as e:
    print(f"Could not connect to MongoDB: {e} ❌❌")
    db = None    