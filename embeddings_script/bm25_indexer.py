"""Generate and save BM25 index for lexical search.

Flow: run this file -> find .md files in approved folders -> tokenize documents
-> build BM25 index -> save index and document mapping to disk.

The BM25 index enables fast lexical search that complements dense vector search
for hybrid retrieval.
"""

import argparse
import os
import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi
from dotenv import load_dotenv
from tqdm import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_FOLDER = Path(__file__).resolve().parent
BM25_INDEX_PATH = SCRIPT_FOLDER / "bm25_index.pkl"
BM25_DOCS_PATH = SCRIPT_FOLDER / "bm25_docs.pkl"

DATA_SOURCES = [
    PROJECT_ROOT / "data/yfinance/clean-mds",
    PROJECT_ROOT / "data/trendlyne/clean-mds",
    PROJECT_ROOT / "data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500",
    PROJECT_ROOT / "data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages",
    PROJECT_ROOT / "data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500",
]


def find_markdown_files():
    """Return all approved Markdown paths, including nested paths.

    Called before indexing starts. Example: returns [Path('.../report.md')].
    """
    markdown_files = []

    for source in DATA_SOURCES:
        if not source.is_dir():
            raise FileNotFoundError(f"ERROR: source folder not found: {source}")

        markdown_files.extend(source.rglob("*.md"))

    return sorted(markdown_files)


def simple_tokenize(text):
    """Tokenize text for BM25 using basic whitespace and lowercase.

    Called for every document. Example: "Hello World" becomes ["hello", "world"].
    """
    return text.lower().split()


def read_arguments():
    """Read the optional force flag to rebuild the index.

    Called before indexing. Example: --force rebuilds even if index exists.
    """
    parser = argparse.ArgumentParser(description="Build BM25 index for Markdown files.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="rebuild index even if it already exists",
    )
    return parser.parse_args()


def main():
    """Build BM25 index from all approved files and save to disk."""
    arguments = read_arguments()
    load_dotenv(PROJECT_ROOT / ".env")

    # Check if index already exists
    if BM25_INDEX_PATH.exists() and BM25_DOCS_PATH.exists() and not arguments.force:
        print(f"BM25 index already exists at {BM25_INDEX_PATH}")
        print("Use --force to rebuild.")
        return

    markdown_files = find_markdown_files()
    print(f"Found {len(markdown_files)} Markdown files.")

    # Store document metadata for retrieval
    doc_metadata = []
    tokenized_docs = []

    print("Processing documents...")
    for file_path in tqdm(markdown_files, desc="Tokenizing files"):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        tokens = simple_tokenize(text)
        tokenized_docs.append(tokens)

        relative_path = file_path.relative_to(PROJECT_ROOT).as_posix()
        doc_metadata.append({
            "filename": file_path.name,
            "filepath": relative_path,
            "source_folder": file_path.parents[1].name,
            "document_text": text,  # Store full text for context extraction
        })

    print("Building BM25 index...")
    bm25 = BM25Okapi(tokenized_docs)

    print(f"Saving BM25 index to {BM25_INDEX_PATH}...")
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(bm25, f)

    print(f"Saving document metadata to {BM25_DOCS_PATH}...")
    with open(BM25_DOCS_PATH, "wb") as f:
        pickle.dump(doc_metadata, f)

    print(f"✓ Completed: BM25 index built with {len(doc_metadata)} documents.")


if __name__ == "__main__":
    main()
