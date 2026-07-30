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
