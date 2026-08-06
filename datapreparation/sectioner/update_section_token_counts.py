"""Write actual tokenizer counts into section manifests.

Flow:
1. Run this file from the project root.
2. The script opens every JSON manifest in the greater-than-10-page sections folder.
3. For each section, it reads the `text` field.
4. It counts tokens with the `text-embedding-3-small` tokenizer.
5. It writes `actual_tokens` with the actual count for that section.
6. It writes the JSON file back in the same manifest shape.
7. It prints a short summary so the run can be checked quickly.

Project terms:
- Section manifest: one JSON file in the `sections` folder for one source document.
- Section: one chunk inside a section manifest, stored under the `sections` list.
- Actual token count: the number of tokens returned by the same tokenizer used for
  `text-embedding-3-small` embeddings.

ASSUMPTION: token size means the token count of the section `text`, not the full
JSON metadata around that text.
"""

import argparse
import json
from pathlib import Path

import tiktoken


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SECTIONS_DIR = (
    PROJECT_ROOT
    / "data"
    / "nse_files_final"
    / "knowledge_extraction"
    / "greater_than_10_pages"
    / "sections"
)
EMBEDDING_MODEL = "text-embedding-3-small"
OLD_TOKEN_FIELD = "estimated" + "_tokens"
NEW_TOKEN_FIELD = "actual_tokens"


def find_json_files(sections_dir):
    """Return sorted section manifest JSON files.

    Args:
        sections_dir: Folder that contains one JSON manifest per long document.

    Returns:
        A sorted list of `.json` paths.

    Example:
        `find_json_files(Path("sections"))` can return `[Path("a.json")]`.
    """

    if not sections_dir.is_dir():
        raise FileNotFoundError(f"ERROR: sections folder not found: {sections_dir}")

    return sorted(sections_dir.glob("*.json"))


def count_section_tokens(encoding, section):
    """Return the actual token count for one section's text.

    Args:
        encoding: Tokenizer returned by `tiktoken.encoding_for_model`.
        section: One dict from a manifest's `sections` list.

    Returns:
        Integer token count for `section["text"]`.

    Example:
        A section with `{"text": "Revenue grew 5%."}` returns the model's token
        count for that sentence.
    """

    text = section.get("text", "")
    if not isinstance(text, str):
        raise ValueError("ERROR: section text must be a string")

    return len(encoding.encode(text))


def update_manifest_file(encoding, json_file):
    """Update one manifest and return count statistics.

    Args:
        encoding: Tokenizer returned by `tiktoken.encoding_for_model`.
        json_file: Section manifest JSON path.

    Returns:
        A dict with file-level counts used by the CLI summary.

    Example:
        Updating a manifest with 2 sections returns `{"section_count": 2, ...}`.
    """

    manifest = json.loads(json_file.read_text(encoding="utf-8"))
    sections = manifest.get("sections", [])
    if not isinstance(sections, list):
        raise ValueError(f"ERROR: sections must be a list in {json_file}")

    changed_sections = 0
    largest_tokens = 0
    smallest_tokens = None

    for section in sections:
        if not isinstance(section, dict):
            raise ValueError(f"ERROR: each section must be an object in {json_file}")

        actual_tokens = count_section_tokens(encoding, section)
        old_tokens = section.get(NEW_TOKEN_FIELD)
        if OLD_TOKEN_FIELD in section:
            section.pop(OLD_TOKEN_FIELD)
            changed_sections += 1
        section[NEW_TOKEN_FIELD] = actual_tokens

        if old_tokens is not None and old_tokens != actual_tokens:
            changed_sections += 1

        if actual_tokens > largest_tokens:
            largest_tokens = actual_tokens
        if smallest_tokens is None or actual_tokens < smallest_tokens:
            smallest_tokens = actual_tokens

    json_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if smallest_tokens is None:
        smallest_tokens = 0

    return {
        "section_count": len(sections),
        "changed_sections": changed_sections,
        "largest_tokens": largest_tokens,
        "smallest_tokens": smallest_tokens,
    }


def update_all_manifests(sections_dir):
    """Update every section manifest in the target folder.

    Args:
        sections_dir: Folder containing section manifest JSON files.

    Returns:
        A summary dict for terminal output.

    Example:
        `update_all_manifests(Path("sections"))` returns file and section totals.
    """

    encoding = tiktoken.encoding_for_model(EMBEDDING_MODEL)
    json_files = find_json_files(sections_dir)

    summary = {
        "file_count": len(json_files),
        "section_count": 0,
        "changed_sections": 0,
        "largest_tokens": 0,
        "smallest_tokens": None,
    }

    for json_file in json_files:
        file_summary = update_manifest_file(encoding, json_file)
        summary["section_count"] += file_summary["section_count"]
        summary["changed_sections"] += file_summary["changed_sections"]

        if file_summary["largest_tokens"] > summary["largest_tokens"]:
            summary["largest_tokens"] = file_summary["largest_tokens"]

        if summary["smallest_tokens"] is None:
            summary["smallest_tokens"] = file_summary["smallest_tokens"]
        elif file_summary["smallest_tokens"] < summary["smallest_tokens"]:
            summary["smallest_tokens"] = file_summary["smallest_tokens"]

    if summary["smallest_tokens"] is None:
        summary["smallest_tokens"] = 0

    return summary


def parse_args():
    """Read CLI arguments.

    Returns:
        Parsed CLI arguments with `sections_dir`.

    Example:
        Running without arguments uses the default greater-than-10-page sections folder.
    """

    parser = argparse.ArgumentParser(
        description="Write section actual_tokens with actual tokenizer counts."
    )
    parser.add_argument(
        "--sections-dir",
        default=str(DEFAULT_SECTIONS_DIR),
        help="Folder containing section manifest JSON files.",
    )
    return parser.parse_args()


def main():
    """Run the token update flow and print a short verification summary."""

    args = parse_args()
    sections_dir = Path(args.sections_dir)
    summary = update_all_manifests(sections_dir)

    print(f"Updated JSON files: {summary['file_count']}")
    print(f"Updated sections: {summary['section_count']}")
    print(f"Changed token values: {summary['changed_sections']}")
    print(f"Smallest actual token count: {summary['smallest_tokens']}")
    print(f"Largest actual token count: {summary['largest_tokens']}")
    print(f"Tokenizer model: {EMBEDDING_MODEL}")


if __name__ == "__main__":
    main()
