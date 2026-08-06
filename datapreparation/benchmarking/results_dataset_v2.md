# Dataset Benchmark Results V2

All benchmarks on this page use `data/infosys_rag_test_dataset_50_queries_v2.csv`
as the evaluation dataset (50 investor-oriented questions, clean ground-truth
full relative filepaths).

---

## Metadata-only Embedding Pipeline

**Scripts:** `metadata_embedding_pipeline/metadata_embedding_pipeline.py` (indexing), `metadata_embedding_pipeline/metadata_embedding_benchmark.py` (evaluation)

**Benchmark dataset:** `data/infosys_rag_test_dataset_50_queries_v2.csv` — a new 50-question dataset with properly labeled ground truth (full relative filepaths for every source, no old/current split). Questions were generated as investor-style rephrashings of the `sample_queries` found in each document's YAML front matter.

**Chroma collection:** `metadata_embeddings` (stored in `metadata_embedding_pipeline/chroma_db/`)

**What changed:** Unlike all previous pipelines, which embed the full file content (YAML front matter + Markdown body), this pipeline embeds **only the YAML metadata** section of each v2 document. The Markdown body is discarded at indexing time. The embedded text is a readable conversion of the YAML fields — `section_title`, `section_description`, `topics`, and `sample_queries` — concatenated with no body text.

**Files indexed:** 1,875 Markdown files across five source directories (the two section-chunk directories use their `_v2` versions with the first YAML block stripped).

**Results** — `data/infosys_rag_test_dataset_50_queries_v2_metadata_embeddings_results.csv`:

| Metric | Result |
|---|---:|
| Successful questions | 50/50 |
| Recall@3 | 37/50 — 74% |
| Recall@5 | 39/50 — 78% |
| Recall@7 | 41/50 — 82% |
| Average latency | 0.478 s/question |

By source category, Recall@3 was:

| Source | Recall@3 | Notes |
|---|---:|---|
| NSE ≤10 pages | 23/24 | Near-perfect; each press release has unique metadata |
| NSE >10 pages | 8/10 | Strong; AI Day, AGM, and earnings transcripts retrieved correctly |
| Yahoo Finance | 3/3 | Perfect |
| Trendlyne | 2/3 | One analyst note (FY27 guidance) lost to competing quarterly reports |
| IR | 1/10 | Weakest category; many Q1–Q4 chunks share very similar YAML vocabulary |

**Key observations:**

- **NSE ≤10 pages (23/24):** The single miss (Q34 — financial losses from AI incidents) was retrieved at Recall@5, not @3. Press releases are highly distinctive; metadata-only embedding works almost perfectly for this category.

- **IR (1/10 at Recall@3, 2/10 at Recall@5, 4/10 at Recall@7):** The weakest category by a wide margin. All quarterly earnings calls (Q1–Q4), press conferences, press releases, and fact sheets discuss the same vocabulary — revenue guidance, operating margin, large-deal TCV, constant currency — in nearly identical terms. Their `sample_queries` and `topics` fields overlap heavily, so the correct quarter-specific chunk does not rank above its siblings. Full-content embedding (which includes actual numbers and named entities from the body) would differentiate these better.

- **Latency:** At 0.478 s/question average, this pipeline is **13× faster** than the plain non-reranking pipeline (6.251 s) and **513× faster** than the reranking pipeline (245.342 s). There is no LLM call and no reranker — only one embedding API call and one Chroma vector query per question.

---

## Metadata-only Embedding + Re-ranking Pipeline

**Scripts:** `metadata_embedding_pipeline/metadata_embedding_pipeline.py` (indexing, unchanged),
`metadata_embedding_pipeline/metadata_embedding_reranker_benchmark.py` (evaluation)

**Chroma collection:** `metadata_embeddings` (same collection as the pipeline above; no re-indexing needed)

### Retrieval process

