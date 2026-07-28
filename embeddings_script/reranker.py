"""Score question-document pairs with the local BGE cross-encoder.

Flow: create ``BGEReranker`` -> count tokens -> truncate only an oversized
document body -> score metadata and body separately -> return normalized scores.
Metadata means the YAML front matter at the start of a Markdown document.

ASSUMPTION: BGE's normalized score is already suitable for combining the two
signals with the configured weights.
"""

import warnings

import yaml


MODEL_NAME = "BAAI/bge-reranker-v2-m3"
MAX_TOKENS = 8190


def split_front_matter(document):
    """Return ``(metadata_text, body, metadata)`` for one Markdown document.

    Called before reranking and final context creation. For example, a document
    beginning with ``---\\ntitle: Report\\n---\\nBody`` returns ``("title: Report",
    "Body", {"title": "Report"})``. Missing or malformed YAML returns an empty
    metadata value and preserves the document as the body.
    """
    if not document.startswith("---"):
        return "", document, {}

    lines = document.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", document, {}

    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        warnings.warn("YAML front matter is missing its closing delimiter.")
        return "", document, {}

    metadata_text = "".join(lines[1:closing_index]).strip()
    body = "".join(lines[closing_index + 1:]).lstrip("\r\n")

    try:
        metadata = yaml.safe_load(metadata_text) or {}
        if not isinstance(metadata, dict):
            raise ValueError("front matter must contain a mapping")
    except (yaml.YAMLError, ValueError) as error:
        warnings.warn(f"Could not parse YAML front matter: {error}")
        return "", body, {}

    return metadata_text, body, metadata


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


def score_document(reranker, question, document):
    """Score YAML metadata and body independently and return both scores.

    Called once for every Chroma candidate. Metadata is never appended to the
    body, so a matching title cannot replace the body's relevance signal.
    """
    metadata_text, body, metadata = split_front_matter(document)
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
