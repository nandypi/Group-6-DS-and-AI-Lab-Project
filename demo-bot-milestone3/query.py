'''Test retrieval'''

import chromadb

from embedding import model


DB_DIR = "chroma_db"
COLLECTION_NAME = "infosys_docs"


def main():

    client = chromadb.PersistentClient(path=DB_DIR)

    collection = client.get_collection(COLLECTION_NAME)

    while True:

        question = input("\nAsk a question (or type 'exit'): ")

        if question.lower() == "exit":
            break

        query_embedding = model.encode(
            question,
            normalize_embeddings=True
        )

        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=3,
            include=["documents", "metadatas", "distances"]
        )

        print("\nTop Results\n")

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        for i in range(len(docs)):

            similarity = 1 - distances[i]

            print("=" * 70)
            print(f"Result {i + 1}")
            print(f"File      : {metas[i]['source']}")
            print(f"Chunk     : {metas[i]['chunk']}")
            print(f"Similarity: {similarity:.4f}\n")
            print(docs[i][:600])
            print()


if __name__ == "__main__":
    main()