1. The query is embedded with `text-embedding-3-small` (identical to the metadata-only pipeline).
2. The top **20** candidates are retrieved from the `metadata_embeddings` Chroma collection
   (wider window than the metadata-only pipeline's top-10 to give the re-ranker more candidates to work with).

### Re-ranker

| Property | Value |
|---|---|
| Model | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Library | `transformers` + `torch` (`AutoModelForSequenceClassification`) |
| Input | `(query, passage)` pairs |
| Passage text | YAML front matter of the candidate file, read from disk using `get_metadata_text_for_filepath()` — the same text that was embedded at indexing time |
| Output | Logit score per pair (higher = more relevant) |

The re-ranker is implemented as the `CrossEncoderReranker` class in
`metadata_embedding_reranker_benchmark.py`.  Swapping the model requires
changing only the `RERANKER_MODEL` constant at the top of that file.

### Re-ranking process

3. For each of the 20 retrieved candidates, the YAML front matter text is read
   from disk (via the stored `filepath` in Chroma metadata).
4. The cross-encoder scores all 20 `(query, passage)` pairs in a single batch.
5. Candidates are sorted by score descending and assigned new ranks 1–20.
6. Recall@3, @5, @7 are evaluated on the re-ranked order.

### Results

**Results** — `data/infosys_rag_test_dataset_50_queries_v2_metadata_reranker_results.csv`:

| Metric | Result |
|---|---:|
| Successful questions | 50/50 |
| Recall@3 | 37/50 — 74% |
| Recall@5 | 41/50 — 82% |
| Recall@7 | 44/50 — 88% |
| Avg reranker latency | 1.738 s/question |
| Avg total latency | 3.173 s/question |

By source category, Recall@3 was:

| Source | Recall@3 | Recall@5 | Recall@7 |
|---|---:|---:|---:|
| NSE ≤10 pages | 24/24 | 24/24 | 24/24 |
| NSE >10 pages | 7/10 | 8/10 | 10/10 |
| Yahoo Finance | 3/3 | 3/3 | 3/3 |
| Trendlyne | 2/3 | 2/3 | 2/3 |
| IR | 1/10 | 4/10 | 5/10 |

**Key observations:**

- **NSE ≤10 pages (24/24):** Perfect recall at all ranks. The wider top-20 retrieval window combined with re-ranking promoted the one previously missed document (Q34) into the top 3.

- **IR (1/10 at Recall@3, 4/10 at Recall@5, 5/10 at Recall@7):** Recall@3 is unchanged but Recall@5 and @7 improved significantly (2→4 and 4→5 respectively). The re-ranker rescores similar quarterly chunks and surfaces the correct one at higher ranks, but still cannot reliably place it in the top 3 when the YAML vocabulary is nearly identical across quarters.

- **NSE >10 pages:** Recall@3 dropped slightly (8→7) while Recall@5 held (8) and Recall@7 improved to a perfect 10/10. The re-ranker occasionally demoted a correctly-retrieved candidate below rank 3 when scoring very similar long-document chunks.

- **Latency:** At 3.173 s/question average, the re-ranking pipeline is ~6.6× slower than the metadata-only pipeline (0.478 s) but still ~77× faster than the BGE reranking pipeline on the original dataset (245.342 s). Re-ranking accounts for 1.738 s/question (55% of total latency).

---

## Pipeline Comparison

| Pipeline | Recall@3 | Recall@5 | Recall@7 |
|---|---:|---:|---:|
| Metadata-only Embedding | 74% | 78% | 82% |
| Metadata-only Embedding + Re-ranking | 74% | 82% | 88% |

Re-ranking did not change Recall@3 overall (37/50 in both cases) but improved
Recall@5 by 4 points (39→41) and Recall@7 by 6 points (41→44).  The gain is
concentrated in the IR category at higher ranks and in NSE ≤10 pages at rank 3,
where the wider top-20 retrieval window gives the re-ranker room to promote the
correct document.  For the Trendlyne miss (Q4 — FY27 guidance), neither pipeline
recovers the correct document within rank 7, suggesting a retrieval ceiling that
requires embedding or indexing changes rather than re-ranking alone.

---

## RAGAS Evaluation

All RAGAS scripts live in `datapreparation/benchmarking/ragas_v2/`.

### Evaluation Setup

| Property | Value |
|---|---|
| Benchmark dataset | `data/infosys_rag_test_dataset_50_queries_v2.csv` |
| Questions | 50 |
| Reference answers | `datapreparation/benchmarking/ragas_v2/reference_answers_v2_template.csv` |
| Reference generation model | `gpt-4o-mini` (OpenAI Chat Completions API) |
| RAGAS evaluator LLM | `gpt-4o-mini` |
| RAGAS evaluator embeddings | `text-embedding-3-small` |
| RAGAS metrics | faithfulness, answer_relevancy, context_precision, context_recall |

**Pipeline A** (`pipeline_a_answers_v2.csv`): metadata-only top-10 retrieval → top-3 context → `gpt-4o-mini` answer.

**Pipeline B** (`pipeline_b_answers_v2.csv`): metadata-only top-20 retrieval → cross-encoder re-ranking → top-3 context → `gpt-4o-mini` answer.

### Workflow

```text
Step 1 — Generate reference answers (one per question from its source document):
    python datapreparation/benchmarking/ragas_v2/generate_grounded_source_answers_v2.py
    → writes: datapreparation/benchmarking/ragas_v2/grounded_source_answers_v2.csv
    → writes: datapreparation/benchmarking/ragas_v2/reference_answers_v2_template.csv
    (human review: edit reference_answers_v2_template.csv before Step 3)

Step 2 — Generate pipeline answers:
    python datapreparation/benchmarking/ragas_v2/generate_pipeline_answers_v2.py --pipeline a
    python datapreparation/benchmarking/ragas_v2/generate_pipeline_answers_v2.py --pipeline b
    → writes: datapreparation/benchmarking/ragas_v2/pipeline_a_answers_v2.csv
    → writes: datapreparation/benchmarking/ragas_v2/pipeline_b_answers_v2.csv

Step 3 — Run RAGAS evaluation:
    python datapreparation/benchmarking/ragas_v2/run_ragas_evaluation_v2.py --pipeline a
    python datapreparation/benchmarking/ragas_v2/run_ragas_evaluation_v2.py --pipeline b
    → writes: datapreparation/benchmarking/ragas_v2/pipeline_a_ragas_results_v2.csv
    → writes: datapreparation/benchmarking/ragas_v2/pipeline_b_ragas_results_v2.csv
    → writes: datapreparation/benchmarking/ragas_v2/pipeline_a_ragas_summary_v2.md
    → writes: datapreparation/benchmarking/ragas_v2/pipeline_b_ragas_summary_v2.md
```

### Results

**Pipeline A** — `datapreparation/benchmarking/ragas_v2/pipeline_a_ragas_results_v2.csv` (50/50 successful):

| Metric | Pipeline A (no reranking) | Pipeline B (with reranking) |
|---|---:|---:|
| faithfulness | 0.8929 | — |
| answer_relevancy | 0.8439 | — |
| context_precision | 0.9683 | — |
| context_recall | 0.8725 | — |

Pipeline A lowest-scoring questions (by mean metric score):

| ID | Mean score | Question |
|---|---:|---|
| 46 | 0.3638 | What was the total value of large deals Infosys won during fiscal year 2024–25 as reported at the 44th Annual General Meeting? |
| 15 | 0.6474 | What third-party rankings and industry recognitions has Infosys received for its AI and cloud service capabilities as listed in the Q2 FY26 press release? |
| 8 | 0.6667 | What reasons does Infosys management give for expecting H1 FY26 to outperform H2, and what assumptions underpin the upper and lower ends of the guidance range? |
| 34 | 0.6721 | What financial losses and reputational damage from AI-related incidents does the Infosys research report document? |
| 44 | 0.7333 | What factors have driven Infosys's stronger growth in Europe, and how sustainable does management consider that momentum to be? |

**Pipeline B** results to be added after the evaluation run completes.
