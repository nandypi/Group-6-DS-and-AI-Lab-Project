'''ingest markdown files and create embeddings for them and store them in a vector database'''

from pathlib import Path

import chromadb

from embedding import model
from chunker import chunk_text


DATA_DIR = Path("data")
DB_DIR = "chroma_db"
COLLECTION_NAME = "infosys_docs"


def main():

    print("Connecting to ChromaDB...")

    client = chromadb.PersistentClient(path=DB_DIR)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # Optional: remove old embeddings every run
    try:
        client.delete_collection(COLLECTION_NAME)
    except:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    markdown_files = list(DATA_DIR.glob("*.md"))

    print(f"Found {len(markdown_files)} markdown files.\n")

    total_chunks = 0

    for file in markdown_files:

        print(f"Reading {file.name}")

        text = file.read_text(encoding="utf-8")

        chunks = chunk_text(text)

        embeddings = model.encode(
            chunks,
            normalize_embeddings=True
        )

        ids = []
        metadatas = []

        for i in range(len(chunks)):
            ids.append(f"{file.stem}_{i}")

            metadatas.append(
                {
                    "source": file.name,
                    "chunk": i
                }
            )

        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings.tolist(),
            metadatas=metadatas
        )

        total_chunks += len(chunks)

        print(f"Stored {len(chunks)} chunks.")

    print("\nDone!")
    print(f"Total chunks stored: {total_chunks}")


if __name__ == "__main__":
    main()