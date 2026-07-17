"""
Reason this file exists:
Copy downstream NSE markdown files into page-count buckets.

Code flow:
1. Read markdown files from the NSE keep folder and GPT-accepted review folder.
2. Parse the top-level `pages` metadata value from each markdown file.
3. Copy files with pages <= 10 into equal_or_less_than_10_pages.
4. Copy files with pages > 10 into more_than_10_pages.
5. Print copied, missing-pages, invalid-pages, and duplicate-name counts.
"""

import os
import re
import shutil


SOURCE_DIRS = (
    os.path.join("data", "nse_files_final", "keep"),
    os.path.join(
        "data",
        "nse_files_final",
        "final_categorisation_by_gpt-5.5",
        "accepted_by_gpt",
    ),
)
OUTPUT_ROOT = os.path.join("data", "nse_files_final", "categorisation_by_pages")
LESS_THAN_OR_EQUAL_TO_10_DIR = os.path.join(
    OUTPUT_ROOT,
    "equal_or_less_than_10_pages",
)
MORE_THAN_10_DIR = os.path.join(OUTPUT_ROOT, "more_than_10_pages")

PAGES_PATTERN = re.compile(r"^pages:\s*['\"]?(\d+)['\"]?\s*$")


def parse_page_count(file_path):
    """
    Return the integer pages value from the markdown metadata block.

    Only the first 50 lines are inspected because `pages` is expected in the
    top-level metadata at the start of each file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if line_number > 50:
                break

            match = PAGES_PATTERN.match(line.strip())
            if match:
                return int(match.group(1))

    return None


def unique_destination_path(destination_dir, file_name, used_destinations):
    """
    Avoid silent overwrites when two source folders contain the same file name.
    """
    destination_path = os.path.join(destination_dir, file_name)

    if destination_path not in used_destinations and not os.path.exists(destination_path):
        used_destinations.add(destination_path)
        return destination_path, False

    stem, extension = os.path.splitext(file_name)
    counter = 2

    while True:
        candidate_path = os.path.join(destination_dir, f"{stem}__duplicate_{counter}{extension}")
        if candidate_path not in used_destinations and not os.path.exists(candidate_path):
            used_destinations.add(candidate_path)
            return candidate_path, True

        counter += 1


def copy_files_by_page_count():
    os.makedirs(LESS_THAN_OR_EQUAL_TO_10_DIR, exist_ok=True)
    os.makedirs(MORE_THAN_10_DIR, exist_ok=True)

    counts = {
        "equal_or_less_than_10_pages": 0,
        "more_than_10_pages": 0,
        "missing_pages": 0,
        "invalid_source_dirs": 0,
        "duplicates_renamed": 0,
    }
    missing_pages_files = []
    used_destinations = set()

    for source_dir in SOURCE_DIRS:
        if not os.path.isdir(source_dir):
            counts["invalid_source_dirs"] += 1
            print(f"Missing source folder: {source_dir}")
            continue

        for entry in os.scandir(source_dir):
            if not entry.is_file() or not entry.name.lower().endswith(".md"):
                continue

            page_count = parse_page_count(entry.path)

            if page_count is None:
                counts["missing_pages"] += 1
                missing_pages_files.append(entry.path)
                continue

            if page_count <= 10:
                destination_dir = LESS_THAN_OR_EQUAL_TO_10_DIR
                counts["equal_or_less_than_10_pages"] += 1
            else:
                destination_dir = MORE_THAN_10_DIR
                counts["more_than_10_pages"] += 1

            destination_path, was_renamed = unique_destination_path(
                destination_dir,
                entry.name,
                used_destinations,
            )
            shutil.copy2(entry.path, destination_path)

            if was_renamed:
                counts["duplicates_renamed"] += 1

    print(f"Copied files with pages <= 10: {counts['equal_or_less_than_10_pages']}")
    print(f"Copied files with pages > 10: {counts['more_than_10_pages']}")
    print(f"Files missing pages metadata: {counts['missing_pages']}")
    print(f"Missing source folders: {counts['invalid_source_dirs']}")
    print(f"Duplicate destination names renamed: {counts['duplicates_renamed']}")

    if missing_pages_files:
        print("Files missing pages metadata:")
        for file_path in missing_pages_files:
            print(f"- {file_path}")


if __name__ == "__main__":
    copy_files_by_page_count()
