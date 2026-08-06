"""Recall benchmark for metadata_embeddings with optional cross-encoder re-ranking.

Re-ranking is toggled by the USE_RERANKING key in the project .env file:

    USE_RERANKING=true   # embed → retrieve top-20 → cross-encoder rerank → recall
    USE_RERANKING=false  # embed → retrieve top-20 → recall (no reranking)

The cross-encoder is loaded with plain transformers + torch (no sentence-transformers)
to avoid the Keras 3 compatibility issue that tf-based imports trigger.

FLOW (USE_RERANKING=true):
1. Embed one question with text-embedding-3-small.
2. Retrieve the top 20 candidates from metadata_embeddings.
3. Read each candidate's YAML front matter from disk (same text embedded at
   indexing time) and score (query, passage) pairs with the cross-encoder.
4. Sort candidates by cross-encoder score descending; assign new ranks.
5. Record whether the expected source appears within reranked ranks 3, 5, 7.
6. Write results to a separate CSV after every completed question.

FLOW (USE_RERANKING=false):
Steps 1-2 are identical.  Step 3-4 are skipped.  Recall is evaluated on the
original Chroma retrieval order.

ASSUMPTION: Chroma metadata contains a `filename` and `filepath` for every
indexed Markdown document (written by metadata_embedding_pipeline.py).

Usage
-----
    python metadata_embedding_pipeline/metadata_embedding_reranker_benchmark.py
    python metadata_embedding_pipeline/metadata_embedding_reranker_benchmark.py --limit 2
    python metadata_embedding_pipeline/metadata_embedding_reranker_benchmark.py --start 3 --limit 48
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

# Allow sibling imports when this file is executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metadata_embedding_utils import (
    BENCHMARK_INPUT_CSV,
    COLLECTION_NAME,
    DB_PATH,
    EMBEDDING_MODEL,
    PROJECT_ROOT,
    RERANKER_BENCHMARK_OUTPUT_CSV,
    expected_document_is_in_rank,
    get_metadata_text_for_filepath,
)

RETRIEVAL_TOP_K: int = 20
RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "retrieved_documents_top_20",
    "retrieved_filepaths_top_20",
    "reranked_documents_top_7",
    "reranked_filepaths_top_7",
    "recall@3",
    "recall@5",
    "recall@7",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
    "reranker_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS


# ---------------------------------------------------------------------------
# Lazy global clients (initialised once on first question)
# ---------------------------------------------------------------------------

_openai_client: OpenAI | None = None
_collection = None
_reranker: "CrossEncoderReranker | None" = None


def get_clients():
    """Return (OpenAI client, Chroma collection), initialising on first call.

    Uses an absolute DB_PATH so no os.chdir() is needed.
    """
    global _openai_client, _collection
    if _openai_client is None:
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("ERROR: OPENAI_API_KEY is not set in .env.")
        _openai_client = OpenAI(api_key=api_key)
        chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
        _collection = chroma_client.get_collection(name=COLLECTION_NAME)
    return _openai_client, _collection


def get_reranker() -> "CrossEncoderReranker":
    """Return the shared reranker, loading the cross-encoder model on first call."""
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker


# ---------------------------------------------------------------------------
# Re-ranker
# ---------------------------------------------------------------------------

class CrossEncoderReranker:
    """Lightweight wrapper around sentence_transformers CrossEncoder.

    Scores every (query, passage) pair and returns candidates sorted by
    cross-encoder score descending.  The RERANKER_MODEL constant at the top
    of this module controls which model is loaded; swapping the model requires
    no other code changes.

    Example:
        reranker = CrossEncoderReranker()
        reranked = reranker.rerank("What is the revenue guidance for FY26?", candidates)
        # reranked[0] is the cross-encoder's highest-ranked candidate.
    """

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        # Import only PyTorch parts of transformers to avoid the Keras 3 / TF
        # import chain that sentence_transformers triggers indirectly.
        import torch
        from transformers import (  # type: ignore[import]
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """Score candidates and return them sorted by relevance (highest first).

        Each candidate dict must have a 'filepath' key pointing to the source
        Markdown file relative to PROJECT_ROOT.  The YAML front matter of that
        file is used as the passage text for the cross-encoder — the same text
        that was embedded at indexing time by metadata_embedding_pipeline.py.

        New keys added to each returned dict:
        - 'rank': new 1-based rank after re-ranking.
        - 'reranker_score': raw cross-encoder logit score (higher = more relevant).

        Example:
            candidates = [{"rank": 1, "filename": "group_001.md", "filepath": "data/…"}]
            reranked   = reranker.rerank("revenue guidance?", candidates)
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
        reranked: list[dict] = []
        for new_rank, (doc, score) in enumerate(scored, start=1):
            reranked.append({**doc, "rank": new_rank, "reranker_score": float(score)})
        return reranked


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def read_rows() -> list[dict]:
    """Read the untouched input questions in their existing order.

    Example: a 50-row input file returns a list of 50 dictionaries.
    """
    with BENCHMARK_INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def add_existing_results(rows: list[dict]) -> list[dict]:
    """Retain completed result fields when resuming a partial benchmark run.

    Example: after a two-question trial, running with `--start 3` keeps the
    first two completed rows and fills only rows three onward.
    """
    if not RERANKER_BENCHMARK_OUTPUT_CSV.exists():
        return rows
    with RERANKER_BENCHMARK_OUTPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        existing_rows = {row["id"]: row for row in csv.DictReader(fh)}
    for row in rows:
        existing_row = existing_rows.get(row["id"])
        if existing_row:
            for column in RESULT_COLUMNS:
                row[column] = existing_row.get(column, "")
    return rows


