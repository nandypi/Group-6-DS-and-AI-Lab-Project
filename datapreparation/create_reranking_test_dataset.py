"""Create the fixed 50-question dataset used to evaluate reranking.

Flow: read the benchmark CSV -> group rows by difficulty -> sample 25 Easy,
15 Medium, and 10 Hard rows with a fixed seed -> add empty evaluation columns
-> write ``data/test_with_reranking.csv``.

Run from the repository root with:

    python datapreparation/create_reranking_test_dataset.py

ASSUMPTION: the source CSV contains one row per question and uses the exact
difficulty labels ``Easy``, ``Medium``, and ``Hard``.
"""

import csv
import random
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = PROJECT_ROOT / "data" / "benchmark_dataset - QA_with_citations.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "test_with_reranking.csv"
SAMPLE_COUNTS = {
    "Easy": 25,
    "Medium": 15,
    "Hard": 10,
}
RANDOM_SEED = 42

EVALUATION_COLUMNS = [
    "reranking_answer",
    "answer_correct",
    "retrieved_documents",
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


def read_source_rows():
    """Read all benchmark rows for sampling.

    Returns a list of dictionaries. The helper exists so file reading and
    validation stay separate from the sampling logic.
    """
    with SOURCE_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows = list(reader)

    required_columns = {"Document", "Difficulty", "Question", "Answer"}
    missing_columns = required_columns - set(reader.fieldnames or [])
    if missing_columns:
        names = ", ".join(sorted(missing_columns))
        raise ValueError(f"Source CSV is missing required columns: {names}")
    return rows


def choose_questions(rows):
    """Choose the requested number of questions from each difficulty.

    Example: 25 Easy + 15 Medium + 10 Hard returns exactly 50 rows. The fixed
    random seed makes repeated runs produce the same selection.
    """
    rows_by_difficulty = {difficulty: [] for difficulty in SAMPLE_COUNTS}
    for row in rows:
        difficulty = row.get("Difficulty", "").strip()
        if difficulty in rows_by_difficulty:
            rows_by_difficulty[difficulty].append(row)

    random_generator = random.Random(RANDOM_SEED)
    selected_rows = []
    for difficulty, required_count in SAMPLE_COUNTS.items():
        available_rows = rows_by_difficulty[difficulty]
        if len(available_rows) < required_count:
            raise ValueError(
                f"Need {required_count} {difficulty} questions, but found "
                f"only {len(available_rows)}."
            )
        selected_rows.extend(random_generator.sample(available_rows, required_count))

    return selected_rows


def add_evaluation_columns(rows):
    """Copy selected rows and add blank fields for future pipeline results.

    The original benchmark answer and evidence remain unchanged. Evaluation
    code can fill the added columns in the same output file after each run.
    """
    prepared_rows = []
    for row in rows:
        prepared_row = dict(row)
        for column in EVALUATION_COLUMNS:
            prepared_row[column] = ""
        prepared_rows.append(prepared_row)
    return prepared_rows


def write_output(rows):
    """Write the selected questions and empty evaluation fields to the output CSV."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    source_columns = ["Document", "Difficulty", "Question", "Answer", "Evidence", "Page(s)"]
    output_columns = source_columns + EVALUATION_COLUMNS

    with OUTPUT_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=output_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    """Create the deterministic evaluation input file and report its counts."""
    source_rows = read_source_rows()
    selected_rows = choose_questions(source_rows)
    output_rows = add_evaluation_columns(selected_rows)
    write_output(output_rows)

    print(f"Created: {OUTPUT_FILE}")
    print(f"Total questions: {len(output_rows)}")
    for difficulty, count in SAMPLE_COUNTS.items():
        print(f"{difficulty}: {count}")


if __name__ == "__main__":
    main()
