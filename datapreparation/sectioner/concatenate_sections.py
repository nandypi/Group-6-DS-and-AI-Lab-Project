"""Create smaller sectioned Markdown files from section JSON manifests.

Flow:
1. User runs this script with a manifest directory and an output directory.
2. The script reads each JSON manifest in sorted order.
3. For each document, it walks the manifest sections in their existing order.
4. Any source section above 3000 actual tokens is split by Markdown block
   boundaries so no final file is above the hard cap.
5. Consecutive sections are packed toward 2500 tokens.
6. If a group is still below 1500 tokens, the next section can be added up to
   3000 tokens to preserve section boundaries.
7. Small leftover groups are merged into a neighbor when that stays under 3000.
8. The completed group is written as `group_001.md`, then the next group starts.
9. A summary is printed for every processed document.

Project terms:
- A manifest is the JSON file produced by `datapreparation.sectioner.cli`.
- A grouped section file is a Markdown file containing one or more consecutive
  extraction units from the manifest.

ASSUMPTION: grouping measures the final serialized Markdown, including its
front matter and section separators. This enforces the hard cap on the files
that downstream extraction actually reads.

ASSUMPTION: if a single manifest section is already above 3000 tokens, it may be
split for final files because the user requested that no sectioned file exceed
3000 tokens under any case.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from datapreparation.sectioner.tokens import count_actual_tokens

TOKEN_TARGET = 2500
SOFT_MIN = 1500
HARD_MAX = 3000
FILE_METADATA_TOKEN_BUFFER = 300


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
    soft_min = args.soft_min
    hard_max = args.hard_max

    if not manifests_dir.exists() or not manifests_dir.is_dir():
        print(f"ERROR: --manifests must be an existing directory: {manifests_dir}", file=sys.stderr)
        return 2
    if token_target < 1:
        print("ERROR: --token-target must be >= 1", file=sys.stderr)
        return 2
    if soft_min < 1:
        print("ERROR: --soft-min must be >= 1", file=sys.stderr)
        return 2
    if hard_max < token_target:
        print("ERROR: --hard-max must be >= --token-target", file=sys.stderr)
        return 2
    if soft_min > token_target:
        print("ERROR: --soft-min must be <= --token-target", file=sys.stderr)
        return 2

    manifest_paths = sorted(manifests_dir.glob("*.json"), key=lambda path: path.name.lower())
    if not manifest_paths:
        print(f"ERROR: no JSON manifests found in {manifests_dir}", file=sys.stderr)
        return 2

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        total_groups = 0
        for manifest_path in manifest_paths:
            result = process_manifest(manifest_path, output_dir, token_target, soft_min, hard_max)
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
        The parser accepts `--manifests`, `--output`, `--soft-min`,
        `--token-target`, and `--hard-max`.
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
        help="Preferred maximum for most grouped files. Defaults to 2500.",
    )
    parser.add_argument(
        "--soft-min",
        type=int,
        default=SOFT_MIN,
        help="Preferred minimum for most grouped files. Defaults to 1500.",
    )
    parser.add_argument(
        "--hard-max",
        type=int,
        default=HARD_MAX,
        help="Hard maximum allowed for any grouped file. Defaults to 3000.",
    )
    return parser


def process_manifest(
    manifest_path: Path,
    output_dir: Path,
    token_target: int,
    soft_min: int,
    hard_max: int,
) -> dict[str, object]:
    """Create grouped Markdown files for one manifest.

    Args:
        manifest_path: JSON manifest path.
        output_dir: Base output directory for grouped Markdown files.
        token_target: Preferred token maximum for most groups.
        soft_min: Preferred token minimum for most groups.
        hard_max: Absolute maximum for all output files.

    Returns:
        Summary values for CLI logging.

    Example:
        Sections with token counts `900, 1200, 1800` become groups
        around the 1500-2500 target range.
    """

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    document_name = str(manifest["document_name"])
    document_stem = Path(document_name).stem
    original_sections = list(manifest["sections"])
    sections = split_oversized_sections(original_sections, hard_max - FILE_METADATA_TOKEN_BUFFER)

    document_dir = output_dir / document_stem
    replace_document_output_dir(document_dir)

    groups = make_groups(document_name, sections, token_target, soft_min, hard_max)
    written_paths = []
    for index, group in enumerate(groups, start=1):
        output_path = document_dir / f"group_{index:03d}.md"
        output_path.write_text(build_group_file_text(document_name, index, group), encoding="utf-8")
        written_paths.append(output_path)

    token_counts = [group_file_token_total(document_name, index, group) for index, group in enumerate(groups, start=1)]
    return {
        "document": document_name,
        "source_sections": len(original_sections),
        "working_sections_after_oversize_split": len(sections),
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


def split_oversized_sections(
    sections: list[dict[str, object]],
    hard_max: int,
) -> list[dict[str, object]]:
    """Split source sections that already exceed the hard cap.

    Args:
        sections: Manifest sections in document order.
        hard_max: Maximum tokens allowed for any final file.

    Returns:
        Sections and section parts in document order.

    Example:
        A 4000-token source section becomes two part records.
    """

    split_sections = []
    for section in sections:
        if read_section_tokens(section) <= hard_max:
            split_sections.append(section)
            continue
        split_sections.extend(split_one_oversized_section(section, hard_max))
    return split_sections


def split_one_oversized_section(section: dict[str, object], hard_max: int) -> list[dict[str, object]]:
    """Split one oversized section by Markdown block boundaries.

    Args:
        section: One manifest section.
        hard_max: Maximum tokens allowed for any part.

    Returns:
        New section-like dicts that keep the source section id.

    Example:
        A long section with many paragraphs becomes `part_001`, `part_002`, etc.
    """

    text_blocks = split_text_into_blocks(str(section["text"]))
    parts = []
    current_blocks = []
    current_tokens = 0

    for block_text in text_blocks:
        block_tokens = count_actual_tokens(block_text)
        if block_tokens > hard_max:
            small_blocks = split_large_text_block(block_text, hard_max)
        else:
            small_blocks = [block_text]

        for small_block in small_blocks:
            small_tokens = count_actual_tokens(small_block)
            if current_blocks and current_tokens + small_tokens > hard_max:
                parts.append(build_section_part(section, len(parts) + 1, current_blocks))
                current_blocks = []
                current_tokens = 0
            current_blocks.append(small_block)
            current_tokens += small_tokens

    if current_blocks:
        parts.append(build_section_part(section, len(parts) + 1, current_blocks))

    return parts


def split_text_into_blocks(text: str) -> list[str]:
    """Split Markdown text at blank-line block boundaries.

    Args:
        text: Section Markdown text.

    Returns:
        Non-empty Markdown blocks.

    Example:
        `"A\\n\\nB"` returns `["A", "B"]`.
    """

    blocks = []
    current = []
    for line in text.splitlines():
        if line.strip() == "":
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def split_large_text_block(text: str, hard_max: int) -> list[str]:
    """Split one very large block by lines and then words.

    Args:
        text: Oversized Markdown block.
        hard_max: Maximum estimated tokens per returned block.

    Returns:
        Smaller text blocks.

    Example:
        A large table-like block can be split by rows without exceeding 3000 tokens.
    """

    line_parts = pack_text_parts(text.splitlines(), "\n", hard_max)
    final_parts = []
    for part in line_parts:
        if count_actual_tokens(part) <= hard_max:
            final_parts.append(part)
            continue
        final_parts.extend(pack_text_parts(part.split(), " ", hard_max))
    return final_parts


def pack_text_parts(parts: list[str], separator: str, hard_max: int) -> list[str]:
    """Pack text fragments without crossing the hard maximum.

    Args:
        parts: Lines or words.
        separator: Text used to join parts.
        hard_max: Maximum estimated tokens per output string.

    Returns:
        Packed text strings.

    Example:
        Many table rows are packed into row groups below the hard cap.
    """

    packed = []
    current = []
    for part in parts:
        candidate = separator.join(current + [part]) if current else part
        if current and count_actual_tokens(candidate) > hard_max:
            packed.append(separator.join(current))
            current = [part]
            continue
        current.append(part)
    if current:
        packed.append(separator.join(current))
    return packed


def build_section_part(
    section: dict[str, object],
    part_number: int,
    text_blocks: list[str],
) -> dict[str, object]:
    """Build a section-like record for one split part.

    Args:
        section: Original manifest section.
        part_number: One-based part number.
        text_blocks: Markdown blocks in this part.

    Returns:
        Dict shaped like a manifest section.

    Example:
        Section `report__071` becomes `report__071__part_001`.
    """

    text = "\n\n".join(text_blocks).strip()
    part = dict(section)
    part["section_id"] = f"{section['section_id']}__part_{part_number:03d}"
    part["actual_tokens"] = count_actual_tokens(text)
    part["text"] = text
    return part


def make_groups(
    document_name: str,
    sections: list[dict[str, object]],
    token_target: int,
    soft_min: int,
    hard_max: int,
) -> list[list[dict[str, object]]]:
    """Group consecutive manifest sections by the token threshold.

    Args:
        document_name: Source Markdown document name.
        sections: Manifest sections in document order.
        token_target: Preferred maximum for most groups.
        soft_min: Preferred minimum for most groups.
        hard_max: Absolute maximum for every output group.

    Returns:
        List of grouped sections in the same order.

    Example:
        With target 2500, `900, 1200, 1800` becomes `[900, 1200]` and `[1800]`.
    """

    groups = []
    current_group = []

    for section in sections:
        candidate_group = current_group + [section]
        group_number = len(groups) + 1
        candidate_tokens = group_file_token_total(document_name, group_number, candidate_group)
        current_tokens = group_file_token_total(document_name, group_number, current_group) if current_group else 0
        crosses_target = candidate_tokens > token_target
        crosses_hard_max = candidate_tokens > hard_max
        current_is_too_small = current_tokens < soft_min

        if current_group and crosses_hard_max:
            groups.append(current_group)
            current_group = []

        elif current_group and crosses_target and not current_is_too_small:
            groups.append(current_group)
            current_group = []

        current_group.append(section)

    if current_group:
        groups.append(current_group)

    merge_small_groups_with_neighbors(document_name, groups, soft_min, hard_max)
    return groups


def merge_small_groups_with_neighbors(
    document_name: str,
    groups: list[list[dict[str, object]]],
    soft_min: int,
    hard_max: int,
) -> None:
    """Merge small leftover groups into neighbors when it is safe.

    Args:
        document_name: Source Markdown document name.
        groups: Grouped sections, updated in place.
        soft_min: Preferred minimum for most groups.
        hard_max: Absolute maximum for every output group.

    Returns:
        None.

    Example:
        A 500-token group merges into a 2200-token previous group.
    """

    index = 0
    while index < len(groups):
        group_number = index + 1
        current_tokens = group_file_token_total(document_name, group_number, groups[index])
        if current_tokens >= soft_min:
            index += 1
            continue

        if index > 0:
            previous_group_number = index
            previous_merge = groups[index - 1] + groups[index]
            previous_merge_tokens = group_file_token_total(
                document_name,
                previous_group_number,
                previous_merge,
            )
            if previous_merge_tokens <= hard_max:
                groups[index - 1] = previous_merge
                groups.pop(index)
                index = max(index - 1, 0)
                continue

        if index + 1 < len(groups):
            next_merge = groups[index] + groups[index + 1]
            next_merge_tokens = group_file_token_total(
                document_name,
                group_number,
                next_merge,
            )
            if next_merge_tokens <= hard_max:
                groups[index] = next_merge
                groups.pop(index + 1)
                continue

        index += 1


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

    actual_tokens = stable_group_file_token_total(document_name, group_number, group)
    return build_group_file_text_with_tokens(document_name, group_number, group, actual_tokens)


def stable_group_file_token_total(
    document_name: str,
    group_number: int,
    group: list[dict[str, object]],
) -> int:
    """Return the actual token count for the final grouped Markdown text.

    Args:
        document_name: Source Markdown document name.
        group_number: One-based output file number.
        group: Consecutive manifest sections.

    Returns:
        Token count for the exact final Markdown, including metadata.

    Example:
        A group starts with the section-token sum, then re-counts after the
        `actual_tokens` metadata value is inserted.
    """

    actual_tokens = group_token_total(group)
    for _ in range(5):
        text = build_group_file_text_with_tokens(document_name, group_number, group, actual_tokens)
        new_actual_tokens = count_actual_tokens(text)
        if new_actual_tokens == actual_tokens:
            return actual_tokens
        actual_tokens = new_actual_tokens
    return actual_tokens


def build_group_file_text_with_tokens(
    document_name: str,
    group_number: int,
    group: list[dict[str, object]],
    actual_tokens: int,
) -> str:
    """Build grouped Markdown using an already calculated metadata token count.

    Args:
        document_name: Source Markdown document name.
        group_number: One-based group number.
        group: Consecutive manifest sections to concatenate.
        actual_tokens: Token count to write into the metadata header.

    Returns:
        Markdown text with metadata followed by concatenated section text.

    Example:
        Passing `actual_tokens=1800` writes `actual_tokens: 1800`.
    """

    source_ids = [str(section["section_id"]) for section in group]

    lines = [
        "---",
        f'document_name: "{document_name}"',
        f"group_id: \"{Path(document_name).stem}__group_{group_number:03d}\"",
        f"source_section_count: {len(group)}",
        f"actual_tokens: {actual_tokens}",
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
        Integer actual token count.

    Example:
        `{"actual_tokens": 3000}` returns `3000`.
    """

    return int(section["actual_tokens"])


def group_token_total(group: list[dict[str, object]]) -> int:
    """Add manifest token counts for one group.

    Args:
        group: Consecutive manifest sections.

    Returns:
        Sum of `actual_tokens`.

    Example:
        Token counts `300` and `510` return `810`.
    """

    return sum(read_section_tokens(section) for section in group)


def group_file_token_total(
    document_name: str,
    group_number: int,
    group: list[dict[str, object]],
) -> int:
    """Estimate tokens in the exact Markdown text written for one group.

    Args:
        document_name: Source Markdown document name.
        group_number: One-based output file number.
        group: Consecutive manifest sections.

    Returns:
        Estimated tokens in the final Markdown file.

    Example:
        A group of two sections includes both section text and generated front matter.
    """

    return stable_group_file_token_total(document_name, group_number, group)


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
    print("Working sections after oversize split:")
    print(result["working_sections_after_oversize_split"])
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
