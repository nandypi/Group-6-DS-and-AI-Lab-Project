"""Mark boilerplate blocks and sections before sizing.

Flow:
1. `mark_boilerplate` counts repeated short text.
2. It marks repeated headers or footers, image-only blocks, and known wrapper
   headings as excluded.
3. It marks a section excluded only when all meaningful content below it is excluded.

ASSUMPTION: boilerplate is excluded from sizing and from pure-boilerplate output
units, but original source text is not modified.
"""

from __future__ import annotations

import re
from collections import Counter

from datapreparation.sectioner.models import MarkdownBlock, SectionNode
from datapreparation.sectioner.tree import clean_heading_text, visible_blocks_for, walk_nodes

BOILERPLATE_HEADINGS = {
    "safe harbor",
    "media contacts",
    "contact details",
    "signatures",
    "table of contents",
    "to all stock exchanges",
    "bse limited national stock exchange of india limited new york stock exchange",
}


def mark_boilerplate(root: SectionNode) -> None:
    """Mark blocks and sections that should not drive extraction unit sizing.

    Args:
        root: Heading tree root.

    Returns:
        None. The tree is updated in place.

    Example:
        A `<!-- image -->` block becomes `excluded=True`.
    """

    repeated_text = find_repeated_short_text(root)
    for block in visible_blocks_for(root, True):
        if block.block_type in {"blank", "page_marker", "image"}:
            block.excluded = True
            continue
        normalized = normalize_text(block.text)
        if normalized in repeated_text:
            block.excluded = True
            continue
        if block.block_type == "heading":
            heading = normalize_text(clean_heading_text(block.text))
            if heading in BOILERPLATE_HEADINGS:
                block.excluded = True

    for node in reversed(walk_nodes(root)):
        node.excluded = is_pure_boilerplate(node)


def find_repeated_short_text(root: SectionNode) -> set[str]:
    """Find repeated short lines that act like headers or footers.

    Args:
        root: Heading tree root.

    Returns:
        Normalized text values that appear at least three times.

    Example:
        Repeated `Deloitte Haskins & Sells LLP` headings are returned.
    """

    values = []
    for block in visible_blocks_for(root, True):
        if block.block_type not in {"heading", "paragraph"}:
            continue
        normalized = normalize_text(block.text)
        if 0 < len(normalized) <= 90:
            values.append(normalized)

    counts = Counter(values)
    return {text for text, count in counts.items() if count >= 3}


def is_pure_boilerplate(node: SectionNode) -> bool:
    """Decide whether a whole section has only excluded content.

    Args:
        node: Section node after block exclusions have been marked.

    Returns:
        True when the node should not become its own extraction unit.

    Example:
        An image-only section returns True.
    """

    own_blocks = []
    if node.heading_block is not None:
        own_blocks.append(node.heading_block)
    own_blocks.extend(node.content_blocks)

    has_real_block = any(block.block_type not in {"blank", "page_marker"} for block in own_blocks)
    has_counted_block = any(not block.excluded for block in own_blocks)
    children_count = any(not child.excluded for child in node.children)

    if not has_real_block and not children_count:
        return True
    return not has_counted_block and not children_count


def normalize_text(text: str) -> str:
    """Normalize text for boilerplate matching only.

    Args:
        text: Original Markdown text.

    Returns:
        Lowercase text with Markdown and whitespace simplified.

    Example:
        `normalize_text("##  Media Contacts ")` returns `"media contacts"`.
    """

    text = re.sub(r"^#{1,6}\s+", "", text.strip())
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()
