"""Write section manifests, section files, and validation reports.

Flow:
1. `save_manifest` writes the exact JSON shape required by the plan.
2. `save_section_files_from_manifest` reads that JSON and writes one Markdown file
   for each final extraction unit.
3. `save_report` writes a human-readable text report beside the manifests.
4. `summarize_units` calculates CLI logging numbers.

Project terms:
- A section file is the final Markdown file for one extraction unit. It is
  generated from the JSON manifest so downstream users can choose JSON or files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from datapreparation.sectioner.models import ExtractionUnit


def save_manifest(document_name: str, units: list[ExtractionUnit], output_dir: Path) -> Path:
    """Save a section manifest JSON file.

    Args:
        document_name: Source Markdown file name.
        units: Extraction units for the document.
        output_dir: Directory for JSON manifests.

    Returns:
        Path to the written manifest.

    Example:
        `save_manifest("a.md", units, Path("greater_than_10_pages/sections"))` writes `a.json`.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "document_name": document_name,
        "total_sections": len(units),
        "sections": [unit_to_dict(unit) for unit in units],
    }
    output_path = output_dir / f"{Path(document_name).stem}.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def save_section_files_from_manifest(manifest_path: Path, section_files_dir: Path) -> list[Path]:
    """Write one Markdown file per section from a manifest JSON file.

    Args:
        manifest_path: JSON manifest written by `save_manifest`.
        section_files_dir: Base directory where section Markdown files are written.

    Returns:
        Paths to the written Markdown section files.

    Example:
        A manifest with section id `report__001` writes
        `greater_than_10_pages/sectioned_files/report/section_001.md`.
    """

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    document_name = str(manifest["document_name"])
    document_stem = Path(document_name).stem
    document_dir = section_files_dir / document_stem
    document_dir.mkdir(parents=True, exist_ok=True)
    clear_existing_section_files(document_dir)

    written_paths = []
    for index, section in enumerate(manifest["sections"], start=1):
        section_id = str(section["section_id"])
        section_path = document_dir / f"section_{index:03d}.md"
        section_text = build_section_file_text(document_name, section)
        section_path.write_text(section_text, encoding="utf-8")
        written_paths.append(section_path)

    return written_paths


def clear_existing_section_files(document_dir: Path) -> None:
    """Remove old generated Markdown section files before rewriting a document.

    Args:
        document_dir: Per-document output directory.

    Returns:
        None.

    Example:
        Rerunning the CLI deletes old `.md` section files so stale files do not
        remain when the section count changes.
    """

    for path in document_dir.glob("*.md"):
        remove_file(path)


def remove_file(path: Path) -> None:
    """Remove one generated file, including long paths on Windows.

    Args:
        path: File path to remove.

    Returns:
        None.

    Example:
        Old long section ids can be deleted before short `section_001.md` files
        are written.
    """

    absolute_path = path.resolve()
    if os.name == "nt":
        os.remove("\\\\?\\" + str(absolute_path))
        return
    absolute_path.unlink()


def build_section_file_text(document_name: str, section: dict[str, object]) -> str:
    """Build the final Markdown text for one section file.

    Args:
        document_name: Source Markdown document name.
        section: One section dict from the JSON manifest.

    Returns:
        Markdown text with a small metadata header followed by exact section text.

    Example:
        A section with text `## Opinion` keeps that text after the metadata header.
    """

    heading_path = section.get("heading_path", [])
    if not isinstance(heading_path, list):
        heading_path = []

    lines = [
        "---",
        f'document_name: "{document_name}"',
        f'section_id: "{section["section_id"]}"',
        f"page_start: {section['page_start']}",
        f"page_end: {section['page_end']}",
        f"estimated_tokens: {section['estimated_tokens']}",
        "heading_path:",
    ]
    for heading in heading_path:
        safe_heading = str(heading).replace('"', '\\"')
        lines.append(f'  - "{safe_heading}"')
    lines.append("---")
    lines.append("")
    lines.append(str(section["text"]).rstrip())
    lines.append("")
    return "\n".join(lines)


def save_report(document_name: str, units: list[ExtractionUnit], reports_dir: Path) -> Path:
    """Save a validation report for human inspection.

    Args:
        document_name: Source Markdown file name.
        units: Extraction units for the document.
        reports_dir: Directory for text reports.

    Returns:
        Path to the written report.

    Example:
        `save_report("a.md", units, Path("greater_than_10_pages/reports"))` writes `a.txt`.
    """

    reports_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for index, unit in enumerate(units, start=1):
        lines.append(f"{index:03d}")
        lines.append("")
        lines.append(f"Pages {unit.page_start}-{unit.page_end}")
        lines.append("")
        lines.append(f"{unit.estimated_tokens} tokens")
        lines.append("")
        if unit.heading_path:
            for path_index, heading in enumerate(unit.heading_path):
                if path_index:
                    lines.append(">")
                    lines.append("")
                lines.append(heading)
                lines.append("")
        else:
            lines.append(Path(document_name).stem)
            lines.append("")
        lines.append("-" * 50)
        lines.append("")

    report_path = reports_dir / f"{Path(document_name).stem}.txt"
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def unit_to_dict(unit: ExtractionUnit) -> dict[str, object]:
    """Convert one unit to the exact manifest shape.

    Args:
        unit: Extraction unit object.

    Returns:
        JSON-ready dict.

    Example:
        The returned dict contains `section_id`, `heading_path`, pages, tokens, and text.
    """

    return {
        "section_id": unit.section_id,
        "heading_path": unit.heading_path,
        "page_start": unit.page_start,
        "page_end": unit.page_end,
        "estimated_tokens": unit.estimated_tokens,
        "text": unit.text,
    }


def summarize_units(units: list[ExtractionUnit]) -> dict[str, int]:
    """Calculate CLI summary numbers.

    Args:
        units: Extraction units for one document.

    Returns:
        Counts for sections, average, largest, and smallest token values.

    Example:
        Two units with 10 and 20 tokens return average `15`.
    """

    if not units:
        return {"sections": 0, "average": 0, "largest": 0, "smallest": 0}
    token_counts = [unit.estimated_tokens for unit in units]
    return {
        "sections": len(units),
        "average": round(sum(token_counts) / len(token_counts)),
        "largest": max(token_counts),
        "smallest": min(token_counts),
    }
