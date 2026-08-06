"""Generate LLM answers for the v2 benchmark using the metadata-embedding pipeline.

Two pipeline modes are selected with --pipeline a or --pipeline b:

  Pipeline A (no reranking):
    1. Embed the query with text-embedding-3-small.
    2. Retrieve the top 10 candidates from the metadata_embeddings collection.
    3. Read the top 3 documents from disk (YAML front matter stripped).
    4. Ask gpt-4o-mini for an answer grounded in those three documents.

  Pipeline B (with reranking):
    1. Embed the query with text-embedding-3-small.
    2. Retrieve the top 20 candidates from the metadata_embeddings collection.
    3. Re-rank all 20 with cross-encoder/ms-marco-MiniLM-L-6-v2.
    4. Read the top 3 reranked documents from disk (YAML front matter stripped).
    5. Ask gpt-4o-mini for an answer grounded in those three documents.

Both pipelines write a CSV compatible with run_ragas_evaluation_v2.py:
the key columns are query, llm_answer, and llm_context_filepaths_top_3
(pipe-separated project-relative paths).

ASSUMPTION: The metadata_embeddings Chroma collection already exists at
metadata_embedding_pipeline/chroma_db/ (built by metadata_embedding_pipeline.py).
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


RAGAS_V2_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Allow imports from the metadata_embedding_pipeline directory.
sys.path.insert(0, str(PROJECT_ROOT / "metadata_embedding_pipeline"))
from metadata_embedding_utils import (  # noqa: E402
    COLLECTION_NAME,
    DB_PATH,
    EMBEDDING_MODEL,
)

INPUT_FILE = PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries_v2.csv"
OUTPUT_FILES: dict[str, Path] = {
    "a": RAGAS_V2_DIR / "pipeline_a_answers_v2.csv",
    "b": RAGAS_V2_DIR / "pipeline_b_answers_v2.csv",
}
LLM_MODEL = "gpt-4o-mini"
CONTEXT_CHAR_LIMIT = 4000  # Characters per context document sent to the LLM.
RETRIEVAL_TOP_K: dict[str, int] = {"a": 10, "b": 20}
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

SOURCE_COLUMNS = ["id", "query", "source_category", "source_document"]
RESULT_COLUMNS = [
    "llm_answer",
    "llm_context_filepaths_top_3",
    "embedding_latency_seconds",
    "chroma_retrieval_latency_seconds",
    "reranker_latency_seconds",
    "llm_latency_seconds",
    "overall_latency_seconds",
    "pipeline_status",
    "pipeline_error",
]
OUTPUT_COLUMNS = SOURCE_COLUMNS + RESULT_COLUMNS


# ---------------------------------------------------------------------------
# Lazy global clients
# ---------------------------------------------------------------------------

_openai_client: OpenAI | None = None
_collection = None
_reranker = None  # CrossEncoderReranker; loaded only for pipeline B.


def get_clients() -> tuple[OpenAI, object]:
    """Return (OpenAI client, Chroma collection), initialising on first call."""
    global _openai_client, _collection
    if _openai_client is None:
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in .env.")
        _openai_client = OpenAI(api_key=api_key)
        chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
        _collection = chroma_client.get_collection(name=COLLECTION_NAME)
    return _openai_client, _collection


def get_reranker():
    """Return the shared CrossEncoderReranker, loading the model on first call."""
    global _reranker
    if _reranker is None:
        from metadata_embedding_reranker_benchmark import CrossEncoderReranker  # noqa: E402
        _reranker = CrossEncoderReranker(model_name=RERANKER_MODEL)
    return _reranker


# ---------------------------------------------------------------------------
# Document body helpers
# ---------------------------------------------------------------------------

def remove_yaml_front_matter(document: str) -> str:
    """Return the Markdown body without the leading YAML front matter block.

    Example: ``---\\ntitle: A\\n---\\nBody`` becomes ``Body``.  Files without
    a YAML block are returned unchanged.
    """
    if not document.startswith("---"):
        return document
    lines = document.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return document
    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        return document
    return "".join(lines[closing_index + 1:]).lstrip("\r\n")


def read_context_body(filepath: str) -> str:
    """Read a document file and return its body text, stripped and truncated.

    YAML front matter is removed so only the human-readable document body is
    sent to the LLM.  Long bodies are truncated to CONTEXT_CHAR_LIMIT characters
    to stay within the model's context window when three are combined.
    """
    path = PROJECT_ROOT / filepath
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return f"[Could not read: {filepath}]"
    body = remove_yaml_front_matter(content)
    return body[:CONTEXT_CHAR_LIMIT] if len(body) > CONTEXT_CHAR_LIMIT else body


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve_top_k(question: str, top_k: int, timings: dict) -> list[dict]:
    """Embed one question and return top_k Chroma candidates as ranked dicts.

    Example: top_k=10 returns a list of 10 dicts, each with 'rank',
    'filename', and 'filepath' keys.
    """
    openai_client, collection = get_clients()

    t0 = time.perf_counter()
    embedding = openai_client.embeddings.create(
        model=EMBEDDING_MODEL, input=[question]
    ).data[0].embedding
    timings["embedding"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        include=["metadatas"],
    )
    timings["chroma_retrieval"] = time.perf_counter() - t0

    documents: list[dict] = []
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


# ---------------------------------------------------------------------------
# LLM answer generation
# ---------------------------------------------------------------------------

def build_answer_prompt(question: str, context_bodies: list[str]) -> str:
    """Build a RAG prompt from the question and the retrieved document bodies."""
    context_section = "\n\n---\n\n".join(
        f"[Document {i + 1}]\n{body}" for i, body in enumerate(context_bodies)
    )
    return (
        f"Answer the following question using only the provided documents.\n\n"
        f"Question: {question}\n\n"
        f"Documents:\n{context_section}\n\n"
        f"Answer:"
    )


def ask_llm(client: OpenAI, prompt: str) -> str:
    """Call gpt-4o-mini and return the model's text response."""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer questions based only on the provided documents. "
                    "Be concise and accurate."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Per-question processing
