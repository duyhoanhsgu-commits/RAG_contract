"""Run Contract RAG V1 end-to-end: retrieve, generate, and print sources."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.generator import generate_answer  # noqa: E402
from app.rag.retriever import retrieve  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--contract-id")
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    filters = {"contract_id": args.contract_id} if args.contract_id else None
    chunks = retrieve(args.query, filters=filters, top_k=args.top_k)
    result = generate_answer(args.query, chunks)

    print(f"Answer:\n{result.answer}\n")
    print("Sources:")
    if not result.sources:
        print("  (none)")
    for source in result.sources:
        print(f"  {asdict(source)}")


if __name__ == "__main__":
    main()
