"""Evaluate saved RAG answers with RAGAS without rerunning the RAG pipeline.

FLOW:
1. Read a completed pipeline-results CSV and manually approved reference CSV.
2. Reopen the stored top-three context files and remove YAML front matter.
3. Give the saved question, answer, context, and reference answer to RAGAS.
4. Save one row of metric scores immediately after it is evaluated.
5. Write a Markdown report with average scores and review candidates.

TERM: ``saved context`` is the exact set of Markdown files recorded in
``llm_context_filepaths_top_3`` when the answer model was called.

ASSUMPTION: the source paths in the pipeline result are relative to the
project root. This script evaluates no-reranking results first, but accepts
any future result CSV with the same answer and context-path columns.
"""

import argparse
import csv
import math
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAGAS_FOLDER = Path(__file__).resolve().parent
DEFAULT_ANSWERS_FILE = (
    PROJECT_ROOT
    / "data"
    / "infosys_rag_test_dataset_50_queries_without_reranking_results.csv"
)
DEFAULT_REFERENCES_FILE = RAGAS_FOLDER / "reference_answers_template.csv"
DEFAULT_OUTPUT_FILE = RAGAS_FOLDER / "no_reranking_ragas_results.csv"
DEFAULT_SUMMARY_FILE = RAGAS_FOLDER / "no_reranking_ragas_summary.md"
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


def read_csv_rows(file_path):
    """Read a UTF-8 CSV into dictionaries.

    Example: a saved benchmark CSV returns one dictionary for each question.
    This runs before validation so no OpenAI call happens for invalid inputs.
    """
    with file_path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def validate_and_join_rows(answer_rows, reference_rows):
    """Join saved pipeline rows to complete manual reference answers.

    Example: answer ID ``3`` joins reference ID ``3`` and becomes one RAGAS
    input record. Missing, duplicate, or blank reference answers stop before
    evaluation because reference-based metrics would be misleading.
    """
    if not answer_rows:
        raise ValueError("Answer-result CSV is empty.")
    if len({row.get("id", "") for row in answer_rows}) != len(answer_rows):
        raise ValueError("Answer-result CSV contains duplicate IDs.")

    references_by_id = {}
    for reference in reference_rows:
        reference_id = reference.get("id", "")
        if reference_id in references_by_id:
            raise ValueError("Reference-answer CSV contains duplicate IDs.")
        if not reference.get("reference_answer", "").strip():
            raise ValueError(f"Reference answer is blank for ID {reference_id}.")
        references_by_id[reference_id] = reference

    joined_rows = []
    for answer in answer_rows:
        answer_id = answer.get("id", "")
        reference = references_by_id.get(answer_id)
        if reference is None:
            raise ValueError(f"Reference answer is missing for ID {answer_id}.")
        if not answer.get("llm_answer", "").strip():
            raise ValueError(f"Saved LLM answer is blank for ID {answer_id}.")
        if not answer.get("llm_context_filepaths_top_3", "").strip():
            raise ValueError(f"Saved context paths are blank for ID {answer_id}.")

        joined_rows.append(
            {
                "id": answer_id,
                "question": answer["query"],
                "source_category": answer.get("source_category", ""),
                "source_document": answer.get("source_document", ""),
                "llm_answer": answer["llm_answer"],
                "llm_context_filepaths_top_3": answer["llm_context_filepaths_top_3"],
                "reference_answer": reference["reference_answer"].strip(),
            }
        )
    return joined_rows


def remove_yaml_front_matter(document):
    """Return a Markdown body without valid or malformed YAML front matter.

    Example: ``---\\ntitle: A\\n---\\nBody`` becomes ``Body``. This mirrors
    the answer pipeline's body-only context policy without importing pipeline
    code into the RAGAS workspace.
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


def read_saved_contexts(filepath_text):
    """Read the exact saved context paths and return body-only text blocks.

    Example: two pipe-separated project-relative paths return two Markdown
    bodies in the same order. A missing path raises a clear error for that row.
    """
    filepaths = [path.strip() for path in filepath_text.split("|") if path.strip()]
    if not filepaths:
        raise ValueError("No saved context paths were found.")

    contexts = []
    for filepath in filepaths:
        source_path = PROJECT_ROOT / filepath
        if not source_path.is_file():
            raise FileNotFoundError(f"Context file does not exist: {filepath}")
        document = source_path.read_text(encoding="utf-8")
        contexts.append(remove_yaml_front_matter(document))
    return contexts


def run_ragas_metrics(row, contexts):
    """Ask RAGAS to score one saved answer against its original context.

    Example: a question, answer, three context bodies, and a reference answer
    return four numeric scores. Imports stay inside this function so template
    and CSV checks can run without loading the evaluation stack.
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


