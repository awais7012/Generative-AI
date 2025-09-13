from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # API
    app_name: str = "Simple RAG Application"
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")

    # LLM
    groq_api_key: str = Field(..., env="GROQ_API_KEY")

    # Pinecone
    pinecone_api_key: str = Field(..., env="PINECONE_API_KEY")
    pinecone_environment: str = Field(..., env="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field(..., env="PINECONE_INDEX_NAME")

    # MongoDB
    mongodb_url: str = Field(..., env="MONGODB_URL")
    mongodb_db_name: str = Field(default="rag_db", env="MONGODB_DB_NAME")

    # Redis
    redis_url: str = Field(..., env="REDIS_URL")
    redis_ttl: int = Field(default=3600, env="REDIS_TTL")

    # Embeddings
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=384, env="EMBEDDING_DIMENSION")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
