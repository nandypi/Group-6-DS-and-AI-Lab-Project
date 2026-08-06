"""Recall benchmark for the metadata_embeddings Chroma collection.

Measures retrieval recall using the same 50-question test CSV, the same
Recall@3 / @5 / @7 methodology, and the same top-10 retrieval window as
run_without_reranking_benchmark.py.  The only variable is the Chroma
collection being queried: metadata_embeddings instead of finance_file_embeddings.

No reranking is performed.  No LLM answers are generated.  Only retrieval
recall is evaluated, which allows a fair comparison of embedding quality.

FLOW:
1. Embed one question with text-embedding-3-small.
2. Retrieve the top 10 candidates from metadata_embeddings.
3. Record whether the expected source document appears within ranks 3, 5, 7.
4. Write results to a separate CSV after every completed question.

EXAMPLE: if an expected source appears at rank 4, the output records
recall@3=False, recall@5=True, and recall@7=True.

ASSUMPTION: Chroma metadata contains a `filename` and `filepath` for every
indexed Markdown document (written by metadata_embedding_pipeline.py).

Usage
-----
    python metadata_embedding_pipeline/metadata_embedding_benchmark.py
    python metadata_embedding_pipeline/metadata_embedding_benchmark.py --limit 2
    python metadata_embedding_pipeline/metadata_embedding_benchmark.py --start 3 --limit 48
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
    BENCHMARK_OUTPUT_CSV,
    COLLECTION_NAME,
    DB_PATH,
    EMBEDDING_MODEL,
    PROJECT_ROOT,
    expected_document_is_in_rank,
    normalize_filename,
)

RETRIEVAL_TOP_K: int = 10

SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "retrieved_documents_top_10",
    "retrieved_filepaths_top_10",
    "recall@3",
    "recall@5",
    "recall@7",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
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
    """Keep completed result fields when a later run processes remaining rows.

    Example: after a two-question trial, running with `--start 3` retains the
    first two completed rows and fills only rows three onward.
    """
    if not BENCHMARK_OUTPUT_CSV.exists():
        return rows

    with BENCHMARK_OUTPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        existing_rows = {row["id"]: row for row in csv.DictReader(fh)}

    for row in rows:
        existing_row = existing_rows.get(row["id"])
        if existing_row:
            for column in RESULT_COLUMNS:
                row[column] = existing_row.get(column, "")

    return rows


def write_rows(rows: list[dict]) -> None:
    """Save the current benchmark state to the output CSV.

    Example: after question 2 succeeds, this writes its retrieval results
    while leaving unprocessed rows blank.  Prevents lost progress.
    """
    with BENCHMARK_OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def make_retrieved_document_list(results: dict) -> list[dict]:
    """Keep Chroma's original rank, filename, and filepath for all results.

    Example: the first Chroma result produces a dictionary with rank=1.
    Mirrors make_retrieved_document_list in run_without_reranking_benchmark.py.
    """
    documents = []
    for rank, metadata in enumerate(
        results.get("metadatas", [[]])[0], start=1
    ):
        filepath = metadata.get("filepath", metadata.get("filename", ""))
        documents.append(
            {
                "rank": rank,
                "filename": metadata.get("filename", filepath or "unknown"),
                "filepath": filepath,
            }
        )
    return documents


def retrieve_top_k(question: str, timings: dict) -> dict:
    """Embed one question and retrieve RETRIEVAL_TOP_K candidates.

    Example: one question returns Chroma ranks 1 through 10.  Timings dict
    is populated with 'embedding' and 'chroma_retrieval' keys in seconds.
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

    return results


# ---------------------------------------------------------------------------
# Per-question processing
# ---------------------------------------------------------------------------

def process_question(row: dict) -> dict:
    """Run one question through metadata-only retrieval and compute recall.

    Example: a source found at rank two gives all three recall columns a
    True value.  No LLM call is made – only retrieval recall is measured.
    """
    question_start = time.perf_counter()
    timings: dict[str, float] = {}

    results = retrieve_top_k(row["query"], timings)
    retrieved_documents = make_retrieved_document_list(results)
    timings["total"] = time.perf_counter() - question_start

    return {
        "retrieved_documents_top_10": " | ".join(
            f"#{doc['rank']} {doc['filename']}" for doc in retrieved_documents
        ),
        "retrieved_filepaths_top_10": " | ".join(
            doc["filepath"] for doc in retrieved_documents
        ),
        "recall@3": str(
            expected_document_is_in_rank(
                row["source_document"], retrieved_documents, 3
            )
        ),
        "recall@5": str(
            expected_document_is_in_rank(
                row["source_document"], retrieved_documents, 5
            )
        ),
        "recall@7": str(
            expected_document_is_in_rank(
                row["source_document"], retrieved_documents, 7
            )
        ),
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_arguments() -> argparse.Namespace:
    """Read the optional question-range arguments.

    Example: `--limit 2` processes only questions one and two, while the
    default processes all 50 questions.
    """
    parser = argparse.ArgumentParser(
        description=(
            f"Recall benchmark for the '{COLLECTION_NAME}' Chroma collection."
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
    """Run the requested number of benchmark questions and save after each one.

    Example: running with --limit 2 writes two completed recall rows to the
    output CSV at data/infosys_rag_test_dataset_50_queries_metadata_embeddings_results.csv.
    """
    arguments = read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print(f"Collection : {COLLECTION_NAME}")
    print(f"DB path    : {DB_PATH}")
    print(f"Output     : {BENCHMARK_OUTPUT_CSV.relative_to(PROJECT_ROOT)}")
    print()

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
            row.update(process_question(row))
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

    # Print summary over all completed rows in the output file.
    finished = [r for r in rows if r.get("pipeline_status") == "Success"]
    if finished:
        r3 = sum(1 for r in finished if r.get("recall@3") == "True")
        r5 = sum(1 for r in finished if r.get("recall@5") == "True")
        r7 = sum(1 for r in finished if r.get("recall@7") == "True")
        n = len(finished)
        avg_lat = (
            sum(float(r["overall_latency_seconds"]) for r in finished) / n
        )
        print()
        print("=== Benchmark Summary ===")
        print(f"Questions completed : {n}")
        print(f"Recall@3            : {r3}/{n} — {r3/n:.0%}")
        print(f"Recall@5            : {r5}/{n} — {r5/n:.0%}")
        print(f"Recall@7            : {r7}/{n} — {r7/n:.0%}")
        print(f"Avg latency         : {avg_lat:.3f} s/question")

    print(f"\nWrote results to {BENCHMARK_OUTPUT_CSV.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
