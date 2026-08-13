"""Hybrid retrieval combining Chroma (dense) + BM25 (lexical) with RRF fusion.

Flow: receive a question -> embed it -> search Chroma (dense) -> search BM25
(lexical) -> combine rankings using Reciprocal Rank Fusion (RRF) -> return top 3
distinct documents -> remove YAML front matter -> ask LLM.

No reranking is performed. RRF naturally combines the strengths of dense and
lexical search by fusing their ranked lists.
"""

import os
import pickle
import time
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
import tiktoken

if __package__ in (None, ""):
    from reranker import split_front_matter
else:
    from embeddings_script.reranker import split_front_matter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_FOLDER = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

CHROMA_DB_PATH = str(PROJECT_ROOT / "chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "finance_file_embeddings")
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"
FINAL_DOCUMENT_COUNT = int(os.getenv("FINAL_DOCUMENT_COUNT", "3"))
LLM_MAX_INPUT_TOKENS = int(os.getenv("LLM_MAX_INPUT_TOKENS", "128000"))
RRF_K = 50  # Slightly lower than 60 to favor top results
TOP_K_PER_SOURCE = 12  # Slightly higher than 10
CHROMA_WEIGHT = 1.0  # No boost (keep embeddings and keywords balanced)

# BM25 index paths
BM25_INDEX_PATH = SCRIPT_FOLDER / "bm25_index.pkl"
BM25_DOCS_PATH = SCRIPT_FOLDER / "bm25_docs.pkl"

client = None
collection = None
_bm25 = None
_bm25_docs = None


def get_clients():
    """Create the external clients on first use, then reuse them."""
    global client, collection
    if client is None:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if collection is None:
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = chroma_client.get_collection(COLLECTION_NAME)
    return client, collection


def load_bm25_index():
    """Load BM25 index and document metadata from disk.

    Called on first use. Raises an error if the index has not been built.
    """
    global _bm25, _bm25_docs

    if _bm25 is not None and _bm25_docs is not None:
        return _bm25, _bm25_docs

    if not BM25_INDEX_PATH.exists():
        raise RuntimeError(
            f"BM25 index not found at {BM25_INDEX_PATH}. "
            "Run bm25_indexer.py to build the index first."
        )

    if not BM25_DOCS_PATH.exists():
        raise RuntimeError(
            f"BM25 documents not found at {BM25_DOCS_PATH}. "
            "Run bm25_indexer.py to build the index first."
        )

    with open(BM25_INDEX_PATH, "rb") as f:
        _bm25 = pickle.load(f)

    with open(BM25_DOCS_PATH, "rb") as f:
        _bm25_docs = pickle.load(f)

    return _bm25, _bm25_docs


def get_embedding(text):
    """Create the OpenAI embedding used for Chroma retrieval."""
    openai_client, _ = get_clients()
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def simple_tokenize(text):
    """Tokenize text for BM25 query matching."""
    return text.lower().split()


def retrieve_dense(question, top_k=None, timings=None):
    """Search Chroma for dense vector matches."""
    if top_k is None:
        top_k = TOP_K_PER_SOURCE
    
    _, chroma_collection = get_clients()

    embedding_start = time.perf_counter()
    query_embedding = get_embedding(question)
    if timings is not None:
        timings["embedding"] = time.perf_counter() - embedding_start

    retrieval_start = time.perf_counter()
    results = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )
    if timings is not None:
        timings["dense_retrieval"] = time.perf_counter() - retrieval_start

    # Convert Chroma results to ranked format
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    ranked_results = []
    for rank, (document, metadata, distance) in enumerate(
        zip(documents, metadatas, distances)
    ):
        ranked_results.append({
            "rank": rank,
            "filepath": metadata.get("filepath", metadata.get("filename", "")),
            "filename": metadata.get("filename", ""),
            "document": document,
            "metadata": metadata,
            "source": "dense",
            "score": 1 - distance,  # Convert distance to similarity
        })

    return ranked_results


