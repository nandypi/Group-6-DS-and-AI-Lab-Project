"""Shared data structures for the sectioning pipeline.

Flow:
1. Parser creates `MarkdownBlock` records.
2. Tree builder groups those blocks into `SectionNode` records.
3. Splitter returns `ExtractionUnit` records.
4. Writer serializes extraction units to JSON and text reports.

ASSUMPTION: dataclasses are useful here because the same structured records are
passed across several modules and each record carries more than one related value.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarkdownBlock:
    """One ordered piece of Markdown text.

    Args:
        block_type: Plain label such as `heading`, `paragraph`, `table`, or `list`.
        text: Exact Markdown text for this block.
        page: Original PDF page number, or the best deterministic estimate.
        heading_level: Markdown heading level for heading blocks.
        excluded: True when the block should not count toward section sizing.

    Example:
        `MarkdownBlock("heading", "## Opinion", 3, 2).text` returns `"## Opinion"`.
    """

    block_type: str
    text: str
    page: int
    heading_level: int = 0
    excluded: bool = False


@dataclass
class SectionNode:
    """A heading and the content below it.

    The tree builder creates these after a heading is found. The root node has an
    empty heading and level 0 so documents with front matter or no headings still
    have a stable parent.

    Example:
        A `## Opinion` node under `# Audit Report` has heading path
        `["Audit Report", "Opinion"]`.
    """

    heading: str
    level: int
    heading_block: MarkdownBlock | None = None
    content_blocks: list[MarkdownBlock] = field(default_factory=list)
    children: list["SectionNode"] = field(default_factory=list)
    excluded: bool = False


@dataclass
class ExtractionUnit:
    """Final unit written to the JSON manifest.

    Args:
        section_id: Stable identifier made from the document name and unit number.
        heading_path: Full heading path from top-level heading to leaf heading.
        page_start: First original PDF page represented by the text.
        page_end: Last original PDF page represented by the text.
        estimated_tokens: Rough deterministic token estimate.
        text: Exact Markdown text assembled from original blocks.

    Example:
        Unit 1 for `report.md` becomes section id `report__001`.
    """

    section_id: str
    heading_path: list[str]
    page_start: int
    page_end: int
    estimated_tokens: int
    text: str
