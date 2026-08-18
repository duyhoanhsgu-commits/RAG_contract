"""Vector store interfaces and a persistent Chroma implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import chromadb

MetadataValue: TypeAlias = str | int | float | bool
MetadataFilters: TypeAlias = dict[str, MetadataValue]


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    text: str
    metadata: dict[str, MetadataValue]
    distance: float

    @property
    def score(self) -> float:
        """Cosine similarity derived from Chroma's cosine distance."""
        return 1.0 - self.distance


class VectorStore(ABC):
    @abstractmethod
    def upsert(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str | int | float | bool]],
    ) -> None:
        """Insert new records or update records with matching IDs."""

    @abstractmethod
    def search_with_metadata(
        self,
        embedding: Sequence[float],
        limit: int = 5,
        filters: MetadataFilters | None = None,
    ) -> list[SearchResult]:
        """Return nearest records including metadata and distance."""

    def search(self, embedding: Sequence[float], limit: int = 5) -> list[str]:
        """Compatibility helper used by the existing Retriever."""
        return [result.text for result in self.search_with_metadata(embedding, limit)]


class ChromaVectorStore(VectorStore):
    """Persistent local Chroma collection using caller-provided embeddings."""

    def __init__(self, persist_directory: Path | str, collection_name: str) -> None:
        path = Path(persist_directory).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        return self.collection.count()

    def upsert(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str | int | float | bool]],
    ) -> None:
        sizes = {len(ids), len(texts), len(embeddings), len(metadatas)}
        if len(sizes) != 1:
            raise ValueError("ids, texts, embeddings, and metadatas must have equal lengths")
        if not ids:
            return
        self.collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search_with_metadata(
        self,
        embedding: Sequence[float],
        limit: int = 5,
        filters: MetadataFilters | None = None,
    ) -> list[SearchResult]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if self.count == 0:
            return []

        query: dict[str, object] = {
            "query_embeddings": [list(embedding)],
            "n_results": min(limit, self.count),
            "include": ["documents", "metadatas", "distances"],
        }
        if filters:
            # Chroma requires an explicit logical operator for multiple fields.
            query["where"] = (
                filters
                if len(filters) == 1
                else {"$and": [{key: value} for key, value in filters.items()]}
            )

        response = self.collection.query(
            **query,
        )
        ids = response["ids"][0]
        documents = (response["documents"] or [[]])[0]
        metadatas = (response["metadatas"] or [[]])[0]
        distances = (response["distances"] or [[]])[0]
        return [
            SearchResult(
                chunk_id=chunk_id,
                text=document or "",
                metadata=metadata or {},
                distance=float(distance),
            )
            for chunk_id, document, metadata, distance in zip(
                ids, documents, metadatas, distances, strict=True
            )
        ]
