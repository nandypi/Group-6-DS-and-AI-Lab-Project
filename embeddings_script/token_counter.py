"""Count embedding tokens for every approved Markdown file.

Flow: run this file -> find .md files in the five approved folders -> read one
file -> count tokens with the text-embedding-3-small tokenizer -> save all
results to token_counts.json -> print files above the API token limit.

For example, a report.md file produces one JSON entry with its path and token
count. ASSUMPTION: Markdown files use UTF-8 text encoding.
"""

import json
from pathlib import Path

import tiktoken


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = Path(__file__).resolve().parent / "token_counts.json"
EMBEDDING_MODEL = "text-embedding-3-small"
TOKEN_LIMIT = 8192

DATA_SOURCES = [
    PROJECT_ROOT / "data/yfinance/clean-mds",
    PROJECT_ROOT / "data/trendlyne/clean-mds",
    PROJECT_ROOT / "data/infosys_earning_calls_press_conf_fact_sheets_results/infosys_ir_earning_calls_clean_markdowns",
    PROJECT_ROOT / "data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages",
    PROJECT_ROOT / "data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files",
]


def find_markdown_files():
    """Return all approved Markdown files, including nested files.

    Called before counting. Example: returns [Path('.../report.md')].
    """
    markdown_files = []

    for source in DATA_SOURCES:
        if not source.is_dir():
            raise FileNotFoundError(f"ERROR: source folder not found: {source}")

        markdown_files.extend(source.rglob("*.md"))

    return sorted(markdown_files)


def count_tokens(encoding, file_path):
    """Return the token count for one complete Markdown file.

    Called once per file. Example: a small report can return 250 tokens.
    """
    text = file_path.read_text(encoding="utf-8")
    return len(encoding.encode(text))


def main():
    """Write complete token counts to JSON and print files above the API limit."""
    encoding = tiktoken.encoding_for_model(EMBEDDING_MODEL)
    markdown_files = find_markdown_files()
    results = []

    for file_path in markdown_files:
        relative_path = file_path.relative_to(PROJECT_ROOT).as_posix()
        token_count = count_tokens(encoding, file_path)
        results.append({"filepath": relative_path, "token_count": token_count})

    over_limit_files = [item for item in results if item["token_count"] > TOKEN_LIMIT]
    output = {
        "embedding_model": EMBEDDING_MODEL,
        "token_limit": TOKEN_LIMIT,
        "file_count": len(results),
        "over_limit_file_count": len(over_limit_files),
        "files": results,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as output_file:
        json.dump(output, output_file, indent=2)
        output_file.write("\n")

    print(f"Saved token counts for {len(results)} files to {OUTPUT_FILE.name}.")
    print(f"Files above {TOKEN_LIMIT} tokens: {len(over_limit_files)}")

    for item in over_limit_files:
        print(f"{item['filepath']}: {item['token_count']} tokens")


if __name__ == "__main__":
    main()
