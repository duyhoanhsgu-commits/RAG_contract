"""Embed contract chunks, upsert them into Chroma, and run a smoke query."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.rag.embedder import OpenAIEmbeddingAdapter  # noqa: E402
from app.rag.vector_store import ChromaVectorStore  # noqa: E402

DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"
DEFAULT_METADATA_INPUT = PROJECT_ROOT / "data" / "processed" / "chunks_with_metadata.jsonl"
DEFAULT_QUERY = "How can either party terminate the agreement?"
MetadataValue = str | int | float | bool


def read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON at line {line_number}: {error}") from error
            for required in ("chunk_id", "contract_id", "chunk_index", "text"):
                if required not in record:
                    raise ValueError(f"Missing {required!r} at line {line_number}")
            yield record


def batches(records: Iterable[dict[str, object]], size: int) -> Iterable[list[dict[str, object]]]:
    batch: list[dict[str, object]] = []
    for record in records:
        batch.append(record)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def load_metadata(path: Path) -> dict[str, dict[str, object]]:
    """Index enriched records so base chunks can be joined by chunk_id."""
    metadata_by_id: dict[str, dict[str, object]] = {}
    for record in read_jsonl(path):
        chunk_id = str(record["chunk_id"])
        if chunk_id in metadata_by_id:
            raise ValueError(f"Duplicate chunk_id in {path}: {chunk_id}")
        metadata_by_id[chunk_id] = record
    return metadata_by_id


def join_metadata(
    records: Iterable[dict[str, object]],
    metadata_by_id: dict[str, dict[str, object]],
) -> Iterable[dict[str, object]]:
    for record in records:
        chunk_id = str(record["chunk_id"])
        enriched = metadata_by_id.get(chunk_id)
        if enriched is None:
            raise ValueError(f"No enriched metadata found for chunk_id: {chunk_id}")
        yield {**record, **enriched, "text": record["text"]}


def chroma_metadata(record: dict[str, object]) -> dict[str, MetadataValue]:
    """Keep scalar metadata supported by Chroma; omit text and null values."""
    metadata: dict[str, MetadataValue] = {}
    for key, value in record.items():
        if key in {"chunk_id", "text", "section_heading"} or value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value

    heading = record.get("section_heading")
    if heading is not None and "section" not in metadata:
        metadata["section"] = str(heading)
    return metadata


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--metadata-input", type=Path, default=DEFAULT_METADATA_INPUT)
    parser.add_argument("--persist-dir", type=Path, default=Path(settings.vector_store_path))
    parser.add_argument("--collection", default=settings.vector_store_collection)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("batch-size must be positive")

    settings = get_settings()
    embedder = OpenAIEmbeddingAdapter(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    vector_store = ChromaVectorStore(args.persist_dir, args.collection)
    metadata_by_id = load_metadata(args.metadata_input.resolve())
    records = join_metadata(read_jsonl(args.input.resolve()), metadata_by_id)

    input_count = 0
    for batch_number, batch in enumerate(batches(records, args.batch_size), start=1):
        texts = [str(record["text"]) for record in batch]
        embeddings = embedder.embed_batch(texts)
        vector_store.upsert(
            ids=[str(record["chunk_id"]) for record in batch],
            texts=texts,
            embeddings=embeddings,
            metadatas=[chroma_metadata(record) for record in batch],
        )
        input_count += len(batch)
        print(f"Upserted batch {batch_number}: {input_count} chunks", end="\r", flush=True)

    print(f"Input chunks: {input_count:<10}")
    print(f"Collection records: {vector_store.count}")

    query_embedding = embedder.embed_text(args.query)
    results = vector_store.search_with_metadata(query_embedding, limit=args.top_k)
    print(f"\nQuery: {args.query}\n")
    for rank, result in enumerate(results, start=1):
        section = result.metadata.get("section", "Unknown")
        preview = " ".join(result.text.split())[:240]
        print(
            f"{rank}. score={result.score:.6f} "
            f"chunk_id={result.chunk_id} section={section}\n"
            f"   {preview}"
        )


if __name__ == "__main__":
    main()
