"""Token counting helpers.

Flow:
1. Splitter asks `estimate_tokens` for each block or candidate unit.
2. The estimate uses words and punctuation only.
3. The estimate guides deterministic merging and splitting decisions.
4. Writers ask `count_actual_tokens` before storing a final token count.
5. The actual count uses the `text-embedding-3-small` tokenizer.

ASSUMPTION: a rough local estimate is enough because the plan says token counts
only guide section sizing and this module must not call an LLM.
ASSUMPTION: actual token count means the tokenizer used by the embedding model.
"""

from __future__ import annotations

import re

import tiktoken

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
EMBEDDING_MODEL = "text-embedding-3-small"
ACTUAL_TOKEN_ENCODING = tiktoken.encoding_for_model(EMBEDDING_MODEL)


def estimate_tokens(text: str) -> int:
    """Estimate token count for Markdown text.

    Args:
        text: Markdown text from one block or extraction unit.

    Returns:
        A deterministic rough token count.

    Example:
        `estimate_tokens("Revenue grew 5%.")` returns `5`.
    """

    if not text.strip():
        return 0
    return len(TOKEN_PATTERN.findall(text))


def count_actual_tokens(text: str) -> int:
    """Count tokens with the embedding-model tokenizer.

    Args:
        text: Markdown text from one final section or group.

    Returns:
        Actual tokenizer count for `text-embedding-3-small`.

    Example:
        `count_actual_tokens("Revenue grew 5%.")` returns that sentence's
        tokenizer-specific token count.
    """

    if not text.strip():
        return 0
    return len(ACTUAL_TOKEN_ENCODING.encode(text))
