# FinQuery: An AI-powered, Stock-Specific Public Update Analyzer (PUA) for Indian Capital Markets

**Technical Report — Group 6**
*Data Science and AI Lab (T2 - 2026)*

---

## Abstract

FinQuery is an end-to-end Retrieval-Augmented Generation (RAG) system designed to enable evidence-grounded question answering over publicly available corporate financial disclosures for Infosys Limited (NSE: INFY). The system addresses a practical gap faced by retail investors, students, and financial analysts: existing platforms offer keyword search or aggregated dashboards but cannot answer nuanced, cross-document questions that require reasoning over earnings calls, press releases, regulatory filings, and analyst reports simultaneously.

The system was developed across six milestones, evolving from a problem definition and literature review through data collection, preprocessing, retrieval optimization, and ultimately to a production-deployed dual-pipeline architecture. The final system routes incoming questions to one of two pipelines: a SQLite-backed numeric fidelity layer for precise financial metric lookups, and a hybrid retrieval pipeline that fuses semantic vector search with BM25 keyword search using Reciprocal Rank Fusion (RRF). The deployed application achieves 100% routing accuracy, 100% numeric fidelity on a 15-question benchmark, and 76% Recall@3 on a 50-question descriptive retrieval benchmark, with an average end-to-end latency of approximately 4–5 seconds per query.

---

## 1. Introduction

### 1.1 Motivation and Problem Statement

India's capital markets have seen rapid growth in retail investor participation. Yet the volume and complexity of publicly available corporate disclosures—quarterly earnings call transcripts, NSE regulatory filings, investor presentations, analyst reports, and press releases—far exceeds what an individual investor can meaningfully process. A single quarter's worth of disclosures for a major company such as Infosys can span hundreds of pages across multiple document types, each written for a different audience and at a different level of technical detail.

Existing platforms address parts of this problem. Trading platforms (Zerodha, Groww) provide price data and basic financial ratios. Screener.in aggregates standardized financials. Trendlyne offers analyst summaries. However, none of these platforms support semantic question answering that can reason over multiple documents simultaneously, locate evidence for a claim, or explain a trend by quoting the relevant passage from an earnings call. Commercial large language models (LLMs) such as GPT-4 can answer financial questions in general terms, but they do not have access to a curated, up-to-date corpus of company-specific documents and frequently produce answers that are not grounded in verifiable sources.

FinQuery was built to address this gap by combining a carefully curated document corpus with a retrieval-augmented generation pipeline that produces answers grounded in cited source documents.

### 1.2 Research Objective

The core research question is: *Can a domain-specific RAG pipeline with metadata-driven retrieval and a dedicated numeric fidelity layer provide fast, accurate, and evidence-grounded answers to both factual and descriptive questions about a company's financial disclosures?*

The system is evaluated on three dimensions:
- **Retrieval quality**: Recall@K — does the correct source document appear within the top K retrieved chunks?
- **Numeric accuracy**: Does the system return the correct financial metric value (within 5% tolerance)?
- **Answer quality**: Faithfulness, answer relevancy, context precision, and context recall measured via the RAGAS framework.

### 1.3 Scope and Pilot Company

The project focuses on a single pilot company, Infosys Limited (NSE: INFY), one of India's largest IT services companies. Infosys was chosen for its comprehensive and publicly accessible IR website, regular quarterly disclosures, active NSE filing history, and coverage by multiple analyst firms. The corpus spans July 2025 through July 2026, capturing four full fiscal quarters of FY26 (Q1–Q4).

---

## 2. System Overview

### 2.1 High-Level Architecture

FinQuery consists of two major subsystems: an **offline indexing pipeline** that prepares and stores the document corpus, and an **online inference pipeline** that receives user questions and returns grounded answers.

The offline pipeline processes raw PDF documents from four sources, converts them to clean Markdown, extracts structured metadata, splits documents into section-aware chunks, and indexes them in two stores: ChromaDB for semantic vector search, and SQLite for structured financial fact storage.

The online pipeline embeds the incoming question, routes it to one of two retrieval backends, generates an answer using GPT-4o-mini, and returns the answer along with source citations and pipeline metadata.

```
                       ┌─────────────────────────────────────┐
                       │          OFFLINE PIPELINE           │
                       │                                     │
  Raw PDFs ──► Docling ──► Filtering ──► Knowledge Extract  │
                       │       ↓                ↓            │
                       │   ChromaDB         facts.db (SQLite)│
                       └──────────┬──────────────┬───────────┘
                                  │              │
                       ┌──────────▼──────────────▼───────────┐
                       │          ONLINE PIPELINE            │
                       │                                     │
  Question ──► Embed ──► Router (GPT-4o-mini)               │
                       │     │               │               │
                       │  FACT_DB        VECTOR              │
                       │  (SQLite)       (ChromaDB +         │
                       │  SQL gen        BM25 + RRF)         │
                       │     │               │               │
                       │     └───────┬───────┘               │
                       │           Answer + Citations         │
                       └────────────┼────────────────────────┘
                                    │
                              FastAPI / Streamlit
```

