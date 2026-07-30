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