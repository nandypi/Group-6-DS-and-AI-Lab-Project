"""Run interactive or batch retrieval using HyDE (Hypothetical Document
Embeddings) against the existing Chroma collection.

HyDE flow: receive a question -> ask an LLM to write a plausible answer
passage (the "hypothetical document") -> embed that passage instead of the
raw question -> query Chroma with the hypothetical-document embedding ->
answer using the real retrieved documents.

This module is self-contained: it duplicates the small pieces of
embeddings_script/retriever.py it needs (client setup, front-matter
stripping, context building, answering) instead of importing that package,
so every HyDE-specific change stays inside this directory.

ASSUMPTION: Chroma metadata contains ``filename`` and ``filepath`` for every
indexed document, matching the collection built by
embeddings_script/index_documents.py.
"""

import os
import time
from pathlib import Path

import chromadb
import yaml
from dotenv import load_dotenv
from openai import OpenAI
import tiktoken


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

CHROMA_DB_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "finance_file_embeddings")

EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"
FINAL_DOCUMENT_COUNT = 3

client = None
collection = None


def get_clients():
    """Create the OpenAI and Chroma clients on first use, then reuse them."""
    global client, collection
    if client is None:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if collection is None:
        chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        collection = chroma_client.get_collection(COLLECTION_NAME)
    return client, collection


def generate_hypothetical_document(question):
    """Return one LLM-written passage that would plausibly answer the question.

    Called before embedding. Example: "What was Q1 revenue?" returns a short
    passage that reads like an excerpt from a financial disclosure.
    """
    openai_client, _ = get_clients()

    prompt = f"""You are a financial analyst writing an excerpt from a company disclosure.
The source could be a press release, an annual report section, a regulatory
filing, an earnings call transcript, or a research note — choose whichever
register the question itself implies (for example, a question about
"pillars of corporate strategy" or "capital allocation policy" reads like
annual-report or filing language, not an earnings call).

Write a short, plausible passage (3-5 sentences) that would directly answer
the question below, as if it were pulled from such a document. Stay generic
and structural where the real figure is unknown — do not invent specific
numbers, percentages, or dates. Do not mention that this is hypothetical or
that you are an AI.

QUESTION: {question}
"""

    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def get_embedding(text):
    """Create the OpenAI embedding for the given text."""
    openai_client, _ = get_clients()
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def retrieve(question, timings=None, candidate_count=FINAL_DOCUMENT_COUNT):
    """Return Chroma candidates retrieved with a HyDE query embedding.

    Generates one hypothetical document and embeds it in place of the raw
    question. Example: a vague question still retrieves documents that
    resemble its hypothetical answer.
    """
    _, chroma_collection = get_clients()

    hyde_start = time.perf_counter()
    hypothetical_document = generate_hypothetical_document(question)
    if timings is not None:
        timings["hyde_generation"] = time.perf_counter() - hyde_start

    embedding_start = time.perf_counter()
    query_embedding = get_embedding(hypothetical_document)
    if timings is not None:
        timings["embedding"] = time.perf_counter() - embedding_start

    retrieval_start = time.perf_counter()
    results = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=candidate_count,
    )
    if timings is not None:
        timings["chroma_retrieval"] = time.perf_counter() - retrieval_start

    return results, hypothetical_document


def split_front_matter(document):
    """Return ``(metadata_text, body, metadata)`` for one Markdown document.

    Mirrors embeddings_script/reranker.py's front-matter split so the final
    LLM context never includes YAML metadata.
    """
    if not document.startswith("---"):
        return "", document, {}

    lines = document.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", document, {}

    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        return "", document, {}

    metadata_text = "".join(lines[1:closing_index]).strip()
    body = "".join(lines[closing_index + 1:]).lstrip("\r\n")

    try:
        metadata = yaml.safe_load(metadata_text) or {}
        if not isinstance(metadata, dict):
            raise ValueError("front matter must contain a mapping")
    except (yaml.YAMLError, ValueError):
        return "", body, {}

    return metadata_text, body, metadata


def select_documents(results, limit=FINAL_DOCUMENT_COUNT):
    """Return distinct Chroma results with YAML front matter removed.

    Called after retrieval. Example: 10 candidates with one duplicate
    filepath become at most ``limit`` records ready for the LLM context.
    """
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    selected = []
    seen_files = set()

    for document, metadata in zip(documents, metadatas):
        filepath = metadata.get("filepath", metadata.get("filename", ""))
        if filepath in seen_files:
            continue
        seen_files.add(filepath)
        _, body, _ = split_front_matter(document)
        selected.append({
            "filename": metadata.get("filename", filepath or "unknown"),
            "filepath": filepath,
            "body": body,
        })

    return selected[:limit]


def build_context(selected_documents):
    """Build final answer context from complete bodies, without YAML."""
    sections = []
    for document in selected_documents:
        sections.append(
            "==============================\n"
            f"FILE : {document['filename']}\n"
            "==============================\n\n"
            f"{document['body']}\n"
        )
    return "\n".join(sections)


def count_tokens(text):
    """Estimate GPT input tokens using the encoding for the configured model."""
    encoding = tiktoken.encoding_for_model(LLM_MODEL)
    return len(encoding.encode(text))


def make_prompt(question, context):
    """Build the grounded answer prompt from the question and body-only context."""
    return f"""You are a financial assistant.

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


def ask_llm(question, context):
    """Ask GPT using the selected bodies as grounding context."""
    openai_client, _ = get_clients()
    prompt = make_prompt(question, context)
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def main():
    """Run an interactive HyDE question-and-answer loop."""
    while True:
        print("\n" + "=" * 80)
        question = input("Ask a question (type 'exit' to quit): ")
        if question.lower() == "exit":
            break

        timings = {}
        pipeline_start = time.perf_counter()

        print("\nGenerating hypothetical document and retrieving...")
        results, hypothetical_document = retrieve(question, timings)
        selected_documents = select_documents(results)

        print("\n" + "=" * 80)
        print("HYPOTHETICAL DOCUMENT (used for retrieval)")
        print("=" * 80)
        print(hypothetical_document)

        print("\n" + "=" * 80)
        print("SELECTED DOCUMENTS")
        print("=" * 80)
        for index, document in enumerate(selected_documents, start=1):
            print(f"Rank #{index}: {document['filename']}")

        if not selected_documents:
            print("No documents were retrieved.")
            continue

        context = build_context(selected_documents)
        print(f"\nFinal context estimate: {count_tokens(context)} tokens")

        print("\nGenerating answer...")
        llm_start = time.perf_counter()
        answer = ask_llm(question, context)
        timings["llm"] = time.perf_counter() - llm_start
        timings["total"] = time.perf_counter() - pipeline_start

        print("\n" + answer)

        print("\nPIPELINE LATENCY")
        print("-" * 80)
        for key, label in [
            ("hyde_generation", "Hypothetical document generation"),
            ("embedding", "Embedding"),
            ("chroma_retrieval", "Chroma retrieval"),
            ("llm", "LLM request"),
            ("total", "Total question latency"),
        ]:
            if key in timings:
                print(f"{label}: {timings[key]:.3f} seconds")


if __name__ == "__main__":
    main()