def retrieve_lexical(question, top_k=None, timings=None):
    """Search BM25 for lexical matches."""
    if top_k is None:
        top_k = TOP_K_PER_SOURCE
    
    lexical_start = time.perf_counter()
    bm25, bm25_docs = load_bm25_index()

    query_tokens = simple_tokenize(question)
    scores = bm25.get_scores(query_tokens)

    # Get top_k results
    top_indices = sorted(
        range(len(scores)), key=lambda i: scores[i], reverse=True
    )[:top_k]

    if timings is not None:
        timings["lexical_retrieval"] = time.perf_counter() - lexical_start

    ranked_results = []
    for rank, idx in enumerate(top_indices):
        doc_meta = bm25_docs[idx]
        ranked_results.append({
            "rank": rank,
            "filepath": doc_meta["filepath"],
            "filename": doc_meta["filename"],
            "document": doc_meta["document_text"],
            "metadata": {
                "filename": doc_meta["filename"],
                "filepath": doc_meta["filepath"],
                "source_folder": doc_meta["source_folder"],
            },
            "source": "lexical",
            "score": scores[idx],
        })

    return ranked_results


def reciprocal_rank_fusion(dense_results, lexical_results, k=None, chroma_weight=1.0):
    """Combine two ranked lists using Reciprocal Rank Fusion with optional weighting.

    RRF formula: score = 1 / (k + rank)
    With weighting: dense_score = (1 / (k + rank)) * chroma_weight

    Results from both lists are scored and merged. Duplicates (same filepath)
    are combined by summing their RRF scores.
    """
    if k is None:
        k = RRF_K
    
    fusion_scores = {}
    seen_docs = {}

    # Process dense results
    for result in dense_results:
        filepath = result["filepath"]
        rrf_score = (1.0 / (k + result["rank"] + 1)) * chroma_weight
        if filepath not in fusion_scores:
            fusion_scores[filepath] = 0.0
            seen_docs[filepath] = result
        fusion_scores[filepath] += rrf_score

    # Process lexical results
    for result in lexical_results:
        filepath = result["filepath"]
        rrf_score = 1.0 / (k + result["rank"] + 1)
        if filepath not in fusion_scores:
            fusion_scores[filepath] = 0.0
            seen_docs[filepath] = result
        else:
            # For duplicates, keep the dense result (has full document)
            pass
        fusion_scores[filepath] += rrf_score

    # Sort by RRF score
    ranked_docs = sorted(
        fusion_scores.items(), key=lambda x: x[1], reverse=True
    )

    # Return merged results
    fused_results = []
    for rank, (filepath, rrf_score) in enumerate(ranked_docs):
        result = seen_docs[filepath].copy()
        result["rank"] = rank
        result["fusion_score"] = rrf_score
        result["sources"] = []
        if any(r["filepath"] == filepath and r["source"] == "dense" for r in dense_results):
            result["sources"].append("dense")
        if any(r["filepath"] == filepath and r["source"] == "lexical" for r in lexical_results):
            result["sources"].append("lexical")
        fused_results.append(result)

    return fused_results


def retrieve(question, timings=None):
    """Perform hybrid retrieval combining dense and lexical search with RRF."""
    # Get top N from each source using optimized parameters
    dense_results = retrieve_dense(question, top_k=TOP_K_PER_SOURCE, timings=timings)
    lexical_results = retrieve_lexical(question, top_k=TOP_K_PER_SOURCE, timings=timings)

    # Fuse rankings using RRF with optional Chroma weighting
    fusion_start = time.perf_counter()
    fused_results = reciprocal_rank_fusion(
        dense_results, lexical_results, k=RRF_K, chroma_weight=CHROMA_WEIGHT
    )
    if timings is not None:
        timings["rrf_fusion"] = time.perf_counter() - fusion_start

    return fused_results


def select_documents(fused_results, document_count=None):
    """Prepare selected documents by removing YAML front matter.

    Called after hybrid retrieval. Removes YAML metadata before the final
    context builder runs.
    """
    if document_count is None:
        document_count = FINAL_DOCUMENT_COUNT

    selected = []
    for result in fused_results[:document_count]:
        _, body, _ = split_front_matter(result["document"], result["filepath"])
        selected.append({
            "filename": result["filename"],
            "filepath": result["filepath"],
            "body": body,
            "fusion_score": result.get("fusion_score", 0.0),
            "sources": result.get("sources", []),
        })

    return selected


