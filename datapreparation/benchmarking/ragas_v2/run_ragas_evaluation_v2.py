"""Evaluate v2 pipeline answers with RAGAS.

FLOW:
1. Read a completed pipeline-answers CSV and a human-reviewed reference CSV.
2. Reopen the stored top-three context files and remove YAML front matter.
3. Give the saved question, answer, context, and reference answer to RAGAS.
4. Save one row of metric scores immediately after each evaluation.
5. Write a Markdown summary with average scores and the lowest-scored rows.

PIPELINE SELECTION:
    --pipeline a   reads pipeline_a_answers_v2.csv  (no reranking)
    --pipeline b   reads pipeline_b_answers_v2.csv  (with reranking)

REFERENCE FILE:
    reference_answers_v2_template.csv produced by generate_grounded_source_answers_v2.py
    and approved/edited by a human reviewer.

ASSUMPTION: source paths in the pipeline-answer CSV are relative to the
project root.  Context files are read from those same stored paths.
"""

import argparse
import csv
import math
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv


RAGAS_V2_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
REFERENCE_FILE = RAGAS_V2_DIR / "reference_answers_v2_template.csv"
ANSWERS_FILES: dict[str, Path] = {
    "a": RAGAS_V2_DIR / "pipeline_a_answers_v2.csv",
    "b": RAGAS_V2_DIR / "pipeline_b_answers_v2.csv",
}
OUTPUT_FILES: dict[str, Path] = {
    "a": RAGAS_V2_DIR / "pipeline_a_ragas_results_v2.csv",
    "b": RAGAS_V2_DIR / "pipeline_b_ragas_results_v2.csv",
}
SUMMARY_FILES: dict[str, Path] = {
    "a": RAGAS_V2_DIR / "pipeline_a_ragas_summary_v2.md",
    "b": RAGAS_V2_DIR / "pipeline_b_ragas_summary_v2.md",
}
EVALUATOR_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
METRIC_COLUMNS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]
OUTPUT_COLUMNS = [
    "id",
    "question",
    "source_category",
    "source_document",
    "llm_answer",
    "llm_context_filepaths_top_3",
    "reference_answer",
] + METRIC_COLUMNS + ["evaluation_status", "evaluation_error"]


def read_csv_rows(file_path: Path) -> list[dict]:
    """Read a UTF-8 CSV into a list of row dictionaries."""
    with file_path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def validate_and_join_rows(
    answer_rows: list[dict], reference_rows: list[dict]
) -> list[dict]:
    """Join pipeline-answer rows to their human-reviewed reference answers.

    Example: answer ID 3 joins reference ID 3 and becomes one RAGAS input
    record.  Missing, duplicate, or blank reference answers stop execution
    before any evaluation call is made.
    """
    if not answer_rows:
        raise ValueError("Answer-result CSV is empty.")
    if len({row.get("id", "") for row in answer_rows}) != len(answer_rows):
        raise ValueError("Answer-result CSV contains duplicate IDs.")

    references_by_id: dict[str, dict] = {}
    for ref in reference_rows:
        ref_id = ref.get("id", "")
        if ref_id in references_by_id:
            raise ValueError("Reference-answer CSV contains duplicate IDs.")
        if not ref.get("reference_answer", "").strip():
            raise ValueError(f"Reference answer is blank for ID {ref_id}.")
        references_by_id[ref_id] = ref

    joined: list[dict] = []
    for answer in answer_rows:
        answer_id = answer.get("id", "")
        ref = references_by_id.get(answer_id)
        if ref is None:
            raise ValueError(f"Reference answer is missing for ID {answer_id}.")
        if not answer.get("llm_answer", "").strip():
            raise ValueError(f"Saved LLM answer is blank for ID {answer_id}.")
        if not answer.get("llm_context_filepaths_top_3", "").strip():
            raise ValueError(f"Saved context paths are blank for ID {answer_id}.")
        joined.append(
            {
                "id": answer_id,
                "question": answer["query"],
                "source_category": answer.get("source_category", ""),
                "source_document": answer.get("source_document", ""),
                "llm_answer": answer["llm_answer"],
                "llm_context_filepaths_top_3": answer["llm_context_filepaths_top_3"],
                "reference_answer": ref["reference_answer"].strip(),
            }
        )
    return joined


