from app.db.pinecone_db import get_pinecone
from services.embeddings import generate_embedding_query
from pinecone_text.sparse import BM25Encoder
import pickle
import redis
from app.config.settings import settings

redis_client = redis.Redis.from_url(settings.redis_url)

def get_user_bm25(user_id: str):
    """Get or create BM25 encoder for user"""
    try:
        bm25_key = f"bm25:{user_id}"
        bm25_data = redis_client.get(bm25_key)
        
        if bm25_data:
            return pickle.loads(bm25_data)
        else:
            # Create new BM25 encoder
            bm25 = BM25Encoder().default()
            return bm25
    except:
        return BM25Encoder().default()

def save_user_bm25(user_id: str, bm25_encoder):
    """Save user's BM25 encoder to Redis"""
    try:
        bm25_key = f"bm25:{user_id}"
        bm25_data = pickle.dumps(bm25_encoder)
        redis_client.setex(bm25_key, settings.redis_ttl, bm25_data)
    except Exception as e:
        print(f"❌ BM25 save error: {e}")

def train_bm25_for_user(user_id: str, new_texts: list):
    """Train BM25 encoder with user's documents"""
    try:
        bm25 = get_user_bm25(user_id)
        
        # Get existing texts from Pinecone
        pc = get_pinecone()
        index = pc.Index(settings.pinecone_index_name)
        
        # Query all user documents
        existing_results = index.query(
            namespace=user_id,
            vector=[0] * settings.embedding_dimension,
            top_k=10000,
            include_metadata=True
        )
        
        existing_texts = [match.metadata["text"] for match in existing_results.matches]
        all_texts = existing_texts + new_texts
        
        # Train BM25
        if all_texts:
            bm25.fit(all_texts)
            save_user_bm25(user_id, bm25)
        
    except Exception as e:
        print(f"❌ BM25 training error: {e}")

def hybrid_search(user_id: str, query: str, top_k: int = 5):
    """Hybrid search with user isolation"""
    try:
        pc = get_pinecone()
        index = pc.Index(settings.pinecone_index_name)
        
        # Dense vector (semantic)
        dense_vector = generate_embedding_query(query)
        
        # Sparse vector (keyword BM25) - user-specific
        bm25 = get_user_bm25(user_id)
        sparse_vector = bm25.encode_queries(query)
        
        # Hybrid search in user's namespace
        results = index.query(
            namespace=user_id,
            vector=dense_vector,
            sparse_vector=sparse_vector,
            top_k=top_k,
            include_metadata=True,
            filter={"user_id": user_id}  # Extra safety
        )
        
        return [match.metadata["text"] for match in results.matches if match.score > 0.5]
        
    except Exception as e:
        print(f"❌ Hybrid search error: {e}")
        return []