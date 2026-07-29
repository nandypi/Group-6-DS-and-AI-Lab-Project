"""Run the 50-question BGE reranking benchmark and save each result.

Flow: verify ``DO_RERANKING=True`` -> load the benchmark CSV -> load BGE once
-> retrieve 10 Chroma candidates for one question -> rerank them -> ask the
LLM -> record scores, documents, answer, tokens, and timings -> write the CSV
before moving to the next question.

Run from the repository root with:

    python datapreparation/run_reranking_benchmark.py

ASSUMPTION: ``data/test_with_reranking.csv`` has already been created and the
indexed Chroma metadata uses filenames that can be compared with its
``Document`` column.
"""

import csv
import os
import re
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMBEDDINGS_SCRIPT = PROJECT_ROOT / "embeddings_script"
sys.path.insert(0, str(EMBEDDINGS_SCRIPT))

import retriever


BENCHMARK_FILE = PROJECT_ROOT / "data" / "test_with_reranking.csv"
SOURCE_COLUMNS = ["Document", "Difficulty", "Question", "Answer", "Evidence", "Page(s)"]
EVALUATION_COLUMNS = [
    "reranking_answer",
    "answer_correct",
    "retrieved_documents",
    "retrieved_filepaths",
    "correct_document_fetched",
    "input_prompt_tokens",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
    "reranking_latency_seconds",
    "context_preparation_latency_seconds",
    "llm_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + EVALUATION_COLUMNS


def read_rows():
    """Read the benchmark rows that will be updated after every question."""
    with BENCHMARK_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_rows(rows):
    """Persist all current results so an interruption does not lose progress."""
    with BENCHMARK_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def comparable_text(value):
    """Lowercase text and keep only letters and numbers for simple comparison."""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def answer_matches(expected, actual):
    """Return a transparent first-pass answer check based on containment.

    This marks an answer as correct when the normalized expected answer is
    contained in the model answer, or when the model answer is contained in
    the expected answer. It is a screening signal, not a substitute for
    human review of nuanced answers.
    """
    expected_text = comparable_text(expected)
    actual_text = comparable_text(actual)
    if not expected_text or not actual_text:
        return "Review"
    if expected_text in actual_text or actual_text in expected_text:
        return "Yes"
    return "No"


def document_was_fetched(expected_document, selected_documents):
    """Check whether a selected filename matches the benchmark source document."""
    expected_name = comparable_text(Path(expected_document).name)
    for document in selected_documents:
        selected_name = comparable_text(document["filename"])
        if expected_name in selected_name or selected_name in expected_name:
            return "Yes"
    return "No"


def process_question(row, reranker):
    """Run one question through the mandatory reranking branch.

    Returns the row's evaluation fields. Complete document bodies are used for
    the answer, while the CSV stores only filenames and ranking scores.
    """
    question_start = time.perf_counter()
    timings = {}
    results = retriever.retrieve(row["Question"], timings)

    reranking_start = time.perf_counter()
    selected_documents = retriever.rerank_results(
        results,
        row["Question"],
        reranker,
    )
    timings["reranking"] = time.perf_counter() - reranking_start

    if not selected_documents:
        raise ValueError("No documents were retrieved after reranking.")

    context_start = time.perf_counter()
    context = retriever.build_context(selected_documents)
    timings["context"] = time.perf_counter() - context_start
    prompt = retriever.make_prompt(row["Question"], context)
    prompt_tokens = retriever.count_tokens(prompt)

    llm_start = time.perf_counter()
    answer = retriever.ask_llm(row["Question"], context)
    timings["llm"] = time.perf_counter() - llm_start
    timings["total"] = time.perf_counter() - question_start

    document_names = []
    document_paths = []
    for document in selected_documents:
        document_names.append(
            f"{document['filename']} (score={document['final_score']:.4f})"
        )
        document_paths.append(document["filepath"])

    return {
        "reranking_answer": answer,
        "answer_correct": answer_matches(row["Answer"], answer),
        "retrieved_documents": " | ".join(document_names),
        "retrieved_filepaths": " | ".join(document_paths),
        "correct_document_fetched": document_was_fetched(
            row["Document"], selected_documents
        ),
        "input_prompt_tokens": prompt_tokens,
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "reranking_latency_seconds": f"{timings['reranking']:.3f}",
        "context_preparation_latency_seconds": f"{timings['context']:.3f}",
        "llm_latency_seconds": f"{timings['llm']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def main():
    """Process rows sequentially and save the CSV after every question."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not retriever.DO_RERANKING:
        raise RuntimeError(
            "Refusing to run: DO_RERANKING is not True. Set DO_RERANKING=True in .env."
        )

    # The existing retriever keeps its Chroma path relative to its run folder.
    os.chdir(EMBEDDINGS_SCRIPT)
    rows = read_rows()
    if len(rows) != 50:
        raise ValueError(f"Expected 50 benchmark rows, found {len(rows)}.")

    reranker = retriever.BGEReranker(
        model_name=retriever.os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
        max_tokens=int(retriever.os.getenv("RERANKER_MAX_TOKENS", "8190")),
    )

    for index, row in enumerate(rows, start=1):
        print(f"[{index}/50] {row['Question']}")
        try:
            row.update(process_question(row, reranker))
            print(f"  status=Success latency={row['overall_latency_seconds']} seconds")
        except Exception as error:
            row["pipeline_status"] = "Error"
            row["pipeline_error"] = str(error)
            print(f"  status=Error error={error}")
        write_rows(rows)

    print(f"Completed benchmark updates in {BENCHMARK_FILE}")


if __name__ == "__main__":
    main()