def remove_yaml_front_matter(document: str) -> str:
    """Return a Markdown body without the leading YAML front matter block.

    Example: ``---\\ntitle: A\\n---\\nBody`` becomes ``Body``.  This mirrors
    the answer pipeline's body-only context policy without importing pipeline
    code into this evaluation script.
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
    metadata_text = "".join(lines[1:closing_index]).strip()
    try:
        yaml.safe_load(metadata_text)
    except yaml.YAMLError:
        pass
    return "".join(lines[closing_index + 1:]).lstrip("\r\n")


def read_saved_contexts(filepath_text: str) -> list[str]:
    """Read the exact saved context paths and return body-only text blocks.

    Example: two pipe-separated project-relative paths return two Markdown
    bodies in the same order.  A missing path raises a clear error.
    """
    filepaths = [path.strip() for path in filepath_text.split("|") if path.strip()]
    if not filepaths:
        raise ValueError("No saved context paths were found.")
    contexts: list[str] = []
    for filepath in filepaths:
        source_path = PROJECT_ROOT / filepath
        if not source_path.is_file():
            raise FileNotFoundError(f"Context file does not exist: {filepath}")
        document = source_path.read_text(encoding="utf-8")
        contexts.append(remove_yaml_front_matter(document))
    return contexts


def run_ragas_metrics(row: dict, contexts: list[str]) -> dict[str, float]:
    """Ask RAGAS to score one saved answer against its original context.

    RAGAS imports stay inside this function so CSV validation can run without
    loading the full evaluation stack.
    """
    from datasets import Dataset
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    dataset = Dataset.from_list(
        [
            {
                "user_input": row["question"],
                "response": row["llm_answer"],
                "retrieved_contexts": contexts,
                "reference": row["reference_answer"],
            }
        ]
    )
    evaluator_llm = ChatOpenAI(model=EVALUATOR_MODEL, temperature=0)
    evaluator_embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        raise_exceptions=True,
    )
    result_row = result.to_pandas().iloc[0]
    return {metric: float(result_row[metric]) for metric in METRIC_COLUMNS}


def add_existing_results(rows: list[dict], output_file: Path) -> list[dict]:
    """Copy prior successful scores so reruns resume from where they left off.

    Example: after IDs 1–10 finish, a second run skips them and continues at
    ID 11, avoiding repeated API calls.
    """
    if not output_file.exists():
        return rows
    existing_rows = {row["id"]: row for row in read_csv_rows(output_file)}
    for row in rows:
        existing = existing_rows.get(row["id"])
        if existing and existing.get("evaluation_status") == "Success":
            for col in METRIC_COLUMNS + ["evaluation_status", "evaluation_error"]:
                row[col] = existing.get(col, "")
    return rows


def write_rows(rows: list[dict], output_file: Path) -> None:
    """Write all rows to the output CSV after every completed evaluation."""
    with output_file.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number_or_none(value) -> float | None:
    """Convert one stored metric to a number, or return None for blanks."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def write_summary(
    rows: list[dict],
    pipeline: str,
    answers_file: Path,
    references_file: Path,
    summary_file: Path,
) -> None:
    """Write a Markdown summary with averages and the lowest-scored rows."""
    successful = [row for row in rows if row.get("evaluation_status") == "Success"]
    failed = [row for row in rows if row.get("evaluation_status") == "Error"]

    averages: dict[str, float | None] = {}
    for metric in METRIC_COLUMNS:
        values = [
            v
            for v in (number_or_none(r.get(metric)) for r in successful)
            if v is not None
        ]
        averages[metric] = sum(values) / len(values) if values else None

    scored_rows = []
    for row in successful:
        scores = [
            v
            for v in (number_or_none(row.get(m)) for m in METRIC_COLUMNS)
            if v is not None
        ]
        if scores:
            scored_rows.append((sum(scores) / len(scores), row))
    scored_rows.sort(key=lambda item: item[0])

    pipeline_label = "no reranking" if pipeline == "a" else "with reranking"
    lines = [
        f"# Pipeline {pipeline.upper()} ({pipeline_label}) RAGAS Evaluation Summary",
        "",
        f"- Evaluator model: `{EVALUATOR_MODEL}`",
        f"- Embedding model: `{EMBEDDING_MODEL}`",
        f"- Pipeline results: `{answers_file.relative_to(PROJECT_ROOT)}`",
        f"- Reference answers: `{references_file.relative_to(PROJECT_ROOT)}`",
        f"- Successful rows: {len(successful)}",
        f"- Failed rows: {len(failed)}",
        "",
        "## Average scores",
        "",
    ]
    for metric in METRIC_COLUMNS:
        value = averages[metric]
        if value is not None:
            lines.append(f"- {metric}: {value:.4f}")
        else:
            lines.append(f"- {metric}: no score")

    lines.extend(["", "## Lowest average-score questions", ""])
    if scored_rows:
        for avg, row in scored_rows[:5]:
            lines.append(f"- ID {row['id']} ({avg:.4f}): {row['question']}")
    else:
        lines.append("- No successful evaluations yet.")

    if failed:
        lines.extend(["", "## Failed rows", ""])
        for row in failed:
            lines.append(f"- ID {row['id']}: {row.get('evaluation_error', 'Unknown error')}")

    summary_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_arguments() -> argparse.Namespace:
    """Parse the required --pipeline argument plus optional flags."""
    parser = argparse.ArgumentParser(
        description="Evaluate v2 pipeline answers with RAGAS."
    )
    parser.add_argument(
        "--pipeline",
        choices=["a", "b"],
        required=True,
        help="'a' = Pipeline A (no reranking), 'b' = Pipeline B (with reranking).",
    )
    parser.add_argument(
        "--references-file",
        type=Path,
        default=REFERENCE_FILE,
        help="Path to the human-reviewed reference-answer CSV (default: reference_answers_v2_template.csv).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of unfinished rows to evaluate (default: all).",
    )
    arguments = parser.parse_args()
    if arguments.limit is not None and arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


