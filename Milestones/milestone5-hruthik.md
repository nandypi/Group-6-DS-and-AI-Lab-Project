# Milestone 5 Work Done - Hruthik

## 2026-08-06 - Created v2 Source Directories for Metadata Pipeline

Task: prepare v2 variants of the two section-chunk source directories so each
file contains exactly one YAML front matter block (the knowledge-extraction
output block), which is the text the metadata embedding pipeline embeds.

What changed:

- Created `data/infosys_earning_calls_press_conf_fact_sheets_results/cleaned_section_files_1500_2500_v2`
  containing cleaned IR section files with the first YAML block removed.
- Created `data/nse_files_final/knowledge_extraction/greater_than_10_pages/cleaned_section_files_1500_2500_v2`
  containing cleaned NSE long-document section files with the first YAML block removed.
- The other three source directories (yfinance, trendlyne, NSE ≤10 pages) were
  used unchanged because those files already carry a single YAML front matter block.

File counts in v2 directories:

- IR v2 (`cleaned_section_files_1500_2500_v2`): 58 Markdown files across 16 document folders.
- NSE >10 v2 (`cleaned_section_files_1500_2500_v2`): 1,699 Markdown files across 28 document folders.

## 2026-08-06 - Built the Metadata-Only Embedding Pipeline

Task: create a self-contained pipeline that embeds only the YAML front matter
of each Markdown chunk into a dedicated ChromaDB collection, enabling a fair
comparison of metadata-only retrieval against the existing full-text pipeline.

What changed:

- Added `metadata_embedding_pipeline/metadata_embedding_utils.py`.
  Shared constants and pure helper functions used by both the pipeline and
  benchmark scripts.  Contains:
  - `PROJECT_ROOT`, `DB_PATH`, `BENCHMARK_INPUT_CSV`, `BENCHMARK_OUTPUT_CSV`,
    `DATA_SOURCES`, `COLLECTION_NAME`, `EMBEDDING_MODEL`, `BATCH_SIZE`.
  - `find_markdown_files()` — discovers all `.md` files under the five approved
    source directories (two of which point to the v2 variants).
  - `extract_yaml_front_matter()` — parses the single `---` … `---` block from
    each v2 file.
  - `metadata_to_text()` — converts any YAML metadata dict to embeddable plain
    text dynamically (no hardcoded keys; lists become bullet lines).
  - `normalize_filename()`, `_recall_key()`, `expected_document_is_in_rank()` —
    recall helpers that match on `parent_directory/filename` for grouped section
    files and on normalised basename for whole-document files, making the
    comparison insensitive to the `_v2` directory name difference.

- Added `metadata_embedding_pipeline/metadata_embedding_pipeline.py`.
  Reads every Markdown file found by `find_markdown_files()`, extracts its YAML
  front matter, converts it to embeddable text with `metadata_to_text()`, embeds
  it in batches of 20 using `text-embedding-3-small`, and upserts each chunk into
  the `metadata_embeddings` Chroma collection with `filename` and `filepath`
  metadata fields.  Files whose YAML produces empty text are skipped.

- Added `metadata_embedding_pipeline/metadata_embedding_benchmark.py`.
  Runs a Recall@3 / Recall@5 / Recall@7 benchmark against the
  `metadata_embeddings` collection using the same 50-question test CSV and
  top-10 retrieval window as the existing pipelines.  No reranking and no LLM
  calls are made — only retrieval recall is evaluated.  Supports `--start` and
  `--limit` arguments for incremental runs and writes results after every
  completed question to prevent lost progress.

Pipeline run summary:

- Source directories scanned: 5 (3 unchanged + 2 v2 variants).
- Markdown files found: 1,877.
- Files embedded and upserted: 1,875.
- Files skipped (empty YAML text): 2.
- Chroma collection: `metadata_embeddings`.
- Chroma database path: `metadata_embedding_pipeline/chroma_db/`.
- Embedding model: `text-embedding-3-small`.
- Batch size: 20.

Verification:

- `python -m py_compile metadata_embedding_pipeline/metadata_embedding_utils.py`
  passed.
- `python -m py_compile metadata_embedding_pipeline/metadata_embedding_pipeline.py`
  passed.
- `python -m py_compile metadata_embedding_pipeline/metadata_embedding_benchmark.py`
  passed.
- `python metadata_embedding_pipeline/metadata_embedding_pipeline.py` completed
  successfully and reported 1,875 files upserted.

## 2026-08-06 - Created New Benchmark Dataset with Clean Ground Truth

Task: build a new 50-question benchmark CSV with clean ground-truth labels,
giving the metadata-only pipeline a fair and correct evaluation target.

What changed:

- Added `data/infosys_rag_test_dataset_50_queries_v2.csv`.
  Schema: `id`, `query`, `source_category`, `source_document`.
  All 50 `source_document` values are full relative filepaths starting with
  `data/…`, uniform across all five source categories.

