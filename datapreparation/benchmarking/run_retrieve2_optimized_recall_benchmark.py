"""Benchmark the optimized hybrid retriever (retrieve2.py)."""

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
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "csv_files_from_milestone5"
OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "infosys_rag_test_dataset_50_queries_retrieve2_optimized_recall_results.csv"
)

SOURCE_COLUMNS = [
    "id",
    "query",
    "source_category",
    "old_source_document",
    "current_source_document",
]

RESULT_COLUMNS = [
    "retrieved_documents_top_10",
    "retrieved_filepaths_top_10",
    "retrieved_sources_top_10",
    "recall@3",
    "recall@5",
    "recall@7",
    "recall@9",
    "embedding_latency_seconds",
    "dense_retrieval_latency_seconds",
    "lexical_retrieval_latency_seconds",
    "rrf_fusion_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]

OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS

sys.path.insert(0, str(EMBEDDINGS_SCRIPT))


def read_rows():
    """Read the original question rows."""
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def add_existing_results(rows):
    """Keep completed rows when resuming."""
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
    """Save results to CSV."""
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_filename(filename):
    """Normalize filename for comparison."""
    return re.sub(r"[^a-z0-9]+", "", Path(filename).name.lower())


def normalize_path(filepath):
    """Normalize path for comparison."""
    return filepath.replace("\\", "/").lstrip("./").lower()


def expected_document_is_in_rank(expected_document, ranked_documents, rank_limit):
    """Check if expected document is in top ranked_documents."""
    expected_is_path = "/" in expected_document or "\\" in expected_document
    expected_path = normalize_path(expected_document) if expected_is_path else ""
    expected_name = normalize_filename(expected_document)

    for document in ranked_documents[:rank_limit]:
        if expected_is_path:
            if normalize_path(document["filepath"]) == expected_path:
                return True
            continue
        if normalize_filename(document["filename"]) == expected_name:
            return True

    return False


def retrieve_hybrid_top_ten(question, timings):
    """Retrieve using optimized hybrid (retrieve2)."""
    try:
        from retrieve2 import (
            retrieve_dense, retrieve_lexical, reciprocal_rank_fusion,
            RRF_K, TOP_K_PER_SOURCE, CHROMA_WEIGHT
        )
    except ImportError as exc:
        raise RuntimeError(
            f"Failed to import retrieve2: {exc}. "
            "Ensure retrieve2.py exists and bm25_indexer.py has been run."
        ) from exc

    # Get top N from each source using parameters from retrieve2.py
    dense_results = retrieve_dense(question, top_k=TOP_K_PER_SOURCE, timings=timings)
    lexical_results = retrieve_lexical(question, top_k=TOP_K_PER_SOURCE, timings=timings)

    # Fuse using parameters from retrieve2.py
    fusion_start = time.perf_counter()
    fused_results = reciprocal_rank_fusion(
        dense_results, 
        lexical_results, 
        k=RRF_K,
        chroma_weight=CHROMA_WEIGHT
    )
    if timings is not None:
        timings["rrf_fusion"] = time.perf_counter() - fusion_start

    return fused_results


def make_retrieved_document_list(fused_results):
    """Convert fused results to document list."""
    documents = []
    for rank, result in enumerate(fused_results[:10], start=1):
        documents.append({
            "rank": rank,
            "filename": result.get("filename", "unknown"),
            "filepath": result.get("filepath", ""),
            "sources": ",".join(result.get("sources", [])),
            "score": result.get("fusion_score", 0.0),
        })
    return documents


def process_question(row):
    """Retrieve one question and measure recall."""
    question_start = time.perf_counter()
    timings = {}

    try:
        fused_results = retrieve_hybrid_top_ten(row["query"], timings)
    except Exception as exc:
        raise RuntimeError(f"Retrieval failed: {exc}") from exc

    retrieved_documents = make_retrieved_document_list(fused_results)

    if not retrieved_documents:
        raise ValueError("No documents were retrieved.")

    return {
        "retrieved_documents_top_10": " | ".join(
            f"#{doc['rank']} {doc['filename']} ({doc['sources']})"
            for doc in retrieved_documents
        ),
        "retrieved_filepaths_top_10": " | ".join(
            doc["filepath"] for doc in retrieved_documents
        ),
        "retrieved_sources_top_10": " | ".join(
            f"#{doc['rank']}:{doc['sources']}"
            for doc in retrieved_documents
        ),
        "recall@3": str(
            expected_document_is_in_rank(row["current_source_document"], retrieved_documents, 3)
        ),
        "recall@5": str(
            expected_document_is_in_rank(row["current_source_document"], retrieved_documents, 5)
        ),
        "recall@7": str(
            expected_document_is_in_rank(row["current_source_document"], retrieved_documents, 7)
        ),
        "recall@9": str(
            expected_document_is_in_rank(row["current_source_document"], retrieved_documents, 9)
        ),
        "embedding_latency_seconds": f"{timings.get('embedding', 0):.3f}",
        "dense_retrieval_latency_seconds": f"{timings.get('dense_retrieval', 0):.3f}",
        "lexical_retrieval_latency_seconds": f"{timings.get('lexical_retrieval', 0):.3f}",
        "rrf_fusion_latency_seconds": f"{timings.get('rrf_fusion', 0):.3f}",
        "overall_latency_seconds": f"{time.perf_counter() - question_start:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def read_arguments():
    """Read command line arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark optimized hybrid retriever (retrieve2.py)."
    )
    parser.add_argument("--start", type=int, default=1, help="Start question number (1-based)")
    parser.add_argument("--limit", type=int, default=50, help="Number of questions to process")
    arguments = parser.parse_args()

    if arguments.start < 1:
        parser.error("--start must be at least 1.")
    if arguments.limit < 1:
        parser.error("--limit must be at least 1.")

    return arguments


def print_summary(rows):
    """Print summary statistics."""
    completed_rows = [r for r in rows if r.get("pipeline_status") == "Success"]
    if not completed_rows:
        print("\n⚠ No successful results to summarize.")
        return

    recall_stats = {
        "recall@3": 0,
        "recall@5": 0,
        "recall@7": 0,
        "recall@9": 0,
    }

    for row in completed_rows:
        for key in recall_stats:
            if row.get(key, "").lower() == "true":
                recall_stats[key] += 1

    total = len(completed_rows)
    print("\n" + "=" * 80)
    print("OPTIMIZED HYBRID RETRIEVAL (retrieve2.py) RECALL RESULTS")
    print("=" * 80)
    for key in sorted(recall_stats.keys()):
        count = recall_stats[key]
        percentage = (count / total * 100) if total > 0 else 0
        bar_length = int(percentage / 5)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        print(f"{key}: {count:2d}/{total} ({percentage:5.1f}%) {bar}")

    print("\n" + "-" * 80)
    print("AVERAGE LATENCIES")
    print("-" * 80)

    latency_keys = [
        "embedding_latency_seconds",
        "dense_retrieval_latency_seconds",
        "lexical_retrieval_latency_seconds",
        "rrf_fusion_latency_seconds",
        "overall_latency_seconds",
    ]

    for key in latency_keys:
        values = []
        for row in completed_rows:
            try:
                val = float(row.get(key, 0))
                values.append(val)
            except (ValueError, TypeError):
                pass

        if values:
            avg = sum(values) / len(values)
            label = key.replace("_latency_seconds", "").replace("_", " ").title()
            print(f"{label}: {avg:.3f}s")


def main():
    """Run the benchmark."""
    arguments = read_arguments()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    os.chdir(EMBEDDINGS_SCRIPT)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    print("Loading input questions...")
    rows = add_existing_results(read_rows())
    if len(rows) != 50:
        raise ValueError(f"Expected 50 input questions, found {len(rows)}.")

    start_index = arguments.start - 1
    end_index = start_index + arguments.limit

    if start_index >= len(rows):
        raise ValueError(f"--start cannot exceed the {len(rows)} input questions.")
    if end_index > len(rows):
        raise ValueError("--start and --limit extend beyond the input questions.")

    print(f"Testing optimized hybrid retriever (retrieve2.py)")
    print(f"Questions {arguments.start} to {min(end_index, len(rows))}")
    print("=" * 80)

    for index, row in enumerate(rows[start_index:end_index], start=arguments.start):
        print(f"[{index:2d}/{len(rows)}] {row['query'][:60]:<60s} ", end="", flush=True)

        try:
            row.update(process_question(row))
            recall7 = row.get("recall@7", "").lower() == "true"
            status = "✓" if recall7 else "✗"
            latency = row.get("overall_latency_seconds", "?")
            print(f"[{status}] recall@7={recall7} latency={latency}s")
        except Exception as error:
            row["pipeline_status"] = "Error"
            row["pipeline_error"] = str(error)
            print(f"[E] ERROR: {error}")

        write_rows(rows)

    print_summary(rows)
    print(f"\n✓ Results written to: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