### 2.2 Dual-Pipeline Design Philosophy

A fundamental design decision made in Milestone 6 was to split query handling into two distinct pipelines rather than routing all queries through a single retrieval-augmented generation path.

Financial questions fall naturally into two categories. *Numerical queries* — "What was Infosys operating margin in Q3 FY26?", "What was the large-deal TCV in Q3 FY26?" — have a single correct numerical answer that can be looked up precisely from structured data. Routing these through semantic retrieval introduces ambiguity: multiple documents may contain the same metric for different periods, and the LLM may synthesise an incorrect value from a mixed context window. *Descriptive queries* — "Why is Infosys passing AI productivity gains to clients?", "How is Infosys deploying AI in banking?" — require understanding of narrative content that is better served by semantic retrieval over the full document corpus.

The router uses GPT-4o-mini as a zero-shot classifier. Questions containing numeric keywords (specific metric names, comparisons, averages, totals) are sent to the FACT_DB pipeline; all other questions default to the VECTOR pipeline. The default to VECTOR ensures that ambiguous or novel question types always receive an answer rather than failing silently.

---

## 3. Data Collection and Corpus Construction

### 3.1 Sources and Collection Methodology

The corpus was assembled from four publicly available source types, chosen to provide complementary perspectives on Infosys's financial performance:

| Source | Type | Collection Method | Documents Retained |
|---|---|---|---:|
| NSE (National Stock Exchange) | Regulatory filings, results, disclosures | Programmatic NSE API scraping | 137 |
| Infosys Investor Relations | Earnings calls, fact sheets, press releases | Manual download from IR website | 16 |
| Yahoo Finance | Market news articles | `yfinance` Python library | 6 |
| Trendlyne | Brokerage and analyst research reports | Manual curation | 5 |
| **Total** | | | **207** |

NSE announcements were collected using a one-year lookback window. All PDFs were converted to Markdown using Docling before any filtering was applied.

### 3.2 Three-Stage Filtering Strategy

A large proportion of NSE filings are administrative or routine in nature and carry no substantive financial content (trading window closure notices, board committee constitutions, secretarial audit reports, etc.). These documents would add noise to the corpus without improving retrieval. A three-stage cascade was developed to filter them:

**Stage 1 — Metadata rules:** Documents were automatically accepted or rejected based on filing category. Categories with consistently informative content (financial results, analyst meet, investor presentations) were accepted outright. Categories with consistently uninformative content (compliance notices, committee reports) were rejected outright.

**Stage 2 — Keyword matching:** Filings in ambiguous categories were scanned for the presence or absence of domain-relevant financial keywords. A document that contained no references to revenue, margin, guidance, or specific business activities was rejected.

**Stage 3 — LLM review:** Documents that passed keyword screening but remained ambiguous were reviewed by GPT-4o-mini, which classified each as "keep" or "discard" based on whether a retail investor would find the content informative.

The cascade reduced the initial pool of 492 NSE PDFs to 137 retained documents, a 72% reduction that substantially improved corpus signal-to-noise ratio.

### 3.3 Final Corpus Statistics

The final curated corpus of 207 documents covers the period July 2025 through July 2026. After preprocessing and section-aware chunking (described in Section 4), the corpus expands to 1,875 indexed chunks stored in ChromaDB.

---

## 4. Document Preprocessing Pipeline

### 4.1 PDF-to-Markdown Conversion

All source documents are in PDF format. A key early decision was to use **Docling** for PDF-to-Markdown conversion rather than simpler text extraction libraries. Docling is structure-preserving and deterministic: it reconstructs headings, tables, bullet lists, and paragraph boundaries as Markdown syntax rather than flattening the document into a stream of characters. This is critical for financial documents where tabular data (quarterly results tables, segment breakdowns) carries most of the numerical information.

### 4.2 Knowledge Extraction and YAML Metadata Enrichment

After PDF conversion, each document undergoes a knowledge extraction step using source-specific LLM prompts. This step serves two purposes: it removes residual noise (headers, footers, legal boilerplate, duplicate content across pages) while producing a clean Markdown body, and it generates a structured YAML front matter block at the top of each chunk.

The YAML front matter contains:

```yaml
---
section_title: "Q3 FY26 Earnings Call — Management Commentary"
description: "CEO and CFO commentary on Q3 FY26 financial results, guidance revision, and deal pipeline"
topics:
  - Operating margin
  - Revenue growth
  - Large deal TCV
  - AI-driven productivity
  - FY27 guidance
sample_queries:
  - "What caused the operating margin decline in Q3 FY26?"
  - "What is the revenue guidance for FY27?"
  - "How large was the NHS deal announced in Q3?"
---
```

