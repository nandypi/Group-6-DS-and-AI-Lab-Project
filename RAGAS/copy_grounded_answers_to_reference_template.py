"""Copy generated source-grounded answers into the RAGAS reference template.

FLOW
1. Read the 50 generated answers from grounded_source_answers.csv.
2. Read reference_answers_template.csv.
3. Fill only blank reference_answer cells with successful generated answers.
4. Write the updated reference template back to disk.

Example:
    .\\venv\\Scripts\\python.exe RAGAS\\copy_grounded_answers_to_reference_template.py

ASSUMPTION: Generated answers are drafts. Review them before treating the
template as approved RAGAS ground truth.
"""

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GROUNDED_ANSWERS_FILE = PROJECT_ROOT / "RAGAS" / "grounded_source_answers.csv"
REFERENCE_TEMPLATE_FILE = PROJECT_ROOT / "RAGAS" / "reference_answers_template.csv"


def read_csv_rows(file_path):
    """Read CSV rows from a UTF-8 file.

    Example:
        read_csv_rows(Path("answers.csv"))
        # Returns a list of CSV row dictionaries.
    """
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def copy_blank_reference_answers(reference_rows, grounded_rows):
    """Fill blank references using successful generated answers by matching ID.

    Example:
        copy_blank_reference_answers([{"id": "1", "reference_answer": ""}], rows)
        # Returns 1 when generated row ID 1 has a successful answer.
    """
    answers_by_id = {}
    for row in grounded_rows:
        if row.get("generation_status") != "Success":
            continue

        answer = row.get("generated_grounded_answer", "").strip()
        if answer:
            answers_by_id[row["id"]] = answer

    copied_count = 0
    for row in reference_rows:
        if row.get("reference_answer", "").strip():
            continue

        answer = answers_by_id.get(row["id"])
        if answer:
            row["reference_answer"] = answer
            copied_count += 1

    return copied_count


def write_reference_rows(rows):
    """Write reference rows using the standard RAGAS reference columns.

    Example:
        write_reference_rows([{ "id": "1", "reference_answer": "Answer" }])
        # Rewrites reference_answers_template.csv.
    """
    fieldnames = [
        "id",
        "question",
        "source_category",
        "source_document",
        "reference_answer",
    ]
    with REFERENCE_TEMPLATE_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    """Copy all currently blank reference answers and print the result."""
    if not GROUNDED_ANSWERS_FILE.exists():
        print(f"ERROR: Generated answers file not found: {GROUNDED_ANSWERS_FILE}")
        return 2
    if not REFERENCE_TEMPLATE_FILE.exists():
        print(f"ERROR: Reference template not found: {REFERENCE_TEMPLATE_FILE}")
        return 2

    reference_rows = read_csv_rows(REFERENCE_TEMPLATE_FILE)
    grounded_rows = read_csv_rows(GROUNDED_ANSWERS_FILE)
    copied_count = copy_blank_reference_answers(reference_rows, grounded_rows)
    write_reference_rows(reference_rows)

    print(f"Copied generated answers into blank reference cells: {copied_count}")
    print(f"Reference template updated: {REFERENCE_TEMPLATE_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
