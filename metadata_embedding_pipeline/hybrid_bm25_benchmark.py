"""Hybrid BM25 + Vector recall benchmark (Reciprocal Rank Fusion).

Compares three retrieval strategies on the same 50-question benchmark dataset:
  1. Vector-only  : semantic search (text-embedding-3-small → Chroma top-20)
  2. BM25-only    : keyword search  (BM25Okapi over YAML front-matter texts, top-20)
  3. Hybrid (RRF) : Reciprocal Rank Fusion of the two ranked lists (k=60)

All three recall figures (Recall@3 / @5 / @7) are written to the output CSV
for direct side-by-side comparison.  An optional cross-encoder reranker
(USE_RERANKING=true in .env) is applied to the hybrid-fused list before the
hybrid recall figures are evaluated.

The BM25 corpus is the same YAML front-matter text that was embedded at
indexing time by metadata_embedding_pipeline.py, obtained here via
get_metadata_text_for_filepath() which reads each v2 file from disk.

Requires:
    pip install rank-bm25

FLOW (USE_RERANKING=true):
1. Build BM25 index: for every document in the Chroma collection, read its
   YAML front-matter text (via get_metadata_text_for_filepath) and tokenise.
2. For each question:
   a. Embed with text-embedding-3-small → vector top-20 from Chroma.
   b. Tokenise query → BM25 top-20 from BM25 index.
   c. Reciprocal Rank Fusion (k=60): score = Σ 1 / (60 + rank_i).
   d. Apply cross-encoder to fused top-20; evaluate hybrid recall on result.
   e. Write vector-only, BM25-only, and hybrid recall figures to output CSV.

FLOW (USE_RERANKING=false):
Steps 1–2c identical.  Step 2d skipped.  Hybrid recall evaluated on raw RRF order.

Output CSV columns
------------------
id, query, source_category, source_document (from input)
recall@3_vector / @5 / @7
recall@3_bm25   / @5 / @7
recall@3_hybrid / @5 / @7
vector_filepaths_top_20, bm25_filepaths_top_20, hybrid_filepaths_top_20
final_filepaths_top_7  (after optional reranking)
embedding_latency_seconds, bm25_latency_seconds, rrf_latency_seconds
reranker_latency_seconds, overall_latency_seconds
pipeline_status, pipeline_error

Usage
-----
    python metadata_embedding_pipeline/hybrid_bm25_benchmark.py
    python metadata_embedding_pipeline/hybrid_bm25_benchmark.py --limit 5
    python metadata_embedding_pipeline/hybrid_bm25_benchmark.py --start 3 --limit 48
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover
    raise SystemExit(
        "rank-bm25 is not installed.  Run:\n"
        "    pip install rank-bm25"
    )

# Allow sibling imports when executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metadata_embedding_utils import (
    BENCHMARK_INPUT_CSV,
    COLLECTION_NAME,
    DB_PATH,
    EMBEDDING_MODEL,
    PROJECT_ROOT,
    expected_document_is_in_rank,
    get_metadata_text_for_filepath,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RETRIEVAL_TOP_K: int = 20   # candidates fetched from both vector and BM25
RRF_K: int = 60             # RRF constant (Cormack & Clarke, 2009)
RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

HYBRID_OUTPUT_CSV: Path = (
    PROJECT_ROOT
    / "data"
    / "infosys_rag_test_dataset_50_queries_v2_hybrid_bm25_results.csv"
)

SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "recall@3_vector",
    "recall@5_vector",
    "recall@7_vector",
    "recall@3_bm25",
    "recall@5_bm25",
    "recall@7_bm25",
    "recall@3_hybrid",
    "recall@5_hybrid",
    "recall@7_hybrid",
    "vector_filepaths_top_20",
    "bm25_filepaths_top_20",
    "hybrid_filepaths_top_20",
    "final_filepaths_top_7",
    "embedding_latency_seconds",
    "bm25_latency_seconds",
    "rrf_latency_seconds",
    "reranker_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------

class BM25Index:
    """BM25Okapi index built over the YAML front-matter corpus from Chroma.

    Every document registered in the Chroma collection is retrieved, its YAML
    front-matter text is read from disk via get_metadata_text_for_filepath(),
    and the text is tokenised (lowercase alphanumeric tokens) before being
    handed to BM25Okapi.

    This mirrors exactly what was embedded at indexing time so the BM25
    vocabulary matches the semantic search corpus.

    Example:
        index = BM25Index(collection)
        hits  = index.search("operating margin Q3 FY26", top_k=20)
        # hits → [{"rank": 1, "filename": ..., "filepath": ..., "bm25_score": 4.2}, ...]
    """

    _TOKEN_RE = re.compile(r"[a-z0-9]+")

    def __init__(self, collection) -> None:
        print("Building BM25 index from Chroma corpus…")
        t0 = time.perf_counter()

        # Retrieve filepath metadata for every document in the collection.
        result = collection.get(include=["metadatas"])
        self._meta: list[dict] = result.get("metadatas", [])

        # Read each file and extract YAML front-matter text (same text embedded).
        corpus_texts: list[str] = [
            get_metadata_text_for_filepath(m.get("filepath", ""))
            for m in self._meta
        ]
        tokenized_corpus = [self._tokenize(text) for text in corpus_texts]
        self._bm25 = BM25Okapi(tokenized_corpus)

        elapsed = time.perf_counter() - t0
        print(f"BM25 index ready  ({len(self._meta)} documents, {elapsed:.1f}s)")

    def _tokenize(self, text: str) -> list[str]:
        """Lowercase alphanumeric tokenisation — no stemming, no stopwords."""
        return self._TOKEN_RE.findall(text.lower())

    def search(self, query: str, top_k: int = RETRIEVAL_TOP_K) -> list[dict]:
        """Return top_k documents ranked by BM25Okapi score, highest first.

        Example:
            hits = index.search("large deal TCV Q3 FY26", top_k=20)
        """
        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)  # ndarray, length = corpus size
        ranked_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]
        results: list[dict] = []
        for rank, idx in enumerate(ranked_indices, start=1):
            meta = self._meta[idx]
            fp = meta.get("filepath", meta.get("filename", ""))
            results.append(
                {
                    "rank": rank,
                    "filename": meta.get("filename", fp or "unknown"),
                    "filepath": fp,
                    "bm25_score": float(scores[idx]),
                }
            )
        return results


# ---------------------------------------------------------------------------
# Cross-encoder reranker
# ---------------------------------------------------------------------------

class CrossEncoderReranker:
    """Thin wrapper around a HuggingFace cross-encoder for passage reranking.

    Loads the cross-encoder lazily on first instantiation.  Uses the same
    plain transformers + torch approach as metadata_embedding_reranker_benchmark.py
    to avoid the Keras 3 / TF compatibility issue.

    Example:
        reranker = CrossEncoderReranker()
        reranked = reranker.rerank("What is the revenue for Q4 FY26?", candidates)
        # reranked[0] is the highest-scoring candidate.
    """

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """Score (query, passage) pairs and return candidates sorted by score.

        Passage text for each candidate is its YAML front-matter, read from
        disk by get_metadata_text_for_filepath — identical to the passage used
        at BM25 / embedding time.

        New keys added to each returned dict:
            rank           : new 1-based rank after re-ranking.
            reranker_score : raw cross-encoder logit (higher = more relevant).

        Example:
            reranked = reranker.rerank("voluntary attrition Q1 FY26", docs)
        """
        passages = [
            get_metadata_text_for_filepath(c["filepath"]) for c in candidates
        ]
        pairs = [[query, passage] for passage in passages]
        features = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512,
        )
        with self._torch.no_grad():
            logits = self.model(**features).logits.squeeze(-1)
        scores: list[float] = (
            logits.tolist() if logits.dim() > 0 else [logits.item()]
        )
        scored = sorted(
            zip(candidates, scores), key=lambda x: float(x[1]), reverse=True
        )
        return [
            {**doc, "rank": new_rank, "reranker_score": float(sc)}
            for new_rank, (doc, sc) in enumerate(scored, start=1)
        ]


# ---------------------------------------------------------------------------
# Lazy global singletons
# ---------------------------------------------------------------------------

_openai_client: OpenAI | None = None
_collection = None
_bm25_index: BM25Index | None = None
_reranker: CrossEncoderReranker | None = None


def get_clients() -> tuple[OpenAI, object, BM25Index]:
    """Return (OpenAI client, Chroma collection, BM25Index), initialising once.

    The BM25 index is built on first call (~2-5 s for 1,875 documents).
    """
    global _openai_client, _collection, _bm25_index
    if _openai_client is None:
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in .env.")
        _openai_client = OpenAI(api_key=api_key)
        chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
        _collection = chroma_client.get_collection(name=COLLECTION_NAME)
        _bm25_index = BM25Index(_collection)
    return _openai_client, _collection, _bm25_index


def get_reranker() -> CrossEncoderReranker:
    """Return the cross-encoder reranker, loading the model on first call."""
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker


# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------

def rrf_fuse(
    vector_ranking: list[dict],
    bm25_ranking: list[dict],
    k: int = RRF_K,
) -> list[dict]:
    """Merge two ranked lists using Reciprocal Rank Fusion (RRF).

    Each document accumulates  score += 1 / (k + rank)  from every ranked
    list it appears in (rank is 1-based).  Documents absent from a list
    contribute nothing.  The fused list is sorted by total RRF score descending.

    Args:
        vector_ranking : Ranked list of dicts, each with a 'filepath' key.
        bm25_ranking   : Ranked list of dicts, each with a 'filepath' key.
        k              : RRF constant (default 60, per Cormack & Clarke 2009).

    Returns:
        Merged list sorted by rrf_score desc.  Each entry includes the union
        of keys from both source dicts plus 'rrf_score', 'vector_rank',
        'bm25_rank', and an updated 'rank' (1-based position in fused list).

    Example:
        fused = rrf_fuse(vector_hits, bm25_hits)
        fused[0]["rrf_score"]   # highest combined RRF score
        fused[0]["vector_rank"] # position in the original vector list (or None)
        fused[0]["bm25_rank"]   # position in the original BM25 list (or None)
    """

    def _fp_key(doc: dict) -> str:
        return doc.get("filepath") or doc.get("filename", "")

    all_docs: dict[str, dict] = {}

    for rank, doc in enumerate(vector_ranking, start=1):
        key = _fp_key(doc)
        entry = all_docs.setdefault(
            key,
            {**doc, "vector_rank": None, "bm25_rank": None, "rrf_score": 0.0},
        )
        entry["vector_rank"] = rank
        entry["rrf_score"] += 1.0 / (k + rank)

    for rank, doc in enumerate(bm25_ranking, start=1):
        key = _fp_key(doc)
        entry = all_docs.setdefault(
            key,
            {**doc, "vector_rank": None, "bm25_rank": None, "rrf_score": 0.0},
        )
        entry["bm25_rank"] = rank
        entry["rrf_score"] += 1.0 / (k + rank)

    fused = sorted(all_docs.values(), key=lambda d: d["rrf_score"], reverse=True)
    for new_rank, doc in enumerate(fused, start=1):
        doc["rank"] = new_rank
    return fused


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def read_rows() -> list[dict]:
    """Read the 50-question input CSV in its original order."""
    with BENCHMARK_INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def add_existing_results(rows: list[dict]) -> list[dict]:
    """Retain completed rows when resuming a partial benchmark run.

    Example: after running --limit 5, re-running with --start 6 keeps the
    first five completed rows and fills only rows six onward.
    """
    if not HYBRID_OUTPUT_CSV.exists():
        return rows
    with HYBRID_OUTPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        existing_rows = {row["id"]: row for row in csv.DictReader(fh)}
    for row in rows:
        existing_row = existing_rows.get(row["id"])
        if existing_row:
            for column in RESULT_COLUMNS:
                row[column] = existing_row.get(column, "")
    return rows


def write_rows(rows: list[dict]) -> None:
    """Save the current benchmark state to the output CSV after every question."""
    with HYBRID_OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Per-question processing
# ---------------------------------------------------------------------------

def process_question(row: dict, use_reranking: bool) -> dict:
    """Run one question through all three retrieval strategies and record recall.

    Steps:
    1. Embed query → Chroma vector top-20 (vector_docs).
    2. Tokenise query → BM25 top-20 (bm25_docs).
    3. RRF fuse → hybrid_docs (sorted by RRF score).
    4. Optionally rerank hybrid top-20 → final_docs.
    5. Evaluate Recall@3/5/7 independently for vector_docs, bm25_docs,
       and final_docs (hybrid recall).

    Args:
        row          : One input CSV row with 'query' and 'source_document'.
        use_reranking: Whether to apply cross-encoder reranking to hybrid list.

    Returns:
        Dict of RESULT_COLUMNS values for this question.

    Example:
        result = process_question(row, use_reranking=True)
        result["recall@5_hybrid"]  # → "True" or "False"
    """
    question_start = time.perf_counter()
    timings: dict[str, float] = {}
    openai_client, collection, bm25_index = get_clients()
    query = row["query"]

    # 1. Embed + vector search
    embed_start = time.perf_counter()
    embedding = openai_client.embeddings.create(
        model=EMBEDDING_MODEL, input=[query]
    ).data[0].embedding
    timings["embedding"] = time.perf_counter() - embed_start

    chroma_start = time.perf_counter()
    chroma_result = collection.query(
        query_embeddings=[embedding],
        n_results=RETRIEVAL_TOP_K,
        include=["metadatas"],
    )
    timings["chroma"] = time.perf_counter() - chroma_start

    vector_docs: list[dict] = []
    for rank, meta in enumerate(
        chroma_result.get("metadatas", [[]])[0], start=1
    ):
        fp = meta.get("filepath", meta.get("filename", ""))
        vector_docs.append(
            {
                "rank": rank,
                "filename": meta.get("filename", fp or "unknown"),
                "filepath": fp,
            }
        )

    # 2. BM25 search
    bm25_start = time.perf_counter()
    bm25_docs = bm25_index.search(query, top_k=RETRIEVAL_TOP_K)
    timings["bm25"] = time.perf_counter() - bm25_start

    # 3. RRF fusion
    rrf_start = time.perf_counter()
    hybrid_docs = rrf_fuse(vector_docs, bm25_docs)
    timings["rrf"] = time.perf_counter() - rrf_start

    # 4. Optional cross-encoder reranking of hybrid top-20
    rerank_start = time.perf_counter()
    if use_reranking:
        final_docs = get_reranker().rerank(query, hybrid_docs[:RETRIEVAL_TOP_K])
    else:
        final_docs = hybrid_docs
    timings["reranker"] = time.perf_counter() - rerank_start

    timings["total"] = time.perf_counter() - question_start

    def _paths(docs: list[dict], n: int = RETRIEVAL_TOP_K) -> str:
        return " | ".join(d["filepath"] for d in docs[:n])

    src = row["source_document"]
    return {
        "recall@3_vector":  str(expected_document_is_in_rank(src, vector_docs, 3)),
        "recall@5_vector":  str(expected_document_is_in_rank(src, vector_docs, 5)),
        "recall@7_vector":  str(expected_document_is_in_rank(src, vector_docs, 7)),
        "recall@3_bm25":    str(expected_document_is_in_rank(src, bm25_docs, 3)),
        "recall@5_bm25":    str(expected_document_is_in_rank(src, bm25_docs, 5)),
        "recall@7_bm25":    str(expected_document_is_in_rank(src, bm25_docs, 7)),
        "recall@3_hybrid":  str(expected_document_is_in_rank(src, final_docs, 3)),
        "recall@5_hybrid":  str(expected_document_is_in_rank(src, final_docs, 5)),
        "recall@7_hybrid":  str(expected_document_is_in_rank(src, final_docs, 7)),
        "vector_filepaths_top_20":  _paths(vector_docs),
        "bm25_filepaths_top_20":    _paths(bm25_docs),
        "hybrid_filepaths_top_20":  _paths(hybrid_docs),
        "final_filepaths_top_7":    _paths(final_docs, 7),
        "embedding_latency_seconds":  f"{timings['embedding']:.3f}",
        "bm25_latency_seconds":       f"{timings['bm25']:.3f}",
        "rrf_latency_seconds":        f"{timings['rrf']:.3f}",
        "reranker_latency_seconds":   f"{timings['reranker']:.3f}",
        "overall_latency_seconds":    f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error":  "",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_arguments() -> argparse.Namespace:
    """Parse optional question-range arguments.

    Example: ``--start 6 --limit 5`` processes questions 6 through 10.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Hybrid BM25 + Vector recall benchmark with Reciprocal Rank Fusion."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of leading questions to process (default: 50).",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="One-based question number to begin processing (default: 1).",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1.")
    if args.start < 1:
        parser.error("--start must be at least 1.")
    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the hybrid benchmark and print a three-way recall comparison table.

    The summary table shows Recall@3 / @5 / @7 for all three strategies so
    the contribution of BM25 and the effect of RRF fusion are immediately
    visible.  Illustrative example:

        === Benchmark Summary (50 questions) ===
        Strategy               Recall@3    Recall@5    Recall@7
        --------------------------------------------------------
        Vector-only          35/50  70%   39/50  78%   42/50  84%
        BM25-only            26/50  52%   31/50  62%   35/50  70%
        Hybrid (RRF)         38/50  76%   42/50  84%   45/50  90%

    Results are written to:
        data/infosys_rag_test_dataset_50_queries_v2_hybrid_bm25_results.csv

    Progress is saved after every question so the run can be resumed with
    ``--start N`` if interrupted.
    """
    args = read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    load_dotenv(PROJECT_ROOT / ".env")
    use_reranking = os.getenv("USE_RERANKING", "true").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    print(f"Collection      : {COLLECTION_NAME}")
    print(f"DB path         : {DB_PATH}")
    print(f"Use reranking   : {use_reranking}")
    if use_reranking:
        print(f"Reranker model  : {RERANKER_MODEL}")
    print(f"Retrieval top-K : {RETRIEVAL_TOP_K} (vector and BM25 each)")
    print(f"RRF k           : {RRF_K}")
    print(f"Output          : {HYBRID_OUTPUT_CSV.relative_to(PROJECT_ROOT)}")
    print()

    # Warm up: build BM25 index + optionally load cross-encoder before Q1.
    get_clients()
    if use_reranking:
        print("Loading cross-encoder model…")
        get_reranker()
        print("Cross-encoder ready.\n")

    rows = add_existing_results(read_rows())
    if len(rows) != 50:
        raise ValueError(f"Expected 50 input questions, found {len(rows)}.")

    start_index = args.start - 1
    end_index = start_index + args.limit
    if start_index >= len(rows):
        raise ValueError(f"--start cannot exceed the {len(rows)} input questions.")
    if end_index > len(rows):
        raise ValueError("--start and --limit extend beyond the input questions.")

    for index, row in enumerate(rows[start_index:end_index], start=args.start):
        if row.get("pipeline_status") == "Success":
            print(f"[{index}/{len(rows)}] (cached)  {row['query']}")
            continue
        print(f"[{index}/{len(rows)}] {row['query']}")
        try:
            row.update(process_question(row, use_reranking))
            print(
                f"  status=Success"
                f"  vec@3={row['recall@3_vector']}"
                f"  bm25@3={row['recall@3_bm25']}"
                f"  hybrid@3={row['recall@3_hybrid']}"
                f"  latency={row['overall_latency_seconds']}s"
            )
        except Exception as error:
            row["pipeline_status"] = "Error"
            row["pipeline_error"] = str(error)
            print(f"  status=Error  error={error}")
        write_rows(rows)

    # Three-way summary table
    finished = [r for r in rows if r.get("pipeline_status") == "Success"]
    if finished:
        n = len(finished)

        def _count(col: str) -> int:
            return sum(1 for r in finished if r.get(col) == "True")

        v3, v5, v7 = _count("recall@3_vector"), _count("recall@5_vector"), _count("recall@7_vector")
        b3, b5, b7 = _count("recall@3_bm25"),   _count("recall@5_bm25"),   _count("recall@7_bm25")
        h3, h5, h7 = _count("recall@3_hybrid"),  _count("recall@5_hybrid"),  _count("recall@7_hybrid")
        avg_lat = sum(float(r["overall_latency_seconds"]) for r in finished) / n

        print()
        print(f"=== Benchmark Summary ({n} questions) ===")
        print(f"{'Strategy':<22} {'Recall@3':>12} {'Recall@5':>12} {'Recall@7':>12}")
        print("-" * 60)
        print(
            f"{'Vector-only':<22}"
            f" {v3:>4}/{n} {v3/n:>4.0%}"
            f" {v5:>4}/{n} {v5/n:>4.0%}"
            f" {v7:>4}/{n} {v7/n:>4.0%}"
        )
        print(
            f"{'BM25-only':<22}"
            f" {b3:>4}/{n} {b3/n:>4.0%}"
            f" {b5:>4}/{n} {b5/n:>4.0%}"
            f" {b7:>4}/{n} {b7/n:>4.0%}"
        )
        print(
            f"{'Hybrid (RRF)':<22}"
            f" {h3:>4}/{n} {h3/n:>4.0%}"
            f" {h5:>4}/{n} {h5/n:>4.0%}"
            f" {h7:>4}/{n} {h7/n:>4.0%}"
        )
        print(f"\nAvg latency per question : {avg_lat:.3f} s")

    print(f"\nWrote results to {HYBRID_OUTPUT_CSV.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
