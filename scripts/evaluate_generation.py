"""Generation Evaluation V1 for Contract RAG using CUAD Ground Truth.

Evaluates LLM-generated answers against CUAD ground truth.
Calculates Exact Match (EM) Accuracy and Token F1 metrics.

Usage:
    python scripts/evaluate_generation.py [--limit N] [--top-k K] [--output PATH] [--max-workers W]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.rag.embedder import OpenAIEmbeddingAdapter  # noqa: E402
from app.rag.generator import generate_answer  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402
from app.rag.vector_store import ChromaVectorStore  # noqa: E402

DEFAULT_CUAD_JSON = PROJECT_ROOT / "data" / "raw" / "CUAD_v1.json"
DEFAULT_CONTRACTS_JSONL = PROJECT_ROOT / "data" / "processed" / "contracts.jsonl"
DEFAULT_OUTPUT_JSONL = PROJECT_ROOT / "data" / "processed" / "generation_eval_results.jsonl"

_chroma_lock = threading.Lock()
_thread_local = threading.local()


def get_thread_retriever() -> Retriever:
    """Instantiate a Retriever per thread so SQLite connections remain thread-bound."""
    if not hasattr(_thread_local, "retriever"):
        settings = get_settings()
        _thread_local.retriever = Retriever(
            embedder=OpenAIEmbeddingAdapter(
                api_key=settings.openai_api_key,
                model=settings.embedding_model,
            ),
            vector_store=ChromaVectorStore(
                settings.vector_store_path,
                settings.vector_store_collection,
            ),
        )
    return _thread_local.retriever


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
) -> list[dict[str, object]]:
    """Extract positive ground truth evaluation cases from CUAD_v1.json."""
    if not cuad_json_path.exists():
        raise FileNotFoundError(f"CUAD JSON not found at {cuad_json_path}")

    title_to_contract_id = load_contract_mapping(contracts_path)

    with cuad_json_path.open("r", encoding="utf-8") as file:
        cuad_data = json.load(file)["data"]

    cases: list[dict[str, object]] = []

    for cuad_contract in cuad_data:
        raw_title = cuad_contract["title"]
        contract_id = title_to_contract_id.get(clean_title(raw_title))

        if not contract_id:
            continue

        paragraphs = cuad_contract.get("paragraphs", [])
        for paragraph in paragraphs:
            qas = paragraph.get("qas", [])
            for qa in qas:
                is_impossible = qa.get("is_impossible", False)
                answers = qa.get("answers", [])

                if not is_impossible and answers:
                    gts = [a["text"].strip() for a in answers if a.get("text", "").strip()]
                    if gts:
                        cases.append(
                            {
                                "contract_id": contract_id,
                                "query": qa["question"],
                                "ground_truth_texts": gts,
                                "ground_truth_text": gts[0],
                            }
                        )

    return cases


def normalize_text_for_evaluation(text: str) -> str:
    """Normalize text for metric computation: lowercase, strip punctuation, collapse spaces."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compute_exact_match(prediction: str, truth: str) -> int:
    """Compute Exact Match score (1 or 0) between normalized strings."""
    norm_pred = normalize_text_for_evaluation(prediction)
    norm_truth = normalize_text_for_evaluation(truth)
    return 1 if norm_pred == norm_truth else 0


def compute_token_f1(prediction: str, truth: str) -> float:
    """Compute Token-level F1 score using token frequency counters."""
    norm_pred = normalize_text_for_evaluation(prediction)
    norm_truth = normalize_text_for_evaluation(truth)

    pred_tokens = norm_pred.split()
    truth_tokens = norm_truth.split()

    if not pred_tokens or not truth_tokens:
        return 1.0 if pred_tokens == truth_tokens else 0.0

    pred_counter = Counter(pred_tokens)
    truth_counter = Counter(truth_tokens)

    common = sum((pred_counter & truth_counter).values())
    if common == 0:
        return 0.0

    precision = common / len(pred_tokens)
    recall = common / len(truth_tokens)

    return (2 * precision * recall) / (precision + recall)


