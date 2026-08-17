"""Create token-aware, section-preserving chunks from contracts.jsonl.

Run from the project root:
    python scripts/chunk_contracts.py
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import tiktoken

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "contracts.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"

SECTION_PATTERN = re.compile(
    r"^(?:(?:ARTICLE|SECTION)\s+[\dIVXLC]+|\d+(?:\.\d+)*[.)]?\s+)[A-Z]",
    re.IGNORECASE,
)
NUMBERED_SECTION = re.compile(
    r"^(?:(?:SECTION)\s+)?(?P<number>\d+(?:\.\d+)*|[IVXLC]+)(?=\s|[.):\-–—]|$)[.)]?\s*[-:–—]?\s*(?P<title>.*)$",
    re.IGNORECASE,
)
ARTICLE_SECTION = re.compile(
    r"^ARTICLE\s+(?P<number>\d+|[IVXLC]+)(?=\s|[.:\-–—]|$)[.:]?\s*[-:–—]?\s*(?P<title>.*)$",
    re.IGNORECASE,
)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")


@dataclass(frozen=True)
class Chunk:
    text: str
    section: str | None
    token_count: int


def is_heading(line: str) -> bool:
    """Identify conservative legal-document section headings."""
    stripped = line.strip()
    if not stripped or len(stripped) > 160:
        return False
    if SECTION_PATTERN.match(stripped):
        return True
    letters = [character for character in stripped if character.isalpha()]
    return len(letters) >= 4 and sum(character.isupper() for character in letters) / len(letters) >= 0.85


def split_sections(text: str) -> list[tuple[str | None, str]]:
    """Split on standalone headings while preserving all source text."""
    lines = text.splitlines()
    if not lines:
        return [(None, text)]

    sections: list[tuple[str | None, str]] = []
    title: str | None = None
    content: list[str] = []
    for line in lines:
        if is_heading(line):
            if content or title is not None:
                sections.append((title, "\n".join(content).strip()))
            title = line.strip()
            content = []
        else:
            content.append(line)
    if content or title is not None:
        sections.append((title, "\n".join(content).strip()))
    return sections or [(None, text)]


def section_metadata(heading: str | None) -> tuple[str | None, str | None]:
    """Extract a human-readable title and number from a section heading."""
    if heading is None:
        return None, None

    normalized = " ".join(heading.split())
    match = ARTICLE_SECTION.match(normalized) or NUMBERED_SECTION.match(normalized)
    if not match:
        return normalized, None

    title = match.group("title").strip(" .:-–—") or normalized
    title_prefix = title.split(". ", maxsplit=1)[0]
    prefix_letters = [character for character in title_prefix if character.isalpha()]
    if (
        title_prefix != title
        and prefix_letters
        and sum(character.isupper() for character in prefix_letters) / len(prefix_letters) >= 0.8
    ):
        title = title_prefix
    return title, match.group("number")


def hard_split(text: str, encoding: tiktoken.Encoding, max_tokens: int) -> list[str]:
    """Last-resort split for a single sentence larger than the hard limit."""
    token_ids = encoding.encode(text)
    chunk_count = math.ceil(len(token_ids) / max_tokens)
    base_size, extra = divmod(len(token_ids), chunk_count)
    chunks: list[str] = []
    start = 0
    for index in range(chunk_count):
        size = base_size + (1 if index < extra else 0)
        chunks.append(encoding.decode(token_ids[start : start + size]).strip())
        start += size
    return chunks


def section_units(text: str, encoding: tiktoken.Encoding, max_tokens: int) -> list[str]:
    """Split a section by paragraph, then sentence, only hard-splitting oversized sentences."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    units: list[str] = []
    for paragraph in paragraphs or ([text.strip()] if text.strip() else []):
        if len(encoding.encode(paragraph)) <= max_tokens:
            units.append(paragraph)
            continue
        sentences = [part.strip() for part in SENTENCE_BOUNDARY.split(paragraph) if part.strip()]
        for sentence in sentences:
            if len(encoding.encode(sentence)) <= max_tokens:
                units.append(sentence)
            else:
                units.extend(hard_split(sentence, encoding, max_tokens))
    return units


def join_units(units: list[str], start: int, end: int) -> str:
    return "\n\n".join(units[start:end]).strip()