Design rules applied:

- At most 2 questions per source document.
- Distribution matches the corpus composition:
  - Yahoo Finance: 3 questions.
  - Trendlyne: 3 questions.
  - IR (earning calls / press conferences / fact sheets): 10 questions.
  - NSE ≤10 pages: 24 questions.
  - NSE >10 pages: 10 questions.
- Source documents were verified to exist on disk before the CSV was finalised.

## 2026-08-06 - Ran Benchmark and Documented Results

Task: evaluate the metadata-only embedding pipeline against the new v2 benchmark
dataset and record the results in the shared results document.

Benchmark run summary:

- Questions processed: 50 of 50.
- Pipeline errors: 0.
- Chroma collection queried: `metadata_embeddings`.
- Retrieval top-K: 10.
- Recall evaluation window: ranks 3, 5, 7.

Results:

| Metric       | Score      |
|--------------|-----------|
| Recall@3     | 37/50 — 74% |
| Recall@5     | 39/50 — 78% |
| Recall@7     | 41/50 — 82% |
| Avg latency  | 0.478 s/question |

Per-category Recall@3:

| Category      | Recall@3 |
|---------------|---------|
| Yahoo Finance | 3/3     |
| Trendlyne     | 2/3     |
| NSE ≤10 pages | 23/24   |
| NSE >10 pages | 8/10    |
| IR            | 1/10    |

Key observations:

- NSE ≤10 pages achieves near-perfect recall because each document covers a
  distinct topic (a specific partnership, product launch, or corporate action)
  and its YAML `sample_queries` clearly distinguish it from all other documents.
- IR category is weakest: Q1–Q4 earnings calls, press conferences, and fact
  sheets share overlapping YAML vocabulary (`revenue guidance`, `operating margin`,
  `large-deal TCV`) that causes metadata-only embedding to retrieve the wrong
  quarterly file despite surfacing the correct document group.
- Latency is 0.478 s/question — approximately 13× faster than the baseline
  full-text pipeline with no reranking (6.2 s/question) and more than 500×
  faster than the reranking pipeline (247 s/question).

What changed:

- Updated `datapreparation/benchmarking/results.md` with a new
  "Metadata-Only Embedding Pipeline" section covering scripts, collection,
  benchmark dataset, per-category results, key observations, latency
  comparison, and a cross-pipeline summary table.
- Output results file written to:
  `data/infosys_rag_test_dataset_50_queries_v2_metadata_embeddings_results.csv`.

Verification:

- `python metadata_embedding_pipeline/metadata_embedding_benchmark.py`
  completed successfully with 0 pipeline errors across all 50 questions.
- Results CSV written and verified at
  `data/infosys_rag_test_dataset_50_queries_v2_metadata_embeddings_results.csv`.

## Added Cross-Encoder Re-ranking Stage

Task: extend the metadata-only retrieval pipeline with a lightweight
cross-encoder re-ranking stage and document the comparison results.

What changed:

- Updated `metadata_embedding_pipeline/metadata_embedding_utils.py`.
  - Added `RERANKER_BENCHMARK_OUTPUT_CSV` constant pointing to
    `data/infosys_rag_test_dataset_50_queries_v2_metadata_reranker_results.csv`.
  - Added `get_metadata_text_for_filepath()` — reads a v2 Markdown file by its
    stored Chroma `filepath` and returns its YAML front matter as plain text,
    giving the cross-encoder the same passage text that was embedded at index time.

- Added `metadata_embedding_pipeline/metadata_embedding_reranker_benchmark.py`.
  Extends the metadata-only benchmark with an optional cross-encoder re-ranking
  stage controlled by `USE_RERANKING` in the project `.env` file:
  - `USE_RERANKING=true` — embed → retrieve top-20 → cross-encoder rerank → recall.
  - `USE_RERANKING=false` — embed → retrieve top-20 → recall (no reranking).
  Re-ranking is implemented as the `CrossEncoderReranker` class which uses
  `transformers.AutoModelForSequenceClassification` and `torch` directly
  (no `sentence-transformers`) to avoid the Keras 3 / TF import conflict.
  The reranker model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) is swappable
  by changing the single `RERANKER_MODEL` constant.  Results and per-stage
  latencies are written to the output CSV after every completed question.

- Created `datapreparation/benchmarking/results_dataset_v2.md`.
  New results document for the v2 benchmark dataset covering both pipelines:
  the metadata-only embedding results (copied from `results.md`) and the
  new metadata-only + re-ranking results with the full comparison table.

Benchmark run summary (with re-ranking):

- Questions processed: 50 of 50.
- Pipeline errors: 0.
- Chroma collection queried: `metadata_embeddings`.
- Retrieval top-K: 20 (wider window for re-ranker).
- Re-ranker model: `cross-encoder/ms-marco-MiniLM-L-6-v2`.

