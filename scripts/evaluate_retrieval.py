"""Retrieval Evaluation V1 for Contract RAG using CUAD Ground Truth.

Evaluates the existing Retriever against CUAD ground truth without LLM generation.
Calculates Hit@1, Hit@3, Hit@5, and MRR metrics.

Usage:
    python scripts/evaluate_retrieval.py [--limit N] [--top-k K] [--output PATH] [--max-workers W]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.retriever import get_retriever  # noqa: E402

DEFAULT_CUAD_JSON = PROJECT_ROOT / "data" / "raw" / "CUAD_v1.json"
DEFAULT_MASTER_CSV = PROJECT_ROOT / "data" / "raw" / "master_clauses.csv"
DEFAULT_CONTRACTS_JSONL = PROJECT_ROOT / "data" / "processed" / "contracts.jsonl"
DEFAULT_OUTPUT_JSONL = PROJECT_ROOT / "data" / "processed" / "retrieval_eval_results.jsonl"

_chroma_lock = threading.Lock()


def clean_title(title: str) -> str:
    """Normalize contract title/filename for deterministic mapping."""
    norm = unicodedata.normalize("NFKD", title)
    ascii_str = norm.encode("ASCII", "ignore").decode("utf-8")
    return re.sub(r"[^a-zA-Z0-9]+", "", ascii_str).lower()


def load_contract_mapping(contracts_path: Path) -> dict[str, str]:
    """Map CUAD contract titles/filenames to contract_ids using contracts.jsonl."""
    if not contracts_path.exists():
        raise FileNotFoundError(f"Contracts file not found at {contracts_path}")

    mapping: dict[str, str] = {}
    with contracts_path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                contract = json.loads(line)
                filename = contract["filename"]
                stem = Path(filename).stem
                contract_id = contract["contract_id"]

                mapping[clean_title(filename)] = contract_id
                mapping[clean_title(stem)] = contract_id

    return mapping


def load_evaluation_cases(
    cuad_json_path: Path,
    contracts_path: Path,
) -> list[dict[str, str]]:
    """Extract positive ground truth evaluation cases from CUAD_v1.json."""
    if not cuad_json_path.exists():
        raise FileNotFoundError(f"CUAD JSON not found at {cuad_json_path}")

    title_to_contract_id = load_contract_mapping(contracts_path)

    with cuad_json_path.open("r", encoding="utf-8") as file:
        cuad_data = json.load(file)["data"]

    cases: list[dict[str, str]] = []
    unmapped_count = 0

    for cuad_contract in cuad_data:
        raw_title = cuad_contract["title"]
        contract_id = title_to_contract_id.get(clean_title(raw_title))

        if not contract_id:
            unmapped_count += 1
            continue

        paragraphs = cuad_contract.get("paragraphs", [])
        for paragraph in paragraphs:
            qas = paragraph.get("qas", [])
            for qa in qas:
                is_impossible = qa.get("is_impossible", False)
                answers = qa.get("answers", [])

                if not is_impossible and answers:
                    for ans in answers:
                        ground_truth_text = ans.get("text", "").strip()
                        if ground_truth_text:
                            cases.append(
                                {
                                    "contract_id": contract_id,
                                    "query": qa["question"],
                                    "ground_truth_text": ground_truth_text,
                                }
                            )

    if unmapped_count > 0:
        print(f"Warning: {unmapped_count} CUAD contracts could not be mapped to a contract_id.")

    return cases


def normalize_text_for_matching(text: str) -> str:
    """Normalize text by collapsing whitespace and lowercasing."""
    return re.sub(r"\s+", " ", text).strip().lower()


def is_ground_truth_in_chunk(ground_truth_text: str, chunk_text: str) -> bool:
    """Deterministic matching logic to check if ground truth appears in a chunk.
    
    Handles exact normalized substring, reverse containment, and boundary-spanning text.
    """
    clean_gt = normalize_text_for_matching(ground_truth_text)
    clean_chunk = normalize_text_for_matching(chunk_text)

    if not clean_gt or not clean_chunk:
        return False

    # Direct normalized substring match
    if clean_gt in clean_chunk:
        return True

    # Reverse containment (chunk inside ground truth for short chunks or long ground truth)
    if clean_chunk in clean_gt:
        return True

    # Boundary handling for longer ground truth strings (> 40 characters)
    if len(clean_gt) > 40:
        half_len = len(clean_gt) // 2
        first_half = clean_gt[:half_len].strip()
        second_half = clean_gt[half_len:].strip()
        if (first_half and first_half in clean_chunk) or (second_half and second_half in clean_chunk):
            return True

    return False


def evaluate_single_case(case: dict[str, str], top_k: int) -> dict[str, object]:
    """Execute retriever for a single case and calculate hit ranks."""
    contract_id = case["contract_id"]
    query = case["query"]
    ground_truth_text = case["ground_truth_text"]

    with _chroma_lock:
        retriever = get_retriever()
        retrieved_results = retriever.retrieve(
            query=query,
            filters={"contract_id": contract_id},
            top_k=top_k,
        )

    first_relevant_rank: int | None = None
    retrieved_records: list[dict[str, object]] = []

    for rank, result in enumerate(retrieved_results, start=1):
        retrieved_records.append(
            {
                "rank": rank,
                "chunk_id": result.chunk_id,
                "score": float(result.score),
                "text": result.text,
            }
        )

        if first_relevant_rank is None and is_ground_truth_in_chunk(ground_truth_text, result.text):
            first_relevant_rank = rank

    hit_at_1 = first_relevant_rank is not None and first_relevant_rank <= 1
    hit_at_3 = first_relevant_rank is not None and first_relevant_rank <= 3
    hit_at_5 = first_relevant_rank is not None and first_relevant_rank <= 5

    return {
        "contract_id": contract_id,
        "query": query,
        "ground_truth_text": ground_truth_text,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "first_relevant_rank": first_relevant_rank,
        "retrieved": retrieved_records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cuad-json", type=Path, default=DEFAULT_CUAD_JSON)
    parser.add_argument("--contracts-jsonl", type=Path, default=DEFAULT_CONTRACTS_JSONL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSONL)
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to evaluate (for testing)")
    parser.add_argument("--max-workers", type=int, default=5, help="Thread pool concurrency for retrieval")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Loading evaluation cases from {args.cuad_json}...")
    cases = load_evaluation_cases(args.cuad_json.resolve(), args.contracts_jsonl.resolve())
    print(f"Total positive evaluation cases loaded: {len(cases)}")

    if args.limit and args.limit > 0:
        cases = cases[: args.limit]
        print(f"Limited evaluation to first {len(cases)} cases.")

    results: list[dict[str, object]] = []

    print(f"Running retrieval evaluation (top_k={args.top_k}, max_workers={args.max_workers})...")

    if args.max_workers > 1:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_case = {
                executor.submit(evaluate_single_case, case, args.top_k): case
                for case in cases
            }
            for index, future in enumerate(as_completed(future_to_case), start=1):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as error:
                    case = future_to_case[future]
                    print(f"Error evaluating case {case['contract_id']} / query '{case['query'][:30]}...': {error}")

                if index % 50 == 0 or index == len(cases):
                    print(f"Processed {index}/{len(cases)} cases...")
    else:
        for index, case in enumerate(cases, start=1):
            try:
                result = evaluate_single_case(case, args.top_k)
                results.append(result)
            except Exception as error:
                print(f"Error evaluating case {case['contract_id']}: {error}")

            if index % 50 == 0 or index == len(cases):
                print(f"Processed {index}/{len(cases)} cases...")

    # Calculate summary metrics
    total_cases = len(results)
    if total_cases == 0:
        print("No cases were evaluated.")
        return

    hit1_count = sum(1 for r in results if r["hit_at_1"])
    hit3_count = sum(1 for r in results if r["hit_at_3"])
    hit5_count = sum(1 for r in results if r["hit_at_5"])

    mrr_sum = sum(
        (1.0 / r["first_relevant_rank"]) if r["first_relevant_rank"] is not None else 0.0
        for r in results
    )

    hit_at_1_ratio = hit1_count / total_cases
    hit_at_3_ratio = hit3_count / total_cases
    hit_at_5_ratio = hit5_count / total_cases
    mrr = mrr_sum / total_cases

    # Print summary report
    print("\n========================================")
    print("      RETRIEVAL EVALUATION REPORT       ")
    print("========================================")
    print(f"Total cases: {total_cases}")
    print(f"Hit@1: {hit_at_1_ratio:.4f}")
    print(f"Hit@3: {hit_at_3_ratio:.4f}")
    print(f"Hit@5: {hit_at_5_ratio:.4f}")
    print(f"MRR: {mrr:.4f}")
    print("========================================\n")

    # Save detailed results to output JSONL
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out_file:
        for record in results:
            out_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Detailed results saved to {args.output.resolve()}")


if __name__ == "__main__":
    main()