def pack_section(
    section: str | None,
    text: str,
    encoding: tiktoken.Encoding,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
    min_final_tokens: int,
) -> list[Chunk]:
    """Pack one section, so overlap can never cross a section boundary."""
    units = section_units(text, encoding, max_tokens)
    if not units:
        return []

    ranges: list[tuple[int, int]] = []
    start = 0
    while start < len(units):
        end = start
        while end < len(units):
            candidate = join_units(units, start, end + 1)
            candidate_tokens = len(encoding.encode(candidate))
            if candidate_tokens > max_tokens:
                break
            if end > start and candidate_tokens > target_tokens:
                break
            end += 1

        if end == start:
            end += 1
        ranges.append((start, end))
        if end >= len(units):
            break

        overlap_start = end
        while overlap_start > start:
            candidate = join_units(units, overlap_start - 1, end)
            if len(encoding.encode(candidate)) > overlap_tokens:
                break
            overlap_start -= 1
        # Always advance even when the whole current chunk fits inside the
        # overlap budget (possible when the following unit is very large).
        start = overlap_start if start < overlap_start < end else end

    if len(ranges) > 1:
        last_start, last_end = ranges[-1]
        last_tokens = len(encoding.encode(join_units(units, last_start, last_end)))
        previous_start, _ = ranges[-2]
        merged_text = join_units(units, previous_start, last_end)
        if last_tokens < min_final_tokens and len(encoding.encode(merged_text)) <= max_tokens:
            ranges[-2:] = [(previous_start, last_end)]

    return [
        Chunk(
            text=chunk_text,
            section=section,
            token_count=len(encoding.encode(chunk_text)),
        )
        for start, end in ranges
        if (chunk_text := join_units(units, start, end))
    ]


def chunk_document(
    text: str,
    encoding: tiktoken.Encoding,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
    min_final_tokens: int,
) -> list[Chunk]:
    token_count = len(encoding.encode(text))
    if token_count <= max_tokens:
        return [Chunk(text=text, section=None, token_count=token_count)]

    chunks: list[Chunk] = []
    for section, section_text in split_sections(text):
        content = f"{section}\n\n{section_text}" if section and section_text else section_text or section or ""
        chunks.extend(
            pack_section(
                section,
                content,
                encoding,
                target_tokens,
                max_tokens,
                overlap_tokens,
                min_final_tokens,
            )
        )
    return chunks


def read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"Invalid JSON at line {line_number}: {error}") from error


def build_chunks(args: argparse.Namespace) -> tuple[int, int]:
    if not 0 <= args.overlap_tokens < args.target_tokens <= args.max_tokens:
        raise ValueError("Require 0 <= overlap < target <= max")
    if not 0 <= args.min_final_tokens <= args.max_tokens:
        raise ValueError("Require 0 <= min-final-tokens <= max")

    encoding = tiktoken.get_encoding(args.encoding)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    document_count = 0
    chunk_count = 0

    with args.output.open("w", encoding="utf-8", newline="\n") as output_file:
        for contract in read_jsonl(args.input):
            document_count += 1
            chunks = chunk_document(
                str(contract["text"]),
                encoding,
                args.target_tokens,
                args.max_tokens,
                args.overlap_tokens,
                args.min_final_tokens,
            )
            for chunk_index, chunk in enumerate(chunks, start=1):
                chunk_count += 1
                record = {
                    "chunk_id": f"{contract['contract_id']}_chunk_{chunk_index:04d}",
                    "contract_id": contract["contract_id"],
                    "chunk_index": chunk_index,
                    "section_heading": chunk.section,
                    "token_count": chunk.token_count,
                    "text": chunk.text,
                }
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return document_count, chunk_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--encoding", default="cl100k_base")
    parser.add_argument("--target-tokens", type=int, default=1000)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--overlap-tokens", type=int, default=125)
    parser.add_argument("--min-final-tokens", type=int, default=175)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.input = args.input.expanduser().resolve()
    args.output = args.output.expanduser().resolve()
    documents, chunks = build_chunks(args)
    print(f"Wrote {chunks} chunks from {documents} contracts to {args.output}")


if __name__ == "__main__":
    main()
