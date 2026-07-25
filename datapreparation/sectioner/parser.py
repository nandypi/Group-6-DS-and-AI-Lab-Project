"""Parse Docling Markdown into ordered blocks with page mapping.

Flow:
1. `parse_markdown` removes YAML front matter from block parsing but reads `pages:`.
2. It scans lines in document order and recognizes page markers, headings, tables,
   lists, images, horizontal rules, blank lines, and paragraphs.
3. It preserves every block's original Markdown text.
4. It assigns each block an original PDF page.

ASSUMPTION: some Docling files in this repo contain `pages:` metadata but no
visible page markers. For those files, blocks are assigned to pages by their
character position in the Markdown body so page ranges stay deterministic.
"""

from __future__ import annotations

import re

from datapreparation.sectioner.models import MarkdownBlock

FRONT_MATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
PAGE_MARKER_PATTERNS = [
    re.compile(r"<!--\s*(?:page|pagebreak|page-break)\s*:?\s*(\d+)?\s*-->", re.IGNORECASE),
    re.compile(r"^\s*(?:page|Page)\s+(\d+)\s*$"),
    re.compile(r"^\s*-{0,3}\s*(?:page|Page)\s+(\d+)\s*-{0,3}\s*$"),
]


def parse_markdown(markdown_text: str) -> list[MarkdownBlock]:
    """Parse Markdown text into blocks.

    Args:
        markdown_text: Full Markdown file contents.

    Returns:
        Ordered blocks with exact text and page numbers.

    Example:
        `parse_markdown("# Title\\n\\nBody")[0].block_type` returns `"heading"`.
    """

    metadata, body, body_start = split_front_matter(markdown_text)
    total_pages = read_total_pages(metadata)
    lines = body.splitlines()
    blocks = collect_blocks(lines)
    assign_pages(blocks, total_pages, len(body), body_start)
    return blocks


def split_front_matter(markdown_text: str) -> tuple[dict[str, str], str, int]:
    """Return YAML-like metadata, body text, and body start offset.

    Args:
        markdown_text: Full Markdown file contents.

    Returns:
        Metadata dict, Markdown body, and the character offset where the body starts.

    Example:
        `split_front_matter("---\\npages: 2\\n---\\nHi")[0]["pages"]` returns `"2"`.
    """

    match = FRONT_MATTER_PATTERN.match(markdown_text)
    if not match:
        return {}, markdown_text, 0

    metadata_text = match.group(1)
    metadata = {}
    for line in metadata_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, markdown_text[match.end() :], match.end()


def read_total_pages(metadata: dict[str, str]) -> int | None:
    """Read `pages` from front matter when it is available.

    Args:
        metadata: Front matter parsed by `split_front_matter`.

    Returns:
        Page count as an integer, or None.

    Example:
        `read_total_pages({"pages": "25"})` returns `25`.
    """

    value = metadata.get("pages")
    if value is None:
        return None
    try:
        pages = int(value)
    except ValueError:
        return None
    if pages < 1:
        return None
    return pages


def collect_blocks(lines: list[str]) -> list[MarkdownBlock]:
    """Collect Markdown lines into typed blocks before page assignment.

    Args:
        lines: Markdown body split into lines.

    Returns:
        Blocks in document order. Pages are temporary until `assign_pages` runs.

    Example:
        `collect_blocks(["- a", "- b"])[0].block_type` returns `"list"`.
    """

    blocks: list[MarkdownBlock] = []
    index = 0
    while index < len(lines):
        line = lines[index]

        page_number = read_page_marker(line)
        if page_number is not None:
            blocks.append(MarkdownBlock("page_marker", line, page_number))
            index += 1
            continue

        if line.strip() == "":
            blocks.append(MarkdownBlock("blank", line, 1))
            index += 1
            continue

        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append(MarkdownBlock("heading", line, 1, level))
            index += 1
            continue

        if is_horizontal_rule(line):
            blocks.append(MarkdownBlock("horizontal_rule", line, 1))
            index += 1
            continue

        if is_image_line(line):
            blocks.append(MarkdownBlock("image", line, 1))
            index += 1
            continue

        if is_table_line(line):
            table_lines, index = take_while(lines, index, is_table_or_blank_line)
            blocks.append(MarkdownBlock("table", "\n".join(table_lines), 1))
            continue

        if is_list_line(line):
            list_lines, index = take_while(lines, index, is_list_or_continuation_line)
            blocks.append(MarkdownBlock("list", "\n".join(list_lines), 1))
            continue

        paragraph_lines, index = take_while(lines, index, is_paragraph_line)
        blocks.append(MarkdownBlock("paragraph", "\n".join(paragraph_lines), 1))

    return blocks


