# Generation-quality metrics (ROUGE-L and semantic similarity, no RAGAS)

Reference answers: `RAGAS/reference_answers_template.csv` (human-approved,
reused as plain ground-truth data; the RAGAS library/methods were not used).
Semantic similarity uses the local bi-encoder `sentence-transformers/all-MiniLM-L6-v2` — no OpenAI
calls are made for scoring.

| Pipeline | Questions scored | ROUGE-L F1 (mean) | Semantic similarity (mean) |
|---|---:|---:|---:|
| No reranking (top-3 Chroma, gpt-4o-mini) | 50 | 0.2758 | 0.6263 |
| HyDE, no reranking (top-3 Chroma, gpt-4o-mini) | 50 | 0.2643 | 0.5562 |
| MiniLM reranker — baseline (TOP_K=25, top-3 context, gpt-4o-mini) | 50 | 0.3177 | 0.7002 |
| MiniLM reranker — improved (TOP_K=40, top-5 context, gpt-4o-mini) | 50 | 0.3566 | 0.7499 |
| Hybrid BM25+dense — MiniLM reranker (TOP_K=40, top-5 context, gpt-4o-mini) | 50 | 0.3692 | 0.7521 |

## Lowest semantic-similarity questions per pipeline

### No reranking (top-3 Chroma, gpt-4o-mini)

- ID 17 (semantic_similarity=-0.0587, rouge_l_f1=0.0351): What did Infosys report about client demand for AI advisory and AI transformation services?
- ID 45 (semantic_similarity=-0.0488, rouge_l_f1=0.0217): How is Infosys using Enterprise AI and AI agents across different industries, according to management?
- ID 40 (semantic_similarity=-0.0314, rouge_l_f1=0.0000): How did revenue and profit evolve during the first nine months of FY2026?
- ID 20 (semantic_similarity=-0.0229, rouge_l_f1=0.0625): What are the four pillars of Infosys' long-term corporate strategy?
- ID 15 (semantic_similarity=0.0091, rouge_l_f1=0.0488): How could Global Capability Centers (GCCs) affect Infosys' future growth and profitability?

### HyDE, no reranking (top-3 Chroma, gpt-4o-mini)

- ID 17 (semantic_similarity=-0.0587, rouge_l_f1=0.0351): What did Infosys report about client demand for AI advisory and AI transformation services?
- ID 45 (semantic_similarity=-0.0488, rouge_l_f1=0.0217): How is Infosys using Enterprise AI and AI agents across different industries, according to management?
- ID 20 (semantic_similarity=-0.0229, rouge_l_f1=0.0625): What are the four pillars of Infosys' long-term corporate strategy?
- ID 13 (semantic_similarity=0.0065, rouge_l_f1=0.0247): What are the six capitals used by Infosys in its Integrated Annual Report, and why are they important?
- ID 15 (semantic_similarity=0.0091, rouge_l_f1=0.0488): How could Global Capability Centers (GCCs) affect Infosys' future growth and profitability?

### MiniLM reranker — baseline (TOP_K=25, top-3 context, gpt-4o-mini)

- ID 40 (semantic_similarity=-0.0228, rouge_l_f1=0.0000): How did revenue and profit evolve during the first nine months of FY2026?
- ID 13 (semantic_similarity=0.0065, rouge_l_f1=0.0247): What are the six capitals used by Infosys in its Integrated Annual Report, and why are they important?
- ID 10 (semantic_similarity=0.0464, rouge_l_f1=0.0370): What new capabilities does the Living Labs center in Hubballi add to Infosys' delivery network?
- ID 21 (semantic_similarity=0.0633, rouge_l_f1=0.0169): How does Infosys define its AI-first strategy and Responsible AI framework?
- ID 17 (semantic_similarity=0.1083, rouge_l_f1=0.0351): What did Infosys report about client demand for AI advisory and AI transformation services?

### MiniLM reranker — improved (TOP_K=40, top-5 context, gpt-4o-mini)

- ID 17 (semantic_similarity=-0.0587, rouge_l_f1=0.0351): What did Infosys report about client demand for AI advisory and AI transformation services?
- ID 40 (semantic_similarity=-0.0119, rouge_l_f1=0.0000): How did revenue and profit evolve during the first nine months of FY2026?
- ID 13 (semantic_similarity=0.0065, rouge_l_f1=0.0247): What are the six capitals used by Infosys in its Integrated Annual Report, and why are they important?
- ID 10 (semantic_similarity=0.0464, rouge_l_f1=0.0370): What new capabilities does the Living Labs center in Hubballi add to Infosys' delivery network?
- ID 49 (semantic_similarity=0.3977, rouge_l_f1=0.0667): What are the key risks identified by analysts that could affect Infosys' future performance?

### Hybrid BM25+dense — MiniLM reranker (TOP_K=40, top-5 context, gpt-4o-mini)

- ID 20 (semantic_similarity=-0.0229, rouge_l_f1=0.0625): What are the four pillars of Infosys' long-term corporate strategy?
- ID 40 (semantic_similarity=-0.0188, rouge_l_f1=0.0000): How did revenue and profit evolve during the first nine months of FY2026?
- ID 13 (semantic_similarity=0.0065, rouge_l_f1=0.0247): What are the six capitals used by Infosys in its Integrated Annual Report, and why are they important?
- ID 10 (semantic_similarity=0.0464, rouge_l_f1=0.0370): What new capabilities does the Living Labs center in Hubballi add to Infosys' delivery network?
- ID 22 (semantic_similarity=0.1071, rouge_l_f1=0.0241): What consulting and digital transformation capabilities does Infosys consider its key strengths?