def evaluate_single_generation_case(
    case: dict[str, object],
    top_k: int,
) -> dict[str, object]:
    """Execute retrieval + generation for a single case and score against ground truth."""
    contract_id = str(case["contract_id"])
    query = str(case["query"])
    ground_truth_texts: list[str] = case["ground_truth_texts"]  # type: ignore[assignment]
    primary_gt_text = str(case["ground_truth_text"])

    # 1. Retrieve top-k chunks safely within thread lock
    with _chroma_lock:
        retriever = get_thread_retriever()
        retrieved_chunks = retriever.retrieve(
            query=query,
            filters={"contract_id": contract_id},
            top_k=top_k,
        )

    # 2. Generate answer (concurrent LLM API call)
    rag_answer = generate_answer(query=query, retrieved_chunks=retrieved_chunks)
    generated_answer = rag_answer.answer

    # 3. Compute best EM & Token F1 across all acceptable ground truth spans
    exact_match = max(compute_exact_match(generated_answer, gt) for gt in ground_truth_texts)
    token_f1 = max(compute_token_f1(generated_answer, gt) for gt in ground_truth_texts)

    # Format cited sources and retrieved chunk IDs
    sources = [
        {
            "chunk_id": src.chunk_id,
            "contract_id": src.contract_id,
            "section": src.section,
            "source_pdf": src.source_pdf,
        }
        for src in rag_answer.sources
    ]
    retrieved_chunk_ids = [chunk.chunk_id for chunk in retrieved_chunks]

    return {
        "contract_id": contract_id,
        "query": query,
        "ground_truth_text": primary_gt_text,
        "generated_answer": generated_answer,
        "exact_match": exact_match,
        "token_f1": round(token_f1, 4),
        "sources": sources,
        "retrieved_chunk_ids": retrieved_chunk_ids,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cuad-json", type=Path, default=DEFAULT_CUAD_JSON)
    parser.add_argument("--contracts-jsonl", type=Path, default=DEFAULT_CONTRACTS_JSONL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSONL)
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to evaluate (for testing)")
    parser.add_argument("--max-workers", type=int, default=4, help="Thread pool concurrency for evaluation")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Loading evaluation cases from {args.cuad_json}...")
    cases = load_evaluation_cases(args.cuad_json.resolve(), args.contracts_jsonl.resolve())
    print(f"Total positive QA evaluation cases loaded: {len(cases)}")

    if args.limit and args.limit > 0:
        cases = cases[: args.limit]
        print(f"Limited evaluation to first {len(cases)} cases.")

    results: list[dict[str, object]] = []

    print(f"Running generation evaluation (top_k={args.top_k}, max_workers={args.max_workers})...")

    if args.max_workers > 1:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_case = {
                executor.submit(evaluate_single_generation_case, case, args.top_k): case
                for case in cases
            }
            for index, future in enumerate(as_completed(future_to_case), start=1):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as error:
                    case = future_to_case[future]
                    print(
                        f"Error evaluating case {case['contract_id']} / query '{str(case['query'])[:30]}...': {error}"
                    )

                if index % 5 == 0 or index == len(cases):
                    print(f"Processed {index}/{len(cases)} cases...")
    else:
        for index, case in enumerate(cases, start=1):
            try:
                result = evaluate_single_generation_case(case, args.top_k)
                results.append(result)
            except Exception as error:
                print(f"Error evaluating case {case['contract_id']}: {error}")

            if index % 5 == 0 or index == len(cases):
                print(f"Processed {index}/{len(cases)} cases...")

    # Calculate summary metrics
    total_cases = len(results)
    if total_cases == 0:
        print("No cases were evaluated.")
        return

    exact_match_count = sum(r["exact_match"] for r in results)
    exact_match_accuracy = exact_match_count / total_cases
    avg_token_f1 = sum(float(r["token_f1"]) for r in results) / total_cases

    # Print summary report
    print("\n========================================")
    print("     GENERATION EVALUATION REPORT       ")
    print("========================================")
    print(f"Total cases: {total_cases}")
    print(f"Exact Match Accuracy: {exact_match_accuracy:.4f} ({exact_match_count}/{total_cases})")
    print(f"Average Token F1: {avg_token_f1:.4f}")
    print("========================================\n")

    # Save detailed results to output JSONL
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out_file:
        for record in results:
            out_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Detailed results saved to {args.output.resolve()}")


if __name__ == "__main__":
    main()
