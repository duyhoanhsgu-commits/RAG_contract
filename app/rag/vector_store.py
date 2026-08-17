from collections.abc import Sequence


class VectorStore:
    """Vector database interface."""

    def add(self, texts: Sequence[str], embeddings: Sequence[Sequence[float]]) -> None:
        raise NotImplementedError

    def search(self, embedding: Sequence[float], limit: int = 5) -> list[str]:
        raise NotImplementedError