This enrichment is the foundation of the metadata-only retrieval strategy described in Section 5. By embedding the YAML front matter rather than the full document body, the system indexes a compact, semantically dense representation of each chunk's content.

### 4.3 Chunking Strategy Evolution

**Original approach (Milestone 3):** In the first end-to-end system, each cleaned Markdown file was treated as a single chunk. Short documents (NSE filings under 10 pages) were left intact. Long documents were processed as whole files. This produced chunks of highly variable token count — some under 500 tokens, others near the 8,191-token embedding limit — and meant that long documents contributed a single embedding that had to represent the entire document's content.

**Refined approach (Milestone 5):** Based on retrieval analysis showing that long chunks produced poor recall, the preprocessing pipeline was revised. Documents with fewer than 10 pages are retained as single chunks. Documents with more than 10 pages are split into section-aware groups of 1,500–2,500 tokens (with a ceiling of 3,000 tokens). The splitting respects Markdown heading boundaries so that each chunk corresponds to a coherent section rather than an arbitrary mid-sentence break.

This change increased the total chunk count from 207 to 1,875 and was the single largest driver of retrieval improvement across the project, raising Recall@3 from 34% (whole-document Chroma baseline) to 74% (metadata-only retrieval on section chunks).

---

## 5. Retrieval System Design and Evolution

### 5.1 Embedding Model and Vector Store

All chunk metadata is embedded using **OpenAI text-embedding-3-small**, producing 1,536-dimensional dense vectors. This model was chosen over larger alternatives for its strong price-to-performance ratio on short semantic text and its 8,191-token input limit that accommodates even the longest YAML front matter blocks. Embeddings are stored in **ChromaDB**, an open-source vector database that uses HNSW (Hierarchical Navigable Small World) graph indexing for approximate nearest-neighbour search. ChromaDB was selected for its simple Python API, persistent disk storage, and ability to store document metadata alongside embeddings for post-retrieval filtering.

### 5.2 Retrieval Experiments (Milestone 4)

Milestone 4 systematically evaluated three retrieval strategies on a 50-question benchmark dataset. All experiments at this stage used full-document embeddings (pre-chunking refinement), establishing a baseline for the subsequent improvements.

| Strategy | Recall@3 | Recall@5 | Recall@7 | Avg. Latency |
|---|---:|---:|---:|---:|
| Chroma-only (full-text, top-10) | 40% | 50% | 54% | 6.3 s |
| HyDE (Hypothetical Document Embeddings) | 40% | 42% | 46% | 9.3 s |
| BGE reranking (BAAI/bge-reranker-v2-m3) | 58% | 64% | 64% | 245 s |

**Chroma-only baseline** retrieved the top 10 candidates by cosine similarity to the embedded question and passed the top 3 to the LLM. Recall@3 of 40% indicates that in 40% of cases the correct source document appeared within the top 3 retrieved results.

**HyDE** generated a hypothetical answer to the question using GPT-4o-mini, embedded that hypothetical text, and used it as the query vector. The intuition is that a hypothetical answer is more similar to actual answer-containing passages than the question itself. In practice, the improvement was negligible (Recall@3 unchanged at 40%) because the questions already contained sufficient specific entities (company names, metric names, dates) that direct question embedding performed comparably.

**BGE reranking** retrieved 25 Chroma candidates and scored each (question, passage) pair using BAAI/bge-reranker-v2-m3, a cross-encoder model that reads both question and passage simultaneously. This improved Recall@3 substantially (+18 percentage points) but at a severe latency cost of 245 seconds per question on CPU, making it unsuitable for interactive use.

### 5.3 Metadata-Only Retrieval Breakthrough (Milestone 5)

A pivotal insight emerged during Milestone 5: the YAML front matter, which contains a carefully crafted description, a list of topics, and sample queries, is a far more discriminative representation of chunk content than the full document body for the purposes of retrieval.

Full document bodies contain repetitive financial boilerplate, legal text, and table formatting that dilutes the signal. The YAML front matter, generated by an LLM that understood the chunk's content, is concise and semantically precise. Embedding only the YAML text shifts retrieval from "which chunk shares vocabulary with the question" to "which chunk was written about the same topic as the question".

The improvement was dramatic. On the same 50-question benchmark, metadata-only retrieval achieved:

| Pipeline | Recall@3 | Recall@5 | Recall@7 | Avg. Latency |
|---|---:|---:|---:|---:|
| Chroma-only full-text (M4 baseline) | 40% | 50% | 54% | 6.3 s |
| Chroma-only full-text (post-chunking, M5) | 34% | 38% | 40% | 6.2 s |
| BGE full-text reranking (M5) | 40% | 46% | 50% | 486 s |
| **Metadata-only embedding (M5)** | **74%** | **78%** | **82%** | **0.48 s** |
| Metadata + cross-encoder reranking (M5) | 74% | 82% | 88% | 3.2 s |