# ---------------------------------------------------------------------------

def process_question(row: dict, pipeline: str) -> dict:
    """Run one question through retrieval, optional reranking, and LLM answering.

    Pipeline A uses the original Chroma retrieval order (top 10, no reranking).
    Pipeline B retrieves top 20 candidates, re-ranks them with the cross-encoder,
    and uses the top 3 after reranking.

    Example: for pipeline 'b', a source found at reranked rank 2 goes into the
    LLM context as Document 1 in the final answer prompt.
    """
    question_start = time.perf_counter()
    timings: dict[str, float] = {}

    top_k = RETRIEVAL_TOP_K[pipeline]
    retrieved = retrieve_top_k(row["query"], top_k, timings)

    if pipeline == "b":
        t0 = time.perf_counter()
        final_docs = get_reranker().rerank(row["query"], retrieved)
        timings["reranker"] = time.perf_counter() - t0
    else:
        final_docs = retrieved
        timings["reranker"] = 0.0

    top3 = final_docs[:3]
    top3_filepaths = [doc["filepath"] for doc in top3]
    context_bodies = [read_context_body(fp) for fp in top3_filepaths]

    prompt = build_answer_prompt(row["query"], context_bodies)
    openai_client, _ = get_clients()
    t0 = time.perf_counter()
    answer = ask_llm(openai_client, prompt)
    timings["llm"] = time.perf_counter() - t0

    timings["total"] = time.perf_counter() - question_start

    return {
        "llm_answer": answer,
        "llm_context_filepaths_top_3": " | ".join(top3_filepaths),
        "embedding_latency_seconds": f"{timings['embedding']:.3f}",
        "chroma_retrieval_latency_seconds": f"{timings['chroma_retrieval']:.3f}",
        "reranker_latency_seconds": f"{timings['reranker']:.3f}",
        "llm_latency_seconds": f"{timings['llm']:.3f}",
        "overall_latency_seconds": f"{timings['total']:.3f}",
        "pipeline_status": "Success",
        "pipeline_error": "",
    }


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def read_csv_rows(file_path: Path) -> list[dict]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def add_existing_results(rows: list[dict], output_file: Path) -> list[dict]:
    """Retain completed result fields when resuming a partial run.

    Example: after a five-question trial, running again keeps those five
    rows and processes only the remaining 45.
    """
    if not output_file.is_file():
        return rows
    existing = {row["id"]: row for row in read_csv_rows(output_file)}
    for row in rows:
        saved = existing.get(row["id"])
        if saved and saved.get("pipeline_status") == "Success":
            for col in RESULT_COLUMNS:
                row[col] = saved.get(col, "")
    return rows