def main() -> None:
    """Evaluate unfinished rows, saving each result and the final summary."""
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    arguments = read_arguments()
    pipeline = arguments.pipeline
    answers_file = ANSWERS_FILES[pipeline]
    output_file = OUTPUT_FILES[pipeline]
    summary_file = SUMMARY_FILES[pipeline]
    references_file = arguments.references_file

    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for RAGAS evaluation.")

    rows = validate_and_join_rows(
        read_csv_rows(answers_file),
        read_csv_rows(references_file),
    )
    rows = add_existing_results(rows, output_file)
    unfinished = [row for row in rows if row.get("evaluation_status") != "Success"]
    if arguments.limit is not None:
        unfinished = unfinished[: arguments.limit]

    if not unfinished:
        write_summary(rows, pipeline, answers_file, references_file, summary_file)
        print("No unfinished rows. Summary refreshed.")
        return

    for row in unfinished:
        print(f"Evaluating ID {row['id']}: {row['question']}")
        try:
            contexts = read_saved_contexts(row["llm_context_filepaths_top_3"])
            scores = run_ragas_metrics(row, contexts)
            row.update({metric: f"{scores[metric]:.4f}" for metric in METRIC_COLUMNS})
            row["evaluation_status"] = "Success"
            row["evaluation_error"] = ""
            print(f"ID {row['id']} completed.")
        except Exception as error:
            row["evaluation_status"] = "Error"
            row["evaluation_error"] = str(error)
            print(f"ID {row['id']} failed: {error}", file=sys.stderr)
        write_rows(rows, output_file)

    write_summary(rows, pipeline, answers_file, references_file, summary_file)
    print(f"Saved results to {output_file}")
    print(f"Saved summary to {summary_file}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
