from pathlib import Path

from app.rag.chunker import chunk_text
from app.rag.loader import load_document

RAW_DATA_DIR = Path("data/raw")


def main() -> None:
    for path in RAW_DATA_DIR.rglob("*"):
        if path.is_file():
            chunks = chunk_text(load_document(path))
            print(f"{path}: {len(chunks)} chunks")


if __name__ == "__main__":
    main()
