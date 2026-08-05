"""Score question-document pairs with the lightweight MiniLM cross-encoder.

Flow: create ``MiniLMReranker`` -> reuse ``reranker.py``'s front-matter split,
truncation, and dual metadata/body scoring (via ``score_document``) -> return
a normalized score. This is a drop-in alternative to ``BGEReranker``: it
exposes the same ``.score(question, text)`` method and a Hugging Face-style
``.tokenizer``, so ``retriever.rerank_results`` works unchanged with either.

ASSUMPTION: ``cross-encoder/ms-marco-MiniLM-L-6-v2`` outputs a raw logit, not
a probability. A sigmoid is applied so ``.score()`` falls in the same [0, 1]
range as ``BGEReranker.score`` and can be combined with the same body/metadata
weights used for BGE.
"""

import math
import os

os.environ.setdefault("USE_TF", "0")


MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MAX_TOKENS = 512


class MiniLMReranker:
    """Load MiniLM once and expose the same scoring interface as BGEReranker.

    ~22M parameters versus BGE's ~568M, so both load time and per-pair
    scoring are much faster. The CLI/benchmark scripts create one instance at
    startup rather than per query, same as BGEReranker.
    """

    def __init__(self, model_name=MODEL_NAME, max_tokens=MAX_TOKENS):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name, max_length=max_tokens)
        self.tokenizer = self.model.tokenizer
        self.max_tokens = max_tokens

    def score(self, question, text):
        """Return one normalized MiniLM score for a question and text pair."""
        raw_score = self.model.predict([(question, text)])[0]
        return float(1 / (1 + math.exp(-raw_score)))
