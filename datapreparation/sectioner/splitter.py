"""Create extraction units from a marked heading tree.

Flow:
1. `create_extraction_units` processes each top-level section in document order.
2. `split_node` keeps coherent sections under the soft maximum intact.
3. Oversized sections are split by child headings first.
4. Oversized leaves are split by numbered headings, table boundaries, pages, then
   paragraphs while tables stay atomic.
5. Tiny adjacent sibling units are merged only within the same parent.
6. Stable section ids are assigned at the end.

ASSUMPTION: when a leaf must be split, later pieces keep the original text only
and rely on `heading_path` for context instead of repeating headings that did not
appear again in the source Markdown.

ASSUMPTION: when Docling starts a document at `##` and there are no `#`
headings, those `##` headings are mergeable siblings under the synthetic
document root. This avoids noisy tiny units caused by heading-level offsets.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from datapreparation.sectioner.models import ExtractionUnit, MarkdownBlock, SectionNode
from datapreparation.sectioner.tokens import estimate_tokens
from datapreparation.sectioner.tree import (
    heading_path_for,
    page_range_for_blocks,
    sizing_blocks_for,
    text_from_blocks,
    token_count_for_node,
    visible_blocks_for,
)

PREFERRED_MIN_TOKENS = 2000
SOFT_MAX_TOKENS = 8000
HARD_MAX_TOKENS = 10000


@dataclass
class UnitDraft:
    """Internal extraction unit before the final stable id is known.

    A small dataclass is clearer than parallel lists because merging and splitting
    repeatedly pass the same related values together.
    """

    heading_path: list[str]
    blocks: list[MarkdownBlock]
    parent_key: tuple[str, ...]


def create_extraction_units(root: SectionNode, document_stem: str) -> list[ExtractionUnit]:
    """Create final extraction units from a heading tree.

    Args:
        root: Tree after boilerplate marking.
        document_stem: File stem used in section ids.

    Returns:
        Extraction units in source document order.

    Example:
        The first unit for `annual_report.md` is `annual_report__001`.
    """

    drafts: list[UnitDraft] = []

    if has_counted_text(root.content_blocks):
        root_blocks = [block for block in root.content_blocks if block.block_type != "page_marker"]
        drafts.extend(split_blocks(root_blocks, [root.heading], (root.heading,)))

    if not root.children:
        if not drafts:
            drafts.extend(split_blocks(visible_blocks_for(root, True), [root.heading], (root.heading,)))
    else:
        top_level_drafts = []
        for top_level_node in root.children:
            top_level_drafts.extend(split_node(top_level_node, root))
        drafts.extend(merge_tiny_adjacent_siblings(top_level_drafts))

    units = []
    for index, draft in enumerate(drafts, start=1):
        blocks = [block for block in draft.blocks if block.block_type != "page_marker"]
        text = text_from_blocks(blocks).strip()
        if not text:
            continue
        page_start, page_end = page_range_for_blocks(blocks)
        heading_path = draft.heading_path
        if not heading_path:
            heading_path = [document_stem]
        unit = ExtractionUnit(
            section_id=f"{document_stem}__{index:03d}",
            heading_path=heading_path,
            page_start=page_start,
            page_end=page_end,
            estimated_tokens=estimate_tokens(text),
            text=text,
        )
        units.append(unit)

    return units


def split_node(node: SectionNode, root: SectionNode) -> list[UnitDraft]:
    """Split one section node into extraction-unit drafts.

    Args:
        node: Section node being processed.
        root: Tree root used to calculate heading paths.

    Returns:
        One or more drafts in document order.

    Example:
        A section under 8000 estimated tokens returns one draft.
    """

    if node.excluded:
        return []

    heading_path = heading_path_for(node, root)
    parent_key = tuple(heading_path[:-1])
    total_tokens = token_count_for_node(node, True)

    if total_tokens <= SOFT_MAX_TOKENS:
        return [UnitDraft(heading_path, visible_blocks_for(node, True), parent_key)]

    if node.children:
        drafts: list[UnitDraft] = []
        own_blocks = []
        if node.heading_block is not None:
            own_blocks.append(node.heading_block)
        own_blocks.extend(node.content_blocks)

        if has_counted_text(own_blocks):
            drafts.extend(split_blocks(own_blocks, heading_path, tuple(heading_path)))

        child_drafts = []
        for child in node.children:
            child_drafts.extend(split_node(child, root))
        drafts.extend(merge_tiny_adjacent_siblings(child_drafts))
        return drafts

    return split_blocks(visible_blocks_for(node, False), heading_path, parent_key)


def merge_tiny_adjacent_siblings(drafts: list[UnitDraft]) -> list[UnitDraft]:
    """Merge tiny adjacent drafts that share the same parent.

    Args:
        drafts: Drafts from sibling nodes.

    Returns:
        Drafts after deterministic left-to-right merging.

    Example:
        Two adjacent 500-token sibling drafts become one combined draft.
    """

    merged: list[UnitDraft] = []
    index = 0
    while index < len(drafts):
        current = drafts[index]
        current_tokens = draft_tokens(current)
        index += 1

        while current_tokens < PREFERRED_MIN_TOKENS and index < len(drafts):
            next_draft = drafts[index]
            next_tokens = draft_tokens(next_draft)
            can_merge = current.parent_key == next_draft.parent_key
            if not can_merge:
                break
            if current_tokens + next_tokens > SOFT_MAX_TOKENS:
                break

            current = UnitDraft(
                common_heading_path(current.heading_path, next_draft.heading_path),
                current.blocks + next_draft.blocks,
                current.parent_key,
            )
            current_tokens += next_tokens
            index += 1

        merged.append(current)

    return merged


def split_blocks(
    blocks: list[MarkdownBlock],
    heading_path: list[str],
    parent_key: tuple[str, ...],
) -> list[UnitDraft]:
    """Split blocks without splitting tables arbitrarily.

    Args:
        blocks: Ordered blocks from one oversized leaf or intro section.
        heading_path: Heading path to attach to each draft.
        parent_key: Parent identity used for later merging.

    Returns:
        Unit drafts in document order.

    Example:
        A long leaf with `Note 1` and `Note 2` paragraphs is split before notes.
    """

    if not blocks:
        return []

    if estimate_tokens(text_from_blocks(counted_blocks(blocks))) <= SOFT_MAX_TOKENS:
        return [UnitDraft(heading_path, blocks, parent_key)]

    groups = split_by_numbered_subsections(blocks)
    if len(groups) == 1:
        groups = split_by_table_boundaries(blocks)
    if len(groups) == 1:
        groups = split_by_page_boundaries(blocks)
    if len(groups) == 1:
        groups = split_by_paragraph_boundaries(blocks)

    drafts: list[UnitDraft] = []
    for group in groups:
        if not group:
            continue
        if estimate_tokens(text_from_blocks(counted_blocks(group))) > HARD_MAX_TOKENS:
            drafts.extend(force_split_large_group(group, heading_path, parent_key))
        else:
            drafts.append(UnitDraft(heading_path, group, parent_key))
    return drafts


def split_by_numbered_subsections(blocks: list[MarkdownBlock]) -> list[list[MarkdownBlock]]:
    """Split before numbered subsection starts such as `Note 1` or `1.`.

    Args:
        blocks: Blocks from one oversized leaf.

    Returns:
        Groups split at numbered subsection boundaries.

    Example:
        Paragraphs starting `Note 1` and `Note 2` become separate groups.
    """

    groups: list[list[MarkdownBlock]] = []
    current: list[MarkdownBlock] = []
    for block in blocks:
        if current and starts_numbered_subsection(block):
            groups.append(current)
            current = []
        current.append(block)
    if current:
        groups.append(current)
    return groups


def split_by_table_boundaries(blocks: list[MarkdownBlock]) -> list[list[MarkdownBlock]]:
    """Split around tables while keeping every table block whole.

    Args:
        blocks: Blocks from one oversized leaf.

    Returns:
        Groups ending at or before table boundaries.

    Example:
        Paragraph, table, paragraph becomes up to three groups.
    """

    return pack_blocks_by_limit(blocks, SOFT_MAX_TOKENS)


def split_by_page_boundaries(blocks: list[MarkdownBlock]) -> list[list[MarkdownBlock]]:
    """Split blocks by page while preserving block order.

    Args:
        blocks: Blocks from one oversized leaf.

    Returns:
        One group per page cluster.

    Example:
        Blocks from pages 1 and 2 become two groups when needed.
    """

    groups: list[list[MarkdownBlock]] = []
    current: list[MarkdownBlock] = []
    current_page = blocks[0].page
    for block in blocks:
        if current and block.page != current_page:
            groups.append(current)
            current = []
            current_page = block.page
        current.append(block)
    if current:
        groups.append(current)
    return groups


def split_by_paragraph_boundaries(blocks: list[MarkdownBlock]) -> list[list[MarkdownBlock]]:
    """Split by paragraph-like block boundaries as a last normal strategy.

    Args:
        blocks: Blocks from one oversized leaf.

    Returns:
        Packed groups under the soft maximum where possible.

    Example:
        Three long paragraphs may become three groups.
    """

    return pack_blocks_by_limit(blocks, SOFT_MAX_TOKENS)


def pack_blocks_by_limit(blocks: list[MarkdownBlock], limit: int) -> list[list[MarkdownBlock]]:
    """Pack blocks into groups without splitting a block.

    Args:
        blocks: Blocks in document order.
        limit: Target token limit.

    Returns:
        Groups in document order.

    Example:
        Small adjacent paragraphs are packed until the limit is reached.
    """

    groups: list[list[MarkdownBlock]] = []
    current: list[MarkdownBlock] = []
    current_tokens = 0

    for block in blocks:
        block_tokens = estimate_tokens(block.text) if not block.excluded else 0
        if current and current_tokens + block_tokens > limit:
            groups.append(current)
            current = []
            current_tokens = 0
        current.append(block)
        current_tokens += block_tokens

    if current:
        groups.append(current)
    return groups


def force_split_large_group(
    blocks: list[MarkdownBlock],
    heading_path: list[str],
    parent_key: tuple[str, ...],
) -> list[UnitDraft]:
    """Handle groups that still exceed the hard maximum.

    Args:
        blocks: Oversized block group.
        heading_path: Heading path for produced drafts.
        parent_key: Parent identity for merging.

    Returns:
        Drafts. Large tables are split by row groups with their header repeated.

    Example:
        A single huge table is split into multiple table-shaped drafts.
    """

    drafts: list[UnitDraft] = []
    for block in blocks:
        block_tokens = estimate_tokens(block.text) if not block.excluded else 0
        if block.block_type == "table" and block_tokens > HARD_MAX_TOKENS:
            for table_block in split_large_table(block):
                drafts.append(UnitDraft(heading_path, [table_block], parent_key))
            continue
        if block_tokens > HARD_MAX_TOKENS and block.block_type == "paragraph":
            for paragraph_block in split_large_paragraph(block):
                drafts.append(UnitDraft(heading_path, [paragraph_block], parent_key))
            continue
        drafts.append(UnitDraft(heading_path, [block], parent_key))
    return drafts


def split_large_table(block: MarkdownBlock) -> list[MarkdownBlock]:
    """Split an oversized Markdown table by row groups.

    Args:
        block: One table block that exceeds the hard maximum.

    Returns:
        Smaller table blocks. Header rows are repeated.

    Example:
        A 1000-row table becomes multiple tables with the same header.
    """

    lines = block.text.splitlines()
    if len(lines) <= 3:
        return [block]

    header = lines[:2]
    rows = lines[2:]
    groups: list[MarkdownBlock] = []
    current_rows: list[str] = []
    current_tokens = estimate_tokens("\n".join(header))

    for row in rows:
        row_tokens = estimate_tokens(row)
        if current_rows and current_tokens + row_tokens > SOFT_MAX_TOKENS:
            groups.append(MarkdownBlock("table", "\n".join(header + current_rows), block.page))
            current_rows = []
            current_tokens = estimate_tokens("\n".join(header))
        current_rows.append(row)
        current_tokens += row_tokens

    if current_rows:
        groups.append(MarkdownBlock("table", "\n".join(header + current_rows), block.page))
    return groups


def split_large_paragraph(block: MarkdownBlock) -> list[MarkdownBlock]:
    """Split an unusually large paragraph by sentence boundaries.

    Args:
        block: Paragraph block that exceeds the hard maximum.

    Returns:
        Smaller paragraph blocks.

    Example:
        A paragraph with many sentences becomes multiple paragraph blocks.
    """

    sentences = re.split(r"(?<=[.!?])\s+", block.text)
    groups = []
    current = []
    current_tokens = 0
    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)
        if current and current_tokens + sentence_tokens > SOFT_MAX_TOKENS:
            groups.append(MarkdownBlock("paragraph", " ".join(current), block.page))
            current = []
            current_tokens = 0
        current.append(sentence)
        current_tokens += sentence_tokens
    if current:
        groups.append(MarkdownBlock("paragraph", " ".join(current), block.page))
    return groups


def starts_numbered_subsection(block: MarkdownBlock) -> bool:
    text = block.text.strip()
    return bool(re.match(r"^(Note\s+\d+|[0-9]+[\.)])\b", text, re.IGNORECASE))


def counted_blocks(blocks: list[MarkdownBlock]) -> list[MarkdownBlock]:
    return [block for block in blocks if not block.excluded]


def has_counted_text(blocks: list[MarkdownBlock]) -> bool:
    text = text_from_blocks(counted_blocks(blocks))
    return bool(text.strip())


def draft_tokens(draft: UnitDraft) -> int:
    return estimate_tokens(text_from_blocks(counted_blocks(draft.blocks)))


def common_heading_path(left: list[str], right: list[str]) -> list[str]:
    """Find the shared heading path for a merged sibling unit.

    Args:
        left: First heading path.
        right: Second heading path.

    Returns:
        Shared prefix. An empty list means the merged sections only share the
        synthetic document root.

    Example:
        `["A", "B"]` and `["A", "C"]` return `["A"]`.
    """

    shared = []
    for left_part, right_part in zip(left, right):
        if left_part != right_part:
            break
        shared.append(left_part)
    return shared
