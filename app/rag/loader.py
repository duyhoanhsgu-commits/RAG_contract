from pathlib import Path


def load_document(path: Path) -> str:
    """Load a UTF-8 text document from disk."""
    return path.read_text(encoding="utf-8")
