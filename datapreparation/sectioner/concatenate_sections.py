"""Create larger sectioned Markdown files from section JSON manifests.

Flow:
1. User runs this script with a manifest directory and an output directory.
2. The script reads each JSON manifest in sorted order.
3. For each document, it walks the manifest sections in their existing order.
4. Consecutive sections are concatenated until the estimated token total becomes
   greater than 8000.
5. The completed group is written as `group_001.md`, then the next group starts.
6. A summary is printed for every processed document.

Project terms:
- A manifest is the JSON file produced by `datapreparation.sectioner.cli`.
- A grouped section file is a Markdown file containing one or more consecutive
  extraction units from the manifest.

ASSUMPTION: the token total used for grouping is the manifest's existing
`estimated_tokens` value. This keeps the script deterministic and consistent
with the sectioning pipeline that created the JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

TOKEN_TARGET = 8000


def main() -> int:
    """Run the grouping CLI.

    Args:
        No Python arguments. Command line arguments are read from `sys.argv`.

    Returns:
        Exit code: 0 for success, 2 for bad CLI input, 1 for file errors.

    Example:
        `python -m datapreparation.sectioner.concatenate_sections --manifests data/nse_files_final/knowledge_extraction/greater_than_10_pages/sections --output data/nse_files_final/knowledge_extraction/greater_than_10_pages/sectioned_files`
        writes grouped Markdown section files.
    """

    parser = build_argument_parser()
    args = parser.parse_args()

    manifests_dir = Path(args.manifests)
    output_dir = Path(args.output)
    token_target = args.token_target

    if not manifests_dir.exists() or not manifests_dir.is_dir():
        print(f"ERROR: --manifests must be an existing directory: {manifests_dir}", file=sys.stderr)
        return 2
    if token_target < 1:
        print("ERROR: --token-target must be >= 1", file=sys.stderr)
        return 2

    manifest_paths = sorted(manifests_dir.glob("*.json"), key=lambda path: path.name.lower())
    if not manifest_paths:
        print(f"ERROR: no JSON manifests found in {manifests_dir}", file=sys.stderr)
        return 2

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        total_groups = 0
        for manifest_path in manifest_paths:
            result = process_manifest(manifest_path, output_dir, token_target)
            total_groups += int(result["groups"])
            print_summary(result)
    except OSError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Total grouped files written:")
    print(total_groups)
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Args:
        None.

    Returns:
        Configured `argparse.ArgumentParser`.

    Example:
        The parser accepts `--manifests`, `--output`, and optional `--token-target`.
    """

    parser = argparse.ArgumentParser(
        description="Concatenate consecutive section manifest entries into larger Markdown files."
    )
    parser.add_argument("--manifests", required=True, help="Directory containing section JSON manifests.")
    parser.add_argument("--output", required=True, help="Directory for grouped section Markdown files.")
    parser.add_argument(
        "--token-target",
        type=int,
        default=TOKEN_TARGET,
        help="Stop adding to a group after the running estimated token total exceeds this value.",
    )
    return parser


def process_manifest(manifest_path: Path, output_dir: Path, token_target: int) -> dict[str, object]:
    """Create grouped Markdown files for one manifest.

    Args:
        manifest_path: JSON manifest path.
        output_dir: Base output directory for grouped Markdown files.
        token_target: Token threshold. A group closes after its total becomes greater than this.

    Returns:
        Summary values for CLI logging.

    Example:
        Sections with token counts `3000, 3000, 2500` become one 8500-token group.
    """

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    document_name = str(manifest["document_name"])
    document_stem = Path(document_name).stem
    sections = list(manifest["sections"])

    document_dir = output_dir / document_stem
    replace_document_output_dir(document_dir)

    groups = make_groups(sections, token_target)
    written_paths = []
    for index, group in enumerate(groups, start=1):
        output_path = document_dir / f"group_{index:03d}.md"
        output_path.write_text(build_group_file_text(document_name, index, group), encoding="utf-8")
        written_paths.append(output_path)

    token_counts = [group_token_total(group) for group in groups]
    return {
        "document": document_name,
        "source_sections": len(sections),
        "groups": len(groups),
        "average_tokens": round(sum(token_counts) / len(token_counts)) if token_counts else 0,
        "largest_tokens": max(token_counts) if token_counts else 0,
        "smallest_tokens": min(token_counts) if token_counts else 0,
        "written_paths": written_paths,
    }


