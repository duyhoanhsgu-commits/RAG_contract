from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore


class Retriever:
    def __init__(self, embedder: Embedder, vector_store: VectorStore) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: str, limit: int = 5) -> list[str]:
        query_embedding = self.embedder.embed([query])[0]
        return self.vector_store.search(query_embedding, limit=limit)
