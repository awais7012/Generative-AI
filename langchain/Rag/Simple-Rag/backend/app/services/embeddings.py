from sentence_transformers import SentenceTransformer
from typing import List

class HuggingFaceEmbedding:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def generate(self, text: str) -> List[float]:
        """Generate embedding for a single text string"""
        return self.model.encode(text).tolist()

    def batch_generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        return self.model.encode(texts).tolist()


embedding_service = HuggingFaceEmbedding()
