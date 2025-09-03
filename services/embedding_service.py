import torch
from typing import List
from sentence_transformers import SentenceTransformer
from settings import Settings

class EmbeddingService:
    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = SentenceTransformer(Settings.EMBEDDING_MODEL, device=self.device)
        self.dim = int(self.model.get_sentence_embedding_dimension())
    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts: return []
        return self.model.encode(texts, normalize_embeddings=True).tolist()
    def embed_one(self, text: str) -> List[float]:
        if not text: return []
        return self.embed([text])[0]
embeddings = EmbeddingService()