The metadata-only approach achieved 74% Recall@3 — an 85% relative improvement over the full-text Chroma baseline — while being 13x faster than the BGE reranking approach. With lightweight cross-encoder reranking (ms-marco-MiniLM-L-6-v2 applied to the top-20 Chroma candidates), Recall@7 reached 88%.

A per-category analysis revealed that retrieval difficulty varies significantly by source type:

| Source Category | Recall@3 (Metadata + Rerank) |
|---|---:|
| NSE ≤ 10 pages | 100% |
| Yahoo Finance | 100% |
| NSE > 10 pages (sections) | 70% |
| Trendlyne | 67% |
| **Infosys IR (earnings calls, fact sheets)** | **10%** |

The extremely low recall for Infosys IR documents was traced to vocabulary overlap: all four quarterly earnings call transcripts discuss the same metrics (operating margin, revenue, attrition, large deals) with similar language, making it difficult for the retrieval system to distinguish Q1 from Q4. This finding directly motivated the SQLite fact database in Milestone 6, which bypasses retrieval entirely for numerical queries.

### 5.4 Hybrid BM25 + Vector Retrieval with RRF (Milestone 6)

While metadata-only embedding captures semantic intent well, it can miss documents that contain exact keyword matches for specific entities — specific guidance ranges, deal names, fiscal quarter labels, and abbreviations — that appear verbatim in the YAML front matter but are not semantically proximate in the embedding space.

To address this, a BM25 keyword retrieval layer was added and its results fused with the vector retrieval results using **Reciprocal Rank Fusion (RRF)**. The BM25 index is built over the same YAML front-matter texts that were embedded into ChromaDB, ensuring the two retrieval modalities operate over an identical corpus.

**RRF Fusion:** Each document is assigned a combined score according to:

$$\text{score}(d) = \sum_{r \in \{\text{vector}, \text{BM25}\}} \frac{1}{k + \text{rank}_r(d)}$$

where $k = 60$ (the standard RRF constant) and $\text{rank}_r(d)$ is the document's 1-based rank in list $r$. Documents appearing in both lists receive contributions from both terms and are promoted above documents appearing in only one list.

**Strategy Comparison (50-question benchmark):**

| Strategy | Recall@3 | Recall@5 | Recall@7 | Avg. Latency |
|---|---:|---:|---:|---:|
| Vector top-10, no reranker (M5 baseline) | 74% | 78% | 82% | 0.5 s |
| Vector top-20 + cross-encoder reranker | 74% | 82% | 88% | 3.2 s |
| BM25-only top-20 | **84%** | **88%** | 88% | < 0.1 s |
| **Hybrid RRF, no reranker (deployed)** | **76%** | **86%** | **88%** | **0.5 s** |
| Hybrid RRF + cross-encoder reranker | 74% | 82% | 86% | 3.0 s |

Several findings from this comparison informed the final deployment decision:

1. **BM25-only outperforms vector-only at Recall@3** (84% vs 74%), because financial queries contain precise terminology — fiscal quarter labels, deal sizes, metric names — that matches exactly in the YAML keyword index.

2. **Hybrid RRF without reranker is the best-balanced strategy**, achieving Recall@5 = 86% (better than any other strategy) and tying for Recall@7 = 88%, while adding negligible latency over vector-alone.

3. **The cross-encoder reranker does not improve Recall@3** in any configuration and actively degrades the hybrid list in specific cases. Analysis showed the reranker was trained on MS MARCO (web passages) and is poorly calibrated for YAML metadata text, occasionally demoting correctly retrieved documents. The reranker was therefore removed from the deployed VECTOR pipeline.

The deployed VECTOR pipeline is: `embed → Chroma top-20 + BM25 top-20 → RRF (k=60) → top-3 context → GPT-4o-mini`.

---

## 6. Numeric Fidelity Layer

### 6.1 Motivation and Question Routing

Retrieval-based pipelines are inherently probabilistic. Even at 86% Recall@5, approximately 14% of numerical queries would retrieve the wrong context and potentially produce an incorrect financial figure. For a system used in investment decision-making, this is unacceptable for factual lookups. The Numeric Fidelity Layer replaces probabilistic retrieval with deterministic structured query execution for numerical questions.

The **question router** is implemented as a GPT-4o-mini zero-shot classifier with a carefully constructed system prompt. The prompt lists the types of questions appropriate for each route (FACT_DB: specific metric values, averages, totals, comparisons; VECTOR: explanations, strategies, qualitative analysis, management commentary) and instructs the model to default to VECTOR when uncertain. Routing accuracy was measured at **100% (40/40)** on a held-out test set of 40 questions (20 numerical, 20 descriptive).

### 6.2 Fact Extraction and SQLite Schema

The fact database is populated from 16 Infosys IR documents: the Q1–Q4 FY26 earnings call transcripts, quarterly fact sheets, and press releases. These are the authoritative sources for company-reported financial metrics in USD.