def add_existing_results(rows, output_file):
    """Copy prior successful scores into the current row list for resuming.

    Example: after IDs 1–10 finish, a second run skips them and continues at
    ID 11. This protects completed evaluation calls from being repeated.
    """
    if not output_file.exists():
        return rows

    existing_rows = {row["id"]: row for row in read_csv_rows(output_file)}
    for row in rows:
        existing = existing_rows.get(row["id"])
        if existing and existing.get("evaluation_status") == "Success":
            for column in METRIC_COLUMNS + ["evaluation_status", "evaluation_error"]:
                row[column] = existing.get(column, "")
    return rows


def write_rows(rows, output_file):
    """Write the latest row-level evaluation state after each question.

    Example: if ID 12 fails, IDs 1–11 remain safely recorded in the output.
    """
    with output_file.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number_or_none(value):
    """Convert one stored metric to a number, or return None for blanks.

    Example: ``'0.82'`` becomes ``0.82`` and an empty or ``nan`` cell becomes
    ``None``. This lets the summary ignore unavailable metric values.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def write_summary(rows, answers_file, references_file, summary_file):
    """Create a short report with averages and the weakest scored rows.

    Example: three successful rows produce one average for each metric and up
    to five rows with the lowest mean score for manual review.
    """
    successful_rows = [row for row in rows if row.get("evaluation_status") == "Success"]
    failed_rows = [row for row in rows if row.get("evaluation_status") == "Error"]

    averages = {}
    for metric in METRIC_COLUMNS:
        values = [number_or_none(row.get(metric)) for row in successful_rows]
        values = [value for value in values if value is not None]
        averages[metric] = sum(values) / len(values) if values else None

    scored_rows = []
    for row in successful_rows:
        scores = [number_or_none(row.get(metric)) for metric in METRIC_COLUMNS]
        scores = [score for score in scores if score is not None]
        if scores:
            scored_rows.append((sum(scores) / len(scores), row))
    scored_rows.sort(key=lambda item: item[0])

    lines = [
        "# No-reranking RAGAS evaluation summary",
        "",
        f"- Evaluator model: `{EVALUATOR_MODEL}`",
        f"- Embedding model: `{EMBEDDING_MODEL}`",
        f"- Pipeline results: `{answers_file}`",
        f"- Reference answers: `{references_file}`",
        f"- Successful rows: {len(successful_rows)}",
        f"- Failed rows: {len(failed_rows)}",
        "",
        "## Average scores",
        "",
    ]
    for metric in METRIC_COLUMNS:
        value = averages[metric]
        lines.append(f"- {metric}: {value:.4f}" if value is not None else f"- {metric}: no score")

    lines.extend(["", "## Lowest average-score questions", ""])
    if scored_rows:
        for average, row in scored_rows[:5]:
            lines.append(f"- ID {row['id']} ({average:.4f}): {row['question']}")
    else:
        lines.append("- No successful evaluations yet.")

    if failed_rows:
        lines.extend(["", "## Failed rows", ""])
        for row in failed_rows:
            lines.append(f"- ID {row['id']}: {row.get('evaluation_error', 'Unknown error')}")

    summary_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_arguments():
    """Read the selected input and output paths plus optional row limit.

    Example: ``--limit 2`` evaluates the first two unfinished rows. With no
    arguments, the script evaluates every unfinished row in the result CSV.
    """
    parser = argparse.ArgumentParser(description="Evaluate saved RAG answers with RAGAS.")
    parser.add_argument("--answers-file", type=Path, default=DEFAULT_ANSWERS_FILE)
    parser.add_argument("--references-file", type=Path, default=DEFAULT_REFERENCES_FILE)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--summary-file", type=Path, default=DEFAULT_SUMMARY_FILE)
    parser.add_argument("--limit", type=int, default=None)
    arguments = parser.parse_args()
    if arguments.limit is not None and arguments.limit < 1:
        parser.error("--limit must be at least 1.")
    return arguments


def main():
    """Evaluate unfinished rows, saving each result and the final summary.

    Example: ``python RAGAS/run_ragas_evaluation.py --limit 2`` evaluates two
    rows after the manual reference-answer sheet has been completed.
    """
    # Windows log files must keep every question character, not just cp1252.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    arguments = read_arguments()
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("ERROR: OPENAI_API_KEY is required for RAGAS evaluation.")

    rows = validate_and_join_rows(
        read_csv_rows(arguments.answers_file),
        read_csv_rows(arguments.references_file),
    )
    rows = add_existing_results(rows, arguments.output_file)
    unfinished_rows = [row for row in rows if row.get("evaluation_status") != "Success"]
    if arguments.limit is not None:
        unfinished_rows = unfinished_rows[: arguments.limit]

    if not unfinished_rows:
        write_summary(rows, arguments.answers_file, arguments.references_file, arguments.summary_file)
        print("No unfinished rows. Summary refreshed.")
        return

    for row in unfinished_rows:
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
        write_rows(rows, arguments.output_file)

    write_summary(rows, arguments.answers_file, arguments.references_file, arguments.summary_file)
    print(f"Saved results to {arguments.output_file}")
    print(f"Saved summary to {arguments.summary_file}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
