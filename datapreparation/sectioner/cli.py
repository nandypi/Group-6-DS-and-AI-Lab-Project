"""Command line interface for sectioning Markdown documents.

Flow:
1. User runs `python -m datapreparation.sectioner.cli --input data/nse_files_final/categorisation_by_pages/more_than_10_pages --output data/nse_files_final/knowledge_extraction/greater_than_10_pages/sections`.
2. The CLI validates paths and creates output directories.
3. It finds every Markdown file in the input directory in sorted order.
4. Each file is processed by `pipeline.process_markdown_file`.
5. The pipeline writes JSON manifests, final section Markdown files, and reports.
6. A short deterministic summary is printed for every document.

ASSUMPTION: validation reports live in a sibling `reports` directory when the
caller does not pass `--reports`, matching the `greater_than_10_pages/reports`
output layout.

ASSUMPTION: final sectioned Markdown files live in a sibling `sectioned_files`
directory when the caller does not pass `--section-files`.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from datapreparation.sectioner.pipeline import process_markdown_file


def main() -> int:
    """Run the sectioning CLI.

    Args:
        No Python arguments. Command line arguments are read from `sys.argv`.

    Returns:
        Exit code: 0 for success, 2 for bad CLI input, 1 for processing errors.

    Example:
        `python -m datapreparation.sectioner.cli --input data/nse_files_final/categorisation_by_pages/more_than_10_pages --output data/nse_files_final/knowledge_extraction/greater_than_10_pages/sections`
        processes all Markdown files in the more-than-10-pages NSE folder.
    """

    parser = build_argument_parser()
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    reports_dir = Path(args.reports) if args.reports else output_dir.parent / "reports"
    section_files_dir = (
        Path(args.section_files) if args.section_files else output_dir.parent / "sectioned_files"
    )

    if not input_dir.exists() or not input_dir.is_dir():
        print(f"ERROR: --input must be an existing directory: {input_dir}", file=sys.stderr)
        return 2

    markdown_files = find_markdown_files(input_dir)
    if not markdown_files:
        print(f"ERROR: no Markdown files found in {input_dir}", file=sys.stderr)
        return 2

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        section_files_dir.mkdir(parents=True, exist_ok=True)
        for markdown_path in markdown_files:
            result = process_markdown_file(markdown_path, output_dir, reports_dir, section_files_dir)
            print_document_summary(result)
    except OSError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Args:
        None.

    Returns:
        Configured `argparse.ArgumentParser`.

    Example:
        The parser accepts `--input`, `--output`, optional `--reports`, and
        optional `--section-files`.
    """

    parser = argparse.ArgumentParser(
        description="Convert Markdown documents into section manifests for LLM extraction."
    )
    parser.add_argument("--input", required=True, help="Directory containing Markdown files.")
    parser.add_argument("--output", required=True, help="Directory for section JSON manifests.")
    parser.add_argument("--reports", help="Directory for validation reports. Defaults to output sibling reports.")
    parser.add_argument(
        "--section-files",
        help="Directory for final sectioned Markdown files. Defaults to output sibling sectioned_files.",
    )
    return parser


def find_markdown_files(input_dir: Path) -> list[Path]:
    """Find Markdown files in deterministic order.

    Args:
        input_dir: Directory to scan recursively.

    Returns:
        Sorted list of `.md` and `.markdown` files.

    Example:
        `find_markdown_files(Path("data"))` returns Markdown paths sorted by name.
    """

    files = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".md", ".markdown"}:
            files.append(path)
    return sorted(files, key=lambda path: str(path).lower())


def print_document_summary(result: dict[str, object]) -> None:
    """Print the per-document summary required by the plan.

    Args:
        result: Dict returned by `process_markdown_file`.

    Returns:
        None.

    Example:
        Prints document name, section count, average, largest, and smallest token counts.
    """

    summary = result["summary"]
    if not isinstance(summary, dict):
        raise ValueError("summary must be a dictionary")

    print("Document:")
    print(result["document"])
    print("")
    print("Sections generated:")
    print(summary["sections"])
    print("")
    print("Average tokens:")
    print(summary["average"])
    print("")
    print("Largest section:")
    print(summary["largest"])
    print("")
    print("Smallest section:")
    print(summary["smallest"])
    print("")
    print("Section files written:")
    print(result["section_file_count"])
    print("")


if __name__ == "__main__":
    raise SystemExit(main())
