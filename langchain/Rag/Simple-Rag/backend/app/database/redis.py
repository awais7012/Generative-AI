import redis
from app.config.settings import settings

# Creating redis client
redis_client = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True
)

# Simple helper function to set and get cache
def set_cache(key: str, value: str, ttl: int = None):
    """Set a value in Redis with optional TTL (defaults to settings.redis_ttl)."""
    redis_client.set(key, value, ex=ttl or settings.redis_ttl)

def get_cache(key: str):
    """Get a value from Redis by key."""
    return redis_client.get(key)
