"""Run Chroma-only retrieval and LLM answering for the 50-question RAG test set.

FLOW:
1. Confirm that DO_RERANKING is False.
2. Read the original question CSV without changing it.
3. Embed one question and retrieve its top 10 Chroma documents.
4. Record whether the expected source document occurs within ranks 3, 5, and 7.
5. Send the original top 3 document bodies, without YAML metadata, to gpt-4o-mini.
6. Write results to a separate CSV after every completed question.

EXAMPLE: if an expected source appears at Chroma rank 4, the output records
recall@3=False, recall@5=True, and recall@7=True. The LLM still receives only
Chroma ranks 1 to 3.

TERM: `expected source document` is the filename in the input CSV's
`source_document` column.

ASSUMPTION: Chroma metadata contains a `filename` and `filepath` for every
indexed Markdown document.
ASSUMPTION: this benchmark measures source-document retrieval, because the
input CSV does not include reference answers for automatic answer evaluation.
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
    / "infosys_rag_test_dataset_50_queries_without_reranking_results.csv"
)
SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "llm_answer",
    "retrieved_documents_top_10",
    "retrieved_filepaths_top_10",
    "llm_context_filepaths_top_3",
    "recall@3",
    "recall@5",
    "recall@7",
    "input_prompt_tokens",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
    "context_preparation_latency_seconds",
    "llm_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS

sys.path.insert(0, str(EMBEDDINGS_SCRIPT))
import retriever


def read_rows():
    """Read the untouched input questions in their existing order.

    Example: a 50-row input file returns a list of 50 dictionaries. This runs
    before any question is sent to Chroma or the LLM.
    """
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def add_existing_results(rows):
    """Keep completed result fields when a later run processes remaining rows.

    Example: after a two-question trial, running with `--start 3` retains the
    first two completed rows and fills only rows three onward. This makes the
    output CSV safe to resume after an intentional partial run.
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
    """Save the current benchmark state to the separate output CSV.

    Example: after question 2 succeeds, this writes its answer and retrieval
    results while leaving unprocessed rows blank. This prevents lost progress.
    """
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_filename(filename):
    """Normalize a filename for comparison across source and Chroma metadata.

    Example: `Report-1.md` and `report_1.md` both become `report1md`. This is
    used only when checking whether the expected source was retrieved.
    """
    return re.sub(r"[^a-z0-9]+", "", Path(filename).name.lower())


def expected_document_is_in_rank(expected_document, retrieved_documents, rank_limit):
    """Return True when the expected filename occurs within a rank limit.

    Example: an expected file at position four returns False for limit three
    and True for limit five. This calculates one recall-at-k row value.
    """
    expected_name = normalize_filename(expected_document)
    for document in retrieved_documents[:rank_limit]:
        retrieved_name = normalize_filename(document["filename"])
        if expected_name == retrieved_name:
            return True
    return False


def retrieve_top_ten(question, timings):
    """Embed a question and retrieve ten Chroma candidates without reranking.

    Example: one question returns the original Chroma ranks 1 through 10.
    This is separate from `retriever.retrieve` because the no-reranking
    interactive pipeline normally requests only three candidates.
    """
    _, chroma_collection = retriever.get_clients()

    embedding_start = time.perf_counter()
    query_embedding = retriever.get_embedding(question)
    timings["embedding"] = time.perf_counter() - embedding_start

    retrieval_start = time.perf_counter()
    results = chroma_collection.query(query_embeddings=[query_embedding], n_results=10)
    timings["chroma_retrieval"] = time.perf_counter() - retrieval_start
    return results


def make_retrieved_document_list(results):
    """Keep Chroma's original rank, filename, and full filepath for ten results.

    Example: a first Chroma result produces a dictionary with `rank=1`. The
    list is used for recall checks and for recording all ten candidates.
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
    """Run one question through the Chroma-only retrieval and LLM path.

    Example: a source found at rank two gives all three recall columns a
    `True` value, then sends only ranks one to three to the LLM.
    """
    question_start = time.perf_counter()
    timings = {}
    results = retrieve_top_ten(row["query"], timings)
    retrieved_documents = make_retrieved_document_list(results)

    selection_start = time.perf_counter()
    selected_documents = retriever.select_without_reranking(results)
    timings["context"] = time.perf_counter() - selection_start
    if not selected_documents:
        raise ValueError("No Chroma documents were retrieved.")

    context_start = time.perf_counter()
    context = retriever.build_context(selected_documents)
    prompt = retriever.make_prompt(row["query"], context)
    prompt_tokens = retriever.count_tokens(prompt)
    timings["context"] += time.perf_counter() - context_start

    llm_start = time.perf_counter()
    answer = retriever.ask_llm(row["query"], context)
    timings["llm"] = time.perf_counter() - llm_start
    timings["total"] = time.perf_counter() - question_start

    return {
        "llm_answer": answer,
        "retrieved_documents_top_10": " | ".join(
            f"#{document['rank']} {document['filename']}"
            for document in retrieved_documents
        ),
        "retrieved_filepaths_top_10": " | ".join(
            document["filepath"] for document in retrieved_documents
        ),
        "llm_context_filepaths_top_3": " | ".join(
            document["filepath"] for document in selected_documents
        ),
        "recall@3": str(
            expected_document_is_in_rank(row["source_document"], retrieved_documents, 3)
        ),
        "recall@5": str(
            expected_document_is_in_rank(row["source_document"], retrieved_documents, 5)
        ),
        "recall@7": str(
            expected_document_is_in_rank(row["source_document"], retrieved_documents, 7)
        ),
        "input_prompt_tokens": retriever.count_tokens(prompt),
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "context_preparation_latency_seconds": f"{timings['context']:.3f}",
        "llm_latency_seconds": f"{timings['llm']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def read_arguments():
    """Read the optional number of leading questions to process.

    Example: `--limit 2` processes only questions one and two, while the
    default processes all 50 questions.
    """
    parser = argparse.ArgumentParser(description="Run the Chroma-only benchmark.")
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


def main():
    """Run the requested number of benchmark questions and save after each one.

    Example: `python datapreparation/benchmarking/run_without_reranking_benchmark.py --limit 2`
    writes two completed rows to the separate results CSV.
    """
    arguments = read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if retriever.DO_RERANKING:
        raise RuntimeError(
            "Refusing to run: set DO_RERANKING=False in .env before this benchmark."
        )

    # The retriever's Chroma path is relative to embeddings_script.
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
