"""Section large Markdown documents into deterministic extraction units.

Flow:
1. `datapreparation.sectioner.cli` reads every `.md` file from the input directory.
2. `pipeline.process_markdown_file` reads one Markdown file.
3. `parser.parse_markdown` turns the Markdown into ordered blocks with pages.
4. `tree.build_heading_tree` attaches blocks to their heading hierarchy.
5. `boilerplate.mark_boilerplate` marks low-value blocks and sections.
6. `splitter.create_extraction_units` sizes, splits, and merges sections.
7. `writer.save_manifest` writes JSON and `writer.save_report` writes a text report.

Project terms:
- A block is one Markdown unit such as a heading, paragraph, table, list, image, or page marker.
- A section node is one heading plus all content below it until the next matching heading.
- An extraction unit is the final JSON-ready text chunk used by the downstream LLM pipeline.
"""

__all__ = ["process_markdown_file"]

from datapreparation.sectioner.pipeline import process_markdown_file
