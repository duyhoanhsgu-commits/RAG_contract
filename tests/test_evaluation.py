"""Unit tests for Retrieval and Generation Evaluation V1 logic."""

from __future__ import annotations

from scripts.evaluate_generation import (
    compute_exact_match,
    compute_token_f1,
    normalize_text_for_evaluation,
)
from scripts.evaluate_retrieval import (
    clean_title,
    is_ground_truth_in_chunk,
    normalize_text_for_matching,
)


def test_clean_title() -> None:
    t1 = clean_title("ADMA BioManufacturing, LLC -  Amendment #3 to Manufacturing Agreement")
    t2 = clean_title("ADMA BioManufacturing, LLC -  Amendment 3 to Manufacturing Agreement.txt")
    assert t1 == "admabiomanufacturingllcamendment3tomanufacturingagreement"
    assert t2 == "admabiomanufacturingllcamendment3tomanufacturingagreementtxt"

    assert clean_title("LECLANCHÉ S.A. - JOINT DEVELOPMENT AND MARKETING AGREEMENT") == (
        "leclanchesajointdevelopmentandmarketingagreement"
    )


def test_normalize_text_for_matching() -> None:
    assert normalize_text_for_matching("  Hello \n\t World!  ") == "hello world!"


def test_is_ground_truth_in_chunk() -> None:
    gt_short = "Distributor Agreement"
    chunk = "THIS DISTRIBUTOR AGREEMENT is made between Party A and Party B."
    assert is_ground_truth_in_chunk(gt_short, chunk) is True

    gt_not_present = "Termination for Convenience"
    assert is_ground_truth_in_chunk(gt_not_present, chunk) is False

    # Boundary overlap test for long GT
    long_gt = "This agreement shall be governed by and construed in accordance with the laws of California."
    chunk_half = "This agreement shall be governed by and construed in accordance with the laws of the State."
    assert is_ground_truth_in_chunk(long_gt, chunk_half) is True


def test_compute_exact_match() -> None:
    assert compute_exact_match("DISTRIBUTOR AGREEMENT.", "distributor agreement") == 1
    assert compute_exact_match("June 21, 1999", "June 21 1999") == 1
    assert compute_exact_match("Distributor Agreement Inc", "Distributor Agreement") == 0


def test_compute_token_f1() -> None:
    # Identical text -> F1 = 1.0
    assert compute_token_f1("DISTRIBUTOR AGREEMENT", "distributor agreement") == 1.0

    # Partial overlap
    # tokens: ["the", "contract", "is", "distributor", "agreement"] (5) vs ["distributor", "agreement"] (2)
    # common: 2 -> precision = 2/5 = 0.4, recall = 2/2 = 1.0 -> F1 = 2 * 0.4 * 1.0 / 1.4 = 0.5714
    f1 = compute_token_f1("The contract is Distributor Agreement", "Distributor Agreement")
    assert round(f1, 4) == 0.5714

    # No overlap -> F1 = 0.0
    assert compute_token_f1("California Law", "Distributor Agreement") == 0.0
