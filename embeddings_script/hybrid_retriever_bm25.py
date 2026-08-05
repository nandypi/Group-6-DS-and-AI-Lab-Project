"""BM25 + dense vector hybrid retrieval using Reciprocal Rank Fusion (RRF).

Builds a BM25 index over all Chroma documents at startup, then for each
query merges BM25 and Chroma dense rankings via RRF before passing the
combined candidate list to a cross-encoder reranker (MiniLM or BGE).

WHY BM25 HELPS: Dense embedding search underperforms on exact-keyword queries
such as "CSR spend", "share buyback", "ADR listing", or "exports percentage"
because embedding similarity is semantic rather than lexical. BM25 scores
those terms directly, recovering documents that the embedding model ranks too
low or misses entirely (i.e. the ~20-30% hit-rate gap seen in benchmarks).

RRF FORMULA: score(d) = sum(1 / (k + rank_i(d)))  where k=60 is the standard
constant. A document retrieved by both methods accumulates score from both
rankings, naturally boosting candidates where the two systems agree, without
requiring any score normalisation across retrieval systems.

USAGE:
    from hybrid_retriever_bm25 import HybridBM25Retriever
    import retriever  # existing pipeline module

    os.chdir(EMBEDDINGS_SCRIPT)
    _, chroma_collection = retriever.get_clients()

    hybrid = HybridBM25Retriever(chroma_collection)   # builds BM25 index once

    timings = {}
    results = hybrid.retrieve(
        query=row["query"],
        chroma_collection=chroma_collection,
        get_embedding_fn=retriever.get_embedding,
        top_k=40,
        timings=timings,
    )
    # results is compatible with retriever.rerank_results()
"""

import os
import re
import time

os.environ.setdefault("USE_TF", "0")

RRF_K = 60  # Standard RRF constant; higher value = smoother rank blending


class HybridBM25Retriever:
    """Loads all Chroma documents into a BM25 index and provides hybrid retrieval.

    Instantiate once at benchmark startup — loading 1877 documents and building
    the BM25 index takes roughly 1-2 seconds. After that each per-query BM25
    scoring call is sub-second.
    """

    def __init__(self, chroma_collection):
        """Load all documents from Chroma and build the BM25 index."""
        from rank_bm25 import BM25Okapi

        result = chroma_collection.get(include=["documents", "metadatas"])
        self._ids = result["ids"]
        self._documents = result["documents"]
        self._metadatas = result["metadatas"]

        # Tokenise every document for BM25 (includes YAML front matter so
        # document_name, section_title, and topics are all searchable).
        tokenized = [self._tokenize(doc) for doc in self._documents]
        self._bm25 = BM25Okapi(tokenized)
        print(
            f"HybridBM25Retriever: index built over {len(self._documents)} documents."
        )

    @staticmethod
    def _tokenize(text):
        """Lowercase and split on non-alphanumeric characters for BM25."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def _bm25_top_k(self, query, top_k):
        """Return (chroma_id, document, metadata) tuples ranked by BM25 score."""
        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]
        return [
            (self._ids[i], self._documents[i], self._metadatas[i])
            for i in ranked_indices
        ]

    def retrieve(self, query, chroma_collection, get_embedding_fn, top_k, timings=None):
        """Return a Chroma-compatible result dict with RRF-merged candidates.

        Timing keys written into `timings` (all in seconds):
          "embedding"        - time to call get_embedding_fn
          "chroma_retrieval" - time for the dense Chroma query
          "bm25_retrieval"   - time for BM25 scoring across all 1877 documents
          "rrf_merge"        - time to merge and re-rank via RRF

        The returned dict has the same shape as chromadb Collection.query():
          {"documents": [[...]], "metadatas": [[...]]}
        and is therefore directly compatible with retriever.rerank_results().
        """
        # 1. Embed the query (same OpenAI model as the existing pipeline)
        t0 = time.perf_counter()
        query_embedding = get_embedding_fn(query)
        if timings is not None:
            timings["embedding"] = time.perf_counter() - t0

        # 2. Dense Chroma retrieval
        t0 = time.perf_counter()
        dense_result = chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas"],
        )
        if timings is not None:
            timings["chroma_retrieval"] = time.perf_counter() - t0

        # 3. BM25 sparse retrieval
        t0 = time.perf_counter()
        bm25_results = self._bm25_top_k(query, top_k)
        if timings is not None:
            timings["bm25_retrieval"] = time.perf_counter() - t0

        # 4. Reciprocal Rank Fusion
        t0 = time.perf_counter()
        merged = self._rrf_merge(dense_result, bm25_results, top_k)
        if timings is not None:
            timings["rrf_merge"] = time.perf_counter() - t0

        return merged

    def _rrf_merge(self, dense_result, bm25_results, top_k):
        """Merge dense and BM25 rankings via Reciprocal Rank Fusion.

        Documents appearing in both rankings accumulate score from both; those
        appearing in only one ranking still receive a partial RRF score. The
        merged list is truncated to top_k.
        """
        rrf_scores = {}   # chroma_id -> accumulated RRF score
        docs_by_id = {}   # chroma_id -> (document_text, metadata)

        # Contribute dense ranks
        dense_ids = dense_result.get("ids", [[]])[0]
        dense_docs = dense_result.get("documents", [[]])[0]
        dense_metas = dense_result.get("metadatas", [[]])[0]
        for rank, (doc_id, doc, meta) in enumerate(
            zip(dense_ids, dense_docs, dense_metas), start=1
        ):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
            docs_by_id[doc_id] = (doc, meta)

        # Contribute BM25 ranks
        for rank, (doc_id, doc, meta) in enumerate(bm25_results, start=1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
            docs_by_id[doc_id] = (doc, meta)

        # Sort by combined RRF score and return top_k in Chroma-compatible format
        sorted_ids = sorted(rrf_scores, key=lambda i: rrf_scores[i], reverse=True)[
            :top_k
        ]
        return {
            "documents": [[docs_by_id[i][0] for i in sorted_ids]],
            "metadatas": [[docs_by_id[i][1] for i in sorted_ids]],
        }