def replace_document_output_dir(document_dir: Path) -> None:
    """Clear one document's generated group directory before writing it.

    Args:
        document_dir: Per-document output directory.

    Returns:
        None.

    Example:
        Rerunning after a changed manifest cannot leave stale `group_010.md`.
    """

    if document_dir.exists():
        shutil.rmtree(document_dir)
    document_dir.mkdir(parents=True, exist_ok=True)


def make_groups(sections: list[dict[str, object]], token_target: int) -> list[list[dict[str, object]]]:
    """Group consecutive manifest sections by the token threshold.

    Args:
        sections: Manifest sections in document order.
        token_target: Close a group once the running token total is greater than this.

    Returns:
        List of grouped sections in the same order.

    Example:
        With target 8000, `5000, 3500, 1000` becomes groups `[5000, 3500]` and `[1000]`.
    """

    groups = []
    current_group = []
    current_tokens = 0

    for section in sections:
        current_group.append(section)
        current_tokens += read_section_tokens(section)
        if current_tokens > token_target:
            groups.append(current_group)
            current_group = []
            current_tokens = 0

    if current_group:
        groups.append(current_group)

    return groups


def build_group_file_text(document_name: str, group_number: int, group: list[dict[str, object]]) -> str:
    """Build Markdown for one grouped section file.

    Args:
        document_name: Source Markdown document name.
        group_number: One-based group number.
        group: Consecutive manifest sections to concatenate.

    Returns:
        Markdown text with metadata followed by concatenated section text.

    Example:
        A group with two sections writes one metadata header and both section texts.
    """

    first_section = group[0]
    last_section = group[-1]
    source_ids = [str(section["section_id"]) for section in group]

    lines = [
        "---",
        f'document_name: "{document_name}"',
        f"group_id: \"{Path(document_name).stem}__group_{group_number:03d}\"",
        f"source_section_count: {len(group)}",
        f"page_start: {first_section['page_start']}",
        f"page_end: {last_section['page_end']}",
        f"estimated_tokens: {group_token_total(group)}",
        "source_section_ids:",
    ]
    for section_id in source_ids:
        lines.append(f'  - "{section_id}"')
    lines.append("---")
    lines.append("")

    for index, section in enumerate(group):
        if index:
            lines.append("")
        lines.append(str(section["text"]).rstrip())

    lines.append("")
    return "\n".join(lines)


def read_section_tokens(section: dict[str, object]) -> int:
    """Read a section token count from a manifest section.

    Args:
        section: One section entry from a JSON manifest.

    Returns:
        Integer estimated token count.

    Example:
        `{"estimated_tokens": 3000}` returns `3000`.
    """

    return int(section["estimated_tokens"])


def group_token_total(group: list[dict[str, object]]) -> int:
    """Add manifest token counts for one group.

    Args:
        group: Consecutive manifest sections.

    Returns:
        Sum of `estimated_tokens`.

    Example:
        Token counts `3000` and `5100` return `8100`.
    """

    return sum(read_section_tokens(section) for section in group)


def print_summary(result: dict[str, object]) -> None:
    """Print a short summary for one document.

    Args:
        result: Summary from `process_manifest`.

    Returns:
        None.

    Example:
        Prints source section count, grouped file count, and token range.
    """

    print("Document:")
    print(result["document"])
    print("")
    print("Source sections:")
    print(result["source_sections"])
    print("")
    print("Grouped files written:")
    print(result["groups"])
    print("")
    print("Average tokens:")
    print(result["average_tokens"])
    print("")
    print("Largest grouped file:")
    print(result["largest_tokens"])
    print("")
    print("Smallest grouped file:")
    print(result["smallest_tokens"])
    print("")


if __name__ == "__main__":
    raise SystemExit(main())
