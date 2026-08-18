"""Run a simple Retrieval V1 query against the existing Chroma collection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.retriever import retrieve  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Semantic search query")
    parser.add_argument("contract_id", help="Contract ID used as a metadata filter")
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = retrieve(
        query=args.query,
        filters={"contract_id": args.contract_id},
        top_k=args.top_k,
    )

    print(f"Query: {args.query}")
    print(f"Contract: {args.contract_id}\n")
    if not results:
        print("No matching chunks found.")
        return

    for rank, result in enumerate(results, start=1):
        print(
            f"{rank}. score={result.score:.6f} chunk_id={result.chunk_id} "
            f"chunk_index={result.chunk_index}"
        )
        print(f"   section={result.section_number} {result.section}".rstrip())
        print(f"   source_txt={result.source_txt}")
        print(f"   source_pdf={result.source_pdf}")
        print(f"   text={result.text}\n")


if __name__ == "__main__":
    main()
