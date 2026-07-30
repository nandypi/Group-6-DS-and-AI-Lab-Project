"""Measure BGE reranking retrieval recall without calling the answer LLM.

FLOW:
1. Confirm that DO_RERANKING is True.
2. Read the untouched 50-question input CSV.
3. Embed one question and retrieve 25 Chroma candidates.
4. Use BGE to rerank the 25 candidates and keep their reranked order.
5. Record whether the expected source occurs within reranked ranks 3, 5, and 7.
6. Save the separate result CSV after every completed question.

EXAMPLE: if the expected source moves from Chroma rank 8 to BGE rank 2, the
output records recall@3=True, recall@5=True, and recall@7=True. No answer LLM
is called in this flow.

TERM: `reranked rank` means a candidate's position after BGE scores the 25
documents retrieved by Chroma.

ASSUMPTION: Chroma metadata contains `filename` and `filepath` for every
indexed document. The expected source is a unique filename in the input CSV.
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EMBEDDINGS_SCRIPT = PROJECT_ROOT / "embeddings_script"
INPUT_FILE = PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries.csv"
OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "infosys_rag_test_dataset_50_queries_with_reranking_top_25_recall_results.csv"
)
SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "reranked_documents_top_25",
    "reranked_filepaths_top_25",
    "recall@3",
    "recall@5",
    "recall@7",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
    "reranking_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS

sys.path.insert(0, str(EMBEDDINGS_SCRIPT))
import retriever


def read_rows():
    """Read the original question rows without modifying the input CSV.

    Example: a valid input file returns 50 question dictionaries before BGE is
    loaded or Chroma is queried.
    """
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def add_existing_results(rows):
    """Keep completed rows when a partial run is continued later.

    Example: a run with `--limit 2` can later continue at `--start 3` without
    replacing the result fields for questions one and two.
    """
    if not OUTPUT_FILE.exists():
        return rows

    with OUTPUT_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        existing_rows = {row["id"]: row for row in csv.DictReader(source)}

    for row in rows:
        existing_row = existing_rows.get(row["id"])
        if existing_row:
            for column in RESULT_COLUMNS:
                row[column] = existing_row.get(column, "")

    return rows


def write_rows(rows):
    """Save all current result rows to the separate reranking CSV.

    Example: after question two finishes, its reranked paths and recall flags
    are saved even if a later question fails.
    """
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_filename(filename):
    """Return a normalized filename used for the expected-source comparison.

    Example: `Report-1.md` and `report_1.md` both become `report1md`.
    """
    return re.sub(r"[^a-z0-9]+", "", Path(filename).name.lower())


def expected_document_is_in_rank(expected_document, ranked_documents, rank_limit):
    """Return True if an expected source occurs in the first ranked documents.

    Example: a source at reranked rank four returns False for three and True
    for five. This supplies one per-question recall-at-k value.
    """
    expected_name = normalize_filename(expected_document)
    for document in ranked_documents[:rank_limit]:
        if normalize_filename(document["filename"]) == expected_name:
            return True
    return False


def process_question(row, reranker):
    """Retrieve and rerank one question without building an LLM prompt.

    Example: a question produces 25 reranked paths and three recall flags.
    This function never calls `build_context` or `ask_llm`.
    """
    question_start = time.perf_counter()
    timings = {}
    results = retriever.retrieve(row["query"], timings)

    reranking_start = time.perf_counter()
    ranked_documents = retriever.rerank_results(
        results,
        row["query"],
        reranker,
        document_count=25,
    )
    timings["reranking"] = time.perf_counter() - reranking_start
    timings["total"] = time.perf_counter() - question_start

    if not ranked_documents:
        raise ValueError("No documents were retrieved after reranking.")

    return {
        "reranked_documents_top_25": " | ".join(
            f"#{rank} {document['filename']} (score={document['final_score']:.4f})"
            for rank, document in enumerate(ranked_documents, start=1)
        ),
        "reranked_filepaths_top_25": " | ".join(
            document["filepath"] for document in ranked_documents
        ),
        "recall@3": str(
            expected_document_is_in_rank(row["source_document"], ranked_documents, 3)
        ),
        "recall@5": str(
            expected_document_is_in_rank(row["source_document"], ranked_documents, 5)
        ),
        "recall@7": str(
            expected_document_is_in_rank(row["source_document"], ranked_documents, 7)
        ),
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "reranking_latency_seconds": f"{timings['reranking']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def read_arguments():
    """Read the one-based start and number of questions to process.

    Example: `--start 3 --limit 48` processes the remaining questions after a
    two-question trial. The default processes all 50 questions.
    """
    parser = argparse.ArgumentParser(description="Run the BGE recall benchmark.")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=50)
    arguments = parser.parse_args()
    if arguments.start < 1:
        parser.error("--start must be at least 1.")
    if arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


def main():
    """Run the requested recall-only reranking rows and persist each result.

    Example: `python run_reranking_recall_benchmark.py --limit 2` runs BGE for
    two questions and makes zero calls to the answer LLM.
    """
    arguments = read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not retriever.DO_RERANKING:
        raise RuntimeError(
            "Refusing to run: set DO_RERANKING=True in .env before this benchmark."
        )

    os.chdir(EMBEDDINGS_SCRIPT)
    rows = add_existing_results(read_rows())
    if len(rows) != 50:
        raise ValueError(f"Expected 50 input questions, found {len(rows)}.")

    start_index = arguments.start - 1
    end_index = start_index + arguments.limit
    if start_index >= len(rows):
        raise ValueError(f"--start cannot exceed the {len(rows)} input questions.")
    if end_index > len(rows):
        raise ValueError("--start and --limit extend beyond the input questions.")

    reranker = retriever.BGEReranker(
        model_name=os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
        max_tokens=int(os.getenv("RERANKER_MAX_TOKENS", "8190")),
    )

    for index, row in enumerate(rows[start_index:end_index], start=arguments.start):
        print(f"[{index}/{len(rows)}] {row['query']}")
        try:
            row.update(process_question(row, reranker))
            print(
                f"  status=Success recall@3={row['recall@3']} "
                f"latency={row['overall_latency_seconds']} seconds"
            )
        except Exception as error:
            row["pipeline_status"] = "Error"
            row["pipeline_error"] = str(error)
            print(f"  status=Error error={error}")
        write_rows(rows)

    print(f"Wrote results to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