def write_rows(rows: list[dict]) -> None:
    """Save the current benchmark state to the output CSV.

    Example: after question 2 succeeds, this writes its re-ranking results
    while leaving unprocessed rows blank.  Prevents lost progress.
    """
    with RERANKER_BENCHMARK_OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def make_retrieved_document_list(results: dict) -> list[dict]:
    """Convert raw Chroma results to a list of ranked document dicts.

    Example: the first Chroma result produces {"rank": 1, "filename": …, "filepath": …}.
    Mirrors make_retrieved_document_list in metadata_embedding_benchmark.py.
    """
    documents = []
    for rank, metadata in enumerate(results.get("metadatas", [[]])[0], start=1):
        filepath = metadata.get("filepath", metadata.get("filename", ""))
        documents.append(
            {
                "rank": rank,
                "filename": metadata.get("filename", filepath or "unknown"),
                "filepath": filepath,
            }
        )
    return documents


def retrieve_top_k(question: str, timings: dict) -> list[dict]:
    """Embed one question and retrieve RETRIEVAL_TOP_K Chroma candidates.

    Example: one question returns a ranked list of 20 candidate dicts.
    Timings dict is populated with 'embedding' and 'chroma_retrieval' keys.
    """
    openai_client, collection = get_clients()

    embedding_start = time.perf_counter()
    embedding = openai_client.embeddings.create(
        model=EMBEDDING_MODEL, input=[question]
    ).data[0].embedding
    timings["embedding"] = time.perf_counter() - embedding_start

    retrieval_start = time.perf_counter()
    results = collection.query(
        query_embeddings=[embedding],
        n_results=RETRIEVAL_TOP_K,
        include=["metadatas"],
    )
    timings["chroma_retrieval"] = time.perf_counter() - retrieval_start

    return make_retrieved_document_list(results)


# ---------------------------------------------------------------------------
# Per-question processing
# ---------------------------------------------------------------------------

