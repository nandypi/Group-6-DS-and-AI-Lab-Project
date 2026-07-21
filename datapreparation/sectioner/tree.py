"""Build and read a Markdown heading tree.

Flow:
1. `build_heading_tree` starts with a synthetic root.
2. Heading blocks create new `SectionNode` children.
3. Non-heading blocks attach to the current section.
4. Helper functions return paths, text, pages, and descendants for splitting.
"""

from __future__ import annotations

import re

from datapreparation.sectioner.models import MarkdownBlock, SectionNode
from datapreparation.sectioner.tokens import estimate_tokens


def build_heading_tree(blocks: list[MarkdownBlock], document_name: str) -> SectionNode:
    """Build a heading hierarchy from ordered Markdown blocks.

    Args:
        blocks: Parsed Markdown blocks in document order.
        document_name: Source file name used when the document has no headings.

    Returns:
        Root section node with children and attached content blocks.

    Example:
        A `# A` heading followed by `## B` becomes root -> A -> B.
    """

    root = SectionNode(document_name, 0)
    stack = [root]

    for block in blocks:
        if block.block_type == "page_marker":
            stack[-1].content_blocks.append(block)
            continue

        if block.block_type != "heading":
            stack[-1].content_blocks.append(block)
            continue

        heading = clean_heading_text(block.text)
        while stack and stack[-1].level >= block.heading_level:
            stack.pop()
        parent = stack[-1] if stack else root
        node = SectionNode(heading, block.heading_level, block)
        parent.children.append(node)
        stack.append(node)

    return root


def clean_heading_text(heading_markdown: str) -> str:
    """Remove leading Markdown hashes from a heading.

    Args:
        heading_markdown: Heading block text.

    Returns:
        Human-readable heading text.

    Example:
        `clean_heading_text("## Opinion")` returns `"Opinion"`.
    """

    return re.sub(r"^#{1,6}\s+", "", heading_markdown).strip()


def heading_path_for(node: SectionNode, root: SectionNode) -> list[str]:
    """Return a node's heading path from the root's children down.

    Args:
        node: Section node to locate.
        root: Root of the tree.

    Returns:
        List of heading names. The synthetic root is not included.

    Example:
        A child `Opinion` under `Audit Report` returns `["Audit Report", "Opinion"]`.
    """

    path = find_heading_path(root, node)
    if path is None:
        return []
    return path


def find_heading_path(current: SectionNode, target: SectionNode) -> list[str] | None:
    if current is target:
        if current.level == 0:
            return []
        return [current.heading]

    for child in current.children:
        child_path = find_heading_path(child, target)
        if child_path is not None:
            if current.level == 0:
                return child_path
            return [current.heading] + child_path
    return None


def visible_blocks_for(node: SectionNode, include_children: bool = True) -> list[MarkdownBlock]:
    """Return blocks that should appear in output text for a node.

    Args:
        node: Section to flatten.
        include_children: True when child sections should be included.

    Returns:
        Blocks in document order, including headings.

    Example:
        A section with one heading and paragraph returns two blocks.
    """

    blocks = []
    if node.heading_block is not None:
        blocks.append(node.heading_block)
    blocks.extend(node.content_blocks)
    if include_children:
        for child in node.children:
            blocks.extend(visible_blocks_for(child, True))
    return blocks


def sizing_blocks_for(node: SectionNode, include_children: bool = True) -> list[MarkdownBlock]:
    """Return blocks that count toward section sizing.

    Args:
        node: Section to flatten.
        include_children: True when child sections should be included.

    Returns:
        Non-excluded blocks in document order.

    Example:
        Image-only blocks marked excluded are omitted from the returned list.
    """

    return [block for block in visible_blocks_for(node, include_children) if not block.excluded]


def text_from_blocks(blocks: list[MarkdownBlock]) -> str:
    """Join blocks into Markdown text without rewriting block contents.

    Args:
        blocks: Blocks in document order.

    Returns:
        Markdown text with block boundaries separated by one newline.

    Example:
        Blocks `# A` and `Body` become `"# A\\nBody"`.
    """

    return "\n".join(block.text for block in blocks if block.text != "")


def page_range_for_blocks(blocks: list[MarkdownBlock]) -> tuple[int, int]:
    """Return the inclusive page range for a list of blocks.

    Args:
        blocks: Blocks that form one extraction unit.

    Returns:
        `(page_start, page_end)`.

    Example:
        Blocks from pages 2 and 3 return `(2, 3)`.
    """

    pages = [block.page for block in blocks if block.page >= 1]
    if not pages:
        return 1, 1
    return min(pages), max(pages)


def token_count_for_node(node: SectionNode, include_children: bool = True) -> int:
    """Estimate non-boilerplate tokens for a node.

    Args:
        node: Section to size.
        include_children: True when child sections should count.

    Returns:
        Estimated token count.

    Example:
        A node with excluded image placeholders may return 0.
    """

    text = text_from_blocks(sizing_blocks_for(node, include_children))
    return estimate_tokens(text)


def walk_nodes(node: SectionNode) -> list[SectionNode]:
    """Return all nodes below `node`, including `node`.

    Args:
        node: Root of the walk.

    Returns:
        Nodes in document order.

    Example:
        Root with two children returns root first, then child one, then child two.
    """

    nodes = [node]
    for child in node.children:
        nodes.extend(walk_nodes(child))
    return nodes
