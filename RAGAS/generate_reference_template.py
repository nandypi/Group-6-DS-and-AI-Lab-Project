"""Create the manual reference-answer sheet for RAGAS evaluation.

FLOW:
1. Read the 50 original benchmark questions.
2. Read the completed no-reranking answer results.
3. Check that both files describe the same question IDs.
4. Create a CSV with one blank ``reference_answer`` field per question.
5. A reviewer fills the reference answers before RAGAS evaluation begins.

TERM: a reference answer is a short, human-approved answer that states the
important facts expected for one benchmark question.

ASSUMPTION: the benchmark question CSV and answer-result CSV use the same
``id`` column and contain exactly 50 rows.
"""

import argparse
import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS_FILE = PROJECT_ROOT / "data" / "infosys_rag_test_dataset_50_queries.csv"
DEFAULT_ANSWERS_FILE = (
    PROJECT_ROOT
    / "data"
    / "infosys_rag_test_dataset_50_queries_without_reranking_results.csv"
)
DEFAULT_OUTPUT_FILE = Path(__file__).resolve().parent / "reference_answers_template.csv"
TEMPLATE_COLUMNS = [
    "id",
    "question",
    "source_category",
    "source_document",
    "reference_answer",
]


def read_csv_rows(file_path):
    """Read CSV rows using UTF-8 with Excel-compatible BOM handling.

    Example: a five-row CSV returns five dictionaries. This is called before
    the template is written so input problems do not create a partial file.
    """
    with file_path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def make_template_rows(question_rows, answer_rows):
    """Return blank reference-answer rows after checking matching IDs.

    Example: question ID ``1`` and answer ID ``1`` produce one template row
    with an empty ``reference_answer``. The answer text is not copied because
    reviewers should write an independent expected answer.
    """
    question_ids = [row.get("id", "") for row in question_rows]
    answer_ids = [row.get("id", "") for row in answer_rows]

    if len(question_rows) != 50:
        raise ValueError(f"Expected 50 benchmark questions, found {len(question_rows)}.")
    if len(answer_rows) != 50:
        raise ValueError(f"Expected 50 answer results, found {len(answer_rows)}.")
    if len(set(question_ids)) != len(question_ids):
        raise ValueError("Question CSV contains duplicate IDs.")
    if question_ids != answer_ids:
        raise ValueError("Question and answer-result CSV IDs do not match in order.")

    rows = []
    for question in question_rows:
        rows.append(
            {
                "id": question["id"],
                "question": question["query"],
                "source_category": question["source_category"],
                "source_document": question["source_document"],
                "reference_answer": "",
            }
        )
    return rows


def write_template(rows, output_file):
    """Write all blank reference-answer rows to the requested CSV.

    Example: 50 input rows create a 50-row editable template. This runs only
    after both source CSVs have passed validation.
    """
    with output_file.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=TEMPLATE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_arguments():
    """Read optional input paths and the deliberate overwrite flag.

    Example: ``--overwrite`` replaces a prior blank template. Without it, a
    template is protected from accidentally losing manually entered answers.
    """
    parser = argparse.ArgumentParser(
        description="Create the reference-answer template for RAGAS evaluation."
    )
    parser.add_argument("--questions-file", type=Path, default=DEFAULT_QUESTIONS_FILE)
    parser.add_argument("--answers-file", type=Path, default=DEFAULT_ANSWERS_FILE)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main():
    """Create the template and state the next manual step.

    Example: ``python RAGAS/generate_reference_template.py`` creates
    ``RAGAS/reference_answers_template.csv`` for the current 50 questions.
    """
    arguments = read_arguments()
    if arguments.output_file.exists() and not arguments.overwrite:
        raise FileExistsError(
            f"ERROR: {arguments.output_file} already exists. Review it or use --overwrite."
        )

    question_rows = read_csv_rows(arguments.questions_file)
    answer_rows = read_csv_rows(arguments.answers_file)
    template_rows = make_template_rows(question_rows, answer_rows)
    write_template(template_rows, arguments.output_file)
    print(f"Created {arguments.output_file} with {len(template_rows)} blank reference answers.")
    print("Next step: fill every reference_answer cell, then run run_ragas_evaluation.py.")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(2) from error
