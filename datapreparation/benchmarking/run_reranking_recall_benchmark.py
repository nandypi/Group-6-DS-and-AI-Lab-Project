"""Measure Chroma retrieval recall without calling reranking or the answer LLM.

FLOW:
1. Confirm that DO_RERANKING is True.
2. Read the untouched 50-question input CSV.
3. Embed one question and retrieve the top 10 Chroma candidates.
4. Keep Chroma's original order.
5. Record whether the expected source occurs within ranks 3, 5, 7, and 9.
6. Save the separate result CSV after every completed question.

EXAMPLE: if the expected source moves from Chroma rank 8 to BGE rank 2, the
output records recall@3=True, recall@5=True, and recall@7=True. No answer LLM
is called in this flow.

TERM: `retrieval rank` means a candidate's position in the order returned by
Chroma for the question embedding.

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
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "csv_files_from_milestone5"
OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "infosys_rag_test_dataset_50_queries_recall_results.csv"
)
SOURCE_COLUMNS = [
    "id",
    "query",
    "source_category",
    "old_source_document",
    "current_source_document",
]
RESULT_COLUMNS = [
    "llm_answer",
    "retrieved_documents_top_10",
    "retrieved_filepaths_top_10",
    "llm_context_filepaths_top_3",
    "recall@3",
    "recall@5",
    "recall@7",
    "recall@9",
    "input_prompt_tokens",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
    "reranking_latency_seconds",
    "llm_latency_seconds",
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


def normalize_path(filepath):
    """Normalize a repository path for exact source-file comparison.

    Example: `data\\docs\\group_001.md` and `data/docs/group_001.md` become
    the same lowercase path. This is used only when the expected source is a
    full path from the current test dataset.
    """
    return filepath.replace("\\", "/").lstrip("./").lower()


def expected_document_is_in_rank(expected_document, ranked_documents, rank_limit):
    """Return True if an expected source occurs in the first ranked documents.

    Example: a source at reranked rank four returns False for three and True
    for five. Full expected paths are matched exactly; a basename is matched
    against the candidate filename for unchanged source categories.
    """
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


def retrieve_top_ten(question, timings):
    """Embed one question and retrieve ten Chroma candidates.

    Example: one question returns Chroma ranks 1 through 10. This function
    never loads BGE and never calls `build_context` or `ask_llm`.
    """
    _, chroma_collection = retriever.get_clients()
    embedding_start = time.perf_counter()
    query_embedding = retriever.get_embedding(question)
    timings["embedding"] = time.perf_counter() - embedding_start

    retrieval_start = time.perf_counter()
    results = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
    )
    timings["chroma_retrieval"] = time.perf_counter() - retrieval_start
    return results


def make_retrieved_document_list(results):
    """Keep Chroma's rank, filename, and full filepath for ten results.

    Example: the first metadata record becomes a document with `rank=1`.
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


def process_question(row):
    """Retrieve one question without reranking or building an LLM prompt.

    Example: a source at rank four gives False at @3 and True at @5, @7, and
    @9. The answer model and BGE reranker are never called.
    """
    question_start = time.perf_counter()
    timings = {}
    results = retrieve_top_ten(row["query"], timings)
    retrieved_documents = make_retrieved_document_list(results)

    if not retrieved_documents:
        raise ValueError("No documents were retrieved from Chroma.")

    return {
        "llm_answer": "",
        "retrieved_documents_top_10": " | ".join(
            f"#{document['rank']} {document['filename']}"
            for document in retrieved_documents
        ),
        "retrieved_filepaths_top_10": " | ".join(
            document["filepath"] for document in retrieved_documents
        ),
        "llm_context_filepaths_top_3": "",
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
        "input_prompt_tokens": "",
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "reranking_latency_seconds": "",
        "llm_latency_seconds": "",
        "overall_latency_seconds": f"{time.perf_counter() - question_start:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def read_arguments():
    """Read the one-based start and number of questions to process.

    Example: `--start 3 --limit 48` processes the remaining questions after a
    two-question trial. The default processes all 50 questions.
    """
    parser = argparse.ArgumentParser(description="Run the Chroma recall benchmark.")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=50)
    arguments = parser.parse_args()
    if arguments.start < 1:
        parser.error("--start must be at least 1.")
    if arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


def main():
    """Run the requested recall-only rows and persist each result.

    Example: `python run_reranking_recall_benchmark.py --limit 2` runs Chroma
    retrieval for two questions and makes zero calls to BGE or the answer LLM.
    """
    arguments = read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.chdir(EMBEDDINGS_SCRIPT)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
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
