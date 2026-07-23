import os

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------
# Configuration
# ---------------------------------------------------

CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "finance_documents"

EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"

TOP_K = 3

# ---------------------------------------------------
# OpenAI Client
# ---------------------------------------------------

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ---------------------------------------------------
# ChromaDB
# ---------------------------------------------------

chroma_client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH
)

collection = chroma_client.get_collection(
    COLLECTION_NAME
)

# ---------------------------------------------------
# Get Query Embedding
# ---------------------------------------------------

def get_embedding(text):

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )

    return response.data[0].embedding

# ---------------------------------------------------
# Retrieve Documents
# ---------------------------------------------------

def retrieve(question):

    query_embedding = get_embedding(question)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K
    )

    return results

# ---------------------------------------------------
# Build Context
# ---------------------------------------------------

def build_context(results):

    context = ""

    for i in range(len(results["documents"][0])):

        meta = results["metadatas"][0][i]
        doc = results["documents"][0][i]

        context += f"""
==============================
FILE : {meta['filename']}
==============================

{doc}

"""

    return context

# ---------------------------------------------------
# Ask GPT
# ---------------------------------------------------

def ask_llm(question, context):

    prompt = f"""
You are a financial assistant.

Answer ONLY using the provided context.

If the answer is not present in the context, say:

"I could not find this information in the provided documents."

-------------------------
CONTEXT
-------------------------

{context}

-------------------------
QUESTION
-------------------------

{question}
"""

    response = client.chat.completions.create(

        model=LLM_MODEL,

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content

# ---------------------------------------------------
# Main
# ---------------------------------------------------

if __name__ == "__main__":

    while True:

        print("\n" + "="*80)

        question = input("Ask a question (type 'exit' to quit): ")

        if question.lower() == "exit":
            break

        print("\nGenerating query embedding...")

        results = retrieve(question)

        print("\n")
        print("="*80)
        print("TOP RETRIEVED DOCUMENTS")
        print("="*80)

        docs = results["documents"][0]
        metas = results["metadatas"][0]

        # distances may not be returned depending on Chroma version
        distances = results.get("distances", [[None]*len(docs)])[0]

        for i in range(len(docs)):

            print(f"\nRank #{i+1}")

            print(f"Filename : {metas[i]['filename']}")

            print(f"Company  : {metas[i]['company']}")

            if distances[i] is not None:
                print(f"Distance : {distances[i]}")

            print("\nPreview:\n")

            print(docs[i][:500])

            print("\n" + "-"*80)

        context = build_context(results)

        print("\n")
        print("="*80)
        print("CONTEXT SENT TO GPT")
        print("="*80)

        print(context[:2500])

        print("\n")
        print("="*80)
        print("GENERATING ANSWER")
        print("="*80)

        answer = ask_llm(question, context)

        print("\n")
        print(answer)