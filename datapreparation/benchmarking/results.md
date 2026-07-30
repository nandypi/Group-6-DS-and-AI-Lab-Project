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