Results:

| Metric | Score |
|---|---:|
| Recall@3 | 37/50 — 74% |
| Recall@5 | 41/50 — 82% |
| Recall@7 | 44/50 — 88% |
| Avg reranker latency | 1.738 s/question |
| Avg total latency | 3.173 s/question |

Pipeline comparison:

| Pipeline | Recall@3 | Recall@5 | Recall@7 |
|---|---:|---:|---:|
| Metadata-only Embedding | 74% | 78% | 82% |
| Metadata-only Embedding + Re-ranking | 74% | 82% | 88% |

Re-ranking held Recall@3 flat while improving Recall@5 by +4 points and
Recall@7 by +6 points.  NSE ≤10 pages reached perfect 24/24 recall at all
ranks; IR improved at Recall@5 and @7 (2→4 and 4→5) but remained weak at @3
due to near-identical quarterly YAML vocabulary.

Verification:

- `python -m py_compile metadata_embedding_pipeline/metadata_embedding_reranker_benchmark.py`
  passed.
- `python metadata_embedding_pipeline/metadata_embedding_reranker_benchmark.py`
  completed successfully with 0 pipeline errors across all 50 questions.
- Results CSV written and verified at
  `data/infosys_rag_test_dataset_50_queries_v2_metadata_reranker_results.csv`.

## Built RAGAS V2 Evaluation Pipeline

Task: implement end-to-end RAGAS evaluation for the v2 benchmark dataset,
covering both the metadata-only retrieval pipeline (Pipeline A) and the
metadata + re-ranking pipeline (Pipeline B).

What changed:

- Added `datapreparation/benchmarking/ragas_v2/generate_grounded_source_answers_v2.py`.
  Reads each question's source document directly using the full relative filepath
  in the v2 CSV (no directory-search step needed), calls `gpt-4o-mini` via the
  OpenAI Chat Completions API, and writes `grounded_source_answers_v2.csv` plus
  `reference_answers_v2_template.csv` (a human-reviewable reference-answer sheet).

- Added `datapreparation/benchmarking/ragas_v2/generate_pipeline_answers_v2.py`.
  Accepts `--pipeline a` or `--pipeline b`:
  - Pipeline A: top-10 metadata retrieval → top-3 context → `gpt-4o-mini` answer.
  - Pipeline B: top-20 metadata retrieval → cross-encoder re-ranking →
    top-3 context → `gpt-4o-mini` answer.
  Outputs `pipeline_a_answers_v2.csv` or `pipeline_b_answers_v2.csv` with columns
  compatible with the RAGAS evaluation script (`query`, `llm_answer`,
  `llm_context_filepaths_top_3`).

- Added `datapreparation/benchmarking/ragas_v2/run_ragas_evaluation_v2.py`.
  Mirrors `RAGAS/run_ragas_evaluation.py`.  Accepts `--pipeline a|b` to select
  input/output files.  Reads context bodies from disk (YAML front matter stripped),
  evaluates with RAGAS (faithfulness, answer_relevancy, context_precision,
  context_recall), writes per-question scores and a Markdown summary.

- Updated `requirements.txt` to add `datasets` (HuggingFace; required by RAGAS
  but was missing from the project dependency list).

- Updated `datapreparation/benchmarking/results_dataset_v2.md` with a new
  RAGAS Evaluation section covering evaluation setup, workflow, and results.

Pipeline A benchmark run summary:

- Questions processed: 50 of 50.
- Pipeline errors: 0.
- Reference answers: `datapreparation/benchmarking/ragas_v2/reference_answers_v2_template.csv`.
- RAGAS evaluator: `gpt-4o-mini` + `text-embedding-3-small`.

Results (Pipeline A — metadata-only top-10 retrieval):

| Metric | Score |
|---|---:|
| faithfulness | 0.8929 |
| answer_relevancy | 0.8439 |
| context_precision | 0.9683 |
| context_recall | 0.8725 |

Verification:

- `python3 -m py_compile datapreparation/benchmarking/ragas_v2/generate_grounded_source_answers_v2.py`
  passed.
- `python3 -m py_compile datapreparation/benchmarking/ragas_v2/generate_pipeline_answers_v2.py`
  passed.
- `python3 -m py_compile datapreparation/benchmarking/ragas_v2/run_ragas_evaluation_v2.py`
  passed.
- `python3 datapreparation/benchmarking/ragas_v2/run_ragas_evaluation_v2.py --pipeline a`
  completed successfully with 0 errors across all 50 questions.
- Results CSV written at
  `datapreparation/benchmarking/ragas_v2/pipeline_a_ragas_results_v2.csv`.
- Summary written at
  `datapreparation/benchmarking/ragas_v2/pipeline_a_ragas_summary_v2.md`.
