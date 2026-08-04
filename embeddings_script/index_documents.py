"""Create one vector for every approved Markdown file.

Flow: run this file -> find .md files in the five approved folders -> read one
file -> truncate only over-limit files -> create one OpenAI embedding -> upsert
it into Chroma.

For example, data/yfinance/clean-mds/example.md becomes one Chroma document.

Approved folder means one cleaned corpus folder used by retrieval today:
yfinance, Trendlyne, cleaned Infosys IR section chunks, cleaned NSE small whole
documents, and cleaned NSE long-document section chunks.

ASSUMPTION: the cleaned section chunk folders are the current source of truth
for long NSE documents and Infosys IR documents. Files over the embedding model
limit retain their first 8,191 tokens so every file has one vector.
"""

import argparse
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
import tiktoken
from tqdm import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_FOLDER = Path(__file__).resolve().parent
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "finance_file_embeddings")
DB_PATH = SCRIPT_FOLDER / "chroma_db"
EMBEDDING_MODEL = "text-embedding-3-small"
MAX_EMBEDDING_TOKENS = 8191
BATCH_SIZE = 20

DATA_SOURCES = [
    PROJECT_ROOT / "data/yfinance/clean-mds",
    PROJECT_ROOT / "data/trendlyne/clean-mds",
    PROJECT_ROOT / "data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500",
    PROJECT_ROOT / "data/nse_files_final/whole_document_cleaning/equal_or_less_than_10_pages",
    PROJECT_ROOT / "data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500",
]


def find_markdown_files():
    """Return all approved Markdown paths, including nested paths.

    Called before embedding starts. Example: returns [Path('.../report.md')].
    """
    markdown_files = []

    for source in DATA_SOURCES:
        if not source.is_dir():
            raise FileNotFoundError(f"ERROR: source folder not found: {source}")

        markdown_files.extend(source.rglob("*.md"))

    return sorted(markdown_files)


def read_arguments():
    """Read the optional resume flag used after an interrupted indexing run.

    Called before indexing. Example: --skip-existing processes only missing IDs.
    """
    parser = argparse.ArgumentParser(description="Embed the approved Markdown files.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="skip Chroma IDs already stored from an interrupted run",
    )
    return parser.parse_args()


def get_embeddings(client, texts):
    """Return one embedding for every complete file in a small batch.

    Called after a batch is prepared. Example: two files return two vectors.
    """
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def truncate_for_embedding(encoding, text):
    """Return text that is safe to send to the embedding API.

    Called after a file is read. Example: 9,000 tokens becomes its first 8,191
    tokens and returns True to record that it was truncated.
    """
    token_ids = encoding.encode(text)
    original_token_count = len(token_ids)

    if original_token_count <= MAX_EMBEDDING_TOKENS:
        return text, original_token_count, False

    truncated_text = encoding.decode(token_ids[:MAX_EMBEDDING_TOKENS])
    return truncated_text, original_token_count, True


def main():
    """Embed every approved file and save the vectors in embeddings_script/chroma_db."""
    arguments = read_arguments()
    load_dotenv(PROJECT_ROOT / ".env")

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("ERROR: OPENAI_API_KEY is not set in .env.")

    markdown_files = find_markdown_files()
    print(f"Found {len(markdown_files)} Markdown files.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    encoding = tiktoken.encoding_for_model(EMBEDDING_MODEL)

    for start_index in tqdm(
        range(0, len(markdown_files), BATCH_SIZE),
        desc="Embedding file batches",
    ):
        file_batch = markdown_files[start_index:start_index + BATCH_SIZE]

        if arguments.skip_existing:
            file_ids = [
                file_path.relative_to(PROJECT_ROOT).as_posix()
                for file_path in file_batch
            ]
            stored_ids = set(collection.get(ids=file_ids, include=[])["ids"])
            file_batch = [
                file_path
                for file_path in file_batch
                if file_path.relative_to(PROJECT_ROOT).as_posix() not in stored_ids
            ]

        if not file_batch:
            continue

        document_ids = []
        documents = []
        metadatas = []

        for file_path in file_batch:
            text = file_path.read_text(encoding="utf-8")
            text, original_token_count, was_truncated = truncate_for_embedding(
                encoding,
                text,
            )
            relative_path = file_path.relative_to(PROJECT_ROOT).as_posix()

            document_ids.append(relative_path)
            documents.append(text)
            metadatas.append({
                "filename": file_path.name,
                "filepath": relative_path,
                "source_folder": file_path.parents[1].name,
                "original_token_count": original_token_count,
                "embedded_token_count": len(encoding.encode(text)),
                "was_truncated": was_truncated,
            })

        embeddings = get_embeddings(client, documents)
        collection.upsert(
            ids=document_ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    print(f"Completed: {collection.count()} embeddings in '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()
