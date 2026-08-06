"""
Strip the first YAML front matter block from every Markdown file in the two
source directories, writing results into corresponding _v2 directories.

The first block always starts at line 1 with "---" and contains keys such as
document_name, group_id, source_section_count, actual_tokens, source_section_ids.

Only that block is removed; everything from the second "---" onward is kept.
"""

import os
import shutil
import sys

SOURCE_DIRS = [
    "data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500",
    "data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500",
]

DEST_DIRS = [
    "data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2",
    "data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500_v2",
]

FIRST_BLOCK_KEYS = {
    "document_name",
    "group_id",
    "source_section_count",
    "actual_tokens",
    "source_section_ids",
}


def strip_first_yaml(content: str) -> tuple[str, str]:
    """
    Remove the first YAML front matter block from *content*.

    Returns (stripped_content, status) where status is one of:
      "ok"       – block found and removed
      "no_yaml"  – file does not start with '---'
      "no_close" – opening '---' found but no matching closing delimiter
      "wrong_block" – first block does not look like the metadata block
    """
    lines = content.splitlines(keepends=True)

    # Must start with the YAML delimiter on line 0
    if not lines or lines[0].rstrip("\r\n") != "---":
        return content, "no_yaml"

    # Find the closing '---' of the first block
    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            close_idx = i
            break

    if close_idx is None:
        return content, "no_close"

    # Sanity-check: the block should contain at least one expected key
    block_text = "".join(lines[1:close_idx])
    if not any(key + ":" in block_text for key in FIRST_BLOCK_KEYS):
        return content, "wrong_block"

    # Everything after the closing '---' is kept verbatim
    remaining = "".join(lines[close_idx + 1 :])
    return remaining, "ok"


def process_pair(src_root: str, dst_root: str) -> dict:
    stats = {"processed": 0, "skipped": 0, "errors": []}

    src_root = os.path.abspath(src_root)
    dst_root = os.path.abspath(dst_root)

    for dirpath, dirnames, filenames in os.walk(src_root):
        # Mirror directory structure
        rel_dir = os.path.relpath(dirpath, src_root)
        dst_dir = os.path.join(dst_root, rel_dir)
        os.makedirs(dst_dir, exist_ok=True)

        for filename in filenames:
            src_file = os.path.join(dirpath, filename)
            dst_file = os.path.join(dst_dir, filename)

            if not filename.endswith(".md"):
                # Copy non-Markdown files unchanged
                shutil.copy2(src_file, dst_file)
                continue

            try:
                with open(src_file, "r", encoding="utf-8") as fh:
                    content = fh.read()

                cleaned, status = strip_first_yaml(content)

                if status == "ok":
                    with open(dst_file, "w", encoding="utf-8") as fh:
                        fh.write(cleaned)
                    stats["processed"] += 1
                else:
                    # Copy as-is and record a skip
                    shutil.copy2(src_file, dst_file)
                    stats["skipped"] += 1
                    stats["errors"].append(
                        f"[{status}] {os.path.relpath(src_file, src_root)}"
                    )

            except Exception as exc:
                stats["errors"].append(
                    f"[exception] {os.path.relpath(src_file, src_root)}: {exc}"
                )
                stats["skipped"] += 1

    return stats


def main():
    base = os.path.dirname(os.path.abspath(__file__))

    total_processed = 0
    total_skipped = 0
    all_errors: list[str] = []

    for src_rel, dst_rel in zip(SOURCE_DIRS, DEST_DIRS):
        src = os.path.join(base, src_rel)
        dst = os.path.join(base, dst_rel)

        if not os.path.isdir(src):
            print(f"[WARN] Source directory not found, skipping: {src}")
            continue

        print(f"\nProcessing: {src_rel}")
        print(f"       -> : {dst_rel}")

        stats = process_pair(src, dst)
        total_processed += stats["processed"]
        total_skipped += stats["skipped"]
        all_errors.extend(stats["errors"])

        print(
            f"  Files processed : {stats['processed']}\n"
            f"  Files skipped   : {stats['skipped']}"
        )

    print("\n=== Summary ===")
    print(f"Total processed : {total_processed}")
    print(f"Total skipped   : {total_skipped}")

    if all_errors:
        print(f"\nErrors / warnings ({len(all_errors)}):")
        for e in all_errors:
            print(f"  {e}")
    else:
        print("No errors encountered.")

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
