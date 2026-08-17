def chunk_text(text: str, chunk_size: int = 1_000, overlap: int = 100) -> list[str]:
    """Split text into overlapping character-based chunks."""
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > overlap >= 0")

    step = chunk_size - overlap
    return [text[start : start + chunk_size] for start in range(0, len(text), step)]
