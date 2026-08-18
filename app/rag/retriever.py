"""Semantic retrieval over the existing contract chunk collection."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.rag.embedder import Embedder, OpenAIEmbeddingAdapter
from app.rag.vector_store import ChromaVectorStore, MetadataFilters, VectorStore


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    contract_id: str
    chunk_index: int
    section: str
    section_number: str
    text: str
    score: float
    source_txt: str
    source_pdf: str


class Retriever:
    def __init__(self, embedder: Embedder, vector_store: VectorStore) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        filters: MetadataFilters | None = None,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        query_embedding = self.embedder.embed_text(query)
        matches = self.vector_store.search_with_metadata(
            query_embedding,
            limit=top_k,
            filters=filters,
        )
        return [
            RetrievalResult(
                chunk_id=match.chunk_id,
                contract_id=str(match.metadata.get("contract_id", "")),
                chunk_index=int(match.metadata.get("chunk_index", 0)),
                section=str(match.metadata.get("section", "")),
                section_number=str(match.metadata.get("section_number", "")),
                text=match.text,
                score=match.score,
                source_txt=str(match.metadata.get("source_txt", "")),
                source_pdf=str(match.metadata.get("source_pdf", "")),
            )
            for match in matches
        ]


@lru_cache
def get_retriever() -> Retriever:
    """Build Retrieval V1 from the same settings used during ingestion."""
    settings = get_settings()
    return Retriever(
        embedder=OpenAIEmbeddingAdapter(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
        ),
        vector_store=ChromaVectorStore(
            settings.vector_store_path,
            settings.vector_store_collection,
        ),
    )


def retrieve(
    query: str,
    filters: MetadataFilters | None = None,
    top_k: int = 5,
) -> list[RetrievalResult]:
    """Retrieve the most similar chunks, optionally scoped by metadata."""
    return get_retriever().retrieve(query=query, filters=filters, top_k=top_k)
