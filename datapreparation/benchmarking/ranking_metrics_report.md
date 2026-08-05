# Ranking-quality metrics (MRR and rank statistics)

Computed from the already-saved ranked-documents columns in the
result CSVs. No pipeline was rerun and no input CSV was modified.

- **MRR** (Mean Reciprocal Rank): mean of `1/rank`, scored 0 when the
  expected source is absent from the top 25. Rewards placing the
  correct document as close to rank 1 as possible, unlike recall@k
  which only asks whether it is within the first k.
- **Mean/median rank (when found)**: how deep into the ranking the
  correct document typically sits, among the questions where it was
  retrieved at all.
- **Hit rate@25**: the fraction of questions where the expected source
  appears anywhere in Chroma's original top-25 candidates — the recall
  ceiling reranking alone cannot exceed.

| Pipeline | Questions | MRR | Mean rank (found) | Median rank (found) | Hit rate@25 |
|---|---:|---:|---:|---:|---:|
| BGE reranker (bge-reranker-v2-m3) | 50 | 0.4493 | 2.71 | 2.0 | 70% |
| MiniLM reranker (ms-marco-MiniLM-L-6-v2) | 50 | 0.3400 | 3.26 | 2.0 | 54% |
| MiniLM reranker — baseline (TOP_K=25, top-3 context, gpt-4o-mini) | 50 | 0.3400 | 3.26 | 2.0 | 54% |
| MiniLM reranker — improved (TOP_K=40, top-5 context, gpt-4o-mini) | 50 | 0.3460 | 5.55 | 2.0 | 62% |
| Hybrid BM25+dense — MiniLM reranker (TOP_K=40, top-5 context, gpt-4o-mini) | 50 | 0.3457 | 7.39 | 3.5 | 76% |

## Lowest reciprocal-rank questions per pipeline

### BGE reranker (bge-reranker-v2-m3)

- ID 11 (rank not in top 25): How does Infosys describe its AI strategy and its transition from AI experimentation to enterprise-scale AI adoption?
- ID 17 (rank not in top 25): What did Infosys report about client demand for AI advisory and AI transformation services?
- ID 23 (rank not in top 25): What is Infosys' capital allocation policy beginning FY2025?
- ID 27 (rank not in top 25): What percentage of Infosys' revenue comes from exports?
- ID 29 (rank not in top 25): What grievance redressal and employee well-being mechanisms does Infosys provide?

### MiniLM reranker (ms-marco-MiniLM-L-6-v2)

- ID 11 (rank not in top 25): How does Infosys describe its AI strategy and its transition from AI experimentation to enterprise-scale AI adoption?
- ID 12 (rank not in top 25): What enterprise AI traction has Infosys reported across top clients, AI projects, and new service offerings?
- ID 17 (rank not in top 25): What did Infosys report about client demand for AI advisory and AI transformation services?
- ID 18 (rank not in top 25): What were the major financial highlights of Infosys for FY2026?
- ID 21 (rank not in top 25): How does Infosys define its AI-first strategy and Responsible AI framework?

### MiniLM reranker — baseline (TOP_K=25, top-3 context, gpt-4o-mini)

- ID 11 (rank not in top 25): How does Infosys describe its AI strategy and its transition from AI experimentation to enterprise-scale AI adoption?
- ID 12 (rank not in top 25): What enterprise AI traction has Infosys reported across top clients, AI projects, and new service offerings?
- ID 17 (rank not in top 25): What did Infosys report about client demand for AI advisory and AI transformation services?
- ID 18 (rank not in top 25): What were the major financial highlights of Infosys for FY2026?
- ID 21 (rank not in top 25): How does Infosys define its AI-first strategy and Responsible AI framework?

### MiniLM reranker — improved (TOP_K=40, top-5 context, gpt-4o-mini)

- ID 11 (rank not in top 25): How does Infosys describe its AI strategy and its transition from AI experimentation to enterprise-scale AI adoption?
- ID 12 (rank not in top 25): What enterprise AI traction has Infosys reported across top clients, AI projects, and new service offerings?
- ID 17 (rank not in top 25): What did Infosys report about client demand for AI advisory and AI transformation services?
- ID 18 (rank not in top 25): What were the major financial highlights of Infosys for FY2026?
- ID 24 (rank not in top 25): What were the key details of Infosys' 2025 share buyback?

### Hybrid BM25+dense — MiniLM reranker (TOP_K=40, top-5 context, gpt-4o-mini)

- ID 11 (rank not in top 25): How does Infosys describe its AI strategy and its transition from AI experimentation to enterprise-scale AI adoption?
- ID 24 (rank not in top 25): What were the key details of Infosys' 2025 share buyback?
- ID 25 (rank not in top 25): Where are Infosys equity shares and ADRs listed?
- ID 28 (rank not in top 25): What employee turnover trends has Infosys reported over the past three years?
- ID 32 (rank not in top 25): What acquisitions and strategic investments did Infosys complete during FY2026?

