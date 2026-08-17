"""Enrich chunks.jsonl with document and normalized section metadata.

Run from the project root after chunk_contracts.py:
    python scripts/enrich_chunk_metadata.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from chunk_contracts import section_metadata

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACTS = PROJECT_ROOT / "data" / "processed" / "contracts.jsonl"
DEFAULT_CHUNKS = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "chunks_with_metadata.jsonl"


def read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}: {error}") from error


def load_contracts(path: Path) -> dict[str, dict[str, object]]:
    contracts: dict[str, dict[str, object]] = {}
    for contract in read_jsonl(path):
        contract_id = str(contract["contract_id"])
        if contract_id in contracts:
            raise ValueError(f"Duplicate contract_id in {path}: {contract_id}")
        contracts[contract_id] = contract
    return contracts


def enrich_chunks(contracts_path: Path, chunks_path: Path, output_path: Path) -> int:
    contracts = load_contracts(contracts_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for chunk in read_jsonl(chunks_path):
            contract_id = str(chunk["contract_id"])
            if contract_id not in contracts:
                raise ValueError(f"Unknown contract_id in {chunks_path}: {contract_id}")

            contract = contracts[contract_id]
            heading = chunk.get("section_heading")
            section, section_number = section_metadata(str(heading) if heading is not None else None)
            record = {
                "chunk_id": chunk["chunk_id"],
                "contract_id": contract_id,
                "chunk_index": chunk["chunk_index"],
                "contract_type": contract["contract_type"],
                "dataset_part": contract["part"],
                "section": section,
                "section_number": section_number,
                "token_count": chunk["token_count"],
                "source_txt": Path(str(contract["source_txt"])).name,
                "source_pdf": Path(str(contract["source_pdf"])).name,
                "text": chunk["text"],
            }
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACTS)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = enrich_chunks(
        args.contracts.expanduser().resolve(),
        args.chunks.expanduser().resolve(),
        args.output.expanduser().resolve(),
    )
    print(f"Wrote {count} enriched chunks to {args.output.resolve()}")


if __name__ == "__main__":
    main()
