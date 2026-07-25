"""Token estimation helpers.

Flow:
1. Splitter asks `estimate_tokens` for each block or candidate unit.
2. The estimate uses words and punctuation only.
3. The estimate guides deterministic merging and splitting decisions.

ASSUMPTION: a rough local estimate is enough because the plan says token counts
only guide section sizing and this module must not call an LLM.
"""

from __future__ import annotations

import re

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


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
