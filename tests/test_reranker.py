"""Focused tests for front matter handling and BGE reranking helpers.

Flow: create a small fake tokenizer and scorer -> run the same parsing,
truncation, weighting, and context helpers used by the CLI -> assert that only
body text reaches the final context.
"""

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "embeddings_script"))

from reranker import score_document, split_front_matter, truncate_body_for_reranker
import retriever


class FakeTokenizer:
    """Use one whitespace token per word so truncation is easy to inspect."""

    def encode(self, text, add_special_tokens=False):
        return text.split()

    def decode(self, tokens, skip_special_tokens=True):
        return " ".join(tokens)


class FakeReranker:
    def __init__(self):
        self.tokenizer = FakeTokenizer()
        self.max_tokens = 10
        self.scored_texts = []

    def score(self, question, text):
        self.scored_texts.append(text)
        return 0.8 if "body match" in text else 0.2


class RerankerTests(unittest.TestCase):
    def test_split_front_matter(self):
        metadata_text, body, metadata = split_front_matter(
            "---\ntitle: Report\ncompany: Infosys\n---\nBody text"
        )
        self.assertIn("title: Report", metadata_text)
        self.assertEqual(body, "Body text")
        self.assertEqual(metadata["company"], "Infosys")

    def test_malformed_front_matter_has_zero_metadata(self):
        metadata_text, body, metadata = split_front_matter(
            "---\ntitle: [not closed\n---\nBody"
        )
        self.assertEqual(metadata_text, "")
        self.assertEqual(body, "Body")
        self.assertEqual(metadata, {})

    def test_truncation_changes_only_scoring_body(self):
        tokenizer = FakeTokenizer()
        truncated = truncate_body_for_reranker(
            tokenizer,
            "what body match",
            "one two three four five six seven eight nine",
            max_tokens=10,
        )
        self.assertEqual(truncated, "one two three four")

    def test_score_document_scores_metadata_and_body_separately(self):
        reranker = FakeReranker()
        result = score_document(
            reranker,
            "what body match",
            "---\ntitle: body match\n---\nbody match is here",
        )
        self.assertEqual(result["body"], "body match is here")
        self.assertEqual(len(reranker.scored_texts), 2)
        self.assertNotIn("title: body match", reranker.scored_texts[1])
        self.assertAlmostEqual(0.8 * 0.8 + 0.2 * 0.2, 0.68)

    def test_rerank_selects_three_distinct_documents_and_builds_body_context(self):
        reranker = FakeReranker()
        results = {
            "documents": [[
                "---\ntitle: low\n---\nlow body",
                "---\ntitle: high\n---\nhigh body match",
                "---\ntitle: duplicate\n---\nduplicate body",
                "---\ntitle: third\n---\nthird body match",
            ]],
            "metadatas": [[
                {"filename": "low.md", "filepath": "low"},
                {"filename": "high.md", "filepath": "high"},
                {"filename": "duplicate.md", "filepath": "high"},
                {"filename": "third.md", "filepath": "third"},
            ]],
        }
        selected = retriever.rerank_results(results, "what body match", reranker)
        context = retriever.build_context(selected)
        self.assertEqual([item["filename"] for item in selected], ["high.md", "third.md", "low.md"])
        self.assertAlmostEqual(selected[0]["final_score"], 0.68)
        self.assertIn("high body match", context)
        self.assertNotIn("title: high", context)
        self.assertNotIn("metadata_score", context)

    def test_empty_retrieval_returns_no_documents(self):
        self.assertEqual(retriever.rerank_results({"documents": [[]], "metadatas": [[]]}, "question", FakeReranker()), [])

    def test_non_reranked_pipeline_keeps_chroma_order_without_scores(self):
        results = {
            "documents": [[
                "---\ntitle: first\n---\nfirst body",
                "---\ntitle: second\n---\nsecond body",
            ]],
            "metadatas": [[
                {"filename": "first.md", "filepath": "first"},
                {"filename": "second.md", "filepath": "second"},
            ]],
        }
        selected = retriever.select_without_reranking(results)
        self.assertEqual([item["filename"] for item in selected], ["first.md", "second.md"])
        self.assertEqual(selected[0]["body"], "first body")
        self.assertNotIn("final_score", selected[0])

    def test_long_body_is_preserved_after_scoring(self):
        body = "one two three four five six seven eight nine ten eleven"
        result = score_document(
            FakeReranker(),
            "question",
            f"---\ntitle: report\n---\n{body}",
        )
        self.assertEqual(result["body"], body)


if __name__ == "__main__":
    unittest.main()