def assign_pages(
    blocks: list[MarkdownBlock],
    total_pages: int | None,
    body_length: int,
    body_start: int,
) -> None:
    """Assign page numbers to blocks in place.

    Args:
        blocks: Blocks created by `collect_blocks`.
        total_pages: Metadata page count, if known.
        body_length: Character length of the parsed Markdown body.
        body_start: Body offset in the full file. Kept for readability of the flow.

    Example:
        With no page markers and `total_pages=2`, early blocks get page 1 and
        later blocks get page 2.
    """

    has_page_markers = any(block.block_type == "page_marker" for block in blocks)
    if has_page_markers:
        current_page = 1
        for block in blocks:
            if block.block_type == "page_marker":
                marker_page = read_page_marker(block.text)
                if marker_page is not None:
                    current_page = marker_page
                block.page = current_page
                continue
            block.page = current_page
        return

    if not total_pages:
        for block in blocks:
            block.page = 1
        return

    position = 0
    safe_body_length = max(body_length, 1)
    for block in blocks:
        block_start = position
        page = int(block_start * total_pages / safe_body_length) + 1
        block.page = min(max(page, 1), total_pages)
        position += len(block.text) + 1

    _ = body_start


def read_page_marker(line: str) -> int | None:
    """Read a page number from a supported page marker line.

    Args:
        line: One Markdown line.

    Returns:
        Page number, or 1 for marker styles that omit the number.

    Example:
        `read_page_marker("<!-- page 7 -->")` returns `7`.
    """

    for pattern in PAGE_MARKER_PATTERNS:
        match = pattern.match(line.strip())
        if not match:
            continue
        if match.groups() and match.group(1):
            return int(match.group(1))
        return 1
    return None


def take_while(lines: list[str], start: int, should_take) -> tuple[list[str], int]:
    """Take consecutive lines while `should_take` returns true.

    Args:
        lines: All Markdown lines.
        start: First line index to inspect.
        should_take: Function that decides whether a line belongs to the block.

    Returns:
        Taken lines and the next unread index.

    Example:
        Taking from `["a", "b", ""]` with nonblank predicate returns two lines.
    """

    taken = []
    index = start
    while index < len(lines) and should_take(lines[index]):
        taken.append(lines[index])
        index += 1
    return taken, index


def is_horizontal_rule(line: str) -> bool:
    text = line.strip()
    return text in {"---", "***", "___"}


def is_image_line(line: str) -> bool:
    text = line.strip().lower()
    return text.startswith("![") or text == "<!-- image -->" or "<!-- image" in text


def is_table_line(line: str) -> bool:
    text = line.strip()
    return text.startswith("|") and text.endswith("|")


def is_table_or_blank_line(line: str) -> bool:
    return is_table_line(line) or line.strip() == ""


def is_list_line(line: str) -> bool:
    text = line.strip()
    return bool(re.match(r"^([-*+]\s+|\d+[\.)]\s+)", text))


def is_list_or_continuation_line(line: str) -> bool:
    if line.strip() == "":
        return True
    if is_list_line(line):
        return True
    return line.startswith("  ") or line.startswith("\t")


def is_paragraph_line(line: str) -> bool:
    if line.strip() == "":
        return False
    if read_page_marker(line) is not None:
        return False
    if HEADING_PATTERN.match(line):
        return False
    if is_horizontal_rule(line) or is_image_line(line) or is_table_line(line) or is_list_line(line):
        return False
    return True
