"""
Reason this file exists:
Copy reviewed NSE markdown files into final GPT decision buckets.

Code flow:
1. Read metadata/processed/review_decisions.json.
2. For each record, inspect decision and file_name.
3. Copy ACCEPT files to accepted_by_gpt, REJECT files to rejected_by_gpt,
   and all other decisions to uncateorised_by_gpt.
4. Print copied, skipped, and missing-file counts.
"""

import json
import os
import shutil


REVIEW_DECISIONS_PATH = os.path.join(
    "metadata",
    "processed",
    "review_decisions.json",
)
SOURCE_DIR = os.path.join("data", "nse_files_final", "review")
OUTPUT_ROOT = os.path.join(
    "data",
    "nse_files_final",
    "final_categorisation_by_gpt-5.5",
)

ACCEPTED_DIR = os.path.join(OUTPUT_ROOT, "accepted_by_gpt")
REJECTED_DIR = os.path.join(OUTPUT_ROOT, "rejected_by_gpt")
UNCATEGORISED_DIR = os.path.join(OUTPUT_ROOT, "uncateorised_by_gpt")


def load_review_decisions():
    with open(REVIEW_DECISIONS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not isinstance(records, list):
        raise ValueError(f"Expected a list in {REVIEW_DECISIONS_PATH}")

    return records


def destination_dir_for_decision(decision):
    if decision == "ACCEPT":
        return ACCEPTED_DIR

    if decision == "REJECT":
        return REJECTED_DIR

    return UNCATEGORISED_DIR


def copy_review_decision_files():
    for output_dir in (ACCEPTED_DIR, REJECTED_DIR, UNCATEGORISED_DIR):
        os.makedirs(output_dir, exist_ok=True)

    records = load_review_decisions()
    counts = {
        "accepted": 0,
        "rejected": 0,
        "uncategorised": 0,
        "missing": 0,
        "skipped": 0,
    }
    missing_files = []

    for index, record in enumerate(records, start=1):
        file_name = record.get("file_name")

        if not file_name:
            counts["skipped"] += 1
            print(f"Skipped record {index}: missing file_name")
            continue

        source_path = os.path.join(SOURCE_DIR, file_name)

        if not os.path.isfile(source_path):
            counts["missing"] += 1
            missing_files.append(file_name)
            continue

        decision = record.get("decision")
        destination_dir = destination_dir_for_decision(decision)
        destination_path = os.path.join(destination_dir, file_name)
        shutil.copy2(source_path, destination_path)

        if decision == "ACCEPT":
            counts["accepted"] += 1
        elif decision == "REJECT":
            counts["rejected"] += 1
        else:
            counts["uncategorised"] += 1

    print(f"Copied ACCEPT files: {counts['accepted']}")
    print(f"Copied REJECT files: {counts['rejected']}")
    print(f"Copied other-decision files: {counts['uncategorised']}")
    print(f"Missing source files: {counts['missing']}")
    print(f"Skipped invalid records: {counts['skipped']}")

    if missing_files:
        print("Missing file names:")
        for file_name in missing_files:
            print(f"- {file_name}")


if __name__ == "__main__":
    copy_review_decision_files()
