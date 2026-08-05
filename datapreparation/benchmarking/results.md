# With reranking

The reranking results CSV is complete: 50/50 successful, with no errors.

| Metric | Result |
|---|---:|
| Recall@3 | 29/50 — 58% |
| Recall@5 | 32/50 — 64% |
| Recall@7 | 32/50 — 64% |
| Expected source in ranks 8–25 | 7/50 — 14% |
| Expected source absent from top 25 | 11/50 — 22% |

The reranker improved the top results:

- 29 questions had the expected source in the top 3.
- Three more appeared at ranks 4–5.
- None appeared specifically at ranks 6–7.
- Seven were retrieved by Chroma in the top 25 but not promoted into the top 7.
- Eleven were not in Chroma’s top 25 at all, so reranking could not recover them.

Latency:

- Average total: **245.342 seconds/question** (~4.1 minutes)
- Median: **229.987 seconds**
- Range: **185.544–454.849 seconds**
- Total sequential runtime: **204.45 minutes**

Almost all latency is BGE reranking:

```text
Embedding:          1.236 s average
Chroma retrieval:   0.089 s average
BGE reranking:    243.994 s average
```

By source category, Recall@3 was:

| Source | Recall@3 |
|---|---:|
| NSE ≤10 pages | 9/10 |
| NSE >10 pages | 15/30 |
| IR | 2/5 |
| Trendlyne | 2/4 |
| Yahoo Finance | 1/1 |

Compared with the saved non-reranking benchmark, Recall@3 rose from **40% (20/50)** to **58% (29/50)**. This is directional rather than a perfectly controlled comparison, because non-reranking searched top 10 whereas this reranking run retrieved top 25 before ranking them.

## meaning of last 2 lines:

```text
-Seven were retrieved by Chroma in the top 25 but not promoted into the top 7.
- Eleven were not in Chroma’s top 25 at all, so reranking could not recover them
```

For each question, we know the expected source document from the test CSV.

The flow is:

```text
Expected source document
        ↓
Chroma retrieves 25 candidates
        ↓
BGE reranks those same 25 candidates
        ↓
We check whether the expected source is in ranks 3, 5, or 7
```

So:

- **7 questions: source was in Chroma’s initial top 25, but BGE placed it between ranks 8 and 25.**
  The correct document was available to the reranker, but its body/metadata score was not high enough to enter the top 7.

- **11 questions: source was absent from the 25 candidates Chroma returned.**
  BGE never saw the expected document for those questions. A reranker only changes the order of retrieved candidates; it cannot introduce a document outside Chroma’s top-25 shortlist.

For example:

```text
Expected source: FY26-Q1-earningscall.md

Chroma top 25:
1. annual-report.md
2. q4-results.md
...
25. another-document.md

→ Expected source absent
→ BGE has nothing to score for FY26-Q1-earningscall.md
→ It cannot be moved into the final top 3/5/7
```

Whereas, for the first case:

```text
Chroma top 25 includes:
...
12. expected-source.md
...

After BGE reranking:
...
10. expected-source.md

→ Chroma found it
→ BGE considered it
→ But it still did not rank within the top 7
```

This distinction helps diagnose the next improvement:

- **Absent from top 25** → improve initial retrieval/indexing/query representation.
- **Present in top 25 but low after reranking** → investigate BGE scoring, body length/truncation, metadata weighting, or whether the CSV’s expected source is the only valid answer source.

# With reranking (MiniLM)

From `data/infosys_rag_test_dataset_50_queries_with_minilm_reranking_top_25_recall_results.csv`,
produced by `datapreparation/benchmarking/run_minilm_reranking_recall_benchmark.py`: 50/50
successful, no errors.

This pipeline is identical to the BGE reranking pipeline above — Chroma
retrieves 25 candidates, then a cross-encoder scores body and YAML metadata
independently and combines them as `0.8 × body_score + 0.2 × metadata_score`
— except the cross-encoder is `cross-encoder/ms-marco-MiniLM-L-6-v2`
(~22M parameters) instead of `BAAI/bge-reranker-v2-m3` (~568M parameters),
via `embeddings_script/reranker_minilm.py`.

| Metric | Result |
|---|---:|
| Recall@3 | 25/50 — 50% |
| Recall@5 | 27/50 — 54% |
| Recall@7 | 30/50 — 60% |
| Recall@9 | 34/50 — 68% |

Latency:

