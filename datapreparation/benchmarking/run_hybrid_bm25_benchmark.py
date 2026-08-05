"""Run BM25+dense hybrid retrieval + MiniLM reranking + LLM answering benchmark.

This is identical in structure to run_minilm_reranking_with_answers_benchmark.py
but replaces the Chroma-only candidate retrieval with a hybrid pipeline:

  Chroma dense (top_k) + BM25 keyword (top_k)
    → Reciprocal Rank Fusion (RRF, k=60)
    → MiniLM cross-encoder reranking
    → gpt-4o-mini answer

WHY: Dense embedding search misses ~20-30% of expected source documents
entirely (hit-rate ceiling). Those failures cluster around keyword-heavy
queries ("CSR spend", "share buyback", "ADRs listed", "exports %") where BM25
keyword matching is strong. RRF lets both signals reinforce each other without
normalising scores across retrieval systems.

FLOW:
1. Load all 1877 Chroma documents into a BM25 index (once at startup).
2. For each question: hybrid retrieve → MiniLM rerank → LLM answer.
3. Record the full reranked list, recall@3/5/7/9, the LLM answer, and
   per-stage latencies so results are directly comparable to the MiniLM
   baseline and improved CSVs.
4. Write results after every completed question.
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
    / "infosys_rag_test_dataset_50_queries_with_hybrid_bm25_results.csv"
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
    "bm25_retrieval_latency_seconds",
    "rrf_merge_latency_seconds",
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
from hybrid_retriever_bm25 import HybridBM25Retriever


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
            if normalize(document["filepath"]) == expected_norm:
                return True
    else:
        expected_norm = normalize(Path(expected_document).name)
        for document in ranked_documents[:rank_limit]:
            if normalize(document["filename"]) == expected_norm:
                return True
    return False


def process_question(row, hybrid_retriever, reranker, chroma_collection, final_document_count):
    question_start = time.perf_counter()
    timings = {}

    # Hybrid retrieval (embedding + dense Chroma + BM25 + RRF)
    retrieval_top_k = retriever.RERANKING_RETRIEVAL_TOP_K
    results = hybrid_retriever.retrieve(
        query=row["query"],
        chroma_collection=chroma_collection,
        get_embedding_fn=retriever.get_embedding,
        top_k=retrieval_top_k,
        timings=timings,
    )
    actual_top_k = len(results.get("documents", [[]])[0])

    # MiniLM reranking over the merged candidate list
    reranking_start = time.perf_counter()
    ranked_documents = retriever.rerank_results(
        results,
        row["query"],
        reranker,
        document_count=actual_top_k,
    )
    timings["reranking"] = time.perf_counter() - reranking_start
    if not ranked_documents:
        raise ValueError("No documents were retrieved after reranking.")

    selected_documents = ranked_documents[:final_document_count]

    # Context and LLM answer
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
        "retrieval_top_k": actual_top_k,
        "final_document_count": final_document_count,
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "bm25_retrieval_latency_seconds": f"{timings.get('bm25_retrieval', 0):.3f}",
        "rrf_merge_latency_seconds": f"{timings.get('rrf_merge', 0):.3f}",
        "reranking_latency_seconds": f"{timings['reranking']:.3f}",
        "context_preparation_latency_seconds": f"{timings['context']:.3f}",
        "llm_latency_seconds": f"{timings['llm']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def read_arguments():
    parser = argparse.ArgumentParser(
        description="Run the BM25+dense hybrid retrieval + MiniLM reranking benchmark."
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
        f"FINAL_DOCUMENT_COUNT={final_document_count} "
        f"(hybrid BM25+dense, RRF k={60})"
    )

    os.chdir(EMBEDDINGS_SCRIPT)
    _, chroma_collection = retriever.get_clients()

    # Build BM25 index from all Chroma documents (once)
    hybrid = HybridBM25Retriever(chroma_collection)

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
            row.update(
                process_question(row, hybrid, reranker, chroma_collection, final_document_count)
            )
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
