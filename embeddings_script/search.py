"""Search the persistent Chroma collection with one example question.

Flow: create an embedding for the example question -> search Chroma -> print
the closest stored documents. Example: an AI-risk question returns three files.
"""

import os

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

chroma = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = chroma.get_collection(
    os.getenv("COLLECTION_NAME", "finance_file_embeddings")
)

question = "What AI risks did Infosys mention?"

response = client.embeddings.create(
    model="text-embedding-3-small",
    input=question
)

query_embedding = response.data[0].embedding

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)

for doc, meta in zip(
    results["documents"][0],
    results["metadatas"][0]
):

    print("=" * 60)
    print(meta["filename"])
    print()
    print(doc[:500])
