"""Run an interactive Chroma search with an optional BGE reranking branch.

Flow when ``DO_RERANKING=True``: receive a question -> embed it -> retrieve 25
candidates -> score metadata and body separately -> select the three highest
weighted scores -> ask ``gpt-4o-mini`` using their complete bodies.

Flow when ``DO_RERANKING=False``: receive a question -> embed it -> retrieve
the three closest Chroma documents -> remove their YAML front matter -> ask
``gpt-4o-mini`` using their complete bodies. The BGE model is not loaded.

ASSUMPTION: Chroma metadata contains ``filename`` and ``filepath`` for every
indexed document. The Markdown YAML front matter is the only metadata sent to
the reranker, and it is removed before final answering.
"""

import os
import time

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
import tiktoken
import numpy as np
import bm25s

from reranker import BGEReranker, score_document, split_front_matter


load_dotenv()

CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "finance_file_embeddings")
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"
RERANKING_RETRIEVAL_TOP_K = int(os.getenv("RERANKING_RETRIEVAL_TOP_K", "25"))
FINAL_DOCUMENT_COUNT = int(os.getenv("FINAL_DOCUMENT_COUNT", "3"))
METADATA_WEIGHT = float(os.getenv("METADATA_WEIGHT", "0.2"))
BODY_WEIGHT = float(os.getenv("BODY_WEIGHT", "0.8"))
LLM_MAX_INPUT_TOKENS = int(os.getenv("LLM_MAX_INPUT_TOKENS", "128000"))


def read_bool_setting(name, default=True):
    """Read a clear true/false environment setting.

    Called during startup. Example: ``DO_RERANKING=False`` returns ``False``.
    Invalid values use the supplied default so a typo cannot silently select a
    surprising pipeline.
    """
    value = os.getenv(name)
    if value is None:
        return default
    if value.strip().lower() in {"true", "1", "yes", "on"}:
        return True
    if value.strip().lower() in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"ERROR: {name} must be True or False.")


DO_RERANKING = read_bool_setting("DO_RERANKING", default=True)

client = None
collection = None

bm25_index = None
bm25_documents = None
bm25_metadatas = None


def get_clients():
    """Create the external clients on first use, then reuse them."""
    global client, collection
    if client is None:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if collection is None:
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = chroma_client.get_collection(COLLECTION_NAME)
    return client, collection


def initialize_bm25():
    """Load all Chroma documents and build a BM25 index once."""

    global bm25_index
    global bm25_documents
    global bm25_metadatas

    if bm25_index is not None:
        return

    _, chroma_collection = get_clients()

    print("Loading documents from Chroma for BM25...")

    all_data = chroma_collection.get(
        include=["documents", "metadatas"]
    )

    bm25_documents = all_data["documents"]
    bm25_metadatas = all_data["metadatas"]

    tokenized = bm25s.tokenize(bm25_documents)

    bm25_index = bm25s.BM25()
    bm25_index.index(tokenized)

    print(f"BM25 indexed {len(bm25_documents)} documents.")


def get_embedding(text):
    """Create the OpenAI embedding used for the initial Chroma retrieval."""
    openai_client, _ = get_clients()
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def retrieve(question, timings=None):
    """
    Exact Nearest Neighbor retrieval.

    Computes cosine similarity between the query embedding and every stored
    embedding, then returns the top-k most similar documents.
    """

    _, chroma_collection = get_clients()

    candidate_count = (
        RERANKING_RETRIEVAL_TOP_K
        if DO_RERANKING
        else FINAL_DOCUMENT_COUNT
    )

    embedding_start = time.perf_counter()
    query_embedding = get_embedding(question)
    if timings is not None:
        timings["embedding"] = time.perf_counter() - embedding_start

    retrieval_start = time.perf_counter()

    all_data = chroma_collection.get(
        include=[
            "embeddings",
            "documents",
            "metadatas",
        ]
    )

    embeddings = np.asarray(all_data["embeddings"], dtype=np.float32)
    query_embedding = np.asarray(query_embedding, dtype=np.float32)

    # cosine similarity

    embeddings /= np.linalg.norm(
        embeddings,
        axis=1,
        keepdims=True,
    )

    query_embedding /= np.linalg.norm(query_embedding)

    scores = embeddings @ query_embedding

    top_indices = np.argsort(scores)[::-1][:candidate_count]

    results = {
        "documents": [[all_data["documents"][i] for i in top_indices]],
        "metadatas": [[all_data["metadatas"][i] for i in top_indices]],
        "distances": [[1 - scores[i] for i in top_indices]],
    }

    if timings is not None:
        timings["chroma_retrieval"] = (
            time.perf_counter() - retrieval_start
        )

    return results

def retrieve_bm25(question, k):
    """Retrieve the top-k documents using BM25."""

    query_tokens = bm25s.tokenize(question)

    results, scores = bm25_index.retrieve(
        query_tokens,
        k=k,
    )

    indices = results[0]

    return {
        "documents": [
            bm25_documents[i]
            for i in indices
        ],
        "metadatas": [
            bm25_metadatas[i]
            for i in indices
        ],
        "scores": scores[0],
    }

