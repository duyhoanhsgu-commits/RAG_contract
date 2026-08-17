"""Build a normalized JSONL catalog from the raw CUAD contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "contracts.jsonl"


def find_pdf(txt_path: Path, pdf_by_stem: dict[str, list[Path]]) -> Path:
    """Match a TXT contract to exactly one PDF, tolerating a unique suffix difference."""
    exact_matches = pdf_by_stem.get(txt_path.stem, [])
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise ValueError(f"Multiple PDFs match {txt_path.name}: {exact_matches}")

    prefix_matches = [
        pdf
        for stem, paths in pdf_by_stem.items()
        if stem.startswith(txt_path.stem) or txt_path.stem.startswith(stem)
        for pdf in paths
    ]
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    raise ValueError(
        f"Expected one PDF for {txt_path.name}, found {len(prefix_matches)}: "
        f"{prefix_matches}"
    )


def pdf_metadata(pdf_path: Path, pdf_root: Path) -> tuple[str, str]:
    """Extract Part_I/II/III and contract type from a PDF path."""
    relative = pdf_path.relative_to(pdf_root)
    if len(relative.parts) < 3:
        raise ValueError(f"Unexpected PDF path structure: {pdf_path}")
    return relative.parts[0], relative.parts[1]


def build_catalog(raw_dir: Path, output_path: Path) -> int:
    txt_root = raw_dir / "full_contract_txt"
    pdf_root = raw_dir / "full_contract_pdf"

    txt_paths = sorted(txt_root.glob("*.txt"), key=lambda path: path.name.casefold())
    pdf_paths = sorted(
        (path for path in pdf_root.rglob("*") if path.suffix.lower() == ".pdf"),
        key=lambda path: path.as_posix().casefold(),
    )

    if not txt_paths:
        raise FileNotFoundError(f"No TXT contracts found in {txt_root}")
    if not pdf_paths:
        raise FileNotFoundError(f"No PDF contracts found in {pdf_root}")

    pdf_by_stem: dict[str, list[Path]] = {}
    for pdf_path in pdf_paths:
        pdf_by_stem.setdefault(pdf_path.stem, []).append(pdf_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for index, txt_path in enumerate(txt_paths, start=1):
            pdf_path = find_pdf(txt_path, pdf_by_stem)
            part, contract_type = pdf_metadata(pdf_path, pdf_root)
            text = txt_path.read_text(encoding="utf-8")

            record = {
                "contract_id": f"contract_{index:04d}",
                "filename": txt_path.name,
                "contract_type": contract_type,
                "part": part,
                "source_txt": txt_path.relative_to(raw_dir).as_posix(),
                "source_pdf": pdf_path.relative_to(raw_dir).as_posix(),
                "text": text,
                "char_count": len(text),
            }
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    return len(txt_paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = build_catalog(args.raw_dir.resolve(), args.output.resolve())
    print(f"Wrote {count} contracts to {args.output.resolve()}")


if __name__ == "__main__":
    main()
