# services/embeddings.py
from langchain_community.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def generate_embedding_query(query: str):
    """Embed a user query."""
    return embeddings.embed_query(query)

def generate_embedding_docs(docs: list[str]):
    """Embed multiple document chunks."""
    return embeddings.embed_documents(docs)
