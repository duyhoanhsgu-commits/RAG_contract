"""Embedding interfaces and provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from openai import OpenAI


class Embedder(ABC):
    """Provider-independent embedding interface."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed one non-empty text."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch while preserving input order."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Backward-compatible alias used by the retriever."""
        return self.embed_batch(list(texts))


class OpenAIEmbeddingAdapter(Embedder):
    """Embedding adapter backed by the OpenAI Embeddings API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("All texts must be non-empty strings")

        request: dict[str, object] = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        if self.dimensions is not None:
            request["dimensions"] = self.dimensions

        response = self.client.embeddings.create(**request)
        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(texts):
            raise RuntimeError(f"Expected {len(texts)} embeddings, received {len(ordered)}")
        return [item.embedding for item in ordered]