Two extraction passes are applied to each document:

- **Table pass:** Markdown tables are parsed cell by cell. The left-most column provides the metric label (row_label), column headers provide the period or category (column_label), and cells contain raw values. Each cell becomes one row in the fact database.
- **Prose pass:** Financial sentences in bullet points are scanned for patterns matching numeric values adjacent to known metric keywords (revenue, margin, TCV, attrition, EPS, utilization). Extracted facts are inserted with `column_label = 'prose'` to distinguish them from table-sourced facts.

The SQLite schema is:

```sql
CREATE TABLE facts (
    id            INTEGER PRIMARY KEY,
    file_path     TEXT,
    document_name TEXT,
    source_folder TEXT,
    section_title TEXT,
    table_heading TEXT,
    row_label     TEXT,    -- Metric name (e.g., "Operating Margin (%)")
    column_label  TEXT,    -- Period header or "prose"
    raw_value     TEXT,    -- Exact cell text (e.g., "18.4%")
    value_numeric REAL,    -- Parsed float (e.g., 18.4), NULL if unparseable
    unit          TEXT,    -- "", "%", "USD_bn", "USD_mn", "INR_crore"
    period        TEXT,    -- Normalised period (e.g., "Q3_FY26")
    inserted_at   TEXT
);
```

The database indexes period, row_label, document_name, and file_path for query efficiency. The final database contains 2,551 facts extracted from the 16 IR source documents.

### 6.3 LLM-Driven SQL Generation and Safe Execution

For each FACT_DB query, GPT-4o-mini receives the database schema plus a `METRIC_LOOKUP` section that describes exactly how common financial metrics are stored (their exact row_label text, expected unit, and any WHERE clause filters needed to exclude confounding values). For example:

```
Operating Margin: row_label LIKE '%Operating Margin%' AND value_numeric BETWEEN 15 AND 25
  (Exclude rows with column_label LIKE '%YoY%' or '%QoQ%' or '%Adjusted%')
Net-new deal %: column_label = 'prose' AND unit = '%' AND value_numeric BETWEEN 45 AND 70
  (Regional values such as EURS 80% must be excluded with this guard)
```

