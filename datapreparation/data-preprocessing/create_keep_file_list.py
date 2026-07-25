"""
Reason this file exists:
Create smaller JSON lists for downstream file-copying scripts by keeping only
the fields needed to identify and describe each announcement file.

Code flow:
1. Define the required output fields.
2. Read data/processed/keep.json and write keep-file-list.json.
3. Read data/processed/review.json and write review-file-list.json.
4. Print how many records were written for each output file.
"""

import json
import os


REQUIRED_FIELDS = ("desc", "attchmntText", "attchmntFile")


def write_file_list(input_filename, output_filename):
    """
    Read one processed filing bucket and write its reduced three-field version.

    Called at the bottom of this script once for keep.json and once for
    review.json when the script is run from the command line.
    """
    input_path = os.path.join("data", "processed", input_filename)
    output_path = os.path.join("data", "processed", output_filename)

    with open(input_path, "r") as f:
        filings = json.load(f)

    file_list = []

    for filing in filings:
        file_list.append({
            field: filing[field]
            for field in REQUIRED_FIELDS
        })

    with open(output_path, "w") as f:
        json.dump(file_list, f, indent=2)

    print(f"Wrote {len(file_list)} records to {output_path}")


write_file_list("keep.json", "keep-file-list.json")
write_file_list("review.json", "review-file-list.json")
