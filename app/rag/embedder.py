from collections.abc import Sequence


class Embedder:
    """Embedding provider interface."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError
