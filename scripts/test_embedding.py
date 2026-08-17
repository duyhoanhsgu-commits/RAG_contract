"""Smoke-test embeddings and cosine ranking without a vector database.

Example:
    python scripts/test_embedding.py --query "When may either party terminate?" --limit 5
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.rag.embedder import OpenAIEmbeddingAdapter  # noqa: E402

DEFAULT_CHUNKS = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"


def load_chunks(path: Path, limit: int) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON at line {line_number}: {error}") from error
            chunks.append(chunk)
            if len(chunks) == limit:
                break
    if len(chunks) < limit:
        raise ValueError(f"Requested {limit} chunks, but {path} contains only {len(chunks)}")
    return chunks


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    if len(left_values) != len(right_values):
        raise ValueError("Embedding dimensions do not match")

    dot_product = sum(a * b for a, b in zip(left_values, right_values, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--query", default="Under what conditions may either party terminate the agreement?")
    parser.add_argument("--limit", type=int, choices=range(3, 11), default=5, metavar="3-10")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    chunks = load_chunks(args.chunks.expanduser().resolve(), args.limit)
    embedder = OpenAIEmbeddingAdapter(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )

    chunk_embeddings = embedder.embed_batch([str(chunk["text"]) for chunk in chunks])
    query_embedding = embedder.embed_text(args.query)
    ranked = sorted(
        (
            (
                cosine_similarity(query_embedding, embedding),
                str(chunk["chunk_id"]),
                chunk.get("section_heading") or "Unknown",
            )
            for chunk, embedding in zip(chunks, chunk_embeddings, strict=True)
        ),
        reverse=True,
    )

    print(f"Query: {args.query}\n")
    print(f"{'chunk_id':<32} {'score':>9}  section")
    print("-" * 90)
    for score, chunk_id, section in ranked:
        print(f"{chunk_id:<32} {score:>9.6f}  {section}")


if __name__ == "__main__":
    main()
