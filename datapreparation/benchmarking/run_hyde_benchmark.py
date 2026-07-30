"""Run HyDE retrieval and LLM answering for the 50-question RAG test set.

FLOW:
1. Read the original question CSV without changing it.
2. Generate a hypothetical document for the question, embed it, and retrieve
   its top 10 Chroma documents.
3. Record whether the expected source document occurs within ranks 3, 5, and 7.
4. Send the top 3 retrieved document bodies, without YAML metadata, to
   gpt-4o-mini.
5. Write results to a separate CSV after every completed question.

Mirrors run_without_reranking_benchmark.py's columns and recall methodology
so the two result CSVs are directly comparable, with two HyDE-specific
columns added: hypothetical_document and hyde_generation_latency_seconds.
Retrieval and answering both go through hyde_script/hyde_retriever.py, the
module developed and benchmarked for simple (non-reranked) HyDE.

EXAMPLE: if an expected source appears at Chroma rank 4 after a HyDE query,
the output records recall@3=False, recall@5=True, and recall@7=True. The LLM
still receives only ranks 1 to 3.

TERM: `expected source document` is the filename in the input CSV's
`source_document` column.
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HYDE_SCRIPT = PROJECT_ROOT / "hyde_script"
INPUT_FILE = PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries.csv"
OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "infosys_rag_test_dataset_50_queries_with_hyde_results.csv"
)
RETRIEVAL_TOP_K = 10

SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "hypothetical_document",
    "llm_answer",
    "retrieved_documents_top_10",
    "retrieved_filepaths_top_10",
    "llm_context_filepaths_top_3",
    "recall@3",
    "recall@5",
    "recall@7",
    "input_prompt_tokens",
    "hyde_generation_latency_seconds",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
    "context_preparation_latency_seconds",
    "llm_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS

sys.path.insert(0, str(HYDE_SCRIPT))
import hyde_retriever


def read_rows():
    """Read the untouched input questions in their existing order.

    Example: a 50-row input file returns a list of 50 dictionaries. This runs
    before any question is sent to the LLM or Chroma.
    """
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def add_existing_results(rows):
    """Keep completed result fields when a later run processes remaining rows.

    Example: after a two-question trial, running with `--start 3` retains the
    first two completed rows and fills only rows three onward.
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
    """Save the current benchmark state to the separate output CSV."""
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_filename(filename):
    """Normalize a filename for comparison across source and Chroma metadata.

    Example: `Report-1.md` and `report_1.md` both become `report1md`.
    """
    return re.sub(r"[^a-z0-9]+", "", Path(filename).name.lower())


def expected_document_is_in_rank(expected_document, retrieved_documents, rank_limit):
    """Return True when the expected filename occurs within a rank limit."""
    expected_name = normalize_filename(expected_document)
    for document in retrieved_documents[:rank_limit]:
        retrieved_name = normalize_filename(document["filename"])
        if expected_name == retrieved_name:
            return True
    return False


def make_retrieved_document_list(results):
    """Keep Chroma's original rank, filename, and full filepath for ten results."""
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
    """Run one question through the HyDE retrieval and LLM answer path.

    Example: a source found at rank two gives all three recall columns a
    `True` value, then sends only ranks one to three to the LLM.
    """
    question_start = time.perf_counter()
    timings = {}

    results, hypothetical_document = hyde_retriever.retrieve(
        row["query"], timings, candidate_count=RETRIEVAL_TOP_K
    )
    retrieved_documents = make_retrieved_document_list(results)

    selection_start = time.perf_counter()
    selected_documents = hyde_retriever.select_documents(results)
    timings["context"] = time.perf_counter() - selection_start
    if not selected_documents:
        raise ValueError("No Chroma documents were retrieved.")

    context_start = time.perf_counter()
    context = hyde_retriever.build_context(selected_documents)
    prompt = hyde_retriever.make_prompt(row["query"], context)
    prompt_tokens = hyde_retriever.count_tokens(prompt)
    timings["context"] += time.perf_counter() - context_start

    llm_start = time.perf_counter()
    answer = hyde_retriever.ask_llm(row["query"], context)
    timings["llm"] = time.perf_counter() - llm_start
    timings["total"] = time.perf_counter() - question_start

    return {
        "hypothetical_document": hypothetical_document,
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
        "input_prompt_tokens": prompt_tokens,
        "hyde_generation_latency_seconds": f"{timings['hyde_generation']:.3f}",
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "context_preparation_latency_seconds": f"{timings['context']:.3f}",
        "llm_latency_seconds": f"{timings['llm']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def read_arguments():
    """Read the optional start position and number of questions to process."""
    parser = argparse.ArgumentParser(description="Run the HyDE retrieval benchmark.")
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
    """Run the requested number of benchmark questions and save after each one."""
    arguments = read_arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
