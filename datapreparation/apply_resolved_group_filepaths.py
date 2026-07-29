"""Replace uniquely resolved group basenames in the benchmark CSV.

Flow: read the Chroma recovery findings -> keep only resolved questions ->
replace each logged ``group_xxx.md`` with its exact Chroma filepath -> write
the updated benchmark CSV. Ambiguous and missing group names stay unchanged.

Run from the repository root with:

    python datapreparation/apply_resolved_group_filepaths.py

ASSUMPTION: ``group_filepath_recovery_findings.md`` was generated from the
same version of ``test_with_reranking.csv`` that this script updates.
"""

import csv
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_FILE = PROJECT_ROOT / "data" / "test_with_reranking.csv"
FINDINGS_FILE = PROJECT_ROOT / "data" / "group_filepath_recovery_findings.md"


def read_resolved_paths():
    """Return each resolved question's group filename-to-filepath mapping.

    Example return: ``{"Question?": {"group_035.md": "data/.../group_035.md"}}``.
    """
    lines = FINDINGS_FILE.read_text(encoding="utf-8").splitlines()
    resolved_paths = {}
    question = None
    is_resolved = False
    paths_for_question = {}
    group_name = None

    def save_current_question():
        if question and is_resolved and paths_for_question:
            resolved_paths[question] = dict(paths_for_question)

    for line in lines:
        if line.startswith("### "):
            save_current_question()
            question = line.split(". ", maxsplit=1)[1]
            is_resolved = False
            paths_for_question = {}
            group_name = None
            continue

        if "Finding: **Resolved from Chroma top-10**" in line:
            is_resolved = True
            continue

        group_match = re.match(r"- Chroma matches for `(group_\d+\.md)`:", line)
        if group_match:
            group_name = group_match.group(1)
            continue

        path_match = re.match(r"  - `(data/.+/group_\d+\.md)`", line)
        if group_name and path_match:
            paths_for_question[group_name] = path_match.group(1)
            group_name = None

    save_current_question()
    return resolved_paths


def update_csv(resolved_paths):
    """Replace only uniquely resolved group names and return the update count."""
    with BENCHMARK_FILE.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames:
        raise ValueError("Benchmark CSV has no header row.")

    updated_rows = 0
    for row in rows:
        replacements = resolved_paths.get(row["Question"])
        if not replacements:
            continue
        original_documents = row["retrieved_documents"]
        updated_documents = original_documents
        for group_name, filepath in replacements.items():
            updated_documents = updated_documents.replace(group_name, filepath)
        if updated_documents != original_documents:
            row["retrieved_documents"] = updated_documents
            updated_rows += 1

    with BENCHMARK_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return updated_rows


def main():
    """Apply the resolved paths and report how many benchmark rows changed."""
    resolved_paths = read_resolved_paths()
    updated_rows = update_csv(resolved_paths)
    print(f"Resolved question mappings found: {len(resolved_paths)}")
    print(f"Benchmark rows updated: {updated_rows}")


if __name__ == "__main__":
    main()
