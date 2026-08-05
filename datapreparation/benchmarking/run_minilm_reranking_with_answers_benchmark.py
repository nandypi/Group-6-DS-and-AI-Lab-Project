"""Run MiniLM-reranked retrieval and LLM answering, with the full ranked list
recorded alongside the generated answer.

This is a combined version of the two separate MiniLM/no-reranking
benchmarks: it retrieves and reranks every Chroma candidate (so ranking
metrics like MRR can be computed later), then also builds the final context
and calls the answer LLM (so generation metrics like ROUGE-L / semantic
similarity can be computed later) -- in a single pass per question.

FLOW:
1. Confirm that DO_RERANKING is True.
2. Read the untouched 50-question input CSV.
3. Embed one question and retrieve `RERANKING_RETRIEVAL_TOP_K` Chroma
   candidates (env-configurable, default 25 -- same default as the existing
   pipeline).
4. Use the MiniLM cross-encoder to rerank every retrieved candidate and keep
   the full ranked order.
5. Send the top `FINAL_DOCUMENT_COUNT` reranked bodies (env-configurable,
   default 3 -- same default as the existing pipeline) to gpt-4o-mini.
6. Record the full ranked list, recall@3/5/7/9, the saved answer, the saved
   context paths, and both configured values, so a baseline run and an
   experiment run (different env vars) are self-documenting from their CSV
   alone.

This script does not modify `retriever.py` or any other existing file --
`RERANKING_RETRIEVAL_TOP_K` and `FINAL_DOCUMENT_COUNT` are already read from
the environment by the existing pipeline code, so different experiment
configurations are run purely by setting those environment variables before
invoking this script.
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
DEFAULT_OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_results.csv"
)
SOURCE_COLUMNS = ["id", "query", "source_category", "current_source_document"]
RESULT_COLUMNS = [
    "reranked_documents",
    "reranked_filepaths",
    "llm_answer",
    "llm_context_filepaths",
    "recall@3",
    "recall@5",
    "recall@7",
    "recall@9",
    "input_prompt_tokens",
    "retrieval_top_k",
    "final_document_count",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
    "reranking_latency_seconds",
    "context_preparation_latency_seconds",
    "llm_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS

sys.path.insert(0, str(EMBEDDINGS_SCRIPT))
import retriever
from reranker_minilm import MiniLMReranker


def read_rows():
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def add_existing_results(rows, output_file):
    if not output_file.exists():
        return rows

    with output_file.open("r", encoding="utf-8-sig", newline="") as source:
        existing_rows = {row["id"]: row for row in csv.DictReader(source)}

    for row in rows:
        existing_row = existing_rows.get(row["id"])
        if existing_row:
            for column in RESULT_COLUMNS:
                row[column] = existing_row.get(column, "")

    return rows


def write_rows(rows, output_file):
    with output_file.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def expected_document_is_in_rank(expected_document, ranked_documents, rank_limit):
    """Return True when the expected source is within the first rank_limit results.

    Uses full-path comparison when current_source_document is a filepath
    (IDs 11-45), and basename comparison when it is a plain filename (IDs 1-10,
    46-50). This avoids false positives from duplicate chunk names like group_001.md.
    """
    is_path = "/" in expected_document or "\\" in expected_document
    if is_path:
        expected_norm = normalize(expected_document)
        for document in ranked_documents[:rank_limit]:
            if normalize(document["filepath"]).endswith(expected_norm):
                return True
    else:
        expected_norm = normalize(Path(expected_document).name)
        for document in ranked_documents[:rank_limit]:
            if normalize(document["filename"]) == expected_norm:
                return True
    return False


def process_question(row, reranker, final_document_count):
    question_start = time.perf_counter()
    timings = {}
    results = retriever.retrieve(row["query"], timings)
    retrieval_top_k = len(results.get("documents", [[]])[0])

    reranking_start = time.perf_counter()
    ranked_documents = retriever.rerank_results(
        results,
        row["query"],
        reranker,
        document_count=retrieval_top_k,
    )
    timings["reranking"] = time.perf_counter() - reranking_start
    if not ranked_documents:
        raise ValueError("No documents were retrieved after reranking.")

    selected_documents = ranked_documents[:final_document_count]

    context_start = time.perf_counter()
    context = retriever.build_context(selected_documents)
    prompt = retriever.make_prompt(row["query"], context)
    prompt_tokens = retriever.count_tokens(prompt)
    timings["context"] = time.perf_counter() - context_start

    llm_start = time.perf_counter()
    answer = retriever.ask_llm(row["query"], context)
    timings["llm"] = time.perf_counter() - llm_start
    timings["total"] = time.perf_counter() - question_start

    return {
        "reranked_documents": " | ".join(
            f"#{rank} {document['filename']} (score={document['final_score']:.4f})"
            for rank, document in enumerate(ranked_documents, start=1)
        ),
        "reranked_filepaths": " | ".join(
            document["filepath"] for document in ranked_documents
        ),
        "llm_answer": answer,
        "llm_context_filepaths": " | ".join(
            document["filepath"] for document in selected_documents
        ),
        "recall@3": str(
            expected_document_is_in_rank(row["current_source_document"], ranked_documents, 3)
        ),
        "recall@5": str(
            expected_document_is_in_rank(row["current_source_document"], ranked_documents, 5)
        ),
        "recall@7": str(
            expected_document_is_in_rank(row["current_source_document"], ranked_documents, 7)
        ),
        "recall@9": str(
            expected_document_is_in_rank(row["current_source_document"], ranked_documents, 9)
        ),
        "input_prompt_tokens": prompt_tokens,
        "retrieval_top_k": retrieval_top_k,
        "final_document_count": final_document_count,
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "reranking_latency_seconds": f"{timings['reranking']:.3f}",
        "context_preparation_latency_seconds": f"{timings['context']:.3f}",
        "llm_latency_seconds": f"{timings['llm']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def read_arguments():
    parser = argparse.ArgumentParser(
        description="Run the combined MiniLM reranking + answering benchmark."
    )
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    arguments = parser.parse_args()
    if arguments.start < 1:
        parser.error("--start must be at least 1.")
    if arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


def main():
    arguments = read_arguments()
    arguments.output_file = arguments.output_file.resolve()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not retriever.DO_RERANKING:
        raise RuntimeError(
            "Refusing to run: set DO_RERANKING=True in .env before this benchmark."
        )

    final_document_count = retriever.FINAL_DOCUMENT_COUNT
    retrieval_top_k = retriever.RERANKING_RETRIEVAL_TOP_K
    print(
        f"Config: RERANKING_RETRIEVAL_TOP_K={retrieval_top_k} "
        f"FINAL_DOCUMENT_COUNT={final_document_count}"
    )

    os.chdir(EMBEDDINGS_SCRIPT)
    rows = add_existing_results(read_rows(), arguments.output_file)
    if len(rows) != 50:
        raise ValueError(f"Expected 50 input questions, found {len(rows)}.")

    start_index = arguments.start - 1
    end_index = start_index + arguments.limit
    if start_index >= len(rows):
        raise ValueError(f"--start cannot exceed the {len(rows)} input questions.")
    if end_index > len(rows):
        raise ValueError("--start and --limit extend beyond the input questions.")

    reranker = MiniLMReranker(
        model_name=os.getenv("MINILM_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        max_tokens=int(os.getenv("MINILM_RERANKER_MAX_TOKENS", "512")),
    )

    for index, row in enumerate(rows[start_index:end_index], start=arguments.start):
        print(f"[{index}/{len(rows)}] {row['query']}")
        try:
            row.update(process_question(row, reranker, final_document_count))
            print(
                f"  status=Success recall@3={row['recall@3']} "
                f"latency={row['overall_latency_seconds']} seconds"
            )
        except Exception as error:
            row["pipeline_status"] = "Error"
            row["pipeline_error"] = str(error)
            print(f"  status=Error error={error}")
        write_rows(rows, arguments.output_file)

    try:
        output_display = arguments.output_file.relative_to(PROJECT_ROOT)
    except ValueError:
        output_display = arguments.output_file
    print(f"Wrote results to {output_display}")


if __name__ == "__main__":
    main()
