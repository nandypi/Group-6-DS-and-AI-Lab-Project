"""Score question-document pairs with the local BGE cross-encoder.

Flow: create ``BGEReranker`` -> choose the relevant YAML block from the
filepath -> truncate only an oversized document body -> score metadata and
body separately -> return normalized scores.
Metadata means the YAML front matter at the start of a Markdown document.

ASSUMPTION: BGE's normalized score is already suitable for combining the two
signals with the configured weights.
"""

import warnings

import yaml


MODEL_NAME = "BAAI/bge-reranker-v2-m3"
MAX_TOKENS = 8190
TARGETED_PATH_MARKERS = (
    "greater_than_10_pages",
    "infosys_earning_calls",
)
SEMANTIC_METADATA_FIELDS = {
    "section_title",
    "section_description",
    "topics",
    "sample_queries",
}


def _read_yaml_block(lines, start_index):
    """Read one YAML block starting at ``start_index``.

    Returns the block end index, its inner text, and a parsed mapping. A
    malformed block still returns its location so it can be removed from the
    body without making the whole candidate fail.
    """
    if start_index >= len(lines) or lines[start_index].strip() != "---":
        return None

    for index in range(start_index + 1, len(lines)):
        if lines[index].strip() != "---":
            continue

        metadata_text = "".join(lines[start_index + 1 : index]).strip()
        try:
            metadata = yaml.safe_load(metadata_text) or {}
            if not isinstance(metadata, dict):
                raise ValueError("front matter must contain a mapping")
        except (yaml.YAMLError, ValueError):
            # Keep the raw block usable for reranking even if an older Chroma
            # document was indexed before its YAML quoting was repaired.
            metadata = None
        return index, metadata_text, metadata

    warnings.warn("YAML front matter is missing its closing delimiter.")
    return None


def _path_uses_two_yaml_blocks(filepath):
    """Return whether ``filepath`` belongs to a two-block document category.

    Example: a path containing ``greater_than_10_pages`` returns ``True``;
    an unrelated one-block document returns ``False``.
    """
    normalized_path = filepath.replace("\\", "/").lower()
    return any(marker in normalized_path for marker in TARGETED_PATH_MARKERS)


def split_front_matter(document, filepath=""):
    """Return ``(metadata_text, body, metadata)`` using the relevant YAML block.

    Called before reranking and final context creation. For example, a document
    beginning with ``---\\ntitle: Report\\n---\\nBody`` returns ``("title: Report",
    "Body", {"title": "Report"})``. Missing or malformed YAML returns an empty
    metadata value and preserves the remaining document as the body.

    Documents in the two re-sectioned categories have structural YAML followed
    by semantic YAML. Their filepath selects the second block. Other documents
    retain the original first-block behavior.
    """
    lines = document.splitlines(keepends=True)
    first_block = _read_yaml_block(lines, 0)
    if first_block is None:
        return "", document, {}

    first_close, first_text, first_metadata = first_block
    body_start = first_close + 1
    second_block = _read_yaml_block(lines, body_start)

    if second_block is not None:
        second_close, second_text, second_metadata = second_block
        body_start = second_close + 1
    else:
        second_text = ""
        second_metadata = None

    body = "".join(lines[body_start:]).lstrip("\r\n")

    if _path_uses_two_yaml_blocks(filepath):
        if isinstance(second_metadata, dict):
            return second_text, body, second_metadata

        if isinstance(first_metadata, dict) and SEMANTIC_METADATA_FIELDS.intersection(
            first_metadata
        ):
            return first_text, body, first_metadata

        if second_text:
            return second_text, body, {}

        return first_text, body, {}

    if isinstance(first_metadata, dict):
        return first_text, body, first_metadata

    return first_text, body, {}


def truncate_body_for_reranker(tokenizer, question, body, max_tokens=MAX_TOKENS):
    """Keep the question complete and truncate only the body when needed.

    The returned text is used only for BGE scoring. Example: if the tokenizer
    counts the pair as too long, the body is encoded, shortened, and decoded;
    the original body remains available to the final language-model context.
    """
    question_tokens = tokenizer.encode(question, add_special_tokens=False)
    body_tokens = tokenizer.encode(body, add_special_tokens=False)
    available_body_tokens = max_tokens - len(question_tokens) - 3

    if available_body_tokens <= 0:
        raise ValueError("ERROR: question is too long for the reranker input limit.")

    if len(question_tokens) + len(body_tokens) + 3 <= max_tokens:
        return body

    return tokenizer.decode(body_tokens[:available_body_tokens], skip_special_tokens=True)


class BGEReranker:
    """Load BGE once and expose simple normalized pair scoring.

    The heavy FlagEmbedding import and model download happen on construction,
    which is why the CLI creates one instance at startup rather than per query.
    """

    def __init__(self, model_name=MODEL_NAME, max_tokens=MAX_TOKENS):
        from FlagEmbedding import FlagReranker

        self.model = FlagReranker(model_name, use_fp16=False)
        self.tokenizer = self.model.tokenizer
        self.max_tokens = max_tokens

    def score(self, question, text):
        """Return one normalized BGE score for a question and text pair."""
        score = self.model.compute_score([question, text], normalize=True)
        if isinstance(score, (list, tuple)):
            score = score[0]
        return float(score)


def score_document(reranker, question, document, filepath=""):
    """Score YAML metadata and body independently and return both scores.

    Called once for every Chroma candidate. Metadata is never appended to the
    body, so a matching title cannot replace the body's relevance signal.
    """
    metadata_text, body, metadata = split_front_matter(document, filepath)
    metadata_score = reranker.score(question, metadata_text) if metadata_text else 0.0
    scoring_body = truncate_body_for_reranker(
        reranker.tokenizer,
        question,
        body,
        reranker.max_tokens,
    )
    body_score = reranker.score(question, scoring_body)
    return {
        "metadata_text": metadata_text,
        "metadata": metadata,
        "body": body,
        "metadata_score": metadata_score,
        "body_score": body_score,
    }
