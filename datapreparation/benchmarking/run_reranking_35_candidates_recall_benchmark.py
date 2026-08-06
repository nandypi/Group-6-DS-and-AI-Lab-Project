"""Measure recall after reranking 35 Chroma candidates with BGE.

FLOW:
1. Read the 50-question test CSV without changing it.
2. Embed one question and retrieve 35 candidates from Chroma.
3. Rerank all 35 candidates with the configured BGE reranker.
4. Check the expected current source in reranked positions 3, 5, 7, and 9.
5. Save both retrieval lists and the recall values after every question.

EXAMPLE: if the expected source is reranked to position 6, Recall@3 is False,
while Recall@5 is False, Recall@7 is True, and Recall@9 is True.

ASSUMPTION: `current_source_document` contains an exact path for re-sectioned
NSE and Infosys IR chunks, and a basename for unchanged source categories.
ASSUMPTION: this benchmark never calls an answer LLM.
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EMBEDDINGS_SCRIPT = PROJECT_ROOT / "embeddings_script"
INPUT_FILE = PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries.csv"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "csv_files_from_milestone5"
OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "infosys_rag_test_dataset_50_queries_reranking_35_candidates_recall_results.csv"
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
    "retrieved_documents_top_35",
    "retrieved_filepaths_top_35",
    "reranked_documents_top_35",
    "reranked_filepaths_top_35",
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
from reranker import truncate_body_for_reranker


# The local environment exposes four CPU cores. Using all of them is important
# because this benchmark runs BGE inference without a CUDA device.
torch.set_num_threads(min(4, os.cpu_count() or 1))


def read_rows():
    """Read all test questions before loading the reranker.

    Example: the test CSV returns 50 dictionaries with question and source
    fields, while no result fields are added to the input file.
    """
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def add_existing_results(rows):
    """Reuse completed rows if a run is resumed after interruption.

    Example: a completed row remains in the output when the next run starts
    with `--start 31`.
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
    """Write the current benchmark state, including unfinished blank rows."""
    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_filename(filename):
    """Normalize a basename for unchanged source categories."""
    return re.sub(r"[^a-z0-9]+", "", Path(filename).name.lower())


def normalize_path(filepath):
    """Normalize slash direction and case for exact repository path matching."""
    return filepath.replace("\\", "/").lstrip("./").lower()


def expected_document_is_in_rank(expected_document, ranked_documents, rank_limit):
    """Return whether the expected source appears within the requested rank.

    Full paths use exact path matching, preventing duplicate `group_001.md`
    files from being treated as the same source. Basenames use filename
    matching for unchanged categories.
    """
    expected_is_path = "/" in expected_document or "\\" in expected_document
    expected_path = normalize_path(expected_document) if expected_is_path else ""
    expected_name = normalize_filename(expected_document)

    for document in ranked_documents[:rank_limit]:
        if expected_is_path:
            if normalize_path(document["filepath"]) == expected_path:
                return True
        elif normalize_filename(document["filename"]) == expected_name:
            return True
    return False


def retrieve_top_thirty_five(question, timings):
    """Embed a question and retrieve 35 candidates from Chroma."""
    _, chroma_collection = retriever.get_clients()

    embedding_start = time.perf_counter()
    query_embedding = retriever.get_embedding(question)
    timings["embedding"] = time.perf_counter() - embedding_start

    retrieval_start = time.perf_counter()
    results = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=35,
    )
    timings["chroma_retrieval"] = time.perf_counter() - retrieval_start
    return results


def make_document_list(results):
    """Return Chroma metadata records with their original ranks."""
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