def process_question(row: dict, use_reranking: bool) -> dict:
    """Run one question through retrieval and (optionally) re-ranking.

    When use_reranking is True the cross-encoder re-orders the top-20
    candidates before recall is evaluated.  When False recall is evaluated on
    the original Chroma order and reranker_latency_seconds is recorded as 0.

    Example: a source found at reranked rank 2 gives recall@3=True,
    recall@5=True, recall@7=True.
    """
    question_start = time.perf_counter()
    timings: dict[str, float] = {}

    retrieved_documents = retrieve_top_k(row["query"], timings)

    if use_reranking:
        reranker_start = time.perf_counter()
        final_documents = get_reranker().rerank(row["query"], retrieved_documents)
        timings["reranker"] = time.perf_counter() - reranker_start
    else:
        final_documents = retrieved_documents
        timings["reranker"] = 0.0

    timings["total"] = time.perf_counter() - question_start

    top7 = final_documents[:7]

    return {
        "retrieved_documents_top_20": " | ".join(
            f"#{doc['rank']} {doc['filename']}" for doc in retrieved_documents
        ),
        "retrieved_filepaths_top_20": " | ".join(
            doc["filepath"] for doc in retrieved_documents
        ),
        "reranked_documents_top_7": " | ".join(
            f"#{doc['rank']} {doc['filename']}" for doc in top7
        ) if use_reranking else "",
        "reranked_filepaths_top_7": " | ".join(
            doc["filepath"] for doc in top7
        ) if use_reranking else "",
        "recall@3": str(
            expected_document_is_in_rank(row["source_document"], final_documents, 3)
        ),
        "recall@5": str(
            expected_document_is_in_rank(row["source_document"], final_documents, 5)
        ),
        "recall@7": str(
            expected_document_is_in_rank(row["source_document"], final_documents, 7)
        ),
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "reranker_latency_seconds": f"{timings['reranker']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_arguments() -> argparse.Namespace:
    """Parse optional question-range arguments.

    Example: `--limit 2` processes only questions one and two.
    """
    parser = argparse.ArgumentParser(
        description=(
            f"Recall benchmark for '{COLLECTION_NAME}' "
            f"with cross-encoder re-ranking ({RERANKER_MODEL})."
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
    arguments = parser.parse_args()
    if arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    if arguments.start < 1:
        parser.error("--start must be at least 1.")
    return arguments


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the requested benchmark questions and save after each one.

    Reads USE_RERANKING from the project .env file to decide whether to apply
    cross-encoder re-ranking after the initial Chroma retrieval.

    Example: running with --limit 2 writes two completed recall rows to the
    output CSV and prints a summary for those two questions.
    """
    arguments = read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Load .env early so USE_RERANKING is available before any question runs.
    load_dotenv(PROJECT_ROOT / ".env")
    use_reranking = os.getenv("USE_RERANKING", "true").strip().lower() in (
        "1", "true", "yes"
    )

    print(f"Collection      : {COLLECTION_NAME}")
    print(f"DB path         : {DB_PATH}")
    print(f"Use reranking   : {use_reranking}")
    if use_reranking:
        print(f"Reranker model  : {RERANKER_MODEL}")
    print(f"Retrieval top-K : {RETRIEVAL_TOP_K}")
    print(f"Output          : {RERANKER_BENCHMARK_OUTPUT_CSV.relative_to(PROJECT_ROOT)}")
    print()

    if use_reranking:
        print("Loading cross-encoder model…")
        get_reranker()  # warm up so model load cost is not charged to question 1
        print("Cross-encoder ready.\n")

    rows = add_existing_results(read_rows())
    if len(rows) != 50:
        raise ValueError(f"Expected 50 input questions, found {len(rows)}.")

    start_index = arguments.start - 1
    end_index = start_index + arguments.limit
    if start_index >= len(rows):
        raise ValueError(f"--start cannot exceed the {len(rows)} input questions.")
    if end_index > len(rows):
        raise ValueError("--start and --limit extend beyond the input questions.")

    for index, row in enumerate(rows[start_index:end_index], start=arguments.start):
        print(f"[{index}/{len(rows)}] {row['query']}")
        try:
            row.update(process_question(row, use_reranking))
            print(
                f"  status=Success  recall@3={row['recall@3']}  "
                f"recall@5={row['recall@5']}  recall@7={row['recall@7']}  "
                f"latency={row['overall_latency_seconds']}s"
            )
        except Exception as error:
            row["pipeline_status"] = "Error"
            row["pipeline_error"] = str(error)
            print(f"  status=Error  error={error}")
        write_rows(rows)

    finished = [r for r in rows if r.get("pipeline_status") == "Success"]
    if finished:
        r3 = sum(1 for r in finished if r.get("recall@3") == "True")
        r5 = sum(1 for r in finished if r.get("recall@5") == "True")
        r7 = sum(1 for r in finished if r.get("recall@7") == "True")
        n = len(finished)
        avg_lat = sum(float(r["overall_latency_seconds"]) for r in finished) / n
        print()
        print("=== Benchmark Summary ===")
        print(f"Questions completed    : {n}")
        print(f"Recall@3               : {r3}/{n} — {r3/n:.0%}")
        print(f"Recall@5               : {r5}/{n} — {r5/n:.0%}")
        print(f"Recall@7               : {r7}/{n} — {r7/n:.0%}")
        print(f"Avg total latency      : {avg_lat:.3f} s/question")
        if use_reranking:
            avg_reranker = (
                sum(float(r.get("reranker_latency_seconds", 0)) for r in finished) / n
            )
            print(f"Avg reranker latency   : {avg_reranker:.3f} s/question")

    print(f"\nWrote results to {RERANKER_BENCHMARK_OUTPUT_CSV.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