- Average total: **5.838 seconds/question**
- Median: **5.834 seconds**
- Range: **3.336–17.775 seconds**
- Total sequential runtime: **4.87 minutes** (versus BGE's 204.45 minutes)

```text
Embedding:        0.820 s average
Chroma retrieval:  0.025 s average
MiniLM reranking:  4.989 s average
```

MiniLM reranking runs roughly **42× faster per question** than BGE
(5.838 s vs. 245.342 s average), because it scores 50 much cheaper
cross-encoder comparisons per question (22M-parameter model, 512-token input
cap) instead of BGE's 568M-parameter model with an 8,190-token cap.

**This table is not a strictly controlled comparison with the BGE reranking
results above.** The test dataset's expected-source column was split into
`old_source_document` / `current_source_document` after the BGE benchmark
was run (35 of 50 rows differ between the two). BGE's recall numbers above
were scored against the old labels; MiniLM's recall numbers here were scored
against the corrected `current_source_document` labels. Part of the recall
gap between the two tables may therefore reflect the label correction rather
than a pure model-quality difference. A same-labels rerun of both rerankers
would be needed for an exact head-to-head comparison.

# without reranking

Yes. From `data/infosys_rag_test_dataset_50_queries_without_reranking_results.csv`:

| Metric | Without reranking |
|---|---:|
| Successful questions | 50/50 |
| Recall@3 | 20/50 — 40% |
| Recall@5 | 25/50 — 50% |
| Recall@7 | 27/50 — 54% |
| Average total latency | 6.251 seconds/question |

That pipeline retrieves the top 10 Chroma candidates, calculates recall from those ranks, then sends Chroma’s top 3 directly to `gpt-4o-mini`.

For reference, the top-25 reranking run reached Recall@3 **58%**, Recall@5 **64%**, and Recall@7 **64%**, but averaged **245.342 seconds/question**.

# without reranking, with HyDE

From `data/infosys_rag_test_dataset_50_queries_with_hyde_results.csv` (produced by `datapreparation/benchmarking/run_hyde_benchmark.py`, which imports retrieval and answering logic from `hyde_script/hyde_retriever.py`): 50/50 successful, no errors.

| Metric | Without reranking + HyDE |
|---|---:|
| Successful questions | 50/50 |
| Recall@3 | 20/50 — 40% |
| Recall@5 | 21/50 — 42% |
| Recall@7 | 23/50 — 46% |
| Average total latency | 9.320 seconds/question |
| Median total latency | 7.200 seconds |
| Latency range | 4.095–29.591 seconds |
| Total sequential runtime | ~7.77 minutes |

This pipeline generates one hypothetical answer passage per question with `gpt-4o-mini`, embeds that passage instead of the raw question, retrieves the top 10 Chroma candidates with that embedding, calculates recall from those ranks, then sends the top 3 directly to `gpt-4o-mini` for the final answer — otherwise identical to the non-reranking pipeline above.

Latency breakdown:

```text
Hypothetical document generation: 3.595 s average
Embedding:                        0.835 s average
Chroma retrieval:                 0.015 s average
Context preparation:              0.024 s average
LLM answer:                       4.848 s average
```

By source category, Recall@3 was:

| Source | Recall@3 |
|---|---:|
| NSE ≤10 pages | 9/10 |
| NSE >10 pages | 9/30 |
| IR | 0/5 |
| Trendlyne | 1/4 |
| Yahoo Finance | 1/1 |

Compared with the plain non-reranking baseline, single-pass HyDE **did not improve recall** on this test set: Recall@3 tied at **40% (20/50)**, Recall@5 fell from **50% (25/50)** to **42% (21/50)**, and Recall@7 fell from **54% (27/50)** to **46% (23/50)**.

Two contributors, investigated directly:

- **Query style mismatch.** This test set's questions are unusually entity-heavy — "Sentara partnership," "GlobalFoundries," "IHH Healthcare," "Everest Group's Adobe Services PEAK Matrix" — and the source documents are literal press releases and filings that repeat those same proper nouns. The raw question embedding already matches that vocabulary almost exactly. A generated hypothetical passage, even a well-written one, paraphrases and sometimes drops or genericizes those exact terms, which can move the query vector away from the literal match that would otherwise rank the correct document highly. HyDE was originally designed for underspecified queries with little vocabulary overlap with the answer; it has less to add when the question already contains the answer's key terms.
- **Mislabeled source document.** `data/infosys_rag_test_dataset_50_queries.csv` has at least one row (id 2) where `source_document` repeats row 1's source file for an unrelated question ("Topaz Fabric" vs. "Sentara partnership") — a guaranteed recall miss for any retrieval method.

During development, two alternative combination strategies were tested experimentally against a cached embedding sweep (not part of the shipped pipeline, since the goal here was to keep HyDE simple): averaging the HyDE and raw-question embeddings into one vector performed *worse* than the raw question alone at every blend weight tried (0.0 pure baseline scored highest at Recall@3 20/50, Recall@5 25/50; every weight above 0 was flat or lower). Reciprocal Rank Fusion of two independent Chroma queries (one on the raw question, one on the HyDE passage) scored the highest of everything tested — Recall@3 24/50 (48%), Recall@5 27/50 (54%), Recall@7 29/50 (58%) — because it lets the literal-question match stay intact when it's already strong, instead of diluting it with a single hallucinated passage. That fusion approach was not adopted here per project direction to keep this benchmark to simple, single-pass HyDE, but it's the concrete next step if HyDE recall needs to improve further without adding a reranker.

The NSE >10 pages category remains the weakest for every pipeline tested (baseline 9/30, HyDE 9/30, reranking 15/30) — this looks like a chunking/indexing limitation (long reports split into many similarly-named `group_NNN.md` sections) rather than something a smarter query-side technique alone can fix.

# MiniLM full pipeline — baseline (TOP_K=25, top-3 context)

From `data/infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_baseline_results.csv`,
produced by `datapreparation/benchmarking/run_minilm_reranking_with_answers_benchmark.py` with
`RERANKING_RETRIEVAL_TOP_K=25` and `FINAL_DOCUMENT_COUNT=3`: 50/50 successful, no errors.

This is the combined retrieve → MiniLM rerank → gpt-4o-mini answer pipeline, run to establish
a direct baseline for generation-quality metrics (ROUGE-L, semantic similarity) under the same
parameters as the MiniLM recall-only benchmark above.

| Metric | Result |
|---|---:|
| Recall@3 | 25/50 — 50% |
| Recall@5 | 27/50 — 54% |
| Recall@7 | 30/50 — 60% |
| Recall@9 | 34/50 — 68% |
| Hit rate (source in top-25) | 35/50 — 70% |
| MRR | 0.4500 |
| ROUGE-L F1 (mean, vs reference answers) | 0.3177 |
| Semantic similarity (mean, MiniLM bi-encoder) | 0.7002 |

Latency:

- Average total: **9.485 seconds/question**
- Median: **9.099 seconds**
- Range: **6.796–16.486 seconds**
- Total sequential runtime: **~7.9 minutes**

```text
Embedding:        0.473 s average
Chroma retrieval: 0.056 s average
MiniLM reranking: 5.906 s average
LLM answer:       3.031 s average
```

# MiniLM full pipeline — improved (TOP_K=40, top-5 context)

From `data/infosys_rag_test_dataset_50_queries_with_minilm_reranking_with_answers_improved_results.csv`,
produced by `datapreparation/benchmarking/run_minilm_reranking_with_answers_benchmark.py` with
`RERANKING_RETRIEVAL_TOP_K=40` and `FINAL_DOCUMENT_COUNT=5`: 50/50 successful, no errors.

Motivation: the baseline hit rate of 70% meant ~30% of questions had the correct source absent
from Chroma's top-25 candidates. Widening the candidate pool to 40 gives the reranker more
documents to work with, and passing the top-5 (instead of top-3) to the LLM reduces the chance
that a correctly-retrieved document is cut from the context window.

| Metric | Result |
|---|---:|
| Recall@3 | 27/50 — 54% |
| Recall@5 | 29/50 — 58% |
| Recall@7 | 31/50 — 62% |
| Recall@9 | 32/50 — 64% |
| Hit rate (source in top-40) | 40/50 — 80% |
| MRR | 0.4480 |
| ROUGE-L F1 (mean) | 0.3566 |
| Semantic similarity (mean) | 0.7499 |

Latency:

- Average total: **12.578 seconds/question**
- Median: **12.572 seconds**
- Range: **7.153–35.185 seconds**
- Total sequential runtime: **~10.5 minutes**

```text
Embedding:        0.533 s average
Chroma retrieval: 0.063 s average
MiniLM reranking: 8.549 s average  (more candidates → more cross-encoder calls)
LLM answer:       2.928 s average
```

Compared with the baseline, Recall@3 improved from 50% to 54% and ROUGE-L rose from 0.3177 to
0.3566 (+12%). The hit rate ceiling moved from 70% to 80%, recovering 5 more questions. However,
Recall@9 slightly dropped (68% → 64%) because the larger candidate pool shifts the correct
document deeper in the reranked list for some questions.

# Hybrid BM25+dense — MiniLM reranker (TOP_K=40, top-5 context)

From `data/infosys_rag_test_dataset_50_queries_with_hybrid_bm25_results.csv`, produced by
`datapreparation/benchmarking/run_hybrid_bm25_benchmark.py` with `RERANKING_RETRIEVAL_TOP_K=40`
and `FINAL_DOCUMENT_COUNT=5`: 50/50 successful, no errors.

**Motivation:** the failing questions in the dense-only runs (IDs 24, 25, 26, 27, 35 — share
buyback, ADR listings, employee count, exports %, CSR spend) are all keyword-heavy fact lookups.
Dense embedding search is weak for these because it operates on semantic similarity rather than
exact lexical match. BM25 scores exact keyword overlap directly and recovers these cases.

**Method:** for each query, retrieve top-40 candidates from Chroma (dense) and top-40 from a
BM25 index built over all 1877 Chroma documents (sparse/keyword). Merge both ranked lists using
Reciprocal Rank Fusion (`score(d) = 1/(60 + rank_dense) + 1/(60 + rank_bm25)`, summing only the
terms where each document appears). Pass the merged top-40 to MiniLM for reranking, then send
the top-5 to gpt-4o-mini. The BM25 index is built once at startup from the same text stored in
Chroma — no re-embedding or additional files required.

| Metric | Result |
|---|---:|
| Recall@3 | 25/50 — 50% |
| Recall@5 | 29/50 — 58% |
| Recall@7 | 32/50 — 64% |
| Recall@9 | 35/50 — 70% |
| Hit rate (source in merged top-40) | 43/50 — 86% |
| MRR | 0.4445 |
| ROUGE-L F1 (mean) | 0.3692 |
| Semantic similarity (mean) | 0.7521 |

Latency:

- Average total: **8.429 seconds/question** (faster than the dense-only improved run)
- Median: **7.976 seconds**
- Range: **6.652–15.156 seconds**
- Total sequential runtime: **~7.0 minutes**

```text
Embedding:        0.365 s average
Chroma retrieval: 0.012 s average
BM25 retrieval:   0.013 s average  (in-memory scoring, negligible)
RRF merge:        <0.001 s average
MiniLM reranking: 5.053 s average
LLM answer:       2.972 s average
```

BM25 and RRF together add under 15 ms per query — effectively free. The reranking step is faster
than the dense-only improved run (5.053 s vs. 8.549 s average) because the merged candidate list,
after deduplication, is often smaller than 40, reducing cross-encoder calls.

**Key finding:** BM25 hybrid raises the hit rate from 80% to 86% (+6pp) and pushes ROUGE-L to
0.3692 and semantic similarity to 0.7521 — the best generation scores of any pipeline tested.
Recall@3 stays at 50% (same as the baseline) because BM25 recovers the correct documents but
MiniLM does not always promote them to rank 1-3; they appear more often at ranks 4-9 (recall@7
64%, recall@9 70%). The remaining 14% miss rate (7 questions) represents cases where the correct
source is absent from both dense and BM25 top-40 results.

# Cross-pipeline comparison

All pipelines on the same 50-question test set, scored against `current_source_document` labels
(re-chunked corpus). Generation metrics use `RAGAS/reference_answers_template.csv` as plain
reference data (no RAGAS library; ROUGE-L via `rouge-score`, semantic similarity via local
`sentence-transformers/all-MiniLM-L6-v2` bi-encoder).

| Pipeline | Recall@3 | Recall@5 | Recall@7 | Recall@9 | Hit rate | MRR | ROUGE-L | Sem. sim. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| No reranking (top-3 Chroma) | 40% | 50% | 54% | — | — | — | 0.2758 | 0.6263 |
| HyDE, no reranking (top-3 Chroma) | 40% | 42% | 46% | — | — | — | 0.2643 | 0.5562 |
| BGE reranker (TOP_K=25, top-3) | 58% | 64% | 64% | — | 78% | 0.5182 | — | — |
| MiniLM reranker (TOP_K=25, top-3) | 50% | 54% | 60% | 68% | 70% | 0.4500 | 0.3177 | 0.7002 |
| MiniLM reranker (TOP_K=40, top-5) | 54% | 58% | 62% | 64% | 80% | 0.4480 | 0.3566 | 0.7499 |
| **Hybrid BM25+dense (TOP_K=40, top-5)** | **50%** | **58%** | **64%** | **70%** | **86%** | **0.4445** | **0.3692** | **0.7521** |

Notes:
- BGE generation metrics were not collected (latency ~245 s/question made a full 50-question answer run impractical).
- No-reranking and HyDE recall@9 and hit rate were not collected (those benchmarks retrieved only top-10 from Chroma).
- The BGE vs MiniLM comparison is not fully controlled (different source-document labels; see MiniLM section above).
