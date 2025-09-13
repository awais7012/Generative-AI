# services/search.py
from app.db.pinecone_db import get_pinecone
from services.embeddings import generate_embedding_query
from pinecone_text.sparse import BM25Encoder  # pip install pinecone-text

# Load BM25 encoder (builds sparse vectors from text)
bm25 = BM25Encoder().default()

def build_sparse_vectors(user_texts):
    """Train sparse BM25 encoder on user’s docs once."""
    bm25.fit(user_texts)

def hybrid_search(user_id: str, query: str, top_k: int = 5):
    pc = get_pinecone()
    index = pc.Index("my-index")

    # Dense vector (semantic)
    dense_vector = generate_embedding_query(query)

    # Sparse vector (keyword BM25)
    sparse_vector = bm25.encode_queries(query)

    # Query Pinecone with hybrid search
    results = index.query(
        namespace=user_id,
        vector=dense_vector,
        sparse_vector=sparse_vector,
        top_k=top_k,
        include_metadata=True
    )

    return results
