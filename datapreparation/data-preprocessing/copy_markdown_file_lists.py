"""
Reason this file exists:
Copy markdown files for the selected keep and review announcements into their
own folders, and report any expected markdown files that are missing.

Code flow:
1. Read keep-file-list.json and review-file-list.json from data/processed.
2. Build an index of markdown files in temp/markdown-data/final.
3. Convert each source URL to its expected filename stem.
4. Copy matching markdown files to temp/markdown-data/keep or review.
5. Write missing keep and review filename stems to temp/not-found-files.txt.
6. Print copy and missing-file counts.
"""

import json
import os
import shutil
from urllib.parse import unquote, urlparse


PROCESSED_DIR = os.path.join("data", "processed")
FINAL_DIR = os.path.join("temp", "markdown-data", "final")
KEEP_DIR = os.path.join("temp", "markdown-data", "keep")
REVIEW_DIR = os.path.join("temp", "markdown-data", "review")
NOT_FOUND_PATH = os.path.join("temp", "not-found-files.txt")


def file_stem_from_url(url):
    """
    Convert an announcement PDF URL into the filename stem used for matching.

    Called inside copy_matching_files for each record read from keep-file-list.json
    or review-file-list.json.
    """
    path = unquote(urlparse(url).path)
    filename = os.path.basename(path)
    stem, _ = os.path.splitext(filename)
    return stem


def load_file_list(filename):
    """
    Load one reduced announcement list from data/processed.

    Called by copy_matching_files before that function starts copying either the
    keep list or the review list.
    """
    path = os.path.join(PROCESSED_DIR, filename)
    with open(path, "r") as f:
        return json.load(f)


def index_final_files():
    """
    Build an in-memory list of available files in temp/markdown-data/final.

    Called once near the bottom of this script before keep and review files are
    copied, so both copy passes use the same final-folder index.
    """
    files = []

    for entry in os.scandir(FINAL_DIR):
        if entry.is_file():
            stem, _ = os.path.splitext(entry.name)
            files.append((stem, entry.path))

    return files


def find_matching_file(target_stem, final_files):
    """
    Find the markdown file path that matches an expected source filename stem.

    Called by copy_matching_files for each expected keep or review markdown
    file. It first tries an exact stem match, then a prefix match for older
    truncated filenames.
    """
    exact_matches = [
        path
        for stem, path in final_files
        if stem == target_stem
    ]

    if exact_matches:
        return exact_matches[0]

    prefix_matches = [
        path
        for stem, path in final_files
        if stem.startswith(target_stem)
    ]

    if prefix_matches:
        return prefix_matches[0]

    return None


def copy_matching_files(input_filename, output_dir, final_files):
    """
    Copy all markdown files listed in one reduced announcement JSON file.

    Called twice near the bottom of this script: once for keep-file-list.json
    and once for review-file-list.json.
    """
    os.makedirs(output_dir, exist_ok=True)
    records = load_file_list(input_filename)
    not_found = []
    copied = 0

    for record in records:
        target_stem = file_stem_from_url(record["attchmntFile"])
        source_path = find_matching_file(target_stem, final_files)

        if source_path is None:
            not_found.append(target_stem)
            continue

        destination_path = os.path.join(output_dir, os.path.basename(source_path))
        shutil.copy2(source_path, destination_path)
        copied += 1

    return copied, not_found


def write_not_found(keep_not_found, review_not_found):
    """
    Write the missing keep and review filename stems to the not-found report.

    Called once after both copy_matching_files calls have completed.
    """
    with open(NOT_FOUND_PATH, "w") as f:
        f.write("KEEP FILES NOT FOUND\n")
        f.write("====================\n")
        for filename in keep_not_found:
            f.write(f"{filename}\n")

        f.write("\nREVIEW FILES NOT FOUND\n")
        f.write("======================\n")
        for filename in review_not_found:
            f.write(f"{filename}\n")


final_files = index_final_files()

keep_copied, keep_not_found = copy_matching_files(
    "keep-file-list.json",
    KEEP_DIR,
    final_files,
)
review_copied, review_not_found = copy_matching_files(
    "review-file-list.json",
    REVIEW_DIR,
    final_files,
)

write_not_found(keep_not_found, review_not_found)

print(f"Copied {keep_copied} keep files to {KEEP_DIR}")
print(f"Copied {review_copied} review files to {REVIEW_DIR}")
print(f"Keep files not found: {len(keep_not_found)}")
print(f"Review files not found: {len(review_not_found)}")
print(f"Wrote not-found report to {NOT_FOUND_PATH}")
