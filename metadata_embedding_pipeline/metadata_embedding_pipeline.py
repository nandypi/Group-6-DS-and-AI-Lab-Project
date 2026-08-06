"""Embed YAML metadata from the v2 Markdown files into a new Chroma collection.

Unlike the existing index_documents.py which embeds full file content (both
YAML front matter and Markdown body), this pipeline embeds ONLY the YAML
metadata section.  The Markdown body is deliberately ignored.

Source directories (same five as index_documents.py; two swapped to _v2):
  data/yfinance/clean-mds
  data/trendlyne/clean-mds
  data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2  ← _v2
  data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages
  data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500_v2  ← _v2

Target Chroma collection: metadata_embeddings
Target Chroma database:   metadata_embedding_pipeline/chroma_db/

Embedding model: text-embedding-3-small  (identical to the existing pipeline)
Batch size:      20                       (identical to the existing pipeline)
Token limit:     8 191                    (identical to the existing pipeline)

Usage
-----
    python metadata_embedding_pipeline/metadata_embedding_pipeline.py
    python metadata_embedding_pipeline/metadata_embedding_pipeline.py --skip-existing
"""

import argparse
import os
import sys
from pathlib import Path

import chromadb
import tiktoken
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

# Allow sibling imports when this file is executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metadata_embedding_utils import (
    BATCH_SIZE,
    COLLECTION_NAME,
    DB_PATH,
    EMBEDDING_MODEL,
    MAX_EMBEDDING_TOKENS,
    PROJECT_ROOT,
    extract_yaml_front_matter,
    find_markdown_files,
    metadata_to_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def truncate_for_embedding(
    encoding: tiktoken.Encoding,
    text: str,
) -> tuple[str, int, bool]:
    """Return text that is safe to send to the embedding API.

    Called after metadata text is built.  Example: text exceeding 8 191
    tokens is shortened to its first 8 191 tokens and returns True to record
    that truncation occurred.  Mirrors truncate_for_embedding in
    index_documents.py.
    """
    token_ids = encoding.encode(text)
    original_token_count = len(token_ids)

    if original_token_count <= MAX_EMBEDDING_TOKENS:
        return text, original_token_count, False

    truncated_text = encoding.decode(token_ids[:MAX_EMBEDDING_TOKENS])
    return truncated_text, original_token_count, True


def get_embeddings(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Return one embedding vector for every text in the batch.

    Example: a batch of 20 metadata texts returns 20 embedding vectors.
    Mirrors get_embeddings in index_documents.py.
    """
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_arguments() -> argparse.Namespace:
    """Read the optional resume flag used after an interrupted indexing run.

    Example: --skip-existing embeds only files whose Chroma IDs are absent
    from the collection, allowing a safe resume.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Embed YAML metadata from v2 Markdown files into the "
            f"'{COLLECTION_NAME}' Chroma collection."
        )
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="skip Chroma IDs already stored from an interrupted run",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Embed every v2 file's YAML metadata and save vectors in chroma_db."""
    arguments = read_arguments()
    load_dotenv(PROJECT_ROOT / ".env")

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("ERROR: OPENAI_API_KEY is not set in .env.")

    markdown_files = find_markdown_files()
    print(f"Found {len(markdown_files)} Markdown files in v2 source directories.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    DB_PATH.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    encoding = tiktoken.encoding_for_model(EMBEDDING_MODEL)

    skipped_empty = 0

    for start_index in tqdm(
        range(0, len(markdown_files), BATCH_SIZE),
        desc="Embedding metadata batches",
    ):
        file_batch = markdown_files[start_index : start_index + BATCH_SIZE]

        # --skip-existing: query Chroma for only the IDs in this batch.
        if arguments.skip_existing:
            batch_ids = [
                file_path.relative_to(PROJECT_ROOT).as_posix()
                for file_path in file_batch
            ]
            stored_ids = set(collection.get(ids=batch_ids, include=[])["ids"])
            file_batch = [
                file_path
                for file_path in file_batch
                if file_path.relative_to(PROJECT_ROOT).as_posix() not in stored_ids
            ]

        if not file_batch:
            continue

        document_ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for file_path in file_batch:
            content = file_path.read_text(encoding="utf-8")

            # Extract and convert ONLY the YAML front matter; ignore the body.
            yaml_metadata = extract_yaml_front_matter(content)
            embedding_text = metadata_to_text(yaml_metadata)

            if not embedding_text.strip():
                # No usable metadata: skip rather than embed an empty string.
                skipped_empty += 1
                tqdm.write(f"  [skip – empty metadata] {file_path.name}")
                continue

            embedding_text, original_token_count, was_truncated = (
                truncate_for_embedding(encoding, embedding_text)
            )
            relative_path = file_path.relative_to(PROJECT_ROOT).as_posix()

            document_ids.append(relative_path)
            documents.append(embedding_text)
            metadatas.append(
                {
                    "filename": file_path.name,
                    "filepath": relative_path,
                    "source_folder": file_path.parents[1].name,
                    "original_token_count": original_token_count,
                    "embedded_token_count": len(encoding.encode(embedding_text)),
                    "was_truncated": was_truncated,
                }
            )

        if not document_ids:
            continue

        embeddings = get_embeddings(client, documents)
        collection.upsert(
            ids=document_ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    print(
        f"\nCompleted: {collection.count()} embeddings in '{COLLECTION_NAME}'."
    )
    if skipped_empty:
        print(f"Skipped (empty metadata): {skipped_empty}")


if __name__ == "__main__":
    main()
