"""Run the full Markdown sectioning pipeline for one document.

Flow:
1. Read one Markdown file from disk.
2. Parse structure and preserve page mapping.
3. Build the heading tree.
4. Mark boilerplate before sizing.
5. Create extraction units.
6. Save the JSON manifest.
7. Generate final Markdown section files from the created JSON.
8. Save the validation report.
9. Return paths and summary numbers for CLI logging.
"""

from __future__ import annotations

from pathlib import Path

from datapreparation.sectioner.boilerplate import mark_boilerplate
from datapreparation.sectioner.parser import parse_markdown
from datapreparation.sectioner.splitter import create_extraction_units
from datapreparation.sectioner.tree import build_heading_tree
from datapreparation.sectioner.writer import (
    save_manifest,
    save_report,
    save_section_files_from_manifest,
    summarize_units,
)


def process_markdown_file(
    markdown_path: Path,
    output_dir: Path,
    reports_dir: Path,
    section_files_dir: Path,
) -> dict[str, object]:
    """Process one Markdown file and write its outputs.

    Args:
        markdown_path: Input Markdown file path.
        output_dir: Directory for section JSON manifests.
        reports_dir: Directory for validation reports.
        section_files_dir: Directory for final Markdown section files.

    Returns:
        Summary details used by the CLI.

    Example:
        Processing `report.md` writes `greater_than_10_pages/sections/report.json`,
        `greater_than_10_pages/sectioned_files/report/section_001.md`, and
        `greater_than_10_pages/reports/report.txt`.
    """

    markdown_text = markdown_path.read_text(encoding="utf-8")
    blocks = parse_markdown(markdown_text)
    root = build_heading_tree(blocks, markdown_path.name)
    mark_boilerplate(root)

    units = create_extraction_units(root, markdown_path.stem)
    manifest_path = save_manifest(markdown_path.name, units, output_dir)
    section_file_paths = save_section_files_from_manifest(manifest_path, section_files_dir)
    report_path = save_report(markdown_path.name, units, reports_dir)
    summary = summarize_units(units)

    return {
        "document": markdown_path.name,
        "manifest_path": manifest_path,
        "section_file_count": len(section_file_paths),
        "report_path": report_path,
        "summary": summary,
    }