def write_rows(rows: list[dict], output_file: Path) -> None:
    """Write all rows to the output CSV after every completed question."""
    with output_file.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_arguments() -> argparse.Namespace:
    """Parse the required --pipeline argument and optional --limit."""
    parser = argparse.ArgumentParser(
        description="Generate LLM answers for the v2 benchmark using the metadata pipeline."
    )
    parser.add_argument(
        "--pipeline",
        choices=["a", "b"],
        required=True,
        help="'a' = no reranking (top-10), 'b' = with reranking (top-20).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of unfinished questions to process (default: all).",
    )
    arguments = parser.parse_args()
    if arguments.limit is not None and arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate LLM answers for all unfinished v2 questions, saving after each."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    arguments = read_arguments()
    pipeline = arguments.pipeline
    output_file = OUTPUT_FILES[pipeline]
    pipeline_label = "no reranking" if pipeline == "a" else "with reranking"

    print(f"Pipeline        : {pipeline.upper()} ({pipeline_label})")
    print(f"Retrieval top-K : {RETRIEVAL_TOP_K[pipeline]}")
    print(f"LLM model       : {LLM_MODEL}")
    print(f"Output          : {output_file.relative_to(PROJECT_ROOT)}")
    print()

    if pipeline == "b":
        print("Loading cross-encoder model…")
        get_reranker()
        print("Cross-encoder ready.\n")

    rows = read_csv_rows(INPUT_FILE)
    if len(rows) != 50:
        raise ValueError(f"Expected 50 benchmark questions, found {len(rows)}.")
    rows = add_existing_results(rows, output_file)

    unfinished = [row for row in rows if row.get("pipeline_status") != "Success"]
    if arguments.limit is not None:
        unfinished = unfinished[: arguments.limit]

    if not unfinished:
        print("No unfinished questions.")
        return

    failures = 0
    for number, row in enumerate(unfinished, start=1):
        print(f"[{number}/{len(unfinished)}] ID {row['id']}: {row['query']}")
        try:
            row.update(process_question(row, pipeline))
            print(
                f"  status=Success  llm={row['llm_latency_seconds']}s  "
                f"total={row['overall_latency_seconds']}s"
            )
        except Exception as error:
            row["pipeline_status"] = "Error"
            row["pipeline_error"] = str(error)
            failures += 1
            print(f"  status=Error  error={error}", file=sys.stderr)
        write_rows(rows, output_file)

    finished = [r for r in rows if r.get("pipeline_status") == "Success"]
    if finished:
        n = len(finished)
        avg_total = sum(float(r.get("overall_latency_seconds", 0)) for r in finished) / n
        avg_llm = sum(float(r.get("llm_latency_seconds", 0)) for r in finished) / n
        print()
        print("=== Pipeline Summary ===")
        print(f"Questions completed : {n}")
        print(f"Questions failed    : {failures}")
        print(f"Avg LLM latency     : {avg_llm:.3f} s/question")
        print(f"Avg total latency   : {avg_total:.3f} s/question")
    print(f"\nWrote results to {output_file.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