def build_context(selected_documents):
    """Build final context from complete bodies, without YAML or scores.

    Called immediately before the LLM request.
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
    """Print selected filenames and context size for the hybrid pipeline."""
    print("\n" + "=" * 80)
    print("HYBRID RETRIEVAL (CHROMA + BM25 with RRF)")
    print("=" * 80)
    for index, document in enumerate(selected_documents, start=1):
        sources = ", ".join(document.get("sources", []))
        score = document.get("fusion_score", 0.0)
        print(
            f"Rank #{index}: {document['filename']} "
            f"| sources=[{sources}] | rrf_score={score:.4f}"
        )
    print(f"Final context estimate: {count_tokens(context)} tokens")


def print_latency(timings):
    """Print the measured time for each pipeline stage and the full question."""
    print("\nPIPELINE LATENCY")
    print("-" * 80)
    labels = [
        ("embedding", "Embedding"),
        ("dense_retrieval", "Dense retrieval (Chroma)"),
        ("lexical_retrieval", "Lexical retrieval (BM25)"),
        ("rrf_fusion", "RRF fusion"),
        ("context", "Context preparation"),
        ("llm", "LLM request"),
        ("total", "Total question latency"),
    ]
    for key, label in labels:
        if key in timings:
            print(f"{label}: {timings[key]:.3f} seconds")


def answer_question(question):
    """Run the hybrid RAG pipeline and return the answer plus citations."""
    pipeline_start = time.perf_counter()
    timings = {}

    try:
        fused_results = retrieve(question, timings)
        if not fused_results:
            timings["total"] = time.perf_counter() - pipeline_start
            return {
                "answer": "I could not find this information in the provided documents.",
                "citations": [],
                "context": "",
                "timings": timings,
            }

        selected_documents = select_documents(fused_results)
    except RuntimeError as exc:
        raise RuntimeError(f"Hybrid retrieval failed: {exc}") from exc

    if not selected_documents:
        timings["total"] = time.perf_counter() - pipeline_start
        return {
            "answer": "I could not find this information in the provided documents.",
            "citations": [],
            "context": "",
            "timings": timings,
        }

    context_start = time.perf_counter()
    context = build_context(selected_documents)
    timings["context"] = time.perf_counter() - context_start

    llm_start = time.perf_counter()
    answer = ask_llm(question, context)
    timings["llm"] = time.perf_counter() - llm_start
    timings["total"] = time.perf_counter() - pipeline_start

    citations = []
    for document in selected_documents:
        filepath = document.get("filepath") or document.get("filename") or "unknown"
        citations.append({
            "filename": document.get("filename", filepath),
            "filepath": filepath,
            "score": document.get("fusion_score", 0.0),
        })

    return {
        "answer": answer,
        "citations": citations,
        "context": context,
        "timings": timings,
    }


def main():
    """Start the hybrid pipeline and reuse clients for all interactive questions."""
    print("Loading BM25 index and Chroma collection...")
    try:
        load_bm25_index()
        get_clients()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return

    while True:
        print("\n" + "=" * 80)
        question = input("Ask a question (type 'exit' to quit): ")
        if question.lower() == "exit":
            break

        pipeline_start = time.perf_counter()
        timings = {}
        print("\nSearching (Chroma + BM25 with RRF)...")

        try:
            fused_results = retrieve(question, timings)
            if not fused_results:
                print("No results found.")
                continue

            selected_documents = select_documents(fused_results)
            context_start = time.perf_counter()
            context = build_context(selected_documents)
            timings["context"] = time.perf_counter() - context_start

            print_selected_documents(selected_documents, context)

            llm_start = time.perf_counter()
            answer = ask_llm(question, context)
            timings["llm"] = time.perf_counter() - llm_start
            timings["total"] = time.perf_counter() - pipeline_start

            print("\n" + "=" * 80)
            print("ANSWER")
            print("=" * 80)
            print(answer)
            print_latency(timings)

        except Exception as exc:
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