def score_many_documents(results, question, reranker):
    """Rerank all candidates with batched body and metadata scoring.

    The normal interactive helper scores each candidate separately. This
    benchmark has 35 candidates per question, so batching keeps the same
    weighted score calculation while avoiding 100 separate model calls.
    """
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    body_pairs = []
    metadata_pairs = []
    metadata_indexes = []
    bodies = []

    for index, (document, metadata) in enumerate(zip(documents, metadatas)):
        filepath = metadata.get("filepath", metadata.get("filename", ""))
        metadata_text, body, _ = retriever.split_front_matter(document, filepath)
        scoring_body = truncate_body_for_reranker(
            reranker.tokenizer,
            question,
            body,
            reranker.max_tokens,
        )
        body_pairs.append([question, scoring_body])
        bodies.append((metadata_text, body, metadata, filepath))
        if metadata_text:
            metadata_pairs.append([question, metadata_text])
            metadata_indexes.append(index)

    body_scores = reranker.model.compute_score(
        body_pairs,
        normalize=True,
        batch_size=35,
    )
    if not isinstance(body_scores, (list, tuple)):
        body_scores = [body_scores]

    metadata_scores = {}
    if metadata_pairs:
        scores = reranker.model.compute_score(
            metadata_pairs,
            normalize=True,
            batch_size=35,
        )
        if not isinstance(scores, (list, tuple)):
            scores = [scores]
        metadata_scores = dict(zip(metadata_indexes, scores))

    ranked = []
    seen_files = set()
    for index, ((metadata_text, body, metadata, filepath), body_score) in enumerate(
        zip(bodies, body_scores)
    ):
        if filepath in seen_files:
            continue
        seen_files.add(filepath)
        metadata_score = float(metadata_scores.get(index, 0.0))
        ranked.append(
            {
                "metadata_text": metadata_text,
                "metadata": metadata,
                "body": body,
                "metadata_score": metadata_score,
                "body_score": float(body_score),
                "filename": metadata.get("filename", filepath or "unknown"),
                "filepath": filepath,
                "final_score": (
                    retriever.BODY_WEIGHT * float(body_score)
                    + retriever.METADATA_WEIGHT * metadata_score
                ),
            }
        )

    ranked.sort(key=lambda item: item["final_score"], reverse=True)
    return ranked[:35]


def format_reranked_documents(documents):
    """Record reranked filenames and scores in rank order."""
    return " | ".join(
        f"#{rank} {document['filename']} (score={document['final_score']:.4f})"
        for rank, document in enumerate(documents, start=1)
    )


def process_question(row, reranker):
    """Retrieve and rerank one question without building an LLM prompt."""
    question_start = time.perf_counter()
    timings = {}
    results = retrieve_top_thirty_five(row["query"], timings)
    retrieved_documents = make_document_list(results)

    if not retrieved_documents:
        raise ValueError("No documents were retrieved from Chroma.")

    reranking_start = time.perf_counter()
    ranked_documents = score_many_documents(results, row["query"], reranker)
    timings["reranking"] = time.perf_counter() - reranking_start

    if not ranked_documents:
        raise ValueError("No documents were returned after reranking.")

    expected_source = row["current_source_document"]
    return {
        "llm_answer": "",
        "retrieved_documents_top_35": " | ".join(
            f"#{document['rank']} {document['filename']}"
            for document in retrieved_documents
        ),
        "retrieved_filepaths_top_35": " | ".join(
            document["filepath"] for document in retrieved_documents
        ),
        "reranked_documents_top_35": format_reranked_documents(ranked_documents),
        "reranked_filepaths_top_35": " | ".join(
            document["filepath"] for document in ranked_documents
        ),
        "llm_context_filepaths_top_3": "",
        "recall@3": str(expected_document_is_in_rank(expected_source, ranked_documents, 3)),
        "recall@5": str(expected_document_is_in_rank(expected_source, ranked_documents, 5)),
        "recall@7": str(expected_document_is_in_rank(expected_source, ranked_documents, 7)),
        "recall@9": str(expected_document_is_in_rank(expected_source, ranked_documents, 9)),
        "input_prompt_tokens": "",
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "reranking_latency_seconds": f"{timings['reranking']:.3f}",
        "llm_latency_seconds": "",
        "overall_latency_seconds": f"{time.perf_counter() - question_start:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


def read_arguments():
    """Read the optional one-based range for resumable benchmark runs."""
    parser = argparse.ArgumentParser(
        description="Run 35-candidate BGE reranking recall benchmark."
    )
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=50)
    arguments = parser.parse_args()
    if arguments.start < 1:
        parser.error("--start must be at least 1.")
    if arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


def main():
    """Run the requested rows and save results after each question."""
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