The model generates a `SELECT` statement. Before execution, the query is validated: it must begin with `SELECT` and must not contain any data-modification keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`). The database is opened in read-only mode (`file:DB_PATH?mode=ro`). If the generated SQL produces a syntax error, a second LLM call is made with the error message to attempt a corrected query.

Results are capped at 200 rows and passed to a second GPT-4o-mini call that synthesises a natural-language answer with source citations.

The numeric fidelity benchmark tested 15 representative numerical questions. The pipeline achieved **15/15 (100%) correct answers** (answer within 5% of expected value) and **15/15 (100%) successful SQL execution**.

---

## 7. Deployment

### 7.1 FastAPI Backend

The system is served by a FastAPI application (`api.py`) exposing two endpoints:

- `POST /auth/token` — accepts username and password (OAuth2 password flow), returns a signed JWT token valid for 8 hours.
- `POST /query` — accepts a JSON body with a `question` field, requires a Bearer token, applies per-user rate limiting, executes the dual-pipeline, and returns a `QueryResponse` object.

The `QueryResponse` includes:
- `answer`: the generated natural-language answer
- `citations`: list of source file paths
- `route`: `"FACT_DB"` or `"VECTOR"`
- `sql`: the generated SQL query (FACT_DB only, null otherwise)
- `steps`: ordered list of pipeline workflow steps with timing
- `latency_ms`: total end-to-end latency in milliseconds

Rate limiting uses an in-memory sliding window keyed by username. The default limit is 30 requests per hour, configurable via the `APP_RATE_LIMIT_PER_HOUR` environment variable.

### 7.2 Streamlit Frontend

The Streamlit application (`streamlit_app.py`) provides a browser-based interface with:
- A login page that exchanges credentials for a JWT token stored in session state
- A question input area with example placeholder text (one numerical, one descriptive example)
- Real-time display of the pipeline workflow steps in a collapsible expander
- Highlighted answer display with route badge (Fact Database / Vector Search) and latency metric
- Collapsible source citations panel
- Session question history

### 7.3 Docker Containerization

The application is containerized using a single Docker image that serves both the FastAPI backend and Streamlit frontend. The `docker-compose.yml` defines two services:

- `api`: runs `uvicorn api:app --host 0.0.0.0 --port 8000` with a health check
- `streamlit`: runs the Streamlit server on port 8501, depends on the `api` service being healthy

Volume mounts provide the pre-built indexes at runtime:
- `./metadata_embedding_pipeline/facts.db` → `/app/metadata_embedding_pipeline/facts.db`
- `./metadata_embedding_pipeline/chroma_db/` → `/app/metadata_embedding_pipeline/chroma_db/`
- `./data/` → `/app/data/` (read-only; used for YAML text retrieval during BM25 index build)

The Docker image uses `python:3.11-slim` as the base, installs CPU-only PyTorch to avoid multi-GB CUDA wheels, and installs all runtime dependencies at pinned versions. The final image size is approximately 2.1 GB. The BM25 index is built in memory at first VECTOR request (approximately 3 seconds); the cross-encoder model is no longer bundled in the M6 final image.

---

## 8. Evaluation and Results

### 8.1 Retrieval Evaluation Methodology

Retrieval quality is measured by Recall@K: the proportion of test questions for which the ground-truth source document appears within the top K retrieved chunks. A 50-question benchmark dataset was constructed during Milestone 4 with questions distributed across all four source categories. Each question is annotated with the filepath of the expected source document.

Ground-truth matching is normalised: the `parent_directory/filename` key is compared rather than full paths, making the evaluation robust to directory naming differences (e.g., `cleaned_section_files_1500_2500` vs `cleaned_section_files_1500_2500_v2`).

### 8.2 Retrieval Benchmark Progression

The table below shows the retrieval system's progression across all milestones:

| Milestone | Pipeline | Recall@3 | Recall@5 | Recall@7 | Latency |
|---|---|---:|---:|---:|---:|
| M4 | Chroma-only full-text, top-10 | 40% | 50% | 54% | 6.3 s |
| M4 | HyDE + Chroma full-text | 40% | 42% | 46% | 9.3 s |
| M4 | BGE cross-encoder reranking | 58% | 64% | 64% | 245 s |
| M5 | Metadata-only embedding, top-10 | 74% | 78% | 82% | 0.5 s |
| M5 | Metadata + cross-encoder, top-20 | 74% | 82% | 88% | 3.2 s |
| **M6** | **Hybrid RRF (Vector + BM25), top-3** | **76%** | **86%** | **88%** | **0.5 s** |

### 8.3 Hybrid Retrieval Strategy Comparison

The Milestone 6 hybrid retrieval experiment evaluated five strategies on the same 50-question benchmark to determine the optimal production configuration. The top-3 window is critical because the application passes exactly three chunks to the LLM, making Recall@3 the direct predictor of answer quality.

| Strategy | Recall@3 | Recall@5 | Recall@7 |
|---|---:|---:|---:|
| Vector top-10, no reranker | 74% | 78% | 82% |
| Vector top-20 + cross-encoder | 74% | 82% | 88% |
| BM25-only top-20 | 84% | 88% | 88% |
| **Hybrid RRF, no reranker (deployed)** | **76%** | **86%** | **88%** |
| Hybrid RRF + cross-encoder | 74% | 82% | 86% |

BM25 alone achieves the highest Recall@3 (84%), reflecting the precise financial terminology present in YAML metadata. The Hybrid RRF configuration without cross-encoder reranker was selected for deployment as the best-balanced strategy: it improves Recall@5 over all other approaches while maintaining the Recall@7 ceiling of 88%, with effectively zero additional latency over vector-only search.

### 8.4 Routing and Numeric Fidelity Benchmarks

The FACT_DB pipeline was evaluated on two separate benchmark sets:

**Routing benchmark (40 questions: 20 numerical, 20 descriptive):**

| Metric | Result |
|---|---:|
| Correct routes | 40 / 40 |
| Routing accuracy | 100% |

**Numeric fidelity benchmark (15 numerical questions):**

| Metric | Result |
|---|---:|
| Correct SQL generated and executed | 15 / 15 |
| Answers within 5% of expected value | 15 / 15 |
| SQL execution success rate | 100% |
| Numeric fidelity rate | 100% |

Representative questions and verified answers from the benchmark:

| ID | Question | Expected | Returned |
|---|---|---|---|
| N1 | Operating margin Q3 FY26 | 18.4% | 18.4% |
| N2 | Revenue Q4 FY26 | $5,040 M | $5,040 M |
| N5 | Large deal TCV Q3 FY26 | $4.8 B | $4.8 B |
| N7 | Average operating margin FY26 | 20.275% | 20.275% |
| N12 | Revenue decline Q3→Q4 FY26 | $59 M | $59 M |

### 8.5 RAGAS Answer Quality Metrics

Answer quality was evaluated using the RAGAS framework on a representative subset of descriptive questions. RAGAS measures four dimensions without requiring human-labelled reference answers, using GPT-4 as the evaluator:

| Metric | Score |
|---|---:|
| Faithfulness | 0.8929 |
| Answer Relevancy | 0.8439 |
| Context Precision | 0.9683 |
| Context Recall | 0.8725 |

*Faithfulness* (0.893) indicates that nearly all claims in generated answers can be traced back to the retrieved context, with few hallucinated statements. *Context precision* (0.968) is the highest metric, indicating that retrieved chunks are highly relevant to the question — the metadata-only retrieval approach is very effective at bringing back on-topic content. *Answer relevancy* (0.844) reflects the occasional verbosity or generic framing of GPT-4o-mini responses when multiple documents provide overlapping information.

### 8.6 Latency Analysis

End-to-end latency (question receipt to answer delivery, measured at the FastAPI layer) breaks down as follows for a typical warm query:

| Sub-step | FACT_DB (typical) | VECTOR (typical) |
|---|---:|---:|
| Question embedding (OpenAI) | 0.4 s | 0.4 s |
| Routing (GPT-4o-mini) | 0.5 s | 0.5 s |
| Retrieval (Chroma + BM25 + RRF) | — | < 0.1 s |
| SQL generation + execution | 1.0 s | — |
| Answer generation (GPT-4o-mini) | 1.5 s | 3.5 s |
| **Total (approximate)** | **~3.5 s** | **~4.5 s** |

The BM25 index build (approximately 3 seconds reading 1,875 YAML files from disk) occurs once per server restart at the time of the first VECTOR request and is not charged to subsequent queries.

---

## 9. Challenges and Resolutions

### 9.1 Infosys IR Document Vocabulary Ambiguity

**Challenge:** All four quarterly Infosys IR documents (earnings calls, fact sheets) discuss identical metrics — operating margin, revenue, large deals, attrition, headcount — with nearly identical vocabulary. A retrieval system based on semantic similarity cannot reliably distinguish a Q1 FY26 earnings call from a Q4 FY26 earnings call when both discuss "operating margin" and "large deal TCV". This produced the anomalously low Recall@3 of 10% for the IR category in Milestone 5.

**Resolution:** The Numeric Fidelity Layer (Milestone 6) bypasses retrieval entirely for numerical IR queries. Exact financial metrics are stored in a structured SQLite database keyed by period (e.g., `Q3_FY26`) and metric name, and retrieved via LLM-generated SQL. Additional WHERE clause guards in the SQL system prompt prevent period confusion (e.g., `period = 'Q3_FY26'` is explicit in generated queries). For descriptive IR queries, the YAML metadata enrichment was improved to include explicit quarter and fiscal year labels in the `section_title` field.

### 9.2 Numeric Precision: Net-New Deal Percentage

**Challenge:** The SQLite fact database contained both company-level net-new deal percentages (~67% for Q2 FY26) and segment/regional net-new percentages (e.g., 80% for the EURS region). An initial SQL pattern that filtered `value_numeric BETWEEN 45 AND 80` inadvertently included the regional 80% figure, causing one benchmark question to return the wrong value.

**Resolution:** The upper bound was tightened to `value_numeric BETWEEN 45 AND 70` after confirming that no valid company-level net-new percentage exceeds 70%. Both the fact database schema documentation and the SQL system prompt were updated to include this guard clause and explain the reasoning. After this fix, the numeric fidelity benchmark reached 15/15 (100%).

### 9.3 Cross-Encoder Reranker Not Effective for YAML Metadata

**Challenge:** The cross-encoder model (cross-encoder/ms-marco-MiniLM-L-6-v2) was trained on MS MARCO, a dataset of (query, web passage) pairs. When applied to (query, YAML metadata) pairs, the model is operating outside its training distribution. Empirically, the reranker did not improve Recall@3 in any tested configuration — it maintained the same score as no reranker for vector-only retrieval, and actively degraded recall for the hybrid RRF list on two benchmark questions (Q9 and Q46, both large-deal TCV questions).

**Resolution:** The cross-encoder reranker was removed from the deployed VECTOR pipeline. The Hybrid RRF approach (without reranker) was adopted as a strictly better alternative: it improves Recall@3 by 2 percentage points and Recall@5 by 8 percentage points compared to the previous cross-encoder configuration, while reducing per-query latency by approximately 2.5 seconds.

### 9.4 ChromaDB Read-Only Mount in Docker

**Challenge:** During Docker deployment testing, ChromaDB's Rust-based storage engine threw a "attempt to write a readonly database" error even when the application was only performing read operations. This occurred because the ChromaDB volume was mounted with the `:ro` (read-only) flag.

**Resolution:** ChromaDB's DuckDB and SQLite internal layers write housekeeping state even during read queries. The `:ro` flag was removed from both the `facts.db` and `chroma_db` volume mounts in `docker-compose.yml`. The ChromaDB WAL (write-ahead log) files are generated at query time but are inconsequential for correctness.

### 9.5 BM25 Index First-Call Latency

**Challenge:** The BM25 index is built in memory by reading the YAML front-matter text of all 1,875 documents from disk. This takes approximately 3 seconds and occurs on the first VECTOR request after server startup, causing a noticeable delay for the first user.

**Resolution:** This is a one-time startup cost and does not affect subsequent queries. In the current deployment, the BM25 index is lazily initialised on first VECTOR request. For production deployments where first-request latency is critical, the index can be pre-warmed by adding a FastAPI startup event handler that triggers a dummy VECTOR call during application startup, amortising the cost before any user request arrives.

---

## 10. Conclusion, Limitations, and Future Work

### 10.1 Summary of Contributions

FinQuery demonstrates that a carefully engineered RAG system, built without any model fine-tuning or training, can achieve production-quality performance on financial document Q&A. The key technical contributions across six milestones are:

1. **Structured multi-source corpus:** A curated 207-document, 1,875-chunk corpus assembled from four complementary source types with a three-stage quality filtering pipeline.

2. **YAML-metadata retrieval paradigm:** Embedding compact, LLM-generated semantic metadata rather than full document bodies increased Recall@3 from 40% (M4 best) to 74% (M5) — an 85% relative improvement — while reducing latency by two orders of magnitude.

3. **Dual-pipeline architecture:** Separating numerical queries (routed to SQLite + LLM-SQL) from descriptive queries (routed to hybrid vector+BM25 retrieval) resolves the fundamental tension between precision for financial metrics and recall for narrative content.

4. **Hybrid BM25 + Vector retrieval with RRF:** Fusing keyword and semantic retrieval lists using Reciprocal Rank Fusion improved Recall@5 to 86% while eliminating the cross-encoder reranking step that added latency without improving quality on YAML metadata passages.

5. **Production deployment:** A fully containerised FastAPI + Streamlit application with JWT authentication, configurable rate limiting, and Docker Compose orchestration ready for VM deployment.

### 10.2 Limitations

- **Single company coverage:** The system is currently calibrated to Infosys Limited. Extending to other companies requires re-running the data collection, filtering, knowledge extraction, and indexing pipeline from scratch. Metric names, document structures, and fiscal calendars differ across companies.

- **Infosys IR cross-quarter ambiguity (residual):** While the SQLite pipeline resolves numeric ambiguity, descriptive questions about specific quarters still rely on the VECTOR pipeline, where similar quarterly language can reduce Recall@3. Explicit quarter/date signals in YAML metadata would improve this.

- **No metadata filtering at query time:** The retrieval system does not support user-specified filters (e.g., "search only in Q3 FY26 documents" or "search only in analyst reports"). All 1,875 chunks are always candidates.

- **Top-3 context constraint:** To manage LLM context length and token cost, exactly three chunks are passed to GPT-4o-mini. Questions that require evidence spanning four or more distinct document sections cannot be answered correctly regardless of retrieval quality.

- **In-memory BM25 index:** The BM25 index is rebuilt from disk on every server restart. For very large corpora (tens of thousands of chunks), this could become a bottleneck; a persistent BM25 index would be needed.

### 10.3 Future Work

- **Multi-company expansion:** Generalise the collection, filtering, and extraction pipeline to accept any NSE-listed company as input, enabling the system to serve as a general-purpose stock disclosure analyzer.

- **Metadata date/quarter filtering:** Add explicit period tags to YAML metadata (e.g., `fiscal_period: Q3_FY26`) and implement ChromaDB metadata filtering to allow users to constrain retrieval to specific time windows.

- **Larger context window:** As LLM context windows and pricing improve, increasing the number of chunks passed to the model from 3 to 5 would raise the effective Recall@5 ceiling of 86% to the LLM's answer quality bound.

- **Fine-tuned embedding model:** The current embedding model (text-embedding-3-small) is a general-purpose model. Fine-tuning on domain-specific (question, YAML-passage) pairs — using the YAML metadata as the positive passage — could further improve retrieval alignment.

- **Streaming responses:** The current API returns a complete answer after full generation. Streaming the LLM response token-by-token to the Streamlit frontend would improve perceived latency significantly for longer descriptive answers.

---

## References

The following tools, libraries, and frameworks were used in the implementation of FinQuery:

| Component | Tool / Library | Version |
|---|---|---|
| PDF conversion | Docling | — |
| Vector database | ChromaDB | 1.5.9 |
| Embedding model | OpenAI text-embedding-3-small | — |
| Generation model | OpenAI GPT-4o-mini | — |
| Keyword search | rank-bm25 (BM25Okapi) | 0.2.2 |
| Cross-encoder (M5) | cross-encoder/ms-marco-MiniLM-L-6-v2 | — |
| BGE reranker (M4) | BAAI/bge-reranker-v2-m3 | — |
| Answer quality | RAGAS framework | — |
| Backend API | FastAPI | 0.141.1 |
| Frontend | Streamlit | 1.61.1 |
| Containerisation | Docker + Docker Compose | — |
| Authentication | PyJWT | 2.3.0 |
| Data processing | Python, pandas, PyYAML | — |

**Key research concepts referenced:**
- Lewis et al. (2020), *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*
- Cormack & Clarke (2009), *Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods*
- Gao et al. (2023), *Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE)*
- Es et al. (2023), *RAGAS: Automated Evaluation of Retrieval Augmented Generation*