def rerank_results(results, question, reranker, document_count=None):
    """Return distinct candidates sorted by weighted BGE relevance.

    Called after Chroma retrieval. Example: 25 candidates become at most three
    records for the answer pipeline. A recall benchmark can pass
    ``document_count=25`` to retain every reranked candidate for Recall@k.
    """
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    ranked = []
    seen_files = set()

    for document, metadata in zip(documents, metadatas):
        filepath = metadata.get("filepath", metadata.get("filename", ""))
        if filepath in seen_files:
            continue
        seen_files.add(filepath)
        scores = score_document(reranker, question, document)
        scores["filename"] = metadata.get("filename", filepath or "unknown")
        scores["filepath"] = filepath
        scores["final_score"] = (
            BODY_WEIGHT * scores["body_score"]
            + METADATA_WEIGHT * scores["metadata_score"]
        )
        ranked.append(scores)

    ranked.sort(key=lambda item: item["final_score"], reverse=True)
    if document_count is None:
        document_count = FINAL_DOCUMENT_COUNT
    return ranked[:document_count]


def select_without_reranking(results):
    """Prepare Chroma's original top documents without loading or scoring BGE.

    Called only when ``DO_RERANKING=False``. It preserves Chroma order and
    removes YAML metadata before the shared final-context builder runs.
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

    return selected[:FINAL_DOCUMENT_COUNT]


def build_context(selected_documents):
    """Build final context from complete bodies, without YAML or scores.

    Called immediately before the LLM request. Example: a selected record with
    ``filename='report.md'`` and ``body='Revenue rose.'`` produces a FILE label
    followed by ``Revenue rose.``.
    """
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
    """Ask GPT using complete selected bodies and reject oversized prompts."""
    prompt = make_prompt(question, context)
    token_count = count_tokens(prompt)
    if token_count > LLM_MAX_INPUT_TOKENS:
        raise ValueError(
            f"ERROR: final LLM request is {token_count} tokens, above the "
            f"configured limit of {LLM_MAX_INPUT_TOKENS}."
        )
    openai_client, _ = get_clients()
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def print_selected_documents(selected_documents, context):
    """Print selected filenames and context size for either pipeline."""
    print("\n" + "=" * 80)
    if DO_RERANKING:
        print("BGE RERANKED DOCUMENTS")
    else:
        print("CHROMA DOCUMENTS (NO RERANKING)")
    print("=" * 80)
    for index, document in enumerate(selected_documents, start=1):
        line = f"Rank #{index}: {document['filename']}"
        if "final_score" in document:
            line += (
                f" | score={document['final_score']:.4f} "
                f"(body={document['body_score']:.4f}, "
                f"metadata={document['metadata_score']:.4f})"
            )
        print(line)
    print(f"Final context estimate: {count_tokens(context)} tokens")


def print_latency(timings):
    """Print the measured time for each pipeline stage and the full question.

    Called after a question finishes, including when the final prompt is too
    large. The measurements exclude time spent waiting for the next question.
    """
    print("\nPIPELINE LATENCY")
    print("-" * 80)
    labels = [
        ("embedding", "Embedding"),
        ("chroma_retrieval", "Chroma retrieval"),
        ("reranking", "BGE reranking"),
        ("selection", "Direct selection"),
        ("context", "Context preparation"),
        ("llm", "LLM request"),
        ("total", "Total question latency"),
    ]
    for key, label in labels:
        if key in timings:
            print(f"{label}: {timings[key]:.3f} seconds")


def main():
    """Start the selected pipeline and reuse BGE for all interactive questions."""
    reranker = None
    if DO_RERANKING:
        reranker = BGEReranker(
            model_name=os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            max_tokens=int(os.getenv("RERANKER_MAX_TOKENS", "8190")),
        )
        
    initialize_bm25()

    while True:
        print("\n" + "=" * 80)
        question = input("Ask a question (type 'exit' to quit): ")
        if question.lower() == "exit":
            break
        
        # -------- TEST BM25 --------
        bm25_results = retrieve_bm25(question, 5)

        print("\nBM25 Results")
        for rank, metadata in enumerate(bm25_results["metadatas"], start=1):
            print(f"{rank}. {metadata['filename']}")

        pipeline_start = time.perf_counter()
        timings = {}
        if DO_RERANKING:
            print("\nGenerating query embedding and reranking candidates...")
            results = retrieve(question, timings)
            reranking_start = time.perf_counter()
            selected_documents = rerank_results(results, question, reranker)
            timings["reranking"] = time.perf_counter() - reranking_start
        else:
            print("\nGenerating query embedding and retrieving Chroma documents...")
            results = retrieve(question, timings)
            selection_start = time.perf_counter()
            selected_documents = select_without_reranking(results)
            timings["selection"] = time.perf_counter() - selection_start
        if not selected_documents:
            print("No documents were retrieved.")
            timings["total"] = time.perf_counter() - pipeline_start
            print_latency(timings)
            continue

        context_start = time.perf_counter()
        context = build_context(selected_documents)
        timings["context"] = time.perf_counter() - context_start
        print_selected_documents(selected_documents, context)
        print("\nGenerating answer...")
        llm_start = time.perf_counter()
        try:
            answer = ask_llm(question, context)
            print("\n" + answer)
        except ValueError as error:
            print(error)
        finally:
            timings["llm"] = time.perf_counter() - llm_start
            timings["total"] = time.perf_counter() - pipeline_start
            print_latency(timings)


if __name__ == "__main__":
    main